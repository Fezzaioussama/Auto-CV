"""llm_client.chat must degrade gracefully (return None), never raise.

Providers sometimes answer HTTP 200 with no usable choice — an empty
``choices`` list or an inline ``{"error": ...}`` object (rate limits,
moderation, length). The client must return None so every caller's rule-based
fallback kicks in, instead of letting an IndexError escape and 500 the request.
"""

import autocv.llm_client as llm


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = str(payload)

    def json(self):
        return self._payload


def _patch_post(monkeypatch, payload, status=200):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _FakeResp(payload, status))


def test_chat_returns_none_on_empty_choices(monkeypatch):
    _patch_post(monkeypatch, {"choices": []})
    # api_key forces the call past the "no key" short-circuit.
    assert llm.chat([{"role": "user", "content": "hi"}], api_key="x") is None


def test_chat_returns_none_on_error_payload(monkeypatch):
    _patch_post(monkeypatch, {"error": {"message": "rate limited"}})
    assert llm.chat([{"role": "user", "content": "hi"}], api_key="x") is None


def test_chat_returns_none_on_non_dict_choice(monkeypatch):
    _patch_post(monkeypatch, {"choices": ["unexpected string"]})
    assert llm.chat([{"role": "user", "content": "hi"}], api_key="x") is None


def test_chat_extracts_content_on_valid_response(monkeypatch):
    _patch_post(monkeypatch, {"choices": [{"message": {"content": "hello world"}}]})
    assert llm.chat([{"role": "user", "content": "hi"}], api_key="x") == "hello world"


def test_openrouter_key_selects_openrouter_when_source_is_unset(monkeypatch):
    monkeypatch.delenv("SOURCE_LLM", raising=False)
    monkeypatch.delenv("LLM_SOURCE", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    assert llm.active_source() == "openrouter"


def test_openrouter_default_model_is_gpt_oss_120b(monkeypatch):
    monkeypatch.setenv("SOURCE_LLM", "openrouter")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    assert llm.resolve_model(llm.Task.DEFAULT) == "openai/gpt-oss-120b"


def test_explicit_source_still_wins_over_openrouter_key(monkeypatch):
    monkeypatch.setenv("SOURCE_LLM", "local")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    assert llm.active_source() == "local"
