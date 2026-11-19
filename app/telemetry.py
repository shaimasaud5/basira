"""مراقبة الاستخدام والأداء: أرقام وأحداث فقط. لا نخزّن نص العقد ولا رسائل المحادثة ولا عنوان IP.

الزائر يُعرَّف بمعرّف مجهول = هاش (ملح يومي سري + IP + المتصفح). الـIP نفسه ما يُحفظ أبدًا،
والمعرّف يتغيّر كل يوم، فما نقدر نربط زائر اليوم بزائر أمس ولا نعرف مين هو.
التخزين: SQLite محلي (TELEMETRY_DB). على الخطة المجانية في Render يتصفّر مع كل نشر؛ للحفظ الدائم نبدّل التخزين لاحقًا.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = os.environ.get("TELEMETRY_DB", str(Path(__file__).resolve().parents[1] / "data" / "telemetry.db"))
_SECRET = os.environ.get("TELEMETRY_SECRET") or secrets.token_hex(16)
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL, day TEXT NOT NULL, visitor TEXT NOT NULL,
  kind TEXT NOT NULL, method TEXT, path TEXT, status INTEGER, ms INTEGER, meta TEXT
);
CREATE INDEX IF NOT EXISTS ev_day ON events(day);
CREATE INDEX IF NOT EXISTS ev_visitor ON events(visitor, ts);
"""

LABELS = {
    ("GET", "/"): "فتح الصفحة",
    ("POST", "/contract/preview"): "رفع عقد",
    ("POST", "/contract/redact"): "إخفاء بيانات عقد تجريبي",
    ("POST", "/analyze"): "طلب تحليل",
    ("POST", "/chat"): "رسالة للمساعد",
}


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.executescript(SCHEMA)
    return _conn


def reset(path: str | None = None) -> None:
    """للاختبارات: يغلق الاتصال الحالي (ويغيّر المسار لو أُعطي)."""
    global _conn, DB_PATH
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        if path:
            DB_PATH = path


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def visitor_id(ip: str, user_agent: str, ts: float | None = None) -> str:
    day = _day(ts or time.time())
    salt = hashlib.sha256(f"{_SECRET}:{day}".encode()).hexdigest()
    return hashlib.sha256(f"{salt}:{ip}:{user_agent}".encode()).hexdigest()[:10]


def describe_client(user_agent: str) -> dict:
    ua = user_agent or ""
    low = ua.lower()
    device = "جوال" if ("mobi" in low or "iphone" in low or "android" in low) else "لاب توب/كمبيوتر"
    if "edg/" in low:
        browser = "Edge"
    elif "chrome" in low and "safari" in low and "edg/" not in low:
        browser = "Chrome"
    elif "safari" in low:
        browser = "Safari"
    elif "firefox" in low:
        browser = "Firefox"
    else:
        browser = "غير معروف"
    return {"device": device, "browser": browser}


def source_of(referer: str, utm: str) -> str:
    if utm:
        return utm[:40]
    try:
        host = urlparse(referer or "").netloc
    except ValueError:
        host = ""
    return host[:60] or "مباشر"


def record(kind: str, visitor: str, method: str = "", path: str = "", status: int | None = None,
           ms: int | None = None, meta: dict | None = None) -> None:
    """ما يرمي أي خطأ أبدًا: المراقبة ما تكسر الموقع."""
    try:
        ts = time.time()
        with _lock:
            _db().execute(
                "INSERT INTO events (ts, day, visitor, kind, method, path, status, ms, meta) VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, _day(ts), visitor, kind, method, path, status, ms, json.dumps(meta or {}, ensure_ascii=False)),
            )
            _db().commit()
    except Exception:  # noqa: BLE001
        pass


