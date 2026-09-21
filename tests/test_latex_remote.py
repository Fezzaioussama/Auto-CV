"""The external LaTeX compile service path (LATEX_COMPILE_URL).

On hosts without a local pdflatex (Vercel), ``latex_repair`` POSTs the document
to a compile microservice. These tests drive that path with a mocked HTTP layer
so no network or TeX install is needed.
"""

import base64

from autocv import latex_repair


_TINY_DOC = r"\documentclass{article}\begin{document}Hi\end{document}"


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_remote_compile_success(monkeypatch):
    """A successful service response yields a PDF and uses no local pdflatex."""
    monkeypatch.setenv("LATEX_COMPILE_URL", "https://svc.example/compile")
    monkeypatch.setenv("LATEX_COMPILE_TOKEN", "tok")
    monkeypatch.setenv("LATEX_REPAIR_ATTEMPTS", "0")

    pdf = b"%PDF-1.5 fake"
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["latex"] = json["latex"]
        return _FakeResponse(payload={
            "success": True,
            "pdf_base64": base64.b64encode(pdf).decode(),
            "log": "ok",
            "returncode": 0,
        })

    monkeypatch.setattr("requests.post", fake_post)

    result = latex_repair.render_pdf(_TINY_DOC, max_repair_attempts=0)
    assert result.success is True
    assert result.pdf_bytes == pdf
    assert captured["url"] == "https://svc.example/compile"
    assert captured["headers"]["Authorization"] == "Bearer tok"


def test_remote_compile_unreachable_is_graceful(monkeypatch):
    """Network failure comes back as a failed result, never an unhandled raise."""
    monkeypatch.setenv("LATEX_COMPILE_URL", "https://svc.example/compile")

    import requests

    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr("requests.post", boom)

    result = latex_repair.render_pdf(_TINY_DOC, max_repair_attempts=0)
    assert result.success is False
    assert "unreachable" in result.error_details.lower()


def test_local_path_used_when_service_unset(monkeypatch):
    """With no LATEX_COMPILE_URL, compile_latex falls back to local pdflatex."""
    monkeypatch.delenv("LATEX_COMPILE_URL", raising=False)

    called = {"remote": False}

    def should_not_run(*a, **k):
        called["remote"] = True
        raise AssertionError("remote compile must not be used when URL is unset")

    monkeypatch.setattr(latex_repair, "_remote_compile_latex", should_not_run)

    # Local pdflatex may or may not exist here; we only assert the remote path
    # isn't taken. A missing local binary raises FileNotFoundError, which is the
    # documented contract — accept either that or a CompileResult.
    try:
        latex_repair.compile_latex(_TINY_DOC, "/tmp/autocv-test-localpath")
    except FileNotFoundError:
        pass
    assert called["remote"] is False
