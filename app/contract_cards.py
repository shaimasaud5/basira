"""بطاقات الخطر المبنية على بنود العقد. كل بطاقة دليلها جملة تأكد الكود أنها في العقد."""
from app import calc
from app.contract import ContractFacts, ExtractedField
from app.report import TRUST_COMPUTED, TRUST_DOCUMENTED, RiskCard, _fmt
from app.schemas import ProjectInput

# درجات الخطورة اجتهاد منتج (مو معيار رسمي). عدّلها لو تبي.
AUTO_RENEWAL_SEVERITY = "medium"
INCREASE_SEVERITY = "medium"
PENALTY_SEVERITY = "medium"
MAINTENANCE_TENANT_SEVERITY = "medium"
MAINTENANCE_OTHER_SEVERITY = "low"
NOTICE_ONLY_SEVERITY = "low"
MISMATCH_SEVERITY = "medium"

# فرق صغير يُهمل (تقريب الأرقام)
RENT_MISMATCH_TOLERANCE = 0.5

LABELS = {
    "rent": "الإيجار",
    "duration_months": "مدة العقد",
    "auto_renewal": "التجديد التلقائي",
    "increase_pct": "نسبة زيادة الإيجار",
    "notice_days": "مدة الإشعار",
    "termination_penalty": "غرامة الإنهاء المبكر",
    "maintenance": "الصيانة",
}


def _quote(field: ExtractedField) -> str:
    return f"«{field.quote}»"


def contract_monthly_rent(facts: ContractFacts) -> float | None:
    rent = facts.fields.get("rent")
    if rent and rent.value_verified:
        return calc.monthly_rent_from(rent.value, rent.period)
    return None


def effective_project(p: ProjectInput, facts: ContractFacts) -> ProjectInput:
    """يكمّل الإيجار والمدة من العقد لو المستخدم ما أدخلهم. القيم غير المؤكدة ما تُستخدم."""
    updates = {}
    if not p.monthly_rent:
        monthly = contract_monthly_rent(facts)
        if monthly:
            updates["monthly_rent"] = monthly
    duration = facts.fields.get("duration_months")
    if not p.lease_months and duration and duration.value_verified and float(duration.value).is_integer():
        updates["lease_months"] = int(duration.value)
    return p.model_copy(update=updates)


def _verified_number(facts: ContractFacts, name: str) -> ExtractedField | None:
    field = facts.fields.get(name)
    return field if field and field.value_verified else None


