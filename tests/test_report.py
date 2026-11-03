from app import report
from app.report import RiskCard, build_report, financial_cards, missing_info
from app.schemas import ProjectInput


def project(**kw):
    return ProjectInput(activity="كوفي", city="الرياض", **kw)


def card(severity="low", evidence="دليل", title="x"):
    return RiskCard(
        title=title, category="financial", severity=severity,
        why="w", recommendation="r", evidence=evidence, trust_label=report.TRUST_COMPUTED,
    )


def test_ratio_card_uses_user_numbers_and_computed_label():
    cards = financial_cards(project(monthly_rent=8000, monthly_revenue=40000))
    assert len(cards) == 1
    c = cards[0]
    assert c.trust_label == report.TRUST_COMPUTED
    assert "8,000" in c.recommendation and "20%" in c.recommendation
    assert "8,000 ÷ 40,000 × 100 = 20%" in c.evidence


def test_stress_scenario_is_computed():
    c = financial_cards(project(monthly_rent=8000, monthly_revenue=40000))[0]
    assert "32,000" in c.evidence and "25%" in c.evidence


def test_severity_thresholds():
    def sev(rent):
        return financial_cards(project(monthly_rent=rent, monthly_revenue=10000))[0].severity
    assert sev(1000) == "low"
    assert sev(1500) == "medium"   # 15% بالضبط
    assert sev(3000) == "high"     # 30% بالضبط


def test_total_rent_card_needs_months():
    assert financial_cards(project(monthly_rent=8000)) == []
    c = financial_cards(project(monthly_rent=8000, lease_months=24))[0]
    assert "192,000" in c.evidence


def test_no_numbers_no_financial_cards():
    assert financial_cards(project()) == []


def test_missing_info_shrinks_as_data_is_given():
    assert len(missing_info(project())) > len(
        missing_info(project(monthly_rent=1, monthly_revenue=2, lease_months=12))
    )


def test_build_report_sorts_by_severity():
    r = build_report([card("low", title="a"), card("high", title="b"), card("medium", title="c")], [])
    assert [c.title for c in r["top"]] == ["b", "c", "a"]


def test_build_report_rejects_card_without_evidence():
    r = build_report([card(evidence=""), card(evidence="   "), card(title="ok")], [])
    assert [c.title for c in r["top"]] == ["ok"]
    assert r["rejected_count"] == 2


def test_build_report_splits_top_and_more():
    r = build_report([card(title=str(i)) for i in range(10)], [])
    assert len(r["top"]) == 7 and len(r["more"]) == 3


def test_build_report_has_disclaimer_and_missing():
    r = build_report([], ["سؤال"])
    assert r["disclaimer"] == "قراءة أولية وليست استشارة قانونية."
    assert r["missing_info"] == ["سؤال"]
