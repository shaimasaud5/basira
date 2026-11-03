"""حسابات المخاطر المالية. كود بحت: الأرقام يحسبها الكود فقط وليس الـ AI."""


class InputError(ValueError):
    """مدخل غير صالح. الرسالة عربية وجاهزة للعرض للمستخدم."""


def _positive(value: float, label: str) -> float:
    if value is None or value <= 0:
        raise InputError(f"{label} لازم يكون رقم أكبر من صفر.")
    return value


def total_rent(monthly_rent: float, months: int) -> float:
    """إجمالي الإيجار على مدة العقد = الإيجار الشهري × عدد الشهور."""
    _positive(monthly_rent, "الإيجار الشهري")
    _positive(months, "مدة العقد بالشهور")
    return round(monthly_rent * months, 2)


def rent_to_revenue_pct(monthly_rent: float, monthly_revenue: float) -> float:
    """نسبة الإيجار من الإيراد الشهري المتوقع، بالمئة."""
    _positive(monthly_rent, "الإيجار الشهري")
    _positive(monthly_revenue, "الإيراد الشهري المتوقع")
    return round(monthly_rent / monthly_revenue * 100, 2)


def monthly_rent_from(amount: float, period: str | None) -> float | None:
    """يحوّل الإيجار المذكور في العقد إلى شهري. None لو الفترة غير معروفة."""
    _positive(amount, "الإيجار")
    if period == "monthly":
        return round(amount, 2)
    if period == "yearly":
        return round(amount / 12, 2)
    return None


def rent_after_increase(monthly_rent: float, increase_pct: float) -> float:
    """الإيجار الشهري بعد تطبيق نسبة الزيادة (مثلاً عند التجديد)."""
    _positive(monthly_rent, "الإيجار الشهري")
    if increase_pct is None or increase_pct < 0:
        raise InputError("نسبة الزيادة لازم تكون صفر أو أكثر.")
    return round(monthly_rent * (1 + increase_pct / 100), 2)
