import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.main import app
from app.ratelimit import RateLimited, RateLimiter

client = TestClient(app)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(3, 60, clock=Clock())
    for _ in range(3):
        limiter.check("a")
    with pytest.raises(RateLimited, match="انتظر دقيقة"):
        limiter.check("a")


def test_limit_is_per_visitor():
    limiter = RateLimiter(1, 60, clock=Clock())
    limiter.check("a")
    limiter.check("b")
    with pytest.raises(RateLimited):
        limiter.check("a")


def test_window_slides():
    clock = Clock()
    limiter = RateLimiter(1, 60, clock=clock)
    limiter.check("a")
    clock.now = 59
    with pytest.raises(RateLimited):
        limiter.check("a")
    clock.now = 60
    limiter.check("a")  # انتهت النافذة


def test_analyze_endpoint_is_limited_with_arabic_429(monkeypatch):
    monkeypatch.setattr(ratelimit, "analyze_limiter", RateLimiter(2, 60))
    ok = {"activity": "كوفي", "city": "جدة"}
    assert client.post("/analyze", json=ok).status_code == 200
    assert client.post("/analyze", json=ok).status_code == 200
    r = client.post("/analyze", json=ok)
    assert r.status_code == 429 and "انتظر دقيقة" in r.json()["errors"][0]


def test_chat_endpoint_is_limited(monkeypatch):
    tiny = RateLimiter(1, 60)
    monkeypatch.setattr(ratelimit, "chat_limiter", tiny)
    payload = {"question": "سؤال", "report": {"missing_info": ["x"]}}
    monkeypatch.setattr("app.llm.chat_json", lambda s, u: {"answer": "ok"})
    assert client.post("/chat", json=payload).status_code == 200
    assert client.post("/chat", json=payload).status_code == 429
