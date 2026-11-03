from app import report
from app.contract import ContractFacts, ExtractedField
from app.contract_cards import contract_cards, contract_missing, effective_project
from app.schemas import ProjectInput


def field(name, value, quote, period=None, verified=True):
    return ExtractedField(name=name, value=value, quote=quote, period=period, value_verified=verified)


def facts_of(*fields, not_found=()):
    return ContractFacts(fields={f.name: f for f in fields}, not_found=list(not_found))


def project(**kw):
    return ProjectInput(activity="كوفي", city="الرياض", **kw)


RENT = field("rent", 96000.0, "الإيجار السنوي 96,000 ريال", period="yearly")
RENEWAL = field("auto_renewal", True, "يتجدد العقد تلقائياً")
NOTICE = field("notice_days", 60.0, "قبل 60 يوماً")
INCREASE = field("increase_pct", 5.0, "يزداد الإيجار بنسبة 5%")
PENALTY = field("termination_penalty", "إيجار ثلاثة أشهر", "يدفع المستأجر إيجار ثلاثة أشهر")
MAINT = field("maintenance", "المستأجر", "الصيانة الدورية على المستأجر")


def by_title(cards, part):
    return next(c for c in cards if part in c.title)


def test_effective_project_fills_rent_and_months_from_contract():
    p = effective_project(project(), facts_of(RENT, field("duration_months", 24.0, "مدة العقد 24 شهراً")))
    assert p.monthly_rent == 8000 and p.lease_months == 24


def test_effective_project_keeps_user_values():
    p = effective_project(project(monthly_rent=7000, lease_months=12), facts_of(RENT))
    assert p.monthly_rent == 7000 and p.lease_months == 12


def test_unverified_values_are_not_used():
    unverified = field("duration_months", 24.0, "مدة العقد سنتان", verified=False)
    assert effective_project(project(), facts_of(unverified)).lease_months is None
    bad_rent = field("rent", 50000.0, "الإيجار السنوي 96,000 ريال", period="yearly", verified=False)
    assert effective_project(project(), facts_of(bad_rent)).monthly_rent is None


def test_auto_renewal_with_notice_is_documented_and_uses_notice():
    c = by_title(contract_cards(project(), facts_of(RENEWAL, NOTICE)), "يتجدد")
    assert c.trust_label == report.TRUST_DOCUMENTED and c.category == "contract"
    assert "60" in c.recommendation and "«يتجدد العقد تلقائياً»" in c.evidence


def test_auto_renewal_without_notice_says_notice_not_found():
    c = by_title(contract_cards(project(), facts_of(RENEWAL)), "يتجدد")
    assert "ما لقينا في النص مدة إشعار" in c.recommendation


def test_auto_renewal_false_makes_no_renewal_card():
    cards = contract_cards(project(), facts_of(field("auto_renewal", False, "لا يتجدد العقد تلقائياً")))
    assert cards == []


def test_notice_alone_makes_low_card():
    c = contract_cards(project(), facts_of(NOTICE))[0]
    assert c.severity == "low" and "60" in c.recommendation


def test_increase_card_is_computed_with_user_numbers():
    c = by_title(contract_cards(project(monthly_rent=8000, monthly_revenue=40000), facts_of(INCREASE)), "يزيد")
    assert c.trust_label == report.TRUST_COMPUTED
    assert "8,400" in c.recommendation and "4,800" in c.recommendation
    assert "21%" in c.recommendation  # 8400 / 40000
    assert "8,000 × (1 + 5%) = 8,400" in c.evidence and "«يزداد الإيجار بنسبة 5%»" in c.evidence


def test_increase_uses_rent_from_contract_when_form_empty():
    c = by_title(contract_cards(project(), facts_of(RENT, INCREASE)), "يزيد")
    assert "8,400" in c.recommendation


def test_increase_without_rent_is_documented_not_computed():
    c = contract_cards(project(), facts_of(INCREASE))[0]
    assert c.trust_label == report.TRUST_DOCUMENTED and "ما قدرنا نحسب" in c.recommendation


def test_increase_unverified_percent_is_not_computed():
    unverified = field("increase_pct", 5.0, "تزداد خمسة بالمئة", verified=False)
    c = contract_cards(project(monthly_rent=8000), facts_of(unverified))[0]
    assert c.trust_label == report.TRUST_DOCUMENTED and "8,400" not in c.recommendation


def test_penalty_card_compares_with_monthly_rent():
    c = contract_cards(project(monthly_rent=8000), facts_of(PENALTY))[0]
    assert "8,000" in c.recommendation and c.trust_label == report.TRUST_DOCUMENTED


def test_maintenance_severity_depends_on_tenant():
    tenant = contract_cards(project(), facts_of(MAINT))[0]
    landlord = contract_cards(project(), facts_of(field("maintenance", "المؤجر", "الصيانة على المؤجر")))[0]
    assert tenant.severity == "medium" and landlord.severity == "low"


def test_rent_mismatch_card():
    c = by_title(contract_cards(project(monthly_rent=7000), facts_of(RENT)), "يختلف")
    assert c.trust_label == report.TRUST_COMPUTED
    assert "7,000" in c.recommendation and "8,000" in c.recommendation


def test_no_mismatch_when_equal_or_user_gave_nothing():
    assert contract_cards(project(monthly_rent=8000), facts_of(RENT)) == []
    assert contract_cards(project(), facts_of(RENT)) == []


def test_every_card_has_evidence():
    all_facts = facts_of(RENT, RENEWAL, NOTICE, INCREASE, PENALTY, MAINT)
    cards = contract_cards(project(monthly_rent=7000, monthly_revenue=40000), all_facts)
    assert len(cards) >= 5 and all(c.evidence.strip() for c in cards)


def test_contract_missing_asks_when_rent_period_unknown():
    no_period = field("rent", 96000.0, "الإيجار 96,000 ريال", period=None)
    assert any("شهري أو سنوي" in q for q in contract_missing(facts_of(no_period)))


def test_contract_missing_lists_absent_and_unverified():
    unverified = field("duration_months", 24.0, "مدة العقد سنتان", verified=False)
    qs = contract_missing(facts_of(RENT, unverified))
    assert any("الصيانة" in q and "ما لقينا" in q for q in qs)
    assert any("مدة العقد" in q and "ما قدرنا نتأكد" in q for q in qs)
    assert not any("«الإيجار»" in q for q in qs)
