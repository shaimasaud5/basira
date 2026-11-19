"""مراقبة الاستخدام والأداء: أرقام وأحداث فقط. لا نخزّن نص العقد ولا رسائل المحادثة ولا عنوان IP.

الزائر يُعرَّف بمعرّف مجهول = هاش (ملح يومي سري + IP + المتصفح). الـIP نفسه ما يُحفظ أبدًا،
والمعرّف يتغيّر كل يوم، فما نقدر نربط زائر اليوم بزائر أمس ولا نعرف مين هو.
التخزين: لو DATABASE_URL موجود (Postgres مثل Neon) تُحفظ البيانات دائمًا ولا تُحذف أبدًا.
بدونه نستخدم SQLite محلي (TELEMETRY_DB) وعلى الخطة المجانية في Render يتصفّر مع كل نشر.
"""
import contextvars
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


DATABASE_URL = os.environ.get("DATABASE_URL", "")
PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id BIGSERIAL PRIMARY KEY,
  ts DOUBLE PRECISION NOT NULL, day TEXT NOT NULL, visitor TEXT NOT NULL,
  kind TEXT NOT NULL, method TEXT, path TEXT, status INTEGER, ms INTEGER, meta TEXT
);
CREATE INDEX IF NOT EXISTS ev_day ON events(day);
CREATE INDEX IF NOT EXISTS ev_visitor ON events(visitor, ts);
"""


def using_postgres() -> bool:
    return bool(DATABASE_URL)


def _db():
    """اتصال واحد مشترك (يُنشأ عند أول استخدام). Postgres لو DATABASE_URL موجود، وإلا SQLite."""
    global _conn
    if _conn is None:
        if DATABASE_URL:
            import psycopg  # noqa: PLC0415
            _conn = psycopg.connect(DATABASE_URL, autocommit=True, connect_timeout=8)
            with _conn.cursor() as cur:
                cur.execute(PG_SCHEMA)
        else:
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn.executescript(SCHEMA)
    return _conn


def _run(sql: str, args: tuple = (), fetch: bool = False):
    """ينفّذ استعلامًا على القاعدة المختارة. لو انقطع اتصال Postgres نعيد الاتصال مرة وحدة."""
    global _conn
    for attempt in (0, 1):
        try:
            conn = _db()
            if DATABASE_URL:
                with conn.cursor() as cur:
                    cur.execute(sql.replace("?", "%s"), args)
                    return cur.fetchall() if fetch else None
            cur = conn.execute(sql, args)
            if fetch:
                return cur.fetchall()
            conn.commit()
            return None
        except Exception:  # noqa: BLE001
            if not DATABASE_URL or attempt:
                raise
            try:
                _conn.close()
            except Exception:  # noqa: BLE001
                pass
            _conn = None


# ---- سياق الطلب الحالي: يربط أحداث الموديل والملاحظات بالزائر بدون ما نمرّرها يدويًا ----
_visitor_var: contextvars.ContextVar[str] = contextvars.ContextVar("visitor", default="-")
_notes_var: contextvars.ContextVar[dict | None] = contextvars.ContextVar("notes", default=None)


def bind(visitor: str) -> dict:
    """يربط الطلب الحالي بزائر ويرجّع قاموس الملاحظات (يُحفظ مع حدث الطلب)."""
    notes: dict = {}
    _visitor_var.set(visitor)
    _notes_var.set(notes)
    return notes


def current_visitor() -> str:
    return _visitor_var.get()


def note(**kv) -> None:
    """يضيف ملاحظات (أرقام وكلمات قصيرة فقط، مو نصوص المستخدم) على الطلب الحالي."""
    notes = _notes_var.get()
    if notes is not None:
        notes.update(kv)


def reset(path: str | None = None) -> None:
    """للاختبارات: يغلق الاتصال الحالي (ويغيّر المسار لو أُعطي)."""
    global _conn, DB_PATH
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:  # noqa: BLE001
                pass
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
            _run("INSERT INTO events (ts, day, visitor, kind, method, path, status, ms, meta) VALUES (?,?,?,?,?,?,?,?,?)",
                 (ts, _day(ts), visitor, kind, method, path, status, ms, json.dumps(meta or {}, ensure_ascii=False)))
    except Exception:  # noqa: BLE001
        pass


def _rows(sql: str, args: tuple = ()) -> list:
    with _lock:
        return _run(sql, args, fetch=True) or []


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
    rows = _rows("SELECT ts, day, visitor, kind, method, path, status, ms, meta FROM events WHERE kind = 'req' ORDER BY ts DESC LIMIT 50000")
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


# ---------- تقارير مفصّلة للوحة ----------
def _name_of(meta: dict) -> str:
    return " ".join(filter(None, [meta.get("first"), meta.get("last")])).strip()


def _names_by_visitor() -> dict[tuple, str]:
    out: dict[tuple, str] = {}
    for day, vid, meta in _rows("SELECT day, visitor, meta FROM events WHERE kind = 'identity' ORDER BY ts"):
        n = _name_of(json.loads(meta or "{}"))
        if n:
            out[(day, vid)] = n
    return out


def _step_text(method: str, path: str, status, meta: dict) -> str:
    """وصف مفصّل بالعربي للخطوة (من الأرقام فقط، بدون أي نص للمستخدم)."""
    if method == "GET" and path == "/":
        bits = [meta.get("device"), meta.get("browser"), meta.get("country"), ("من " + meta["source"]) if meta.get("source") not in (None, "", "مباشر") else "دخول مباشر"]
        return "فتح الصفحة" + (" (" + "، ".join(b for b in bits if b) + ")" if any(bits) else "")
    if path == "/contract/preview":
        if meta.get("error"):
            return f"حاول يرفع عقد وفشل: {meta['error']}"
        bits = [f"ملف {meta['ext']}" if meta.get("ext") else "", f"{meta['size_kb']} ك.ب" if meta.get("size_kb") is not None else "",
                f"{meta['chars']} حرف" if meta.get("chars") is not None else "",
                f"أُخفي {meta['redacted']} بيان شخصي" if meta.get("redacted") else ""]
        return "رفع عقد (" + "، ".join(b for b in bits if b) + ")"
    if path == "/analyze":
        if (status or 0) >= 400:
            return "طلب تحليل وفشل" + (f": {meta['error']}" if meta.get("error") else "")
        bits = [meta.get("activity"), meta.get("city"), f"عقد {meta['lease_months']} شهر" if meta.get("lease_months") else "",
                f"الإيجار {meta['rent_ratio']}% من الإيراد" if meta.get("rent_ratio") is not None else "",
                f"قرأ عقد ({meta['contract_chars']} حرف)" if meta.get("contract_chars") else "بدون عقد",
                f"{meta['cards']} بطاقة" if meta.get("cards") is not None else "",
                f"عالية {meta['high']}" if meta.get("high") else "", f"تحذيرات {meta['warnings']}" if meta.get("warnings") else ""]
        return "طلب تحليل: " + "، ".join(b for b in bits if b)
    if path == "/chat":
        bits = [f"سؤال {meta['question_len']} حرف" if meta.get("question_len") is not None else "",
                "قبل التحليل (وضع الدليل)" if meta.get("mode") == "guide" else ("عن تقريره" if meta.get("mode") else ""),
                f"رد {meta['answer_len']} حرف" if meta.get("answer_len") else ""]
        return "رسالة للمساعد: " + "، ".join(b for b in bits if b) + (" (فشل)" if (status or 0) >= 400 else "")
    if path == "/contract/redact":
        return "إخفاء بيانات عقد تجريبي"
    return ""


def _llm_text(status, ms, meta: dict) -> str:
    key = meta.get("key", "?")
    what = meta.get("what", "")
    state = {200: "نجح", 429: "رفضه Groq (زحمة/حد الطلبات)", 401: "المفتاح مرفوض"}.get(status or 0, f"فشل ({status})")
    return f"الموديل — مفتاح {key}{' · ' + what if what else ''}: {state}"


def journey_steps(rows) -> list[dict]:
    steps = []
    for ts, kind, method, path, status, ms, meta in rows:
        m = json.loads(meta or "{}")
        if kind == "identity":
            label, tone = "عرّف بنفسه: " + _name_of(m), "info"
        elif kind == "req":
            label, tone = _step_text(method, path, status, m), ("bad" if (status or 0) >= 400 else "")
            if not label:
                continue
        elif kind == "llm":
            label, tone = _llm_text(status, ms, m), ("bad" if status != 200 else "model")
        else:
            continue
        steps.append({"time": ts, "label": label, "status": status, "ms": ms, "tone": tone})
    return steps


def person_journey(person: str) -> list[dict]:
    """كل خطوات شخص (بالاسم) عبر كل الأيام."""
    vids = [k for k, n in _names_by_visitor().items() if n == person]
    steps: list[dict] = []
    for day, vid in vids:
        rows = _rows("SELECT ts, kind, method, path, status, ms, meta FROM events WHERE visitor = ? AND day = ? ORDER BY ts", (vid, day))
        steps += journey_steps(rows)
    return sorted(steps, key=lambda x: x["time"])


def visitor_journey(vid: str) -> list[dict]:
    return journey_steps(_rows("SELECT ts, kind, method, path, status, ms, meta FROM events WHERE visitor = ? ORDER BY ts", (vid,)))


def people(limit: int = 200) -> list[dict]:
    """كل شخص عرّف بنفسه: مجموع استخدامه عبر الأيام."""
    names = _names_by_visitor()
    by_vid = {}
    for (day, vid), n in names.items():
        by_vid.setdefault(vid, {})[day] = n
    rows = _rows("SELECT ts, day, visitor, kind, method, path, status, ms, meta FROM events WHERE kind IN ('req','llm') ORDER BY ts")
    out: dict[str, dict] = {}
    for ts, day, vid, kind, method, path, status, ms, meta in rows:
        n = names.get((day, vid))
        if not n:
            continue
        p = out.setdefault(n, {"name": n, "first": ts, "last": ts, "days": set(), "views": 0, "uploads": 0, "analyses": 0, "analyses_ok": 0,
                               "chats": 0, "errors": 0, "model_blocked": 0, "ms_total": 0, "device": "", "country": ""})
        p["first"], p["last"] = min(p["first"], ts), max(p["last"], ts)
        p["days"].add(day)
        m = json.loads(meta or "{}") if meta else {}
        if kind == "llm":
            if status != 200:
                p["model_blocked"] += 1
            continue
        if (status or 0) >= 400:
            p["errors"] += 1
        if method == "GET" and path == "/":
            p["views"] += 1
            p["device"], p["country"] = p["device"] or m.get("device", ""), p["country"] or m.get("country", "")
        elif path == "/contract/preview":
            p["uploads"] += 1
        elif path == "/analyze":
            p["analyses"] += 1
            if (status or 0) < 400:
                p["analyses_ok"] += 1
                p["ms_total"] += ms or 0
        elif path == "/chat":
            p["chats"] += 1
    res = []
    for p in out.values():
        p["days"] = len(p["days"])
        p["avg_analysis_ms"] = int(p["ms_total"] / p["analyses_ok"]) if p["analyses_ok"] else None
        del p["ms_total"]
        res.append(p)
    return sorted(res, key=lambda x: -x["last"])[:limit]


def health(days: int = 7) -> dict:
    """صحة النظام والموديل: أداء كل مسار، توزيع حالات الموديل، المفاتيح، ومن تأثّر."""
    since = _day(time.time() - (days - 1) * 86400)
    ev = _rows("SELECT ts, day, visitor, kind, method, path, status, ms, meta FROM events WHERE day >= ? AND kind IN ('req','llm') ORDER BY ts", (since,))
    names = _names_by_visitor()
    endpoints: dict[str, dict] = {}
    for ts, day, vid, kind, method, path, status, ms, meta in ev:
        if kind != "req" or (method, path) not in LABELS:
            continue
        e = endpoints.setdefault(f"{method} {path}", {"label": LABELS[(method, path)], "n": 0, "err": 0, "ms": []})
        e["n"] += 1
        e["err"] += (status or 0) >= 400
        if ms is not None and (status or 0) < 400:
            e["ms"].append(ms)
    endpoint_rows = [{"label": e["label"], "n": e["n"], "err": e["err"], "p50": _pct(e["ms"], .5), "p95": _pct(e["ms"], .95), "max": max(e["ms"]) if e["ms"] else None}
                     for e in endpoints.values()]
    keys: dict[str, dict] = {}
    blocked_people: dict[str, int] = {}
    events = []
    for ts, day, vid, kind, method, path, status, ms, meta in ev:
        if kind != "llm":
            continue
        m = json.loads(meta or "{}")
        k = keys.setdefault(str(m.get("key", "?")), {"key": str(m.get("key", "?")), "ok": 0, "limited": 0, "rejected": 0, "other": 0, "ms": []})
        if status == 200:
            k["ok"] += 1
            k["ms"].append(ms or 0)
        elif status == 429:
            k["limited"] += 1
        elif status == 401:
            k["rejected"] += 1
        else:
            k["other"] += 1
        if status != 200:
            who = names.get((day, vid)) or ("زائر مجهول " + vid if vid != "-" else "—")
            blocked_people[who] = blocked_people.get(who, 0) + 1
            events.append({"time": ts, "who": who, "key": str(m.get("key", "?")), "status": status, "what": m.get("what", "")})
    total = sum(k["ok"] + k["limited"] + k["rejected"] + k["other"] for k in keys.values())
    bad = sum(k["limited"] + k["rejected"] + k["other"] for k in keys.values())
    return {
        "days": days, "endpoints": endpoint_rows,
        "llm_total": total, "llm_bad": bad,
        "keys": [{**{x: v for x, v in k.items() if x != "ms"}, "avg_ms": int(sum(k["ms"]) / len(k["ms"])) if k["ms"] else None}
                 for k in sorted(keys.values(), key=lambda x: x["key"])],
        "blocked_people": sorted(blocked_people.items(), key=lambda x: -x[1])[:15],
        "blocked_events": events[-20:][::-1],
    }


def funnel(days: int = 7) -> list[list]:
    """قمع الاستخدام: كم زائر وصل لكل مرحلة."""
    since = _day(time.time() - (days - 1) * 86400)
    rows = _rows("SELECT day, visitor, method, path, status FROM events WHERE kind = 'req' AND day >= ?", (since,))
    steps = {"فتح الصفحة": set(), "رفع عقد": set(), "طلب تحليل": set(), "تحليل ناجح": set(), "سأل المساعد": set()}
    for day, vid, method, path, status in rows:
        key = (day, vid)
        if method == "GET" and path == "/":
            steps["فتح الصفحة"].add(key)
        elif path == "/contract/preview":
            steps["رفع عقد"].add(key)
        elif path == "/analyze":
            steps["طلب تحليل"].add(key)
            if (status or 0) < 400:
                steps["تحليل ناجح"].add(key)
        elif path == "/chat":
            steps["سأل المساعد"].add(key)
    return [[k, len(v)] for k, v in steps.items()]


def export_rows() -> list[list]:
    """كل الأحداث للتصدير (CSV). أرقام وكلمات قصيرة فقط."""
    names = _names_by_visitor()
    rows = _rows("SELECT ts, day, visitor, kind, method, path, status, ms, meta FROM events ORDER BY ts")
    out = [["الوقت (UTC)", "اليوم", "الاسم", "الزائر", "النوع", "الطلب", "الحالة", "الزمن (مللي)", "وصف"]]
    for ts, day, vid, kind, method, path, status, ms, meta in rows:
        m = json.loads(meta or "{}")
        text = _step_text(method, path, status, m) if kind == "req" else (_llm_text(status, ms, m) if kind == "llm" else _name_of(m))
        out.append([datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), day, names.get((day, vid), ""), vid, kind,
                    f"{method} {path}".strip(), status if status is not None else "", ms if ms is not None else "", text])
    return out


def wipe() -> int:
    """يمسح كل أحداث المراقبة (تصفير اللوحة). يرجّع عدد ما انمسح."""
    with _lock:
        n = (_run("SELECT COUNT(*) FROM events", (), fetch=True) or [[0]])[0][0]
        _run("DELETE FROM events")
    return int(n)
