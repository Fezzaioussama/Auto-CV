"""Centralized LLM client for Auto-CV.

Every LLM call in the app (CV analysis, section rewriting, addition proposals,
the interview agent, the smart CV generator) goes through this one module so
that the *provider* and the *model per task* are configured in a single place
via environment variables (loaded from a local ``.env`` file).

Two providers are supported, selected with ``SOURCE_LLM``:

* ``local``      – a self-hosted, OpenAI-compatible server (e.g. vLLM / Ollama).
                   You pass its URL and model name.
* ``openrouter`` – the OpenRouter serverless API (https://openrouter.ai).
                   You pass an API key and a model name per call type.

Both providers speak the same OpenAI ``/chat/completions`` contract, so the
transport is identical; only the base URL, auth header and model name differ.

Design goals
------------
* **One switch.** ``SOURCE_LLM=local`` or ``SOURCE_LLM=openrouter``.
* **Per-task models.** Each kind of call (see :class:`Task`) can use a
  different model, so you can route cheap calls to a small model and hard ones
  to a strong model. Falls back to a global default when not set.
* **Graceful degradation.** Network/HTTP/parse failures return ``None`` so the
  callers' existing rule-based fallbacks keep the app working offline.
* **No secret leakage.** :func:`describe_config` never prints the API key.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import requests

try:  # python-dotenv is a declared dependency; degrade gracefully if absent.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - defensive only
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

# Load the project-root .env once, on import, before any config is read. This
# file lives at <repo>/src/autocv/llm_client.py, so the project root is three
# directories up (autocv -> src -> repo root).
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    """Return the first set, non-empty environment variable among ``names``."""
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip() != "":
            return value.strip()
    return default


# ---------------------------------------------------------------------------
# Task identifiers
# ---------------------------------------------------------------------------


class Task:
    """Logical LLM call types. Each maps to a per-task model env var.

    For ``SOURCE_LLM=openrouter`` the model is read from
    ``OPENROUTER_MODEL_<TASK>`` (falling back to ``OPENROUTER_MODEL``); for
    ``SOURCE_LLM=local`` from ``LOCAL_MODEL_<TASK>`` (falling back to
    ``LOCAL_LLM_MODEL`` / legacy ``VLLM_MODEL``).
    """

    ANALYSIS = "ANALYSIS"              # matcher: CV vs job analysis
    SECTION_REWRITE = "SECTION_REWRITE"  # section_rewriter: rewrite one section
    PROPOSAL = "PROPOSAL"              # section_rewriter: propose new sections
    INTERVIEW = "INTERVIEW"            # interview_agent: questions + review
    SMART_CV = "SMART_CV"             # smart_cv_generator: full CV generation
    LATEX_REPAIR = "LATEX_REPAIR"      # latex_repair: fix compilation errors
    OCR = "OCR"                       # ocr: read text off images / scanned PDFs
    DEFAULT = "DEFAULT"               # anything not otherwise classified


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

# Legacy defaults preserved so the app behaves exactly as before when no .env
# is present (the original hard-coded vLLM endpoint and model).
_LEGACY_LOCAL_URL = "http://127.0.0.1:8002/v1"
_LEGACY_LOCAL_MODEL = "Qwen/Qwen3-Coder-Next-FP8"
_DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1"
_DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-120b"


def active_source() -> str:
    """Return the active provider: ``'local'`` or ``'openrouter'``."""
    explicit_source = _env("SOURCE_LLM", "LLM_SOURCE")
    if not explicit_source and _env("OPENROUTER_API_KEY"):
        return "openrouter"
    source = (explicit_source or "local").lower()
    return "openrouter" if source in ("openrouter", "serverless", "remote") else "local"


def _connect_timeout() -> float:
    return float(_env("LLM_CONNECT_TIMEOUT", "VLLM_CONNECT_TIMEOUT", default="10"))


def _read_timeout() -> float:
    return float(_env("LLM_TIMEOUT", "VLLM_TIMEOUT", default="3600"))


def request_timeout() -> tuple:
    """``(connect, read)`` timeout: fail fast if unreachable, allow a slow read."""
    return (_connect_timeout(), _read_timeout())


def get_max_workers() -> int:
    """Max concurrent LLM requests (used by the parallel section rewriter)."""
    return max(1, int(_env("LLM_MAX_WORKERS", "VLLM_MAX_WORKERS", default="5")))


def _base_url() -> str:
    if active_source() == "openrouter":
        url = _env("OPENROUTER_BASE_URL", default=_DEFAULT_OPENROUTER_URL)
    else:
        url = _env("LOCAL_LLM_URL", "VLLM_API_URL", "LLM_BASE_URL",
                   default=_LEGACY_LOCAL_URL)
    return (url or "").rstrip("/")


def _api_key() -> Optional[str]:
    if active_source() == "openrouter":
        return _env("OPENROUTER_API_KEY")
    return _env("LOCAL_LLM_API_KEY", "VLLM_API_KEY")


def resolve_model(task: str = Task.DEFAULT) -> str:
    """Resolve the model name for ``task`` under the active provider.

    Per-task override → provider default → legacy/hard default.
    """
    task = (task or Task.DEFAULT).upper()
    if active_source() == "openrouter":
        return _env(
            f"OPENROUTER_MODEL_{task}",
            "OPENROUTER_MODEL",
            default=_DEFAULT_OPENROUTER_MODEL,
        )
    return _env(
        f"LOCAL_MODEL_{task}",
        "LOCAL_LLM_MODEL",
        "VLLM_MODEL",
        default=_LEGACY_LOCAL_MODEL,
    )


def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = api_key if api_key is not None else _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if active_source() == "openrouter":
        # Optional OpenRouter attribution headers (used for app ranking).
        referer = _env("OPENROUTER_APP_URL")
        title = _env("OPENROUTER_APP_NAME", default="Auto-CV")
        if referer:
            headers["HTTP-Referer"] = referer
        if title:
            headers["X-Title"] = title
    return headers


# ---------------------------------------------------------------------------
# Core call
# ---------------------------------------------------------------------------


def chat(
    messages: List[Dict[str, str]],
    *,
    task: str = Task.DEFAULT,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 1500,
    log_prefix: str = "llm",
) -> Optional[str]:
    """POST a chat completion and return the assistant message content.

    ``base_url``/``api_key``/``model`` override the env-resolved values when
    given (used for explicit, per-call targeting). Returns ``None`` on any
    failure (unreachable host, non-200, bad JSON, misconfiguration) so callers
    can fall back to rule-based behaviour.
    """
    source = active_source()
    chosen_model = model or resolve_model(task)
    effective_base = (base_url or _base_url()).rstrip("/")
    effective_key = api_key if api_key is not None else _api_key()

    if source == "openrouter" and base_url is None and not effective_key:
        print(
            f"[{log_prefix}] SOURCE_LLM=openrouter but OPENROUTER_API_KEY is "
            f"not set — skipping LLM call. Set it in your .env.",
            flush=True,
        )
        return None

    url = f"{effective_base}/chat/completions"
    payload = {
        "model": chosen_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=_headers(effective_key),
            timeout=request_timeout(),
        )
    except requests.exceptions.RequestException as exc:
        print(f"[{log_prefix}] {source} call failed ({chosen_model}): {exc}", flush=True)
        return None

    if response.status_code != 200:
        print(
            f"[{log_prefix}] {source} HTTP {response.status_code} "
            f"({chosen_model}): {response.text[:200]}",
            flush=True,
        )
        return None

    try:
        data = response.json()
    except ValueError:
        print(f"[{log_prefix}] {source} returned non-JSON body", flush=True)
        return None

    # Some providers return HTTP 200 with no usable choice — a rate-limit,
    # moderation, length, or an inline {"error": ...} object. Treat that as a
    # failure (return None) so callers fall back, instead of letting an
    # IndexError escape on an empty ``choices`` list.
    choices = data.get("choices") or []
    if not choices:
        err = data.get("error")
        detail = f": {str(err)[:200]}" if err else ""
        print(f"[{log_prefix}] {source} returned no usable choice "
              f"({chosen_model}){detail}", flush=True)
        return None
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    return (message.get("content") or None)


def complete(
    user_prompt: str,
    *,
    system_prompt: str,
    task: str = Task.DEFAULT,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 1500,
    log_prefix: str = "llm",
) -> Optional[str]:
    """Convenience wrapper for the common (system, user) two-message call."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return chat(
        messages,
        task=task,
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        log_prefix=log_prefix,
    )


def vision(
    prompt: str,
    image_data_urls: List[str],
    *,
    system_prompt: str,
    task: str = Task.OCR,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 3000,
    log_prefix: str = "vision",
) -> Optional[str]:
    """Multimodal completion: one text instruction plus one or more images.

    ``image_data_urls`` are ``data:<mime>;base64,...`` strings. They are sent
    using the OpenAI-compatible ``image_url`` content blocks, which both
    OpenRouter and most local servers accept. The configured model for
    :attr:`Task.OCR` must support image input; if it does not (e.g. a text-only
    model), the provider returns an error and this returns ``None`` so the
    caller can fall back. Returns ``None`` on any failure, like :func:`chat`.
    """
    if not image_data_urls:
        return None
    content: List[Dict] = [{"type": "text", "text": prompt}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]
    return chat(
        messages,  # type: ignore[arg-type]  # content is a list for vision
        task=task,
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        log_prefix=log_prefix,
    )


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def describe_config() -> str:
    """One-line, secret-free description of the active LLM configuration."""
    source = active_source()
    key_state = "set" if _api_key() else "none"
    return (
        f"LLM provider: {source} | base_url={_base_url()} | "
        f"api_key={key_state} | default_model={resolve_model(Task.DEFAULT)}"
    )
