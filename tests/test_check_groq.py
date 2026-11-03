import check_groq
import pytest

from app import llm


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_key_is_missing():
    assert check_groq.key_is_missing("")
    assert check_groq.key_is_missing("your_key_here")
    assert not check_groq.key_is_missing("gsk_abc")


def test_model_available():
    assert check_groq.model_available(["a", "openai/gpt-oss-120b"], "openai/gpt-oss-120b")
    assert not check_groq.model_available(["a", "b"], "openai/gpt-oss-120b")


def test_status_message():
    assert "401" in check_groq.status_message(401)
    assert "429" in check_groq.status_message(429)
    assert "الرصيد" in check_groq.status_message(402)
    assert "500" in check_groq.status_message(500)


def test_main_without_key_returns_1(monkeypatch, capsys):
    monkeypatch.setattr(check_groq, "load_dotenv", lambda: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert check_groq.main() == 1
    assert "LLM_API_KEY" in capsys.readouterr().out


def test_main_rejected_key_returns_1(monkeypatch, capsys):
    monkeypatch.setattr(check_groq, "load_dotenv", lambda: None)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    monkeypatch.setattr(check_groq.httpx, "get", lambda *a, **k: FakeResponse(401))
    assert check_groq.main() == 1
    assert "401" in capsys.readouterr().out


def test_main_unknown_model_returns_1(monkeypatch, capsys):
    monkeypatch.setattr(check_groq, "load_dotenv", lambda: None)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    monkeypatch.setenv("GROQ_MODEL", "no-such-model")
    monkeypatch.setattr(
        check_groq.httpx, "get", lambda *a, **k: FakeResponse(200, {"data": [{"id": "other"}]})
    )
    assert check_groq.main() == 1
    assert "no-such-model" in capsys.readouterr().out


def test_main_happy_path_returns_0(monkeypatch, capsys):
    monkeypatch.setattr(check_groq, "load_dotenv", lambda: None)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    monkeypatch.setenv("GROQ_MODEL", "m1")
    monkeypatch.setattr(
        check_groq.httpx, "get", lambda *a, **k: FakeResponse(200, {"data": [{"id": "m1"}]})
    )
    reply = {"choices": [{"message": {"content": "تمام"}}]}
    monkeypatch.setattr(check_groq.httpx, "post", lambda *a, **k: FakeResponse(200, reply))
    assert check_groq.main() == 0
    assert "تمام" in capsys.readouterr().out


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """ما نقرأ .env الحقيقي ولا متغيرات LLM_* الحقيقية بالاختبارات."""
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    for name in ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE"):
        monkeypatch.delenv(name, raising=False)
