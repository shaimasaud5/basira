"""إخفاء الهوية قبل إرسال نص العقد لأي طرف ثالث (best-effort بـ regex، مو ضمان 100%).

لا نخفي المبالغ ولا الأرقام العادية لأن الإيجار هو اللي نحلله.
"""
import re

# الأرقام العربية-الهندية والفارسية تتحول لإنجليزية للمطابقة فقط (نفس الطول، فالمواضع تتطابق)
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# الترتيب مهم: الأولوية للأنماط الأطول (آيبان قبل الهوية) عشان ما تتداخل
_PATTERNS = [
    ("iban", "[آيبان]", re.compile(r"SA\s?\d{2}(?:\s?[0-9A-Z]{4}){5}", re.IGNORECASE)),
    ("email", "[بريد]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("mobile", "[جوال]", re.compile(r"(?<!\d)(?:(?:\+|00)?966[\s-]?5|05)(?:[\s-]?\d){8}(?!\d)")),
    ("national_id", "[هوية]", re.compile(r"(?<!\d)[12]\d{9}(?!\d)")),
]


def redact(text: str) -> tuple[str, dict[str, int]]:
    """يرجّع (النص بعد الإخفاء، عدد ما أُخفي لكل نوع). لا يرجّع المحتوى المخفي أبداً."""
    normalized = text.translate(_DIGITS)
    taken: list[tuple[int, int, str]] = []
    counts = {name: 0 for name, _, _ in _PATTERNS}

    for name, tag, pattern in _PATTERNS:
        for m in pattern.finditer(normalized):
            start, end = m.span()
            if any(start < t_end and end > t_start for t_start, t_end, _ in taken):
                continue  # تداخل مع نمط أعلى أولوية
            taken.append((start, end, tag))
            counts[name] += 1

    clean = text
    for start, end, tag in sorted(taken, reverse=True):
        clean = clean[:start] + tag + clean[end:]
    return clean, counts
