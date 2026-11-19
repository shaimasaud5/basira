import pytest

from app import llm, ratelimit, telemetry


@pytest.fixture(autouse=True)
def no_real_llm_calls(request, monkeypatch):
    """يمنع أي اختبار من الاتصال بـ Groq الحقيقي بالغلط. الاختبار يستبدلها بنفسه لو احتاج.

    test_llm.py مستثنى لأنه يختبر الدالة نفسها (ويستبدل httpx.post بدل ذلك).
    """
    if request.module.__name__.endswith("test_llm"):
        return
    monkeypatch.setattr(llm, "chat_json", lambda system, user, temperature=0: {})


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """عدّاد الطلبات يتصفّر قبل كل اختبار، عشان الاختبارات ما تأثر على بعض."""
    ratelimit.analyze_limiter.reset()
    ratelimit.chat_limiter.reset()
    ratelimit.extract_limiter.reset()


@pytest.fixture(autouse=True)
def isolated_telemetry(tmp_path):
    """قاعدة المراقبة مؤقتة لكل اختبار (ما نلوّث data/telemetry.db)."""
    telemetry.reset(str(tmp_path / "telemetry.db"))
    yield
    telemetry.reset()
