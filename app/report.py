"""بطاقات الخطر وتجميع التقرير. العلامات والترتيب والرفض يحددها الكود فقط."""
from typing import Literal

from pydantic import BaseModel

from app import calc
from app.schemas import ProjectInput

# عتبات الخطورة لنسبة الإيجار من الإيراد.
# تنبيه: هذي اجتهاد منتج (مو رقم رسمي ولا معيار صناعة). عدّلها لو تبي.
MEDIUM_RATIO_PCT = 10
HIGH_RATIO_PCT = 15
# سيناريو الضغط: لو الإيراد الفعلي أقل من التوقع بهالنسبة (افتراض للتوضيح فقط)
STRESS_DROP_PCT = 20

MAX_TOP_CARDS = 7
DISCLAIMER = "قراءة أولية وليست استشارة قانونية."

TRUST_DOCUMENTED = "موثّق"
TRUST_COMPUTED = "محسوب بالكود"
TRUST_AI = "اقتراح AI، تحقق منه"

Severity = Literal["high", "medium", "low"]
Category = Literal["financial", "contract", "regulatory", "operational"]
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class RiskCard(BaseModel):
    title: str
    category: Category
    severity: Severity
    why: str
    recommendation: str
    evidence: str
    trust_label: str


def _fmt(n: float) -> str:
    return f"{n:,.2f}".rstrip("0").rstrip(".")


def _severity_for_ratio(pct: float) -> Severity:
    if pct >= HIGH_RATIO_PCT:
        return "high"
    if pct >= MEDIUM_RATIO_PCT:
        return "medium"
    return "low"


def financial_cards(p: ProjectInput) -> list[RiskCard]:
    cards: list[RiskCard] = []

    if p.monthly_rent and p.monthly_revenue:
        pct = calc.rent_to_revenue_pct(p.monthly_rent, p.monthly_revenue)
        stressed_revenue = p.monthly_revenue * (1 - STRESS_DROP_PCT / 100)
        stressed_pct = calc.rent_to_revenue_pct(p.monthly_rent, stressed_revenue)
        cards.append(
            RiskCard(
                title="الإيجار يأخذ جزء كبير من الإيراد" if pct >= MEDIUM_RATIO_PCT
                else "نسبة الإيجار من الإيراد",
                category="financial",
                severity=_severity_for_ratio(pct),
                why=(
                    "الإيجار التزام ثابت يُدفع كل شهر سواء بعت أو لا. "
                    "كل ما كانت نسبته من الإيراد أعلى، قلّ الهامش اللي يتحمل نزول المبيعات."
                ),
                recommendation=(
                    f"إيجارك {_fmt(p.monthly_rent)} ريال يمثل {_fmt(pct)}% من إيرادك المتوقع "
                    f"({_fmt(p.monthly_revenue)} ريال). قبل التوقيع: اسأل عن فترة سماح في أول أشهر، "
                    "وفاوض على الإيجار، وراجع توقع الإيراد بأرقام واقعية."
                ),
                evidence=(
                    f"{_fmt(p.monthly_rent)} ÷ {_fmt(p.monthly_revenue)} × 100 = {_fmt(pct)}%. "
                    f"سيناريو: لو الإيراد الفعلي أقل بـ{STRESS_DROP_PCT}% من توقعك "
                    f"({_fmt(stressed_revenue)} ريال) تصير النسبة {_fmt(stressed_pct)}%."
                ),
                trust_label=TRUST_COMPUTED,
            )
        )

    if p.monthly_rent and p.lease_months:
        total = calc.total_rent(p.monthly_rent, p.lease_months)
        cards.append(
            RiskCard(
                title="إجمالي التزام الإيجار على مدة العقد",
                category="financial",
                severity="low",
                why="توقيع العقد التزام بدفع إيجار كامل المدة، وشروط الإنهاء المبكر تعتمد على نص العقد نفسه.",
                recommendation=(
                    f"التزامك الكلي {_fmt(total)} ريال على {p.lease_months} شهر. "
                    "قبل التوقيع تأكد أن سيولتك واحتياطيك يغطّون هذا الالتزام حتى لو تأخر المشروع."
                ),
                evidence=f"{_fmt(p.monthly_rent)} × {p.lease_months} شهر = {_fmt(total)} ريال.",
                trust_label=TRUST_COMPUTED,
            )
        )

    return cards


def missing_info(p: ProjectInput) -> list[str]:
    """أسئلة تحسّن التحليل، حسب اللي ما انكتب."""
    questions = []
    if not p.monthly_rent:
        questions.append("كم الإيجار الشهري؟")
    if not p.monthly_revenue:
        questions.append("كم الإيراد الشهري المتوقع؟")
    if not p.lease_months:
        questions.append("كم مدة العقد بالشهور؟")
    if not p.contract_text:
        questions.append("ارفع عقد الإيجار (PDF أو Word) لنحلل بنوده.")
    if not p.location_type:
        questions.append("وش نوع الموقع (مجمع، شارع تجاري، ...)؟")
    if p.employees is None:
        questions.append("كم عدد الموظفين؟")
    return questions


def build_report(
    cards: list[RiskCard],
    missing: list[str],
    warnings: list[str] | None = None,
    ai_cards: list[RiskCard] | None = None,
    metrics: dict | None = None,
) -> dict:
    """يرفض بطاقات بدون evidence، ويرتب بالخطورة، ويقسم لأعلى N والباقي.

    اقتراحات الـ AI تظهر في قسم منفصل أسفل التقرير، ولا تدخل في القائمة الرئيسية.
    """
    kept = [c for c in cards if c.evidence and c.evidence.strip()]
    kept.sort(key=lambda c: SEVERITY_ORDER[c.severity])  # الترتيب ثابت (stable)
    ai_kept = [c for c in (ai_cards or []) if c.evidence and c.evidence.strip()]
    ai_kept.sort(key=lambda c: SEVERITY_ORDER[c.severity])
    return {
        "top": kept[:MAX_TOP_CARDS],
        "more": kept[MAX_TOP_CARDS:],
        "ai_suggestions": ai_kept,
        "metrics": metrics or {},
        "missing_info": missing,
        "warnings": warnings or [],
        "rejected_count": len(cards) - len(kept),
        "disclaimer": DISCLAIMER,
    }
