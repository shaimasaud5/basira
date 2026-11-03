import pytest

from app import llm, ratelimit


@pytest.fixture(autouse=True)
def no_real_llm_calls(request, monkeypatch):
    """يمنع أي اختبار من الاتصال بـ Groq الحقيقي بالغلط. الاختبار يستبدلها بنفسه لو احتاج.

    test_llm.py مستثنى لأنه يختبر الدالة نفسها (ويستبدل httpx.post بدل ذلك).
    """
    if request.module.__name__.endswith("test_llm"):
        return
    monkeypatch.setattr(llm, "chat_json", lambda system, user: {})


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """عدّاد الطلبات يتصفّر قبل كل اختبار، عشان الاختبارات ما تأثر على بعض."""
    ratelimit.analyze_limiter.reset()
    ratelimit.chat_limiter.reset()
    ratelimit.extract_limiter.reset()
