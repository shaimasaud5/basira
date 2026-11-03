"""أرقام الداش بورد. يحسبها الكود فقط من البيانات المؤكدة، والواجهة تعرضها بدون ما تحلل نصوص."""
from app import calc
from app.contract import ContractFacts
from app.report import HIGH_RATIO_PCT, MEDIUM_RATIO_PCT
from app.schemas import ProjectInput


def build_metrics(effective: ProjectInput, facts: ContractFacts | None) -> dict:
    """effective: المدخل بعد تكميله من العقد. القيم الناقصة ترجع None والواجهة تعرض حالة فاضية مفيدة."""
    rent, revenue, months = effective.monthly_rent, effective.monthly_revenue, effective.lease_months

    increase = facts.fields.get("increase_pct") if facts else None
    increase_pct = increase.value if increase and increase.value_verified else None
    after = calc.rent_after_increase(rent, increase_pct) if rent and increase_pct is not None else None

    return {
        "monthly_rent": rent,
        "monthly_revenue": revenue,
        "lease_months": months,
        "rent_to_revenue_pct": calc.rent_to_revenue_pct(rent, revenue) if rent and revenue else None,
        "ratio_thresholds": {"medium": MEDIUM_RATIO_PCT, "high": HIGH_RATIO_PCT},  # اجتهاد منتج
        "total_commitment": calc.total_rent(rent, months) if rent and months else None,
        "increase_pct": increase_pct,
        "rent_after_increase": after,
        "monthly_extra_after_increase": round(after - rent, 2) if after is not None else None,
        "yearly_extra_after_increase": round((after - rent) * 12, 2) if after is not None else None,
    }
