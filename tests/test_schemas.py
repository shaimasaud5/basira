import pytest
from pydantic import ValidationError

from app.schemas import MAX_CONTRACT_CHARS, ProjectInput, arabic_errors


def errors_of(**data):
    with pytest.raises(ValidationError) as e:
        ProjectInput(**data)
    return arabic_errors(e.value)


def test_minimal_valid_input():
    p = ProjectInput(activity="كوفي", city="الرياض")
    assert p.activity == "كوفي" and p.monthly_rent is None


def test_full_valid_input_converts_strings_to_numbers():
    p = ProjectInput(
        activity="كوفي", city="الرياض", employees="3",
        monthly_rent="8000", monthly_revenue="40000", lease_months="24",
    )
    assert p.employees == 3 and p.monthly_rent == 8000.0 and p.lease_months == 24


def test_empty_input_reports_both_required_fields():
    errs = errors_of()
    assert "نوع النشاط مطلوب." in errs and "المدينة مطلوبة." in errs


def test_whitespace_only_is_empty():
    assert "المدينة مطلوبة." in errors_of(activity="كوفي", city="   ")


def test_blank_optional_fields_become_none():
    p = ProjectInput(activity="كوفي", city="جدة", monthly_rent="", district="  ")
    assert p.monthly_rent is None and p.district is None


def test_non_numeric_rent():
    assert "الإيجار الشهري لازم يكون رقم." in errors_of(
        activity="كوفي", city="جدة", monthly_rent="abc"
    )


@pytest.mark.parametrize("field", ["monthly_rent", "monthly_revenue", "lease_months"])
@pytest.mark.parametrize("bad", [0, -5])
def test_non_positive_numbers_rejected(field, bad):
    assert errors_of(activity="كوفي", city="جدة", **{field: bad})


def test_fractional_employees_rejected():
    assert errors_of(activity="كوفي", city="جدة", employees="2.5")


def test_contract_requires_consent():
    errs = errors_of(activity="كوفي", city="جدة", contract_text="بند 1")
    assert any("توافق" in m for m in errs)


def test_contract_with_consent_ok():
    p = ProjectInput(activity="كوفي", city="جدة", contract_text="بند 1", consent=True)
    assert p.contract_text == "بند 1"


def test_blank_contract_needs_no_consent():
    assert ProjectInput(activity="كوفي", city="جدة", contract_text="  ").contract_text is None


def test_contract_length_limit():
    ok = "ا" * MAX_CONTRACT_CHARS
    assert ProjectInput(activity="كوفي", city="جدة", contract_text=ok, consent=True)
    errs = errors_of(activity="كوفي", city="جدة", contract_text=ok + "ا", consent=True)
    assert any("أطول من الحد" in m for m in errs)
