"""سيرفر FastAPI: يربط التحقق والحسابات والتقرير."""
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.ai_risks import suggest_risks
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
DATA_DIR = BASE_DIR.parent / "data"
DEMO_TITLES = {
    "01_complete.txt": "عقد كامل البنود",
    "02_missing_clauses.txt": "عقد ناقص بنود",
    "03_tricky_clauses.txt": "عقد فيه بنود مخادعة",
}

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


app.mount("/static", RevalidatingStaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/demo-contracts")
def demo_contracts():
    """العقود التجريبية للعرض (نصوص وهمية كتبناها، مو بيانات مستخدمين)."""
    files = sorted((DATA_DIR / "demo_contracts").glob("*.txt"))
    return [{"name": DEMO_TITLES.get(f.name, f.stem), "text": f.read_text(encoding="utf-8")} for f in files]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(RateLimited)
async def rate_limited(request: Request, exc: RateLimited):
    return JSONResponse(status_code=429, content={"errors": [str(exc)]})


@app.post("/contract/preview", dependencies=[Depends(limit_extract)])
def contract_preview(file: UploadFile = File(...)):
    """يستخرج نص العقد من الملف ويخفي الهوية ويرجّع النص للمعاينة. ما نحفظ الملف ولا نسجّل محتواه."""
    try:
        text = read_contract(file.filename or "", file.file.read(MAX_FILE_BYTES + 1))
    except FileError as e:
        return JSONResponse(status_code=422, content={"errors": [str(e)]})
    clean, counts = redact(text)
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
    try:
        return answer(payload)
    except LLMError as e:
        return JSONResponse(status_code=503, content={"errors": [str(e)]})


@app.post("/analyze", dependencies=[Depends(limit_analyze)])
def analyze(project: ProjectInput):
    # الخصوصية: نسجّل الحالة والطول فقط، ولا نسجّل نص العقد أبداً
    logger.info("analyze: contract_len=%d", len(project.contract_text or ""))

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
        try:
            facts = extract_contract(clean_text)
        except LLMError as e:
            # نكمل بالتقرير المالي ونبلّغ المستخدم، بدل ما نضيّع كل شي
            warnings.append(f"تعذّر تحليل العقد: {e}")

    effective = effective_project(project, facts) if facts else project
    cards = financial_cards(effective)
    missing = missing_info(effective)
    if facts:
        cards += contract_cards(project, facts)
        missing += contract_missing(facts)

    ai_cards: list = []
    if not warnings:  # لو الاتصال بالموديل فشل قبل شوي، ما نكرر المحاولة
        try:
            ai_cards, _ = suggest_risks(effective, clean_text, facts, [c.title for c in cards])
        except LLMError as e:
            warnings.append(f"تعذّر توليد الاقتراحات الإضافية: {e}")
    return build_report(cards, missing, notes + warnings, ai_cards, build_metrics(effective, facts))
