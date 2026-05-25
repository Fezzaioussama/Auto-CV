"""Robust structured output from LLMs: parse → validate → self-repair.

Models frequently return *almost* valid JSON: wrapped in prose, fenced in
```json blocks, missing a brace, with an unescaped quote, or truncated. Simply
retrying the same prompt (what the interview agent used to do) wastes calls and
often fails the same way.

This module instead **asks the model to fix its own output**. It:

1. calls the LLM,
2. extracts and parses the JSON,
3. validates it against an optional caller predicate (shape/schema check),
4. on any failure, sends the broken text back with the parser/validation error
   and a strict "return only corrected JSON" instruction — repeating a few
   times before giving up.

It is intentionally generic so every feature that needs JSON (interview agent,
matcher analysis, proposals, parser skill extraction, cover letters) can route
through one hardened path.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Optional, Tuple

try:  # importable both as a bare module (main.py) and as the src package
    from llm_client import complete, Task
except ImportError:  # pragma: no cover
    from .llm_client import complete, Task


# A validator takes the parsed object and returns (ok, error_message).
Validator = Callable[[Any], Tuple[bool, str]]

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def extract_json(text: Optional[str]) -> Optional[Any]:
    """Pull the first valid JSON object/array out of a noisy LLM response."""
    if not text:
        return None
    cleaned = _THINK_RE.sub("", text).strip()
    fence = _FENCE_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()

    # Try the whole string first, then the widest {...} and [...] slices.
    candidates = [cleaned]
    fo, lo = cleaned.find("{"), cleaned.rfind("}")
    if fo != -1 and lo > fo:
        candidates.append(cleaned[fo:lo + 1])
    fa, la = cleaned.find("["), cleaned.rfind("]")
    if fa != -1 and la > fa:
        candidates.append(cleaned[fa:la + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            continue
    return None


def _check(obj: Any, expect: str, validate: Optional[Validator]) -> Tuple[bool, str]:
    if obj is None:
        return False, "no JSON could be parsed from the response"
    if expect == "object" and not isinstance(obj, dict):
        return False, "expected a JSON object but got a different type"
    if expect == "array" and not isinstance(obj, list):
        return False, "expected a JSON array but got a different type"
    if validate is not None:
        try:
            ok, err = validate(obj)
            return bool(ok), (err or "")
        except Exception as exc:  # noqa: BLE001 - a bad validator must not crash
            return False, f"validation raised: {exc}"
    return True, ""


_REPAIR_SYSTEM = (
    "You are a strict JSON repair tool. You receive text that was meant to be "
    "valid JSON but is malformed, incomplete, fenced, or wrapped in prose. "
    "Return ONLY the corrected JSON value — no explanation, no markdown fences, "
    "no <think> blocks. Preserve all of the original content and meaning; only "
    "fix structure: quotes, commas, escaping, brackets, and truncation. If the "
    "JSON was cut off, complete it minimally so it parses."
)


def _repair_user(broken: str, expect: str, schema_hint: str, error: str) -> str:
    parts = [f"The output must be a valid JSON {expect}."]
    if schema_hint:
        parts.append(f"It must follow this shape:\n{schema_hint}")
    if error:
        parts.append(f"The problem with the previous output was: {error}")
    parts.append("Fix the following so it parses as valid JSON:\n\n" + broken[:8000])
    return "\n\n".join(parts)


def request_json(
    user_prompt: str,
    *,
    system_prompt: str,
    expect: str = "object",
    validate: Optional[Validator] = None,
    schema_hint: str = "",
    task: str = Task.DEFAULT,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    repair_attempts: int = 2,
    log_prefix: str = "llm-json",
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Request JSON, validate it, and repair via the model on failure.

    Returns ``(obj, meta)`` where ``obj`` is the parsed/validated value (or
    ``None`` if it could not be obtained) and ``meta`` is
    ``{ok, repaired, attempts, error}``.
    """
    raw = complete(
        user_prompt,
        system_prompt=system_prompt,
        task=task,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        log_prefix=log_prefix,
    )
    if not raw:
        return None, {"ok": False, "repaired": False, "attempts": 0,
                      "error": "model unreachable"}

    obj = extract_json(raw)
    ok, err = _check(obj, expect, validate)
    if ok:
        return obj, {"ok": True, "repaired": False, "attempts": 1, "error": ""}

    # Hand the broken text back to the model to fix, up to repair_attempts times.
    current = raw
    for i in range(repair_attempts):
        print(f"[{log_prefix}] invalid JSON ({err}); requesting repair "
              f"{i + 1}/{repair_attempts}…", flush=True)
        fixed = complete(
            _repair_user(current, expect, schema_hint, err),
            system_prompt=_REPAIR_SYSTEM,
            task=task,
            model=model,
            temperature=0.0,  # deterministic for a mechanical fix
            max_tokens=max_tokens,
            log_prefix=log_prefix + ":repair",
        )
        if not fixed:
            break
        obj = extract_json(fixed)
        ok, err = _check(obj, expect, validate)
        if ok:
            return obj, {"ok": True, "repaired": True, "attempts": i + 2, "error": ""}
        current = fixed

    return None, {"ok": False, "repaired": False,
                  "attempts": repair_attempts + 1, "error": err}
