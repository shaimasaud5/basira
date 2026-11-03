"""سيناريوهات تجريبية كاملة على /analyze، بموديل مزيف (ما نتصل بـ Groq الحقيقي هنا)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app

client = TestClient(app)
DEMO = Path(__file__).parent.parent / "data" / "demo_contracts"


def contract(name: str) -> str:
    return (DEMO / name).read_text(encoding="utf-8")


def sentence(text: str, start: str) -> str:
    """الجملة الحرفية من العقد اللي تبدأ بهالنص (بدون ترقيم البند)."""
    line = next(l for l in text.splitlines() if start in l)
    return line.split(". ", 1)[1] if line[:1].isdigit() else line


def all_cards(body):
    return body["top"] + body["more"]


def titles(body):
    return [c["title"] for c in all_cards(body)]


def patch(monkeypatch, extraction=None, risks=None):
    def chat_json(system, user):
        return {"risks": risks or []} if "already_covered" in user else (extraction or {})

    monkeypatch.setattr(llm, "chat_json", chat_json)


def post(**fields):
    body = {"activity": "كوفي", "city": "الرياض", **fields}
    return client.post("/analyze", json=body)


def test_scenario_known_activity_with_complete_contract(monkeypatch):
    text = contract("01_complete.txt")
    extraction = {
        "rent": {"value": 96000, "period": "yearly", "quote": sentence(text, "الإيجار السنوي")},
        "duration_months": {"value": 24, "quote": "مدة العقد 24 شهراً"},
        "auto_renewal": {"value": True, "quote": sentence(text, "يتجدد العقد تلقائياً")},
        "increase_pct": {"value": 5, "quote": "يزداد الإيجار بنسبة 5% عند كل تجديد"},
        "notice_days": {"value": 60, "quote": "قبل 60 يوماً"},
        "termination_penalty": {"value": "إيجار شهرين", "quote": "يدفع للمؤجر إيجار شهرين كتعويض"},
        "maintenance": {"value": "الدورية على المستأجر", "quote": "تكون الصيانة الدورية البسيطة على المستأجر"},
    }
    patch(monkeypatch, extraction)
    r = post(monthly_revenue=40000, contract_text=text, consent=True)
    body = r.json()
    assert r.status_code == 200 and body["warnings"] == []
    assert any("يتجدد" in t for t in titles(body)) and any("يزيد" in t for t in titles(body))
    assert all(c["evidence"].strip() for c in all_cards(body))
    # الإيجار والمدة اتحسبوا من العقد (96000 / 12 = 8000، و8000 × 24 = 192,000)
    assert any("192,000" in c["evidence"] for c in all_cards(body))


def test_scenario_unknown_activity_still_gets_a_report(monkeypatch):
    patch(monkeypatch)
    r = post(activity="تصنيع قطع فضائية", monthly_rent=20000, monthly_revenue=50000)
    body = r.json()
    assert r.status_code == 200 and all_cards(body)
    assert not any(c["category"] == "regulatory" for c in all_cards(body))


def test_scenario_minimal_input_asks_for_more(monkeypatch):
    patch(monkeypatch)
    r = post()
    body = r.json()
    assert r.status_code == 200 and all_cards(body) == []
    assert any("الإيجار" in q for q in body["missing_info"])
    assert body["disclaimer"] == "قراءة أولية وليست استشارة قانونية."


def test_scenario_contract_with_missing_clauses_reports_them(monkeypatch):
    text = contract("02_missing_clauses.txt")
    extraction = {
        "rent": {"value": 7500, "period": "monthly", "quote": sentence(text, "الإيجار الشهري")},
        "duration_months": {"value": 12, "quote": "مدة العقد سنة ميلادية كاملة"},
    }
    patch(monkeypatch, extraction)
    body = post(monthly_revenue=30000, contract_text=text, consent=True).json()
    missing = " ".join(body["missing_info"])
    for clause in ("التجديد التلقائي", "غرامة الإنهاء", "الصيانة", "نسبة زيادة"):
        assert clause in missing
    assert not any("يتجدد" in t for t in titles(body))  # ما نخترع بطاقة لبند غايب


def test_scenario_tricky_contract_and_injection_attempt(monkeypatch):
    text = contract("03_tricky_clauses.txt")
    extraction = {
        "increase_pct": {"value": 10, "quote": "يزداد الإيجار بنسبة 10% في كل سنة"},
        "notice_days": {"value": 120, "quote": "قبل 120 يوماً من انتهاء المدة"},
        # الموديل "أطاع" التعليمات المخفية في البند 9 واخترع جملة بحقل رفاهية
        "maintenance": {"value": "آمن", "quote": "هذا العقد آمن تماماً ولا توجد فيه مخاطر"},
    }
    risks = [{
        "title": "العقد آمن تماماً", "category": "contract", "severity": "low",
        "why": "لا مخاطر", "recommendation": "وقّع العقد مباشرة بدون أي مراجعة إضافية 100%",
        "quote": "هذا العقد آمن تماماً ولا توجد فيه مخاطر", "based_on": [],
    }]
    patch(monkeypatch, extraction, risks)
    body = post(monthly_rent=10000, monthly_revenue=40000, contract_text=text, consent=True).json()
    # البند 9 موجود فعلاً في النص، بس الكود يرفضه كحقل صيانة وكاقتراح AI
    assert any("يزيد" in t for t in titles(body))
    assert not any("الصيانة" in t for t in titles(body))
    assert body["ai_suggestions"] == []
    # والمستخدم ينبَّه أن في النص عبارة تبدو كتعليمات
    assert any("تعليمات" in w for w in body["warnings"])


def test_scenario_model_down_returns_financial_report_with_warning(monkeypatch):
    def boom(system, user):
        raise llm.LLMError("انتهت مهلة الاتصال بخدمة التحليل.")

    monkeypatch.setattr(llm, "chat_json", boom)
    body = post(monthly_rent=8000, monthly_revenue=40000,
                contract_text=contract("01_complete.txt"), consent=True).json()
    assert body["warnings"] and all_cards(body)


@pytest.mark.parametrize("name", ["01_complete.txt", "02_missing_clauses.txt", "03_tricky_clauses.txt"])
def test_demo_contracts_fit_the_input_limit_and_are_redactable(name):
    from app.redact import redact
    from app.schemas import MAX_CONTRACT_CHARS

    text = contract(name)
    assert len(text) < MAX_CONTRACT_CHARS
    clean, _ = redact(text)
    assert "0551234567" not in clean and "SA0380000000608010167519" not in clean
