"""يتأكد أن مفتاح الموديل شغال وأن اسم الموديل موجود عند المزوّد (OpenRouter أو Groq أو غيره).

التشغيل:  python check_groq.py
"""
import os
import sys

import httpx
from dotenv import load_dotenv

from app import llm

PLACEHOLDER_KEY = "your_key_here"

STATUS_MESSAGES = {
    401: "المفتاح مرفوض (401). تأكد أنك نسخته صح.",
    402: "المفتاح شغال لكن الرصيد غير كافٍ (402). اشحني رصيداً من لوحة المزوّد (OpenRouter: Credits) وأعيدي الفحص.",
    429: "تجاوزت الحد المسموح (429). انتظر شوي وجرب.",
}


def key_is_missing(key: str) -> bool:
    return not key or key == PLACEHOLDER_KEY


def model_available(model_ids: list[str], wanted: str) -> bool:
    return wanted in model_ids


def status_message(code: int) -> str:
    return STATUS_MESSAGES.get(code, f"رد غير متوقع من المزوّد: {code}")


def main() -> int:
    load_dotenv()
    base, key, model = llm.settings()

    if key_is_missing(key):
        print("❌ LLM_API_KEY غير موجود. انسخ .env.example إلى .env وحط المفتاح.")
        return 1

    headers = {"Authorization": f"Bearer {key}"}

    # الخطوة 1: نجيب قائمة الموديلات (هذا يتحقق من المفتاح بنفس الوقت)
    try:
        r = httpx.get(f"{base}/models", headers=headers, timeout=15)
    except httpx.TimeoutException:
        print("❌ انتهت المهلة (timeout) أثناء الاتصال بالمزوّد.")
        return 1
    except httpx.HTTPError as e:
        print(f"❌ فشل الاتصال: {type(e).__name__}")
        return 1

    if r.status_code != 200:
        print(f"❌ {status_message(r.status_code)}")
        return 1

    ids = [m["id"] for m in r.json().get("data", [])]
    print(f"✅ المفتاح شغال. عدد الموديلات المتاحة: {len(ids)}")

    # الخطوة 2: نتأكد أن الموديل المطلوب موجود
    if not model_available(ids, model):
        print(f"❌ الموديل '{model}' غير موجود في حسابك. المتاح:")
        for model_id in sorted(ids):
            print("  -", model_id)
        return 1
    print(f"✅ الموديل '{model}' موجود.")

    # الخطوة 3: طلب تجربة صغير (يكلف أقل من سنت)
    # max_tokens كبير نسبياً لأن gpt-oss يفكر قبل ما يرد، والتفكير يُحسب من الحد
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "قل كلمة واحدة: تمام"}],
        "max_tokens": 300,
    }
    try:
        c = httpx.post(f"{base}/chat/completions", headers=headers, json=body, timeout=30)
    except httpx.HTTPError as e:
        print(f"❌ فشل طلب التجربة: {type(e).__name__}")
        return 1
    if c.status_code != 200:
        print(f"❌ طلب التجربة فشل: {status_message(c.status_code)}")
        return 1
    print("✅ رد الموديل:", c.json()["choices"][0]["message"]["content"].strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
