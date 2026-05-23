"""Interview preparation agent.

Generates interview questions grounded in the candidate's CV and the target job
offer, across several domains (coding, system design, role-specific technical,
behavioural) and seniority levels, then reviews a candidate's written answer or
code — including an *optimized* rewrite with complexity analysis for coding
questions.

The module reuses the same OpenAI-compatible vLLM endpoint as the matcher and
the section rewriter so the whole app speaks to one model. Every LLM call is a
single request returning strict JSON, and the agent degrades gracefully to a
rule-based fallback when the model is unreachable.
"""

import json
import os
import re
from typing import Dict, List, Optional, Union

import requests


# Shared vLLM endpoint (see matcher.py / section_rewriter.py).
VLLM_API_URL = os.environ.get("VLLM_API_URL", "http://195.154.75.46:8002/v1")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen3-Coder-Next-FP8")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY")
# (connect, read): fail fast if the host is unreachable, but allow a slow model
# a long time to actually respond. A single large value would also be applied to
# the connect phase, which makes an unreachable endpoint hang for the full budget.
VLLM_CONNECT_TIMEOUT = float(os.environ.get("VLLM_CONNECT_TIMEOUT", "10"))
VLLM_TIMEOUT = float(os.environ.get("VLLM_TIMEOUT", "3600"))
VLLM_REQUEST_TIMEOUT = (VLLM_CONNECT_TIMEOUT, VLLM_TIMEOUT)


VALID_DOMAINS = ("coding", "system_design", "technical", "behavioral")
VALID_LEVELS = ("junior", "mid", "senior")

DOMAIN_LABELS = {
    "coding": "Coding",
    "system_design": "System Design",
    "technical": "Technical",
    "behavioral": "Behavioral",
}


# ---------------------------------------------------------------------------
# Low-level LLM helpers
# ---------------------------------------------------------------------------


