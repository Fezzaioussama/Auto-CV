"""Regression coverage for public-release security boundaries."""
import importlib.util
from pathlib import Path

import pytest

from autocv import auth, email_utils
from conftest import register, login


@pytest.mark.parametrize("target", ["//evil.example/path", "/\\evil.example/path", "/\tevil.example", "https://evil.example/"])
def test_login_rejects_external_return_targets(client, target):
    register(client)
    client.post("/logout")
    client.get("/login", query_string={"next": target})
    response = login(client)
    assert response.get_json()["redirect"] == "/optimizer"


def test_login_keeps_local_return_target(client):
    register(client)
    client.post("/logout")
    client.get("/login", query_string={"next": "/workspace"})
    assert login(client).get_json()["redirect"] == "/workspace"


def test_production_does_not_log_reset_links(app, monkeypatch, caplog):
    monkeypatch.setitem(app.config, "IS_PRODUCTION", True)
    monkeypatch.setenv("SMTP_HOST", "")
    with app.app_context():
        assert email_utils.send_email("private@example.com", "Reset", "private-reset-token") is False
    assert "private-reset-token" not in caplog.text
    assert "private@example.com" not in caplog.text


def test_production_email_links_ignore_incoming_host(app, monkeypatch):
    monkeypatch.setitem(app.config, "IS_PRODUCTION", True)
    monkeypatch.setitem(app.config, "PUBLIC_BASE_URL", "https://app.example.com")
    with app.test_request_context("/", base_url="https://attacker.example"):
        assert auth._external_url("auth.reset_password", token="test") == "https://app.example.com/reset-password/test"
    monkeypatch.setitem(app.config, "PUBLIC_BASE_URL", "")
    with app.test_request_context("/", base_url="https://attacker.example"):
        with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
            auth._external_url("auth.reset_password", token="test")


@pytest.fixture()
def compile_service():
    path = Path(__file__).resolve().parents[1] / "latex-service" / "server.py"
    spec = importlib.util.spec_from_file_location("compile_service", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compile_service_requires_configured_bearer_token(compile_service, monkeypatch):
    client = compile_service.app.test_client()
    monkeypatch.setattr(compile_service, "COMPILE_TOKEN", "")
    assert client.post("/compile", json={"latex": "test"}).status_code == 401
    monkeypatch.setattr(compile_service, "COMPILE_TOKEN", "test-service-token")
    for header in ["", "test-service-token", "Bearer wrong", "Bearer é"]:
        assert client.post("/compile", headers={"Authorization": header}, json={"latex": "test"}).status_code == 401
    # Correct auth reaches input validation, without invoking TeX.
    header = {"Authorization": "Bearer test-service-token"}
    assert client.post("/compile", headers=header, json={}).status_code == 400
    assert client.post("/compile", headers=header, json=[1]).status_code == 400
    assert client.post("/compile", headers=header, json={"latex": 42}).status_code == 400


def test_compile_service_caps_request_before_json_parsing(compile_service, monkeypatch):
    monkeypatch.setattr(compile_service, "COMPILE_TOKEN", "test-service-token")
    monkeypatch.setitem(compile_service.app.config, "MAX_CONTENT_LENGTH", 64)
    response = compile_service.app.test_client().post(
        "/compile", headers={"Authorization": "Bearer test-service-token"},
        json={"latex": "x" * 100},
    )
    assert response.status_code == 413


def test_smart_template_keeps_generation_markers():
    from autocv.smart_cv_generator import SmartCVGenerator, CVSection
    generator = SmartCVGenerator()
    result = generator._replace_section_content(generator.template_content, {
        "summary": CVSection("Summary", "Synthetic summary"),
        "skills": CVSection("Skills", "Synthetic skills"),
    })
    assert "Synthetic summary" in result
    assert "Synthetic skills" in result


def test_legacy_compile_uses_isolated_compiler(tmp_path, monkeypatch):
    from autocv import latex_gen, latex_repair
    source = tmp_path / "sample.tex"
    source.write_text("synthetic latex")
    workdirs = []
    def fake_compile(latex, *, workdir, timeout):
        assert latex == "synthetic latex"
        assert Path(workdir) != tmp_path
        assert timeout == 60
        workdirs.append(Path(workdir))
        return latex_repair.CompileResult(True, b"%PDF-test", "", 0)
    monkeypatch.setattr(latex_repair, "compile_latex", fake_compile)
    output = latex_gen.compile_latex_to_pdf(str(source))
    assert Path(output).read_bytes() == b"%PDF-test"
    assert all(not workdir.exists() for workdir in workdirs)


def test_keyword_parser_works_without_downloaded_language_data():
    from autocv.parser import JobDescriptionParser
    result = JobDescriptionParser().get_top_skills("The Python developer uses Python and SQL, with Docker.")
    assert result[:3] == ["python", "sql", "docker"]
    assert "the" not in result


def test_logout_rejects_get(client):
    register(client)
    assert client.get("/logout").status_code == 405
    assert client.get("/api/me").get_json()["authenticated"] is True


def test_llm_health_hides_config_in_production(app, client, monkeypatch):
    monkeypatch.setitem(app.config, "IS_PRODUCTION", True)
    body = client.get("/api/llm/health").get_json()
    assert "config" not in body
    assert "source" in body
