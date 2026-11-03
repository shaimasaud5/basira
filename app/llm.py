"""عميل الموديل (أي مزوّد بواجهة OpenAI مثل OpenRouter أو Groq): الدالة الوحيدة اللي تكلّم الموديل.
الأخطاء كلها برسائل عربية.

الخصوصية: لا نسجّل النص المرسل ولا رد الموديل، الحالة فقط.
"""
import json
import logging
import os
import re

import httpx
from dotenv import load_dotenv

logger = logging.getLogger("app.llm")

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
GROQ_BASE = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"   # Llama هو الموديل الرئيسي للمشروع
LEGACY_GROQ_MODEL = "openai/gpt-oss-120b"
TIMEOUT_SECONDS = 60
MAX_TOKENS = 4000  # كبير نسبياً لأن موديلات التفكير تستهلك جزء منه في التفكير
JSON_RETRIES = 1

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class LLMError(Exception):
    """خطأ في الاتصال بالموديل. الرسالة عربية وجاهزة للعرض للمستخدم."""


def _parse_json(content: str) -> dict | None:
    content = (content or "").strip()
    fenced = _FENCE.match(content)
    if fenced:
        content = fenced.group(1)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def settings() -> tuple[str, str, str]:
    """(base, key, model) من متغيرات البيئة. بدون LLM_API_KEY نرجع للإعدادات القديمة (Groq) عشان ما ينكسر شي."""
    load_dotenv()
    key = os.environ.get("LLM_API_KEY", "").strip()
    legacy = not key
    if legacy:
        key = os.environ.get("GROQ_API_KEY", "").strip()
    base = os.environ.get("LLM_BASE", "").strip() or (GROQ_BASE if legacy else OPENROUTER_BASE)
    default_model = LEGACY_GROQ_MODEL if legacy else DEFAULT_MODEL
    model = os.environ.get("LLM_MODEL") or os.environ.get("GROQ_MODEL") or default_model
    return base.rstrip("/"), key, model


def _call(system: str, user: str, base: str, key: str, model: str, json_mode: bool = True) -> tuple[int, str]:
    """يرجّع (رمز الحالة، النص). json_mode يطلب JSON من المزوّد مباشرة (بعض المزودين ما يدعمه)."""
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        r = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "X-Title": "Basira"},
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        logger.warning("llm: timeout")
        raise LLMError("انتهت مهلة الاتصال بخدمة التحليل. جرّب مرة ثانية بعد شوي.")
    except httpx.HTTPError as e:
        logger.warning("llm: network error %s", type(e).__name__)
        raise LLMError("تعذّر الاتصال بخدمة التحليل. تأكد من الإنترنت وجرّب مرة ثانية.")

    logger.info("llm: status=%d", r.status_code)
    if r.status_code == 400 and json_mode:
        return 400, ""   # غالباً المزوّد ما يدعم response_format: نعيد بدونه (البرومبت يطلب JSON أصلاً)
    if r.status_code == 429:
        raise LLMError("الخدمة مشغولة حالياً (تجاوزنا حد الطلبات). انتظر دقيقة وجرّب مرة ثانية.")
    if r.status_code == 402:
        raise LLMError("رصيد حساب خدمة التحليل غير كافٍ. اشحن الرصيد من لوحة المزوّد وجرّب مرة ثانية.")
    if r.status_code in (401, 403):
        raise LLMError("تعذّر الاتصال بخدمة التحليل بسبب مشكلة في المفتاح.")
    if r.status_code != 200:
        raise LLMError(f"تعذّر الحصول على رد من خدمة التحليل (رمز {r.status_code}).")

    try:
        return 200, r.json()["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        return 200, ""


def chat_json(system: str, user: str) -> dict:
    """يرسل طلب للموديل ويرجّع الرد كـ dict. يعيد المحاولة مرة وحدة لو الـ JSON غير صالح."""
    base, key, model = settings()
    if not key or key == "your_key_here":
        raise LLMError("مفتاح خدمة التحليل غير موجود. تأكد من ملف .env.")

    json_mode = True
    attempts = 0
    while attempts <= JSON_RETRIES:
        status, content = _call(system, user, base, key, model, json_mode)
        if status == 400 and json_mode:
            json_mode = False   # المزوّد رفض response_format: نعيد بدونه (ما يحسب كمحاولة)
            logger.warning("llm: provider rejected response_format, retrying without it")
            continue
        data = _parse_json(content)
        if data is not None:
            return data
        attempts += 1
        logger.warning("llm: invalid json (attempt %d)", attempts)

    raise LLMError("رد خدمة التحليل جاء بصيغة غير صالحة. جرّب مرة ثانية.")
