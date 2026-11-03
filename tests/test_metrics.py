from fastapi.testclient import TestClient

from app import llm
from app.contract import ContractFacts, ExtractedField
from app.main import app
from app.metrics import build_metrics
from app.schemas import ProjectInput

client = TestClient(app)


def project(**kw):
    return ProjectInput(activity="كوفي", city="الرياض", **kw)


def increase(value=5.0, verified=True):
    return ContractFacts(fields={"increase_pct": ExtractedField(
        name="increase_pct", value=value, quote="يزداد الإيجار بنسبة 5%", value_verified=verified)})


def test_full_metrics():
    m = build_metrics(project(monthly_rent=8000, monthly_revenue=40000, lease_months=24), increase())
    assert m["rent_to_revenue_pct"] == 20 and m["total_commitment"] == 192000
    assert m["rent_after_increase"] == 8400 and m["monthly_extra_after_increase"] == 400
    assert m["yearly_extra_after_increase"] == 4800 and m["increase_pct"] == 5
    assert m["ratio_thresholds"] == {"medium": 10, "high": 15}


def test_missing_inputs_give_none_not_zero():
    m = build_metrics(project(), None)
    assert m["rent_to_revenue_pct"] is None and m["total_commitment"] is None
    assert m["rent_after_increase"] is None and m["yearly_extra_after_increase"] is None


def test_unverified_increase_is_not_used():
    m = build_metrics(project(monthly_rent=8000), increase(verified=False))
    assert m["increase_pct"] is None and m["rent_after_increase"] is None


def test_increase_without_rent_gives_no_after_value():
    assert build_metrics(project(), increase())["rent_after_increase"] is None


def test_analyze_response_carries_metrics(monkeypatch):
    monkeypatch.setattr(llm, "chat_json", lambda s, u: {})
    body = client.post("/analyze", json={"activity": "كوفي", "city": "جدة", "monthly_rent": 8000,
                                         "monthly_revenue": 40000, "lease_months": 12}).json()
    assert body["metrics"]["rent_to_revenue_pct"] == 20 and body["metrics"]["total_commitment"] == 96000