def _call_vllm(
    user_prompt: str,
    *,
    system_prompt: str,
    max_tokens: int = 2200,
    temperature: float = 0.3,
) -> Optional[str]:
    """POST a chat completion to the configured vLLM endpoint."""
    headers = {"Content-Type": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    try:
        response = requests.post(
            f"{VLLM_API_URL}/chat/completions",
            json={
                "model": VLLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
            headers=headers,
            timeout=VLLM_REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        print(f"[interview-agent] vLLM call failed: {exc}", flush=True)
        return None

    if response.status_code != 200:
        print(
            f"[interview-agent] vLLM HTTP {response.status_code}: "
            f"{response.text[:200]}",
            flush=True,
        )
        return None

    try:
        data = response.json()
    except ValueError:
        return None
    return (
        data.get("choices", [{}])[0].get("message", {}).get("content", "") or None
    )


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def _extract_json(text: str) -> Optional[Union[dict, list]]:
    """Pull the first JSON object/array out of a possibly noisy LLM response."""
    if not text:
        return None
    cleaned = _THINK_RE.sub("", text).strip()

    fence = _FENCE_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()

    # Try the whole string first, then the widest {...} / [...] slice.
    candidates = [cleaned]
    first_obj, last_obj = cleaned.find("{"), cleaned.rfind("}")
    if first_obj != -1 and last_obj > first_obj:
        candidates.append(cleaned[first_obj : last_obj + 1])
    first_arr, last_arr = cleaned.find("["), cleaned.rfind("]")
    if first_arr != -1 and last_arr > first_arr:
        candidates.append(cleaned[first_arr : last_arr + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Context preparation
# ---------------------------------------------------------------------------


_LATEX_COMMENT_RE = re.compile(r"(?<!\\)%.*")
_LATEX_SECTION_RE = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^{}]*)\}")
_LATEX_INLINE_RE = re.compile(r"\\(?:textbf|textit|emph|underline|texttt|href\{[^{}]*\})\{([^{}]*)\}")
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?")


def latex_to_text(cv_latex: str, max_chars: int = 6000) -> str:
    """Best-effort flatten of a LaTeX CV into readable plain text for prompting."""
    if not cv_latex:
        return ""

    text = cv_latex
    # Keep only the document body when a preamble is present.
    body = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.DOTALL)
    if body:
        text = body.group(1)

    text = _LATEX_COMMENT_RE.sub("", text)
    # Drop environment delimiters (\begin{itemize}, \end{tabular}, …) entirely.
    text = re.sub(r"\\(?:begin|end)\{[^{}]*\}(?:\[[^\]]*\])?", "", text)
    text = _LATEX_SECTION_RE.sub(r"\n\n## \1\n", text)
    text = re.sub(r"\\item\b", "\n- ", text)
    # Unwrap simple one-argument formatting commands, keeping their content.
    for _ in range(3):
        text = _LATEX_INLINE_RE.sub(r"\1", text)
    text = text.replace("\\\\", "\n")
    text = re.sub(r"\\&", "&", text)
    text = _LATEX_CMD_RE.sub(" ", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = text.strip()

    if len(text) > max_chars:
        text = text[:max_chars] + "\n…(truncated)"
    return text


def summarize_job(job_description: Union[str, Dict], max_chars: int = 3500) -> str:
    """Normalise a job offer (raw string or parsed dict) into compact text."""
    if isinstance(job_description, str):
        return job_description.strip()[:max_chars]

    if not isinstance(job_description, dict):
        return str(job_description)[:max_chars]

    parts: List[str] = []
    raw = job_description.get("raw_text") or job_description.get("text")
    company = job_description.get("company_info") or {}
    title = company.get("title") or company.get("role")
    if title:
        parts.append(f"Role: {title}")

    skills = job_description.get("skills") or []
    if skills:
        parts.append("Required skills: " + ", ".join(str(s) for s in skills[:30]))

    requirements = job_description.get("requirements") or []
    if requirements:
        parts.append(
            "Requirements:\n"
            + "\n".join(f"- {r}" for r in requirements[:12])
        )

    qualifications = job_description.get("qualifications") or []
    if qualifications:
        parts.append(
            "Qualifications:\n"
            + "\n".join(f"- {q}" for q in qualifications[:8])
        )

    if raw and len("\n".join(parts)) < 400:
        # Parsed fields were thin — fall back to the raw posting.
        parts.append(str(raw))

    return "\n\n".join(parts).strip()[:max_chars]


def _normalize_domains(domains) -> List[str]:
    if not domains:
        return list(VALID_DOMAINS)
    out = [d for d in domains if d in VALID_DOMAINS]
    return out or list(VALID_DOMAINS)


def _normalize_level(level) -> Optional[str]:
    if not level:
        return None
    level = str(level).strip().lower()
    aliases = {
        "jr": "junior",
        "entry": "junior",
        "intermediate": "mid",
        "middle": "mid",
        "sr": "senior",
        "lead": "senior",
        "staff": "senior",
    }
    level = aliases.get(level, level)
    return level if level in VALID_LEVELS else None


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------


_QUESTIONS_SYSTEM = (
    "You are a senior technical interviewer. You design interview questions that "
    "are tightly grounded in the candidate's CV and the target job offer.\n"
    "OUTPUT CONTRACT (critical):\n"
    "- Respond with ONE single valid JSON object and NOTHING else.\n"
    "- No prose before or after, no markdown code fences, no <think> blocks, no comments.\n"
    "- All strings must use double quotes and escape any inner quotes/newlines.\n"
    "- The JSON must parse with a strict JSON parser on the first try."
)


def _build_questions_prompt(
    cv_text: str,
    job_text: str,
    level: Optional[str],
    domains: List[str],
    count: int,
    extra_instructions: Optional[str] = None,
) -> str:
    level_line = (
        f"The interview targets a {level.upper()} seniority level."
        if level
        else "Infer the appropriate seniority level (junior/mid/senior) from the CV and offer."
    )
    domain_line = ", ".join(domains)
    custom_block = ""
    if extra_instructions and extra_instructions.strip():
        custom_block = (
            "\n=== EXTRA INSTRUCTIONS FROM THE USER (follow these closely) ===\n"
            f"{extra_instructions.strip()}\n"
        )
    return f"""{level_line}

Generate exactly {count} interview questions, spread as evenly as possible across these domains: {domain_line}.
Return all {count} — do not return fewer.

Hard requirements:
- Every question MUST be justified by something concrete in the CV AND/OR the job offer.
- Coding questions must be solvable in a code editor and state the suggested language (prefer a language present in the CV or the offer). Include short starter_code when helpful (signature/skeleton only — never the solution).
- System design questions should reflect the scale/stack implied by the offer.
- Behavioral questions must reference real experience visible in the CV (STAR-style).
- Scale difficulty to the seniority level.
{custom_block}
=== CANDIDATE CV ===
{cv_text or "(no CV provided — base questions on the offer only)"}

=== JOB OFFER ===
{job_text or "(no offer provided — base questions on the CV only)"}

Respond with EXACTLY this JSON shape (and only this):
{{
  "detected_level": "junior|mid|senior",
  "role_title": "short role title inferred from the offer",
  "questions": [
    {{
      "domain": "coding|system_design|technical|behavioral",
      "level": "junior|mid|senior",
      "title": "short title (max 8 words)",
      "question": "the full question text",
      "rationale": "one sentence: why this is asked, citing the CV or offer",
      "language": "python|javascript|java|sql|... (coding only, else empty string)",
      "starter_code": "optional skeleton for coding questions, else empty string",
      "evaluation_criteria": ["what a strong answer demonstrates", "..."]
    }}
  ]
}}"""


def _fallback_questions(
    cv_text: str, job_text: str, level: Optional[str], domains: List[str], count: int
) -> Dict:
    """Deterministic, model-free questions so the page still works offline."""
    lvl = level or "mid"
    _stop = {
        "senior", "junior", "mid", "lead", "staff", "engineer", "developer",
        "experience", "years", "the", "and", "with", "for", "you", "our", "team",
        "role", "company", "work", "build", "design", "strong", "must", "have",
        "backend", "frontend", "fullstack", "full-stack", "software", "platform",
    }
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.]{2,}", (job_text or "") + " " + (cv_text or ""))
    skill = next(
        (t.rstrip(".") for t in tokens if t.rstrip(".").lower() not in _stop),
        "the core stack",
    )
    templates = {
        "coding": {
            "title": f"Implement a function using {skill}",
            "question": (
                f"Write a function relevant to {skill}. For example, given a list of "
                "records, group them by a key and return the counts. Optimise for time "
                "and space, and explain your complexity."
            ),
            "language": "python",
            "starter_code": "def solve(records):\n    # your code here\n    pass\n",
            "rationale": f"The offer emphasises {skill}; this checks hands-on coding ability.",
            "evaluation_criteria": ["Correctness", "Time/space complexity", "Readability"],
        },
        "system_design": {
            "title": "Design a scalable service",
            "question": (
                "Design a system that serves the main workload implied by this role. "
                "Discuss the API, data model, scaling strategy, and failure handling."
            ),
            "language": "",
            "starter_code": "",
            "rationale": "The offer implies production systems at scale.",
            "evaluation_criteria": ["Clear components", "Scaling story", "Trade-off reasoning"],
        },
        "technical": {
            "title": f"Deep-dive on {skill}",
            "question": f"Explain how {skill} works under the hood and a pitfall you have hit with it.",
            "language": "",
            "starter_code": "",
            "rationale": f"{skill} appears in the offer's requirements.",
            "evaluation_criteria": ["Depth of understanding", "Real experience"],
        },
        "behavioral": {
            "title": "Tell me about a hard project",
            "question": (
                "Describe a challenging project from your CV using the STAR method: "
                "Situation, Task, Action, Result."
            ),
            "language": "",
            "starter_code": "",
            "rationale": "Validates the experience claimed in the CV.",
            "evaluation_criteria": ["Structured (STAR)", "Concrete impact", "Ownership"],
        },
    }
    questions = []
    i = 0
    while len(questions) < count:
        domain = domains[i % len(domains)]
        base = dict(templates[domain])
        base.update({"domain": domain, "level": lvl})
        questions.append(base)
        i += 1
    return {
        "detected_level": lvl,
        "role_title": "Target role",
        "questions": questions[:count],
        "fallback": True,
    }


def _clean_questions(
    parsed: Union[dict, list, None],
    level: Optional[str],
) -> List[Dict]:
    """Validate and normalise the LLM's question list; drop unusable items."""
    if isinstance(parsed, list):
        parsed = {"questions": parsed}
    if not isinstance(parsed, dict):
        return []

    detected = _normalize_level(parsed.get("detected_level"))
    cleaned: List[Dict] = []
    for q in parsed.get("questions", []):
        if not isinstance(q, dict):
            continue
        text = str(q.get("question") or "").strip()
        if len(text) < 8:  # a real question, not an empty/placeholder string
            continue
        domain = q.get("domain") if q.get("domain") in VALID_DOMAINS else "technical"
        crit = q.get("evaluation_criteria") or []
        if isinstance(crit, str):
            crit = [crit]
        idx = len(cleaned) + 1
        cleaned.append(
            {
                "id": idx,
                "domain": domain,
                "domain_label": DOMAIN_LABELS.get(domain, "Technical"),
                "level": _normalize_level(q.get("level")) or level or detected or "mid",
                "title": str(q.get("title") or f"Question {idx}").strip(),
                "question": text,
                "rationale": str(q.get("rationale") or "").strip(),
                "language": str(q.get("language") or "").strip().lower(),
                "starter_code": str(q.get("starter_code") or ""),
                "evaluation_criteria": [str(c).strip() for c in crit if str(c).strip()],
            }
        )
    return cleaned


# How many times to ask the model before giving up to offline templates, and
# how many valid questions we insist on before accepting an attempt.
QUESTION_ATTEMPTS = max(1, int(os.environ.get("INTERVIEW_QUESTION_ATTEMPTS", "3")))


def generate_questions(
    cv_latex: str,
    job_description: Union[str, Dict],
    level: Optional[str] = None,
    domains: Optional[List[str]] = None,
    count: int = 6,
    extra_instructions: Optional[str] = None,
) -> Dict:
    """Generate interview questions grounded in the CV and the job offer.

    Robust by design: the model is retried a few times (with rising
    temperature and a stern JSON reminder) until it returns enough valid,
    parseable questions. Only after every attempt fails do we fall back to
    deterministic offline templates, which is flagged in the result.
    """
    cv_text = latex_to_text(cv_latex or "")
    job_text = summarize_job(job_description or "")
    level = _normalize_level(level)
    domains = _normalize_domains(domains)
    try:
        count = max(1, min(int(count), 15))
    except (TypeError, ValueError):
        count = 6

    base_prompt = _build_questions_prompt(
        cv_text, job_text, level, domains, count, extra_instructions
    )
    # We accept an attempt once it yields at least this many usable questions.
    min_acceptable = max(1, min(count, (count + 1) // 2))

    best: List[Dict] = []
    best_parsed: Optional[dict] = None
    last_error = "model unreachable or returned no usable JSON"

    for attempt in range(1, QUESTION_ATTEMPTS + 1):
        prompt = base_prompt
        if attempt > 1:
            prompt = (
                base_prompt
                + "\n\nREMINDER: your previous reply could not be parsed or had too "
                f"few questions. Return ONLY one valid JSON object with all {count} "
                "questions, double-quoted strings, no markdown, no extra text."
            )
        # Nudge temperature up a little on retries to escape a bad rut.
        temperature = min(0.3 + 0.2 * (attempt - 1), 0.7)
        raw = _call_vllm(
            prompt,
            system_prompt=_QUESTIONS_SYSTEM,
            max_tokens=2600,
            temperature=temperature,
        )
        if not raw:
            last_error = "model unreachable (connection failed)"
            continue

        parsed = _extract_json(raw)
        if not isinstance(parsed, (dict, list)):
            last_error = "model did not return valid JSON"
            print(f"[interview-agent] attempt {attempt}: unparseable JSON", flush=True)
            continue

        cleaned = _clean_questions(parsed, level)
        print(
            f"[interview-agent] attempt {attempt}/{QUESTION_ATTEMPTS}: "
            f"{len(cleaned)} valid question(s) (need >= {min_acceptable})",
            flush=True,
        )
        if len(cleaned) > len(best):
            best, best_parsed = cleaned, parsed if isinstance(parsed, dict) else {}
        if len(cleaned) >= min_acceptable:
            break
        last_error = f"only {len(cleaned)} usable question(s) returned"

    if best:
        parsed = best_parsed or {}
        return {
            "detected_level": _normalize_level(parsed.get("detected_level")) or level or "mid",
            "role_title": str(parsed.get("role_title") or "Target role").strip(),
            "questions": best[:count],
            "fallback": False,
            "attempts": attempt,
        }

    print(f"[interview-agent] all attempts failed ({last_error}); using offline templates", flush=True)
    result = _fallback_questions(cv_text, job_text, level, domains, count)
    result["error"] = last_error
    return result


# ---------------------------------------------------------------------------
# Answer / code review
# ---------------------------------------------------------------------------


_REVIEW_SYSTEM = (
    "You are a rigorous but encouraging technical interviewer reviewing a "
    "candidate's answer. For coding answers you analyse correctness and "
    "time/space complexity and you provide a cleaner, more OPTIMIZED version. "
    "You respond ONLY with a single valid JSON object — no prose, no markdown "
    "fences, no <think> blocks."
)


def _build_review_prompt(
    question: Dict,
    answer: str,
    language: str,
    job_text: str,
) -> str:
    domain = question.get("domain", "technical")
    is_coding = domain == "coding"
    coding_block = (
        f"""
This is a CODING question (language: {language or question.get('language') or 'unspecified'}).
- Judge correctness against the problem.
- Give time and space complexity of the candidate's solution.
- Provide an OPTIMIZED version in the same language that is correct, idiomatic and faster/cleaner, with its own complexity.
"""
        if is_coding
        else ""
    )
    return f"""Review the candidate's answer to the following interview question.

QUESTION ({question.get('domain_label', domain)} · {question.get('level', 'mid')}):
{question.get('question', '')}

WHAT A STRONG ANSWER SHOWS:
{chr(10).join('- ' + c for c in question.get('evaluation_criteria', [])) or '- (use your judgement)'}

JOB CONTEXT (for relevance):
{job_text[:1500] or '(none)'}
{coding_block}
CANDIDATE ANSWER:
'''
{answer}
'''

Respond with this exact JSON shape (omit coding-only fields for non-coding questions by leaving them empty):
{{
  "score": 0-100,
  "verdict": "one short line, e.g. 'Solid, with minor gaps'",
  "summary": "2-3 sentence assessment",
  "strengths": ["..."],
  "improvements": ["concrete, actionable suggestions"],
  "follow_up_questions": ["a question an interviewer would ask next"],
  "model_answer": "a concise example of a strong answer",
  "is_coding": {str(is_coding).lower()},
  "correctness": "correct|partially_correct|incorrect|n/a",
  "complexity": {{"time": "O(...) or n/a", "space": "O(...) or n/a"}},
  "optimized_code": "optimized solution in the same language, or empty string",
  "optimized_notes": "why the optimized version is better, or empty string"
}}"""


def _fallback_review(question: Dict, answer: str) -> Dict:
    words = len((answer or "").split())
    score = 35 if words < 20 else 55 if words < 80 else 65
    return {
        "score": score,
        "verdict": "Auto-review unavailable — heuristic only",
        "summary": (
            "The AI reviewer could not be reached, so this is a length-based estimate. "
            "Re-run when the model is available for a real assessment."
        ),
        "strengths": ["You submitted an answer to work from."],
        "improvements": [
            "Add concrete detail and structure.",
            "For coding, state your time/space complexity explicitly.",
        ],
        "follow_up_questions": [],
        "model_answer": "",
        "is_coding": question.get("domain") == "coding",
        "correctness": "n/a",
        "complexity": {"time": "n/a", "space": "n/a"},
        "optimized_code": "",
        "optimized_notes": "",
        "fallback": True,
    }


def review_answer(
    question: Dict,
    answer: str,
    language: str = "",
    job_description: Union[str, Dict] = "",
) -> Dict:
    """Review a candidate's answer/code for one question."""
    if not isinstance(question, dict):
        question = {"question": str(question)}
    answer = (answer or "").strip()
    if not answer:
        return {
            "score": 0,
            "verdict": "No answer submitted",
            "summary": "Write an answer or some code, then request a review.",
            "strengths": [],
            "improvements": ["Submit an answer first."],
            "follow_up_questions": [],
            "model_answer": "",
            "is_coding": question.get("domain") == "coding",
            "correctness": "n/a",
            "complexity": {"time": "n/a", "space": "n/a"},
            "optimized_code": "",
            "optimized_notes": "",
        }

    job_text = summarize_job(job_description or "")
    prompt = _build_review_prompt(question, answer, language, job_text)
    raw = _call_vllm(prompt, system_prompt=_REVIEW_SYSTEM, max_tokens=2200, temperature=0.25)
    parsed = _extract_json(raw) if raw else None

    if not isinstance(parsed, dict):
        return _fallback_review(question, answer)

    def _as_list(value):
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    try:
        score = int(round(float(parsed.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(score, 100))

    complexity = parsed.get("complexity")
    if not isinstance(complexity, dict):
        complexity = {"time": "n/a", "space": "n/a"}

    return {
        "score": score,
        "verdict": str(parsed.get("verdict") or "").strip(),
        "summary": str(parsed.get("summary") or "").strip(),
        "strengths": _as_list(parsed.get("strengths")),
        "improvements": _as_list(parsed.get("improvements")),
        "follow_up_questions": _as_list(parsed.get("follow_up_questions")),
        "model_answer": str(parsed.get("model_answer") or "").strip(),
        "is_coding": bool(parsed.get("is_coding")) or question.get("domain") == "coding",
        "correctness": str(parsed.get("correctness") or "n/a").strip(),
        "complexity": {
            "time": str(complexity.get("time", "n/a")),
            "space": str(complexity.get("space", "n/a")),
        },
        "optimized_code": str(parsed.get("optimized_code") or ""),
        "optimized_notes": str(parsed.get("optimized_notes") or "").strip(),
        "fallback": False,
    }
