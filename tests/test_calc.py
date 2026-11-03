import pytest

from app import calc


def test_total_rent():
    assert calc.total_rent(8000, 24) == 192000


def test_rent_to_revenue_pct():
    assert calc.rent_to_revenue_pct(8000, 40000) == 20


def test_rent_to_revenue_pct_rounds():
    assert calc.rent_to_revenue_pct(1000, 3000) == 33.33


def test_rent_after_increase():
    assert calc.rent_after_increase(8000, 10) == 8800


def test_monthly_rent_from_contract_period():
    assert calc.monthly_rent_from(96000, "yearly") == 8000
    assert calc.monthly_rent_from(8000, "monthly") == 8000
    assert calc.monthly_rent_from(8000, None) is None


def test_zero_increase_keeps_rent():
    assert calc.rent_after_increase(8000, 0) == 8000


@pytest.mark.parametrize(
    "call",
    [
        lambda: calc.total_rent(0, 12),
        lambda: calc.total_rent(8000, 0),
        lambda: calc.rent_to_revenue_pct(8000, 0),
        lambda: calc.rent_to_revenue_pct(-1, 1000),
        lambda: calc.rent_after_increase(8000, -5),
        lambda: calc.rent_after_increase(None, 5),
    ],
)
def test_invalid_input_raises_arabic_error(call):
    with pytest.raises(calc.InputError) as e:
        call()
    assert "لازم" in str(e.value)