def contract_cards(p: ProjectInput, facts: ContractFacts) -> list[RiskCard]:
    """p هو المدخل الأصلي. الحسابات تستخدم الإيجار الفعلي (من النموذج أو العقد)."""
    cards: list[RiskCard] = []
    monthly_rent = effective_project(p, facts).monthly_rent
    notice = _verified_number(facts, "notice_days")

    # 1) تجديد تلقائي
    renewal = facts.fields.get("auto_renewal")
    if renewal and renewal.value is True:
        if notice:
            advice = (
                f"لو ما تبي التجديد، سجّل في تقويمك موعد الإخطار قبل {_fmt(notice.value)} يوماً "
                "من نهاية المدة (حسب نص العقد)."
            )
            evidence = f"{_quote(renewal)} / {_quote(notice)}"
        else:
            advice = (
                "ما لقينا في النص مدة إشعار. اسأل المؤجر متى آخر موعد لإخطاره "
                "لو ما تبي التجديد، واطلب كتابتها في العقد."
            )
            evidence = _quote(renewal)
        cards.append(RiskCard(
            title="العقد يتجدد تلقائياً",
            category="contract", severity=AUTO_RENEWAL_SEVERITY,
            why="لو فاتك موعد الإخطار، تلتزم بمدة جديدة بدون ما توقّعن من جديد.",
            recommendation=advice, evidence=evidence, trust_label=TRUST_DOCUMENTED,
        ))
    elif notice:
        cards.append(RiskCard(
            title="مدة إشعار في العقد",
            category="contract", severity=NOTICE_ONLY_SEVERITY,
            why="تفوّت الموعد = تفوّت حقك في الإنهاء أو عدم التجديد.",
            recommendation=f"سجّل في تقويمك موعد الإخطار ({_fmt(notice.value)} يوماً حسب نص العقد).",
            evidence=_quote(notice), trust_label=TRUST_DOCUMENTED,
        ))

    # 2) زيادة الإيجار
    increase = facts.fields.get("increase_pct")
    if increase:
        if increase.value_verified and monthly_rent:
            new_rent = calc.rent_after_increase(monthly_rent, increase.value)
            yearly_extra = round((new_rent - monthly_rent) * 12, 2)
            advice = (
                f"بعد الزيادة يصير إيجارك {_fmt(new_rent)} ريال شهرياً بدل {_fmt(monthly_rent)}، "
                f"يعني {_fmt(yearly_extra)} ريال زيادة في السنة."
            )
            if p.monthly_revenue:
                new_pct = calc.rent_to_revenue_pct(new_rent, p.monthly_revenue)
                advice += f" وتصير نسبته {_fmt(new_pct)}% من إيرادك المتوقع."
            advice += " اسأل: هل الزيادة تتكرر مع كل تجديد؟"
            cards.append(RiskCard(
                title="الإيجار يزيد بعد التجديد",
                category="contract", severity=INCREASE_SEVERITY,
                why="الزيادة ترفع التزامك الثابت بدون ما يزيد إيرادك بالضرورة.",
                recommendation=advice,
                evidence=(
                    f"{_quote(increase)} / {_fmt(monthly_rent)} × (1 + {_fmt(increase.value)}%) "
                    f"= {_fmt(new_rent)} ريال، والفرق السنوي {_fmt(yearly_extra)} ريال."
                ),
                trust_label=TRUST_COMPUTED,
            ))
        else:
            cards.append(RiskCard(
                title="في العقد بند زيادة للإيجار",
                category="contract", severity=INCREASE_SEVERITY,
                why="الزيادة ترفع التزامك الثابت.",
                recommendation=(
                    "ما قدرنا نحسب أثر الزيادة لأن الإيجار أو النسبة غير مؤكدين من نص العقد. "
                    "أدخل الإيجار الشهري في النموذج وراجع النسبة في العقد."
                ),
                evidence=_quote(increase), trust_label=TRUST_DOCUMENTED,
            ))

    # 3) غرامة الإنهاء
    penalty = facts.fields.get("termination_penalty")
    if penalty:
        compare = (
            f" قارنها بإيجارك الشهري ({_fmt(monthly_rent)} ريال)،"
            if monthly_rent else " قارنها بقدرتك على الاستمرار،"
        )
        cards.append(RiskCard(
            title="غرامة أو شرط للإنهاء المبكر",
            category="contract", severity=PENALTY_SEVERITY,
            why="لو تعثّر المشروع، هذا اللي يحدد كم تدفعين لو انسحبتي.",
            recommendation=(
                f"البند يقول: {penalty.value}." + compare +
                " واسأل المؤجر يوضح بالأرقام كيف تُحسب الغرامة قبل التوقيع."
            ),
            evidence=_quote(penalty), trust_label=TRUST_DOCUMENTED,
        ))

    # 4) الصيانة
    maintenance = facts.fields.get("maintenance")
    if maintenance:
        on_tenant = "المستأجر" in str(maintenance.value) or "المستأجر" in maintenance.quote
        cards.append(RiskCard(
            title="من يتحمل الصيانة" if not on_tenant else "الصيانة على المستأجر",
            category="contract",
            severity=MAINTENANCE_TENANT_SEVERITY if on_tenant else MAINTENANCE_OTHER_SEVERITY,
            why="تكلفة الصيانة تنزل من أرباحك لو كانت عليك، وما تظهر في الإيجار.",
            recommendation=(
                f"البند يقول: {maintenance.value}. اسأل عن حدود الصيانة (دورية أو طارئة) "
                "وجهّز لها ميزانية، وصوّر حالة المكان عند الاستلام."
            ),
            evidence=_quote(maintenance), trust_label=TRUST_DOCUMENTED,
        ))

    # 5) فرق بين النموذج والعقد
    contract_rent = contract_monthly_rent(facts)
    if p.monthly_rent and contract_rent and abs(p.monthly_rent - contract_rent) > RENT_MISMATCH_TOLERANCE:
        rent = facts.fields["rent"]
        cards.append(RiskCard(
            title="الإيجار في النموذج يختلف عن العقد",
            category="contract", severity=MISMATCH_SEVERITY,
            why="الحسابات والتقرير كلها مبنية على الإيجار، فأي فرق يغيّر النتيجة.",
            recommendation=(
                f"أنت أدخلت {_fmt(p.monthly_rent)} ريال شهرياً، والعقد يعادل "
                f"{_fmt(contract_rent)} ريال شهرياً. تأكد من الرقم الصحيح وأعد التحليل."
            ),
            evidence=f"{_quote(rent)} / النموذج: {_fmt(p.monthly_rent)} ريال شهرياً، العقد: {_fmt(contract_rent)} ريال شهرياً.",
            trust_label=TRUST_COMPUTED,
        ))

    return cards


def contract_missing(facts: ContractFacts) -> list[str]:
    """بنود ما لقيناها أو ما تأكدنا منها، كأسئلة للمستخدم."""
    questions = []
    for name, label in LABELS.items():
        field = facts.fields.get(name)
        if field is None:
            questions.append(f"ما لقينا في النص بند «{label}». اسأل المؤجر أو تأكد أنك لصقت البند.")
        elif not field.value_verified:
            questions.append(
                f"ما قدرنا نتأكد من رقم «{label}» (ممكن مكتوب بالكلمات). أدخله في النموذج."
            )
        elif name == "rent" and field.period is None:
            questions.append("ما عرفنا هل الإيجار في العقد شهري أو سنوي. أدخل الإيجار الشهري في النموذج.")
    return questions
