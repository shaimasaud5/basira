"""شكل المدخلات والتحقق منها (الخطوة 1 من الـ pipeline). كل الرسائل عربية."""
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

MAX_CONTRACT_CHARS = 20000  # قرار منتج، نعدّله بعد تجربة عقود حقيقية


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _number(value, label: str, integer: bool = False):
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} لازم يكون رقم.")
    if integer:
        if number != int(number):
            raise ValueError(f"{label} لازم يكون رقم صحيح.")
        return int(number)
    return number


class ProjectInput(BaseModel):
    activity: str = Field(default="", validate_default=True)
    city: str = Field(default="", validate_default=True)
    monthly_rent: float | None = None
    monthly_revenue: float | None = None
    lease_months: int | None = None
    contract_text: str | None = None
    consent: bool = False

    @field_validator("activity", mode="before")
    @classmethod
    def _activity(cls, v):
        v = _blank_to_none(v)
        if v is None:
            raise ValueError("نوع النشاط مطلوب.")
        return v

    @field_validator("city", mode="before")
    @classmethod
    def _city(cls, v):
        v = _blank_to_none(v)
        if v is None:
            raise ValueError("المدينة مطلوبة.")
        return v

    @field_validator("monthly_rent", mode="before")
    @classmethod
    def _rent(cls, v):
        n = _number(v, "الإيجار الشهري")
        if n is not None and n <= 0:
            raise ValueError("الإيجار الشهري لازم يكون أكبر من صفر.")
        return n

    @field_validator("monthly_revenue", mode="before")
    @classmethod
    def _revenue(cls, v):
        n = _number(v, "الإيراد الشهري المتوقع")
        if n is not None and n <= 0:
            raise ValueError("الإيراد الشهري المتوقع لازم يكون أكبر من صفر.")
        return n

    @field_validator("lease_months", mode="before")
    @classmethod
    def _months(cls, v):
        n = _number(v, "مدة العقد بالشهور", integer=True)
        if n is not None and n <= 0:
            raise ValueError("مدة العقد بالشهور لازم تكون أكبر من صفر.")
        return n

    @field_validator("contract_text", mode="before")
    @classmethod
    def _contract(cls, v):
        v = _blank_to_none(v)
        if v is not None and len(v) > MAX_CONTRACT_CHARS:
            raise ValueError(
                f"نص العقد أطول من الحد المسموح ({MAX_CONTRACT_CHARS} حرف). الصق البنود المهمة فقط."
            )
        return v

    @model_validator(mode="after")
    def _consent_for_contract(self):
        if self.contract_text and not self.consent:
            raise ValueError(
                "لازم توافق صراحة على إرسال نص العقد إلى خدمة ذكاء اصطناعي (طرف ثالث) عشان نحلله."
            )
        return self


class RedactInput(BaseModel):
    """نص عقد جاهز (مثل العقود التجريبية أو نص عدّله المستخدم) لإخفاء الهوية منه فقط."""
    text: str = Field(default="", validate_default=True)

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, v):
        v = v.strip() if isinstance(v, str) else ""
        if not v:
            raise ValueError("النص فاضي.")
        if len(v) > MAX_CONTRACT_CHARS:
            raise ValueError(f"نص العقد أطول من الحد المسموح ({MAX_CONTRACT_CHARS} حرف).")
        return v


def arabic_errors(exc: ValidationError) -> list[str]:
    """يحوّل أخطاء Pydantic إلى قائمة رسائل عربية نظيفة."""
    return [e["msg"].removeprefix("Value error, ") for e in exc.errors()]
