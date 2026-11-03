"""حد طلبات لكل زائر (في الذاكرة)، يحمي رصيد المفتاح بعد النشر.

الأرقام قرار منتج. خلف Render نشغّل uvicorn بـ --proxy-headers عشان يقرأ عنوان الزائر الحقيقي.
الحد في الذاكرة: يتصفّر عند إعادة تشغيل السيرفر، ولو شغّلنا أكثر من نسخة يصير لكل نسخة عدّاد.
"""
import time
from collections import defaultdict, deque

from fastapi import Request

ANALYZE_PER_MINUTE = 10
CHAT_PER_MINUTE = 30
EXTRACT_PER_MINUTE = 10
WINDOW_SECONDS = 60


class RateLimited(Exception):
    """تجاوز الحد. الرسالة عربية وجاهزة للعرض."""


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = WINDOW_SECONDS, clock=time.monotonic):
        self.max_requests = max_requests
        self.window = window_seconds
        self.clock = clock
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = self.clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.max_requests:
            raise RateLimited("طلبات كثيرة بوقت قصير. انتظر دقيقة وجرّب مرة ثانية.")
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


analyze_limiter = RateLimiter(ANALYZE_PER_MINUTE)
chat_limiter = RateLimiter(CHAT_PER_MINUTE)
extract_limiter = RateLimiter(EXTRACT_PER_MINUTE)


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def limit_analyze(request: Request) -> None:
    analyze_limiter.check(_client(request))


def limit_chat(request: Request) -> None:
    chat_limiter.check(_client(request))


def limit_extract(request: Request) -> None:
    extract_limiter.check(_client(request))
