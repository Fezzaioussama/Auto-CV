"""Compile LaTeX to PDF, and auto-repair compilation errors with the LLM.

Optimizer-generated (or user-edited) LaTeX sometimes fails to compile:
undefined control sequences, packages that aren't installed, unbalanced braces
or environments, unescaped specials (& % $ # _), broken math mode, etc. Rather
than surfacing the raw ``pdflatex`` error to the user, we:

1. compile the document,
2. if no PDF is produced, extract the relevant lines from the ``pdflatex`` log,
3. ask the LLM to return a corrected *full* document (content preserved),
4. recompile — repeating up to a small number of attempts.

Only a genuinely unfixable document (or a missing ``pdflatex``) falls through
to an error. The repaired LaTeX is returned to the caller so the UI can update
the editor to the version that actually compiles.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

try:  # importable both as a bare module (main.py) and as the src package
    from llm_client import complete, Task
except ImportError:  # pragma: no cover
    from .llm_client import complete, Task


# How many LLM repair attempts before giving up (configurable via env).
DEFAULT_REPAIR_ATTEMPTS = max(0, int(os.environ.get("LATEX_REPAIR_ATTEMPTS", "5")))
# Response-token budget for each LLM repair request.
DEFAULT_REPAIR_MAX_TOKENS = max(1, int(os.environ.get("LATEX_REPAIR_MAX_TOKENS", "8000")))
# pdflatex wall-clock budget per compile (seconds). nonstopmode prevents hangs.
COMPILE_TIMEOUT = float(os.environ.get("LATEX_COMPILE_TIMEOUT", "120"))


def _compile_service_url() -> str:
    """URL of the external LaTeX compile service, or '' to use local pdflatex.

    Read at call time (not import) so tests and per-environment config take
    effect without reimporting the module. Set on hosts that can't run a LaTeX
    toolchain themselves (e.g. Vercel serverless) — see ``latex-service/``.
    """
    return os.environ.get("LATEX_COMPILE_URL", "").strip()


# ---------------------------------------------------------------------------
# Package availability + preprocessing (moved here from main.py)
# ---------------------------------------------------------------------------


def latex_package_available(package_name: str) -> bool:
    """Return whether a LaTeX package is installed for the local compiler."""
    if not shutil.which("kpsewhich"):
        return True

    result = subprocess.run(
        ["kpsewhich", f"{package_name}.sty"],
        capture_output=True,
    )
    return result.returncode == 0


def strip_unavailable_latex_package(latex_content: str, package_name: str) -> str:
    """Remove usepackage lines for packages not installed locally."""
    pattern = (
        rf"^[ \t]*\\usepackage(?:\[[^\]]*\])?\{{{re.escape(package_name)}\}}[ \t]*\n?"
    )
    return re.sub(pattern, "", latex_content, flags=re.MULTILINE)


def replace_missing_graphics(latex_content: str) -> str:
    """Replace includegraphics calls whose local image file is unavailable."""
    image_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".eps"}

    def _replace(match):
        image_path = match.group("path").strip()
        _, ext = os.path.splitext(image_path)
        if ext.lower() not in image_extensions:
            return match.group(0)
        if os.path.isabs(image_path):
            exists = os.path.exists(image_path)
        else:
            exists = os.path.exists(os.path.join(os.getcwd(), image_path))
        if exists:
            return match.group(0)
        return r"\fbox{\rule{0pt}{1.6cm}\rule{1.6cm}{0pt}}"

    return re.sub(
        r"\\includegraphics(?:\[[^\]]*\])?\{(?P<path>[^{}]+)\}",
        _replace,
        latex_content,
    )


def ensure_latex_dependencies(latex_content: str) -> str:
    """Add packages required by optimizer-generated LaTeX, drop unavailable ones."""
    required_packages = []

    if not latex_package_available("fontawesome5"):
        latex_content = strip_unavailable_latex_package(latex_content, "fontawesome5")
        latex_content = re.sub(r"\\raisebox\{[^{}]*\}\\faPhone\\?\s*", "Phone: ", latex_content)
        latex_content = re.sub(r"\\raisebox\{[^{}]*\}\\faEnvelope\\?\s*", "Email: ", latex_content)
        latex_content = re.sub(r"\\raisebox\{[^{}]*\}\\faLinkedin\\?\s*", "LinkedIn: ", latex_content)
        latex_content = re.sub(r"\\raisebox\{[^{}]*\}\\faGithub\\?\s*", "GitHub: ", latex_content)
        latex_content = re.sub(r"\\fa(?:Phone|Envelope|Linkedin|Github)\b\\?\s*", "", latex_content)

    if not latex_package_available("CormorantGaramond"):
        latex_content = strip_unavailable_latex_package(latex_content, "CormorantGaramond")

    latex_content = replace_missing_graphics(latex_content)

    has_enumitem = re.search(r"\\usepackage(?:\[[^\]]*\])?\{enumitem\}", latex_content)
    if "[leftmargin=*]" in latex_content and not has_enumitem:
        required_packages.append("\\usepackage{enumitem}")

    if not required_packages:
        return latex_content

    package_block = "\n".join(required_packages)
    document_start = "\\begin{document}"
    if document_start in latex_content:
        return latex_content.replace(document_start, package_block + "\n" + document_start, 1)
    return package_block + "\n" + latex_content


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


@dataclass
class CompileResult:
    success: bool
    pdf_bytes: Optional[bytes]
    log: str
    returncode: int
    timed_out: bool = False


def _sandboxed_env() -> dict:
    """Environment that locks pdflatex down for untrusted input.

    The CV LaTeX we compile is user-controlled (the editor is a raw textarea and
    ``.tex`` uploads pass through verbatim), so a malicious document could try to
    read server files via ``\\input``/``\\openin`` or run commands via
    ``\\write18``. We pin TeX's own file-access policy to "paranoid" so it can
    only touch files in/under the compile directory, and forbid shell escape via
    the config layer too (belt-and-braces with the ``-no-shell-escape`` flag).
    """
    env = dict(os.environ)
    env["openin_any"] = "p"     # paranoid: no reads outside the tree, no dotfiles
    env["openout_any"] = "p"    # paranoid: no writes outside the tree
    env["shell_escape"] = "f"   # disable \write18 at the texmf level as well
    return env


def _remote_compile_latex(latex_content: str, *, timeout: float) -> CompileResult:
    """Compile via the external LaTeX service (``LATEX_COMPILE_URL``).

    The service runs ``pdflatex`` in a TeX Live container and replies with JSON:
    ``{"success": bool, "pdf_base64": str|None, "log": str, "returncode": int,
    "timed_out": bool}``. Returning a :class:`CompileResult` (with the log) lets
    the same LLM repair loop drive a remote compiler exactly like a local one.

    Never raises ``FileNotFoundError``: when a service is configured, a missing
    local ``pdflatex`` is irrelevant. Service/network problems come back as a
    failed ``CompileResult`` so the caller degrades gracefully.
    """
    import requests  # declared dependency; imported lazily to keep import light

    url = _compile_service_url()
    token = os.environ.get("LATEX_COMPILE_TOKEN", "").strip()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.post(
            url,
            json={"latex": latex_content},
            headers=headers,
            # Give the service its own compile budget plus network slack.
            timeout=timeout + 15,
        )
    except requests.RequestException as exc:
        return CompileResult(False, None, f"LaTeX compile service unreachable: {exc}", -1)

    if resp.status_code != 200:
        return CompileResult(
            False, None,
            f"LaTeX compile service returned HTTP {resp.status_code}: {resp.text[:500]}",
            -1,
        )
    try:
        data = resp.json()
    except ValueError:
        return CompileResult(False, None, "LaTeX compile service returned non-JSON", -1)

    log = data.get("log") or ""
    returncode = int(data.get("returncode", -1) or -1)
    if data.get("success") and data.get("pdf_base64"):
        try:
            pdf_bytes = base64.b64decode(data["pdf_base64"])
        except (ValueError, TypeError):
            return CompileResult(False, None, "LaTeX compile service returned invalid PDF data", -1)
        return CompileResult(True, pdf_bytes, log, returncode)
    return CompileResult(False, None, log, returncode, timed_out=bool(data.get("timed_out")))


def compile_latex(latex_content: str, workdir: str, *, timeout: float = COMPILE_TIMEOUT) -> CompileResult:
    """Compile ``latex_content`` to PDF and return the result.

    Uses the external compile service when ``LATEX_COMPILE_URL`` is set (the
    serverless/Vercel path), otherwise runs local ``pdflatex`` in ``workdir``.

    ``success`` means a PDF was produced (pdflatex with ``nonstopmode`` can
    recover from minor issues and still emit a PDF; we accept that, matching the
    app's previous tolerant behaviour). Raises ``FileNotFoundError`` if local
    pdflatex is not installed and no compile service is configured — repair
    cannot help with that.

    The local compile is sandboxed (``-no-shell-escape`` + paranoid file-access
    env + ``cwd`` pinned to the throwaway workdir) because the LaTeX is
    untrusted; the service applies the same sandboxing on its side.
    """
    if _compile_service_url():
        return _remote_compile_latex(latex_content, timeout=timeout)

    os.makedirs(workdir, exist_ok=True)
    tex_file = os.path.join(workdir, "cv.tex")
    pdf_file = os.path.join(workdir, "cv.pdf")
    log_file = os.path.join(workdir, "cv.log")

    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex_content)

    try:
        proc = subprocess.run(
            [
                "pdflatex",
                "-no-shell-escape",        # never run external commands (\write18)
                "-interaction=nonstopmode",
                "-output-directory", workdir,
                # Pass the file by basename, not absolute path: the paranoid
                # ``openin_any=p`` env (set below) makes TeX reject absolute
                # paths even for the main input file, so an absolute path here
                # fails with "I can't find file". cwd is pinned to workdir, so
                # the basename resolves while \input of outside files stays
                # blocked.
                os.path.basename(tex_file),
            ],
            capture_output=True,
            timeout=timeout,
            cwd=workdir,                   # don't let relative paths reach the app tree
            env=_sandboxed_env(),
        )
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, "pdflatex timed out", -1, timed_out=True)

    stdout_text = proc.stdout.decode(errors="replace")
    log_text = stdout_text
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as lf:
                log_text = lf.read()
        except OSError:
            pass

    if os.path.exists(pdf_file):
        with open(pdf_file, "rb") as f:
            pdf_bytes = f.read()
        return CompileResult(True, pdf_bytes, log_text, proc.returncode)

    return CompileResult(False, None, log_text, proc.returncode)


# ---------------------------------------------------------------------------
# Error extraction + LLM repair
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:latex|tex)?\s*\n?(.*?)```", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

_ERROR_MARKERS = (
    "!",  # pdflatex error lines start with "!"
    "l.",  # "l.<n>" line-number context
)
_ERROR_SUBSTRINGS = (
    "! LaTeX Error",
    "Undefined control sequence",
    "Runaway argument",
    "Missing ",
    "Extra ",
    "Emergency stop",
    "not found",
)


def extract_errors(log: str, max_chars: int = 4000) -> str:
    """Pull the relevant error lines out of a noisy pdflatex log."""
    if not log:
        return ""
    lines = log.splitlines()
    picked: list = []
    seen = set()
    for i, line in enumerate(lines):
        hit = (
            any(line.lstrip().startswith(m) for m in _ERROR_MARKERS)
            or any(s in line for s in _ERROR_SUBSTRINGS)
        )
        if not hit:
            continue
        for j in range(max(0, i - 1), min(len(lines), i + 3)):
            if j not in seen:
                seen.add(j)
                picked.append(lines[j])
    text = "\n".join(picked) if picked else "\n".join(lines[-40:])
    return text[:max_chars]


def _clean_latex(response: str) -> str:
    text = _THINK_RE.sub("", response).strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1)
    return text.strip()


REPAIR_SYSTEM_PROMPT = (
    "You are a LaTeX expert. You receive a full LaTeX document that FAILED to "
    "compile with pdflatex, plus the relevant error log. Return a corrected "
    "document that compiles cleanly.\n\n"
    "Rules:\n"
    "- Output the COMPLETE corrected document, from \\documentclass to "
    "\\end{document}.\n"
    "- Fix ONLY what blocks compilation: undefined control sequences, missing "
    "or unavailable packages, unbalanced braces/environments, unescaped special "
    "characters (& % $ # _ ^ ~ and backslash in text), broken math mode, a "
    "missing \\item, and similar syntax errors.\n"
    "- DO NOT change the content, wording, names, dates, numbers or meaning of "
    "the CV. Preserve every piece of information.\n"
    "- If a command or package is undefined and merely decorative (e.g. an "
    "icon), replace it with a plain-text or standard-LaTeX equivalent rather "
    "than deleting the surrounding information.\n"
    "- Prefer packages and commands available in a standard TeX Live install.\n"
    "- Output ONLY the LaTeX document. No explanations, no markdown code "
    "fences, no <think> tags."
)


def repair_latex(
    latex_content: str,
    error_log: str,
    *,
    max_tokens: int = DEFAULT_REPAIR_MAX_TOKENS,
) -> Optional[str]:
    """Ask the LLM to fix a non-compiling document. Returns None on failure."""
    user_prompt = (
        "pdflatex failed to produce a PDF. Relevant error log:\n"
        f"{error_log or '(no specific errors captured)'}\n\n"
        "--- Full LaTeX document to fix ---\n"
        f"{latex_content}\n"
        "--- end of document ---\n\n"
        "Return the complete corrected LaTeX document only."
    )
    raw = complete(
        user_prompt,
        system_prompt=REPAIR_SYSTEM_PROMPT,
        task=Task.LATEX_REPAIR,
        temperature=0.1,
        max_tokens=max_tokens,
        log_prefix="latex-repair",
    )
    if not raw:
        return None
    cleaned = _clean_latex(raw)
    # A valid repair must still be a complete document.
    if "\\documentclass" not in cleaned or "\\end{document}" not in cleaned:
        print("[latex-repair] discarded repair: not a complete document", flush=True)
        return None
    return cleaned


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class RenderResult:
    success: bool
    pdf_bytes: Optional[bytes]
    final_latex: str
    repaired: bool
    attempts: int
    error_details: str


def render_pdf(
    latex_content: str,
    *,
    max_repair_attempts: int = DEFAULT_REPAIR_ATTEMPTS,
    repair_max_tokens: int = DEFAULT_REPAIR_MAX_TOKENS,
    compile_timeout: float = COMPILE_TIMEOUT,
) -> RenderResult:
    """Compile to PDF, auto-repairing compilation errors with the LLM.

    Returns a :class:`RenderResult`. ``final_latex`` is the (possibly repaired)
    source that produced the PDF, so callers can update their editor. Raises
    ``FileNotFoundError`` only if pdflatex itself is missing.
    """
    current = ensure_latex_dependencies(latex_content)
    repaired = False
    last_log = ""

    with tempfile.TemporaryDirectory() as tmp:
        for attempt in range(max_repair_attempts + 1):
            # Fresh sub-dir per attempt so stale aux/pdf can't leak between runs.
            workdir = os.path.join(tmp, f"attempt{attempt}")
            result = compile_latex(current, workdir, timeout=compile_timeout)

            if result.success and result.pdf_bytes:
                if repaired:
                    print(f"[latex-repair] compiled OK after {attempt} repair(s).", flush=True)
                return RenderResult(True, result.pdf_bytes, current, repaired, attempt, "")

            last_log = result.log

            # A timeout is not a syntax error — repairing won't help.
            if result.timed_out or attempt >= max_repair_attempts:
                break

            errors = extract_errors(result.log)
            print(
                f"[latex-repair] compile failed (attempt {attempt + 1}/"
                f"{max_repair_attempts + 1}); asking the LLM to fix it…",
                flush=True,
            )
            fixed = repair_latex(current, errors, max_tokens=repair_max_tokens)
            if not fixed or fixed.strip() == current.strip():
                print("[latex-repair] no usable fix produced; stopping.", flush=True)
                break
            current = ensure_latex_dependencies(fixed)
            repaired = True

    return RenderResult(False, None, current, repaired, max_repair_attempts, extract_errors(last_log))
