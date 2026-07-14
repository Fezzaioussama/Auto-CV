from autocv import latex_repair


_TINY_DOC = r"\documentclass{article}\begin{document}Hi\end{document}"


def test_repair_latex_uses_8000_token_default(monkeypatch):
    captured = {}

    def fake_complete(*_args, **kwargs):
        captured["max_tokens"] = kwargs["max_tokens"]
        return _TINY_DOC

    monkeypatch.setattr(latex_repair, "complete", fake_complete)

    assert latex_repair.repair_latex(_TINY_DOC, "! error") == _TINY_DOC
    assert captured["max_tokens"] == 8000


def test_render_pdf_defaults_to_five_repair_iterations_and_8000_tokens(monkeypatch):
    compile_calls = []
    repair_tokens = []

    def fake_compile(latex_content, workdir, *, timeout):
        compile_calls.append((latex_content, workdir, timeout))
        return latex_repair.CompileResult(False, None, "! error\nl.1 broken", 1)

    def fake_repair(latex_content, _errors, *, max_tokens):
        repair_tokens.append(max_tokens)
        return f"{latex_content}\n% repair {len(repair_tokens)}"

    monkeypatch.setattr(latex_repair, "compile_latex", fake_compile)
    monkeypatch.setattr(latex_repair, "repair_latex", fake_repair)
    monkeypatch.setattr(latex_repair, "ensure_latex_dependencies", lambda content: content)

    result = latex_repair.render_pdf(_TINY_DOC)

    assert result.success is False
    assert result.attempts == 5
    assert len(compile_calls) == 6
    assert repair_tokens == [8000, 8000, 8000, 8000, 8000]
