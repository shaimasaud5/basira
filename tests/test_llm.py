import logging

import httpx
import pytest

from app import llm


class FakeResponse:
    def __init__(self, status_code=200, content='{"ok": true}'):
        self.status_code = status_code
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    monkeypatch.setenv("GROQ_MODEL", "test-model")


def patch_post(monkeypatch, *responses):
    """يرجّع الردود بالترتيب، ويسجّل الطلبات."""
    calls = []
    queue = list(responses)

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json})
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    return calls


def test_success_returns_dict_and_sends_expected_request(monkeypatch):
    calls = patch_post(monkeypatch, FakeResponse())
    assert llm.chat_json("sys", "usr") == {"ok": True}
    sent = calls[0]["json"]
    assert sent["model"] == "test-model" and sent["temperature"] == 0
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["messages"][0] == {"role": "system", "content": "sys"}
    assert calls[0]["headers"]["Authorization"] == "Bearer gsk_fake"


def test_json_inside_code_fence_is_accepted(monkeypatch):
    patch_post(monkeypatch, FakeResponse(content='```json\n{"a": 1}\n```'))
    assert llm.chat_json("s", "u") == {"a": 1}


def test_invalid_json_retries_once_then_succeeds(monkeypatch):
    calls = patch_post(monkeypatch, FakeResponse(content="مو JSON"), FakeResponse(content='{"a": 1}'))
    assert llm.chat_json("s", "u") == {"a": 1}
    assert len(calls) == 2


def test_invalid_json_twice_raises_arabic_error(monkeypatch):
    calls = patch_post(monkeypatch, FakeResponse(content="x"), FakeResponse(content="y"))
    with pytest.raises(llm.LLMError, match="صيغة غير صالحة"):
        llm.chat_json("s", "u")
    assert len(calls) == 2


def test_json_that_is_not_an_object_is_invalid(monkeypatch):
    patch_post(monkeypatch, FakeResponse(content="[1, 2]"), FakeResponse(content="3"))
    with pytest.raises(llm.LLMError):
        llm.chat_json("s", "u")


def test_empty_content_is_invalid(monkeypatch):
    patch_post(monkeypatch, FakeResponse(content=""), FakeResponse(content=""))
    with pytest.raises(llm.LLMError, match="صيغة غير صالحة"):
        llm.chat_json("s", "u")


@pytest.mark.parametrize(
    "outcome, expected",
    [
        (httpx.ReadTimeout("t"), "انتهت مهلة"),
        (httpx.ConnectError("c"), "تعذّر الاتصال"),
        (FakeResponse(429), "حد الطلبات"),
        (FakeResponse(401), "المفتاح"),
        (FakeResponse(500), "500"),
    ],
)
def test_errors_have_arabic_messages_and_do_not_retry(monkeypatch, outcome, expected):
    calls = patch_post(monkeypatch, outcome)
    with pytest.raises(llm.LLMError, match=expected):
        llm.chat_json("s", "u")
    assert len(calls) == 1


def test_missing_key_raises_before_any_request(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    calls = patch_post(monkeypatch)
    with pytest.raises(llm.LLMError, match="مفتاح خدمة التحليل غير موجود"):
        llm.chat_json("s", "u")
    assert calls == []


def test_legacy_groq_settings_still_work_without_llm_vars(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL")
    calls = patch_post(monkeypatch, FakeResponse())
    llm.chat_json("s", "u")
    assert calls[0]["json"]["model"] == llm.LEGACY_GROQ_MODEL
    assert calls[0]["url"].startswith(llm.GROQ_BASE)


def test_llm_vars_default_to_llama_on_openrouter(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY"); monkeypatch.delenv("GROQ_MODEL")
    monkeypatch.setenv("LLM_API_KEY", "sk-or-fake")
    calls = patch_post(monkeypatch, FakeResponse())
    llm.chat_json("s", "u")
    assert calls[0]["json"]["model"] == "meta-llama/llama-3.3-70b-instruct"
    assert calls[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-or-fake"


def test_custom_base_and_model(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE", "https://example.test/v1/")
    monkeypatch.setenv("LLM_MODEL", "meta/llama-x")
    calls = patch_post(monkeypatch, FakeResponse())
    llm.chat_json("s", "u")
    assert calls[0]["url"] == "https://example.test/v1/chat/completions" and calls[0]["json"]["model"] == "meta/llama-x"


def test_provider_rejecting_json_mode_is_retried_without_it(monkeypatch):
    calls = patch_post(monkeypatch, FakeResponse(400), FakeResponse())
    assert llm.chat_json("s", "u") == {"ok": True}
    assert "response_format" in calls[0]["json"] and "response_format" not in calls[1]["json"]


def test_prompt_and_reply_never_logged(monkeypatch, caplog):
    patch_post(monkeypatch, FakeResponse(content='{"سر": "رد سري 999"}'))
    with caplog.at_level(logging.DEBUG):
        llm.chat_json("system", "نص سري جداً 12345")
    assert "12345" not in caplog.text and "999" not in caplog.text
    assert "status=200" in caplog.text


def test_no_credit_402_gives_clear_arabic_error(monkeypatch):
    patch_post(monkeypatch, FakeResponse(402))
    with pytest.raises(llm.LLMError, match="رصيد"):
        llm.chat_json("s", "u")
