"""عميل الموديل (أي مزوّد بواجهة OpenAI مثل OpenRouter أو Groq): الدالة الوحيدة اللي تكلّم الموديل.
الأخطاء كلها برسائل عربية.

الخصوصية: لا نسجّل النص المرسل ولا رد الموديل، الحالة فقط.
"""
import contextvars
import json
import logging
import os
import re
import threading
import time

import httpx
from dotenv import load_dotenv

logger = logging.getLogger("app.llm")

try:
    from app import telemetry
except Exception:  # noqa: BLE001  المراقبة اختيارية
    telemetry = None

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
GROQ_BASE = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:nitro"   # Llama هو الموديل الرئيسي؛ :nitro يوجّه للمزوّد الأسرع (تحليل 3 ثواني بدل 27)
LEGACY_GROQ_MODEL = "openai/gpt-oss-120b"
TIMEOUT_SECONDS = 60
MAX_TOKENS = 4000  # كبير نسبياً لأن موديلات التفكير تستهلك جزء منه في التفكير
JSON_RETRIES = 1

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class LLMError(Exception):
    """خطأ في الاتصال بالموديل. الرسالة عربية وجاهزة للعرض للمستخدم."""


class BusyError(LLMError):
    """المزوّد رفض بسبب حد الطلبات (429). retry_after بالثواني."""
    retry_after: float = 20.0


class KeyProblem(LLMError):
    """المفتاح مرفوض (401/403): نجرّب المفتاح التالي لو موجود."""


_cooldown: dict[str, float] = {}     # مفتاح ← وقت (monotonic) نرجع نستخدمه فيه
_cooldown_lock = threading.Lock()
MAX_COOLDOWN = 90.0
BAD_KEY_COOLDOWN = 300.0


def api_keys() -> list[str]:
    """كل المفاتيح بالترتيب: الأول هو الأساسي والباقي احتياطي (يُجرّب لو الأول انقفل أو بلغ حده).
    الأسماء: LLM_API_KEY و LLM_API_KEY_2 و _3 ... ثم (للإعداد القديم) GROQ_API_KEY و GROQ_API_KEY_2 ... ."""
    load_dotenv()
    keys: list[str] = []
    for prefix in ("LLM_API_KEY", "GROQ_API_KEY"):
        for name in (prefix, f"{prefix}_2", f"{prefix}_3", f"{prefix}_4"):
            value = os.environ.get(name, "").strip()
            if value and value != "your_key_here" and value not in keys:
                keys.append(value)
    return keys


def _cool(key: str, seconds: float) -> None:
    with _cooldown_lock:
        _cooldown[key] = time.monotonic() + min(max(seconds, 1.0), MAX_COOLDOWN if seconds < BAD_KEY_COOLDOWN else seconds)


def _ready(keys: list[str]) -> list[str]:
    now = time.monotonic()
    with _cooldown_lock:
        return [k for k in keys if _cooldown.get(k, 0.0) <= now]


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


def _call(system: str, user: str, base: str, key: str, model: str, json_mode: bool = True, temperature: float = 0) -> tuple[int, str]:
    """يرجّع (رمز الحالة، النص). json_mode يطلب JSON من المزوّد مباشرة (بعض المزودين ما يدعمه)."""
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": MAX_TOKENS,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    effort = os.environ.get("LLM_REASONING_EFFORT", "").strip()
    if effort and "gpt-oss" in model:
        # اختياري: "low" أسرع بحوالي النصف لكنه جرّبناه وأسقط بنودًا (اقتباس غير حرفي، أو الإيجار)، فالافتراضي بدونه
        body["reasoning_effort"] = effort
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
        err = BusyError("الخدمة مشغولة حالياً (تجاوزنا حد الطلبات). انتظر دقيقة وجرّب مرة ثانية.")
        try:
            err.retry_after = float((getattr(r, "headers", {}) or {}).get("retry-after", 20))
        except (TypeError, ValueError):
            err.retry_after = 20.0
        raise err
    if r.status_code == 402:
        raise LLMError("رصيد حساب خدمة التحليل غير كافٍ. اشحن الرصيد من لوحة المزوّد وجرّب مرة ثانية.")
    if r.status_code in (401, 403):
        raise KeyProblem("تعذّر الاتصال بخدمة التحليل بسبب مشكلة في المفتاح.")
    if r.status_code != 200:
        raise LLMError(f"تعذّر الحصول على رد من خدمة التحليل (رمز {r.status_code}).")

    try:
        return 200, r.json()["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        return 200, ""


def chat_json(system: str, user: str, temperature: float = 0) -> dict:
    """يرسل طلب للموديل ويرجّع الرد كـ dict. لو المفتاح الأساسي بلغ حده أو انقفل نجرّب الاحتياطي تلقائيًا."""
    base, _, model = settings()
    keys = api_keys()
    if not keys:
        raise LLMError("مفتاح خدمة التحليل غير موجود. تأكد من ملف .env.")

    candidates = _ready(keys)
    if not candidates:
        raise BusyError("الخدمة مشغولة حالياً (تجاوزنا حد الطلبات). انتظر دقيقة وجرّب مرة ثانية.")
    last: LLMError | None = None
    for position, key in enumerate(candidates):
        started = time.perf_counter()
        try:
            data = _chat_json_with(key, base, model, system, user, temperature)
            _track(200, started, keys.index(key) + 1)
            return data
        except BusyError as e:
            _track(429, started, keys.index(key) + 1)
            _cool(key, e.retry_after)
            last = e
            logger.warning("llm: key #%d rate-limited, trying next (%d left)", keys.index(key) + 1, len(candidates) - position - 1)
        except KeyProblem as e:
            _track(401, started, keys.index(key) + 1)
            _cool(key, BAD_KEY_COOLDOWN)
            last = e
            logger.warning("llm: key #%d rejected, trying next (%d left)", keys.index(key) + 1, len(candidates) - position - 1)
    assert last is not None
    raise last


_purpose: "contextvars.ContextVar[str]" = contextvars.ContextVar("llm_purpose", default="")


def key_status() -> list[dict]:
    """حالة كل مفتاح الحين: جاهز أو في فترة راحة (بدون عرض المفتاح نفسه)."""
    now = time.monotonic()
    with _cooldown_lock:
        return [{"key": i + 1, "ready": _cooldown.get(k, 0.0) <= now, "wait_s": max(0, int(_cooldown.get(k, 0.0) - now))}
                for i, k in enumerate(api_keys())]


def _track(status: int, started: float, key_number: int) -> None:
    if telemetry:
        telemetry.record("llm", telemetry.current_visitor(), status=status, ms=int((time.perf_counter() - started) * 1000), meta={"key": key_number, "what": _purpose.get()})


def _chat_json_with(key: str, base: str, model: str, system: str, user: str, temperature: float) -> dict:
    json_mode = True
    attempts = 0
    while attempts <= JSON_RETRIES:
        status, content = _call(system, user, base, key, model, json_mode, temperature)
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
