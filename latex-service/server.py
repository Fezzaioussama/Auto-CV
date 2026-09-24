"""Stateless LaTeX → PDF compile microservice for Auto-CV.

The main Auto-CV app runs on Vercel, whose serverless Python runtime has no TeX
distribution and can't install one. This tiny service runs ``pdflatex`` inside a
TeX Live container and returns the PDF so the app can stream it to the user. The
app POSTs to ``/compile``; see ``src/autocv/latex_repair.py`` (the
``LATEX_COMPILE_URL`` path).

Security — the LaTeX is user-controlled, so:
* the compile is sandboxed: ``-no-shell-escape`` plus a "paranoid" file-access
  env (no reads/writes outside the throwaway compile dir) and ``cwd`` pinned to
  that dir, so a malicious document can't read server files or run commands;
* ``/compile`` requires a shared bearer token (``COMPILE_TOKEN``, 32+ chars);
* the container runs as a non-root user (see the Dockerfile);
* request size and compile time are capped.
"""

from __future__ import annotations

import base64
import os
import secrets
import shutil
import subprocess
import tempfile

from flask import Flask, jsonify, request

app = Flask(__name__)

# Shared secret the Auto-CV app sends as ``Authorization: Bearer <token>``.
# Missing or weak (guessable) tokens disable compilation.
MIN_TOKEN_LENGTH = 32
COMPILE_TOKEN = os.environ.get("COMPILE_TOKEN", "").strip()
if COMPILE_TOKEN and len(COMPILE_TOKEN) < MIN_TOKEN_LENGTH:
    print(
        f"[latex-service] COMPILE_TOKEN is shorter than {MIN_TOKEN_LENGTH} characters; "
        "compilation is disabled. Generate one with: "
        'python -c "import secrets;print(secrets.token_hex(32))"',
        flush=True,
    )
    COMPILE_TOKEN = ""
# Per-document compile budget (seconds); nonstopmode + this prevents hangs.
COMPILE_TIMEOUT = float(os.environ.get("COMPILE_TIMEOUT", "60"))
# Reject oversized payloads early (defends against memory/CPU abuse).
MAX_LATEX_BYTES = int(os.environ.get("MAX_LATEX_BYTES", str(2 * 1024 * 1024)))  # 2 MB
# Keep the returned log bounded — only the tail matters for error extraction.
MAX_LOG_CHARS = 8000
# Bound the JSON body before parsing, including escaped Unicode content.
app.config["MAX_CONTENT_LENGTH"] = MAX_LATEX_BYTES * 6 + 1024


def _sandboxed_env() -> dict:
    """Lock TeX's file access down to the compile directory (untrusted input)."""
    env = dict(os.environ)
    env["openin_any"] = "p"   # paranoid: no reads outside the tree, no dotfiles
    env["openout_any"] = "p"  # paranoid: no writes outside the tree
    env["shell_escape"] = "f"  # disable \write18 at the texmf level too
    return env


def _authorized() -> bool:
    if not COMPILE_TOKEN:
        return False
    sent = request.headers.get("Authorization", "")
    return secrets.compare_digest(sent.encode("utf-8"), f"Bearer {COMPILE_TOKEN}".encode("utf-8"))


@app.get("/health")
def health():
    """Liveness + whether a usable pdflatex is on PATH."""
    has_pdflatex = shutil.which("pdflatex") is not None
    return jsonify({"ok": has_pdflatex, "pdflatex": has_pdflatex})


@app.post("/compile")
def compile_endpoint():
    if not _authorized():
        return jsonify({"success": False, "log": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "log": "expected a JSON object"}), 400
    latex = data.get("latex") or ""
    if not isinstance(latex, str) or not latex:
        return jsonify({"success": False, "log": "no latex provided"}), 400
    if len(latex.encode("utf-8")) > MAX_LATEX_BYTES:
        return jsonify({"success": False, "log": "document too large"}), 413

    with tempfile.TemporaryDirectory() as workdir:
        tex_path = os.path.join(workdir, "cv.tex")
        pdf_path = os.path.join(workdir, "cv.pdf")
        log_path = os.path.join(workdir, "cv.log")
        with open(tex_path, "w", encoding="utf-8") as fh:
            fh.write(latex)

        timed_out = False
        returncode = -1
        log_text = ""
        try:
            proc = subprocess.run(
                [
                    "pdflatex",
                    "-no-shell-escape",
                    "-interaction=nonstopmode",
                    "-output-directory", workdir,
                    "cv.tex",  # basename; cwd is pinned to workdir
                ],
                capture_output=True,
                timeout=COMPILE_TIMEOUT,
                cwd=workdir,
                env=_sandboxed_env(),
            )
            returncode = proc.returncode
            log_text = proc.stdout.decode(errors="replace")
        except subprocess.TimeoutExpired:
            timed_out = True
            log_text = "pdflatex timed out"
        except FileNotFoundError:
            return jsonify({"success": False,
                            "log": "pdflatex is not installed in this service"}), 500

        # Prefer the real .log file when present — it's more complete than stdout.
        if os.path.exists(log_path):
            try:
                with open(log_path, encoding="utf-8", errors="replace") as lf:
                    log_text = lf.read()
            except OSError:
                pass
        log_text = log_text[-MAX_LOG_CHARS:]

        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as fh:
                pdf_b64 = base64.b64encode(fh.read()).decode("ascii")
            return jsonify({"success": True, "pdf_base64": pdf_b64,
                            "log": log_text, "returncode": returncode})

        return jsonify({"success": False, "pdf_base64": None, "log": log_text,
                        "returncode": returncode, "timed_out": timed_out})


if __name__ == "__main__":
    # Dev server only; production runs under gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