def _rows(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        cur = _db().execute(sql, args)
        return cur.fetchall()


def _pct(values: list[int], q: float) -> int | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def summary(days: int = 7) -> dict:
    since = _day(time.time() - (days - 1) * 86400)
    ev = _rows("SELECT ts, day, visitor, kind, method, path, status, ms, meta FROM events WHERE day >= ? ORDER BY ts", (since,))
    req = [e for e in ev if e[3] == "req"]
    visitors_by_day: dict[str, set] = {}
    for e in req:
        visitors_by_day.setdefault(e[1], set()).add(e[2])
    analyses = [e for e in req if e[4] == "POST" and e[5] == "/analyze"]
    chats = [e for e in req if e[4] == "POST" and e[5] == "/chat"]
    previews = [e for e in req if e[4] == "POST" and e[5] == "/contract/preview"]
    views = [e for e in req if e[4] == "GET" and e[5] == "/"]
    ok = [e for e in analyses if (e[6] or 0) < 400]
    errors = [e for e in req if (e[6] or 0) >= 400]
    llm = [e for e in ev if e[3] == "llm"]
    busy = [e for e in llm if (e[6] or 0) == 429]
    now = time.time()
    hourly = [0] * 24
    for e in req:
        if e[0] >= now - 24 * 3600:
            hourly[23 - int((now - e[0]) // 3600)] += 1

    def top(field: str, n: int = 6) -> list[list]:
        counts: dict[str, int] = {}
        seen: set = set()
        for e in views:
            meta = json.loads(e[8] or "{}")
            key = (e[2], meta.get(field, ""))
            if key in seen or not meta.get(field):
                continue
            seen.add(key)
            counts[meta[field]] = counts.get(meta[field], 0) + 1
        return [[k, v] for k, v in sorted(counts.items(), key=lambda x: -x[1])[:n]]

    ms_ok = [e[7] for e in ok if e[7] is not None]
    keys_used: dict[str, int] = {}
    for e in llm:
        if (e[6] or 0) == 200:
            k = str(json.loads(e[8] or "{}").get("key", "?"))
            keys_used[k] = keys_used.get(k, 0) + 1
    return {
        "days": days,
        "visitors_total": len({e[2] for e in req}),
        "identified": len({(e[1], e[2]) for e in ev if e[3] == "identity"}),
        "visitors_by_day": {d: len(v) for d, v in sorted(visitors_by_day.items())},
        "page_views": len(views),
        "uploads": len(previews),
        "analyses": len(analyses), "analyses_ok": len(ok), "analyses_failed": len(analyses) - len(ok),
        "analysis_ms": {"p50": _pct(ms_ok, 0.5), "p95": _pct(ms_ok, 0.95), "max": max(ms_ok) if ms_ok else None},
        "chats": len(chats),
        "errors": len(errors),
        "llm_calls": len(llm), "llm_rate_limited": len(busy), "llm_keys_used": keys_used,
        "hourly_requests": hourly,
        "top_countries": top("country"), "top_devices": top("device"), "top_sources": top("source"),
        "recent_errors": [{"time": e[0], "path": e[5], "status": e[6]} for e in errors[-8:]][::-1],
    }


def visitors(limit: int = 60) -> list[dict]:
    names = {(d, vid): json.loads(meta or "{}") for d, vid, meta in
             _rows("SELECT day, visitor, meta FROM events WHERE kind = 'identity' ORDER BY ts")}
    rows = _rows("SELECT ts, day, visitor, kind, method, path, status, ms, meta FROM events WHERE kind = 'req' ORDER BY ts DESC LIMIT 4000")
    out: dict[tuple, dict] = {}
    for ts, day, vid, _k, method, path, status, ms, meta in rows:
        v = out.setdefault((day, vid), {"id": vid, "day": day, "first": ts, "last": ts, "views": 0, "uploads": 0, "analyses": 0,
                                         "chats": 0, "errors": 0, "country": "", "device": "", "source": "",
                                         "name": " ".join(filter(None, [names.get((day, vid), {}).get("first"), names.get((day, vid), {}).get("last")]))})
        v["first"], v["last"] = min(v["first"], ts), max(v["last"], ts)
        if (status or 0) >= 400:
            v["errors"] += 1
        if method == "GET" and path == "/":
            v["views"] += 1
            m = json.loads(meta or "{}")
            for f in ("country", "device", "source"):
                v[f] = v[f] or m.get(f, "")
        elif path == "/contract/preview":
            v["uploads"] += 1
        elif path == "/analyze":
            v["analyses"] += 1
        elif path == "/chat":
            v["chats"] += 1
    return sorted(out.values(), key=lambda x: -x["last"])[:limit]


def journey(vid: str) -> list[dict]:
    rows = _rows("SELECT ts, kind, method, path, status, ms, meta FROM events WHERE visitor = ? ORDER BY ts", (vid,))
    steps = []
    for ts, kind, method, path, status, ms, meta in rows:
        if kind == "identity":
            m = json.loads(meta or "{}")
            label = "عرّف بنفسه: " + " ".join(filter(None, [m.get("first"), m.get("last")]))
        else:
            label = LABELS.get((method, path)) if kind == "req" else ("اتصال بالموديل" if kind == "llm" else kind)
        if not label:
            continue
        steps.append({"time": ts, "label": label, "status": status, "ms": ms, "meta": json.loads(meta or "{}")})
    return steps
