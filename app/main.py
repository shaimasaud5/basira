"""سيرفر FastAPI: يربط التحقق والحسابات والتقرير."""
import contextvars
import logging
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from app import llm, telemetry
from app.ai_risks import accept_suggestions, request_suggestions
from app.chat import ChatInput, answer
from app.contract import extract_contract, looks_like_injection
from app.contract_cards import contract_cards, contract_missing, effective_project
from app.llm import LLMError
from app.files import MAX_FILE_BYTES, FileError, read_contract
from app.metrics import build_metrics
from app.ratelimit import RateLimited, limit_analyze, limit_chat, limit_extract
from app.redact import redact
from app.report import build_report, financial_cards, missing_info
from app.schemas import ProjectInput, RedactInput

logger = logging.getLogger("app")

BASE_DIR = Path(__file__).parent

app = FastAPI(title="بصيرة")


@app.exception_handler(RequestValidationError)
async def arabic_validation_errors(request: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        if err["type"] == "value_error":
            msg = err["msg"].removeprefix("Value error, ")
        elif err["type"] == "missing" and "file" in err.get("loc", ()):
            msg = "اختر ملف العقد أول."
        else:
            msg = "المدخلات غير صالحة. تأكد من تعبئة الحقول بالشكل الصحيح."
        if msg not in messages:
            messages.append(msg)
    return JSONResponse(status_code=422, content={"errors": messages})


class RevalidatingStaticFiles(StaticFiles):
    """ملفات الواجهة: المتصفح يتأكد من النسخة كل مرة (no-cache مع ETag)، فيظهر أي تعديل بمجرد التحديث."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


SKIP_TRACKING = ("/static", "/admin", "/health", "/favicon.ico")


@app.middleware("http")
async def track_usage(request: Request, call_next):
    """أرقام فقط: المسار والحالة والزمن ومعرّف مجهول يومي. لا IP ولا محتوى."""
    path = request.url.path
    if path.startswith(SKIP_TRACKING):
        return await call_next(request)
    started = time.perf_counter()
    ua = request.headers.get("user-agent", "")
    vid = telemetry.visitor_id(request.client.host if request.client else "", ua)
    meta = telemetry.bind(vid)  # الموديل والمعالجات تضيف ملاحظاتها هنا (أرقام فقط)
    response = await call_next(request)
    ms = int((time.perf_counter() - started) * 1000)
    if request.method == "GET" and path == "/":
        meta.update({**telemetry.describe_client(ua), "country": request.headers.get("cf-ipcountry", ""),
                "source": telemetry.source_of(request.headers.get("referer", ""), request.query_params.get("utm_source", ""))})
    telemetry.record("req", vid, request.method, path, response.status_code, ms, meta)
    return response


# ---- لوحة المراقبة (محمية بكلمة سر ADMIN_PASSWORD؛ بدونها تكون معطّلة) ----
_basic = HTTPBasic(auto_error=False)


def require_admin(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise HTTPException(status_code=404)
    if credentials is None or not secrets.compare_digest(credentials.password.encode(), password.encode()):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": 'Basic realm="admin"'})


@app.get("/admin", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_page():
    return FileResponse(BASE_DIR / "admin" / "admin.html", headers={"Cache-Control": "no-store"})


@app.get("/admin/app.js", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_js():
    return FileResponse(BASE_DIR / "admin" / "app.js", media_type="text/javascript", headers={"Cache-Control": "no-store"})


@app.get("/admin/api/summary", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_summary(days: int = 7):
    return telemetry.summary(max(1, min(days, 3650)))


@app.get("/admin/api/visitors", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_visitors(limit: int = 60):
    return telemetry.visitors(max(1, min(limit, 200)))


@app.get("/admin/api/visitor/{vid}", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_visitor(vid: str):
    return telemetry.visitor_journey(vid[:32])


@app.get("/admin/api/overview", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_overview(days: int = 7):
    days = max(1, min(days, 3650))
    return {"summary": telemetry.summary(days), "health": telemetry.health(days), "funnel": telemetry.funnel(days),
            "keys_now": llm.key_status(), "storage": "postgres" if telemetry.using_postgres() else "sqlite"}


@app.get("/admin/api/people", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_people():
    return telemetry.people()


@app.get("/admin/api/person", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_person(name: str):
    return telemetry.person_journey(name[:130])


@app.get("/admin/api/export.csv", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_export():
    import csv, io
    buf = io.StringIO()
    csv.writer(buf).writerows(telemetry.export_rows())
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="basira-usage.csv"'})


app.mount("/static", RevalidatingStaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Safari وبعض المتصفحات تطلب /favicon.ico مباشرة ولا تعتمد على SVG
    return FileResponse(BASE_DIR / "static" / "icons" / "favicon-32.png", media_type="image/png",
                        headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(RateLimited)
async def rate_limited(request: Request, exc: RateLimited):
    return JSONResponse(status_code=429, content={"errors": [str(exc)]})


@app.post("/contract/preview", dependencies=[Depends(limit_extract)])
def contract_preview(file: UploadFile = File(...)):
    """يستخرج نص العقد من الملف ويخفي الهوية ويرجّع النص للمعاينة. ما نحفظ الملف ولا نسجّل محتواه."""
    raw = file.file.read(MAX_FILE_BYTES + 1)
    telemetry.note(ext=(file.filename or "").rsplit(".", 1)[-1].lower()[:5], size_kb=round(len(raw) / 1024))
    try:
        text = read_contract(file.filename or "", raw)
    except FileError as e:
        telemetry.note(error=str(e)[:120])
        return JSONResponse(status_code=422, content={"errors": [str(e)]})
    clean, counts = redact(text)
    telemetry.note(chars=len(clean), redacted=sum(v for v in counts.values() if isinstance(v, int)))
    logger.info("preview: chars=%d redacted=%s", len(text), counts)  # أطوال وأعداد فقط
    return {"text": clean, "chars": len(clean), "redacted": counts}


@app.post("/contract/redact", dependencies=[Depends(limit_extract)])
def contract_redact(payload: RedactInput):
    """يخفي الهوية من نص جاهز ويرجّعه للمعاينة. كود بحت، بدون AI ولا حفظ."""
    clean, counts = redact(payload.text)
    logger.info("redact: chars=%d redacted=%s", len(payload.text), counts)
    return {"text": clean, "chars": len(clean), "redacted": counts}


@app.post("/chat")
def chat(payload: ChatInput, _: None = Depends(limit_chat)):
    # الخصوصية: ما نسجّل السؤال ولا الرد ولا العقد، فقط الأطوال
    logger.info("chat: question_len=%d history=%d", len(payload.question), len(payload.history))
    telemetry.note(question_len=len(payload.question), history=len(payload.history),
                   mode="report" if payload.has_report else "guide")
    llm._purpose.set("محادثة")
    try:
        result = answer(payload)
        telemetry.note(answer_len=len(result.get("answer", "")))
        return result
    except LLMError as e:
        telemetry.note(error="الموديل غير متاح")
        return JSONResponse(status_code=503, content={"errors": [str(e)]})


@app.post("/analyze", dependencies=[Depends(limit_analyze)])
def analyze(project: ProjectInput, request: Request):
    # الخصوصية: نسجّل الحالة والطول فقط، ولا نسجّل نص العقد أبداً
    if project.first_name or project.last_name:
        # الاسم يروح للوحة المراقبة فقط (مو للسجلات)، ومربوط بمعرّف الزائر المجهول
        ua = request.headers.get("user-agent", "")
        vid = telemetry.visitor_id(request.client.host if request.client else "", ua)
        telemetry.record("identity", vid, meta={"first": project.first_name or "", "last": project.last_name or ""})
    logger.info("analyze: contract_len=%d", len(project.contract_text or ""))
    llm._purpose.set("تحليل")

    facts = None
    clean_text = None
    notes: list[str] = []      # تنبيهات عن النص نفسه
    warnings: list[str] = []   # أخطاء اتصال بالموديل
    if project.contract_text:
        clean_text, redacted = redact(project.contract_text)
        logger.info("analyze: redacted=%s", redacted)  # أعداد فقط، بدون محتوى
        if looks_like_injection(clean_text):
            notes.append(
                "في النص عبارة تبدو كتعليمات موجّهة للنظام (مثل «تجاهل...»). "
                "تجاهلناها، وراجع هذا البند في عقدك بنفسك."
            )
        # الطلبان للموديل (استخراج بنود العقد + اقتراحات المخاطر) مستقلان، فنشغّلهم بالتوازي عشان نوفّر الوقت
        def _in_ctx(purpose, fn, *args):
            ctx = contextvars.copy_context()  # يحافظ على ربط الزائر داخل خيوط الموديل
            def run():
                llm._purpose.set(purpose)
                return fn(*args)
            return ctx.run, run
        with ThreadPoolExecutor(max_workers=2) as pool:
            runner, job = _in_ctx("استخراج بنود العقد", extract_contract, clean_text)
            extraction = pool.submit(runner, job)
            runner, job = _in_ctx("اقتراحات المخاطر", request_suggestions, project, clean_text)
            suggestions = pool.submit(runner, job)
        suggestion_error: LLMError | None = None
        try:
            facts = extraction.result()
        except LLMError as e:
            # نكمل بالتقرير المالي ونبلّغ المستخدم، بدل ما نضيّع كل شي
            warnings.append(f"تعذّر تحليل العقد: {e}")
        try:
            raw_suggestions = suggestions.result()
        except LLMError as e:
            raw_suggestions, suggestion_error = None, e

    effective = effective_project(project, facts) if facts else project
    cards = financial_cards(effective)
    missing = missing_info(effective)
    if facts:
        cards += contract_cards(project, facts)
        missing += contract_missing(facts)

    ai_cards: list = []
    if clean_text is not None:
        if suggestion_error and not warnings:  # لو الاستخراج فشل قبل، ما نكرر التنبيه
            warnings.append(f"تعذّر توليد الاقتراحات الإضافية: {suggestion_error}")
        elif not warnings:
            ai_cards, _ = accept_suggestions(raw_suggestions, effective, clean_text, facts)
    elif not warnings:
        try:
            ai_cards, _ = accept_suggestions(request_suggestions(effective, None), effective, None, None)
        except LLMError as e:
            warnings.append(f"تعذّر توليد الاقتراحات الإضافية: {e}")
    report = build_report(cards, missing, notes + warnings, ai_cards, build_metrics(effective, facts))
    shown = report["top"] + report["more"]
    ratio = None
    if effective.monthly_rent and effective.monthly_revenue:
        ratio = round(effective.monthly_rent / effective.monthly_revenue * 100)
    telemetry.note(activity=project.activity[:40], city=project.city[:30], lease_months=effective.lease_months,
                   rent_ratio=ratio, contract_chars=len(clean_text or ""), cards=len(shown), ai_cards=len(ai_cards),
                   high=sum(1 for c in shown if c.severity == "high"), warnings=len(warnings),
                   titles=[c.title[:40] for c in shown[:6]])
    return report
