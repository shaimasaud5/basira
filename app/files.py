"""استخراج نص العقد من ملف مرفوع (PDF أو Word نصي). المعالجة في الذاكرة ولا نحفظ الملف.

الملف غير موثوق: نتأكد من نوعه الحقيقي (مو الامتداد بس)، ونحدد الحجم والصفحات،
ونفحص حجم ملف Word بعد فك الضغط قبل ما نفتحه.
الأرقام قرارات منتج/أمان، مو معلومات رسمية.

تنبيه عن PDF العربي: ملف PDF يخزّن النص بترتيب العرض (يسار لليمين)، فمكتبات الاستخراج
تزيح الأرقام وعلامات الترقيم عن أماكنها. نصلحها هنا بترتيب المقاطع حسب إحداثياتها.
جرّبنا الإصلاح على ملفات PDF من Chrome فقط؛ ملفات برامج ثانية (Word، Pages، سكانر) ممكن تتصرف مختلف،
ولهذا المستخدم يشوف النص المستخرج في المعاينة قبل الإرسال.
"""
import io
import re
import unicodedata
import zipfile

from docx import Document
from pypdf import PdfReader

from app.schemas import MAX_CONTRACT_CHARS

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 40
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MIN_TEXT_CHARS = 50  # أقل من هذا في PDF غالباً يعني صورة ممسوحة ضوئياً

UNSUPPORTED = "نوع الملف غير مدعوم. ارفع PDF أو Word (بصيغة docx)."


class FileError(ValueError):
    """مشكلة في الملف. الرسالة عربية وجاهزة للعرض."""


def _detect_kind(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf") and data.startswith(b"%PDF-"):
        return "pdf"
    if name.endswith(".docx") and data.startswith(b"PK\x03\x04"):
        return "docx"
    if name.endswith(".doc"):
        raise FileError("صيغة Word القديمة (doc) غير مدعومة. احفظه بصيغة docx أو PDF وارفعه.")
    raise FileError(UNSUPPORTED)


# ---------------- PDF: ترتيب النص العربي حسب الإحداثيات ----------------
_ARABIC_LETTER = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")
_NUMBER = re.compile(r"^[\d.,/:+\-\u0660-\u0669\u06F0-\u06F9]+$")
_PUNCTUATION_ONLY = re.compile(r"^[.,\u060c\u061b:\u061f!]+$")
_BRACKET_ONLY = re.compile(r"^[()\[\]{}<>]+$")
_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")

_DECIMAL_NEXT_GAP = 0.8   # الكسر العشري يبدأ مباشرة بعد النقطة (× حجم الخط)
_DECIMAL_PREV_GAP = 5.0   # والجزء الصحيح قبلها بمسافة معقولة (× حجم الخط)
_PUNCT_ATTACH_GAP = 0.6   # علامة ترقيم مستقلة أقرب من هالمسافة (× حجم الخط) تلتصق بالمقطع اللي جنبها


def _is_number(text: str) -> bool:
    return bool(_NUMBER.match(text)) and any(ch.isdigit() for ch in text)


def _glue_decimals(frags: list[list]) -> list[list]:
    """يلصق الرقم المقطّع ("7,500" + "." + "50") وهو بترتيب يسار←يمين. frags مرتبة بالـ x."""
    out: list[list] = []
    pending = False
    for i, frag in enumerate(frags):
        x, _y, text, size = frag
        stripped = text.strip()
        nxt = frags[i + 1] if i + 1 < len(frags) else None
        if (
            stripped in (".", ",") and out and _is_number(out[-1][2]) and nxt is not None
            and _is_number(nxt[2].strip()) and nxt[0] - x <= size * _DECIMAL_NEXT_GAP
            and x - out[-1][0] <= size * _DECIMAL_PREV_GAP
        ):
            out[-1][2] += stripped
            pending = True
        elif pending and _is_number(stripped):
            out[-1][2] += stripped
            pending = False
        else:
            pending = False
            out.append([x, frag[1], stripped if _is_number(stripped) else text, size])
    return out


def _attach_punctuation(frags: list[list]) -> list[list]:
    """علامة الترقيم المستقلة (مثل نقطة نهاية الجملة) تُلصق بآخر المقطع القريب منها."""
    words = [f for f in frags if not _PUNCTUATION_ONLY.match(f[2].strip())]
    leftovers = []
    for x, y, text, size in (f for f in frags if _PUNCTUATION_ONLY.match(f[2].strip())):
        near = min(words, key=lambda w: abs(w[0] - x), default=None)
        if near and abs(near[0] - x) <= size * _PUNCT_ATTACH_GAP:
            near[2] = near[2].rstrip() + text.strip()
        else:
            leftovers.append([x, y, text, size])
    return words + leftovers


def _line_text(fragments: list[tuple]) -> str:
    """fragments: (x, y, text, size) لسطر واحد."""
    joined = "".join(f[2] for f in fragments)
    arabic = len(_ARABIC_LETTER.findall(joined))
    rtl = arabic > 0 and arabic >= len(_LATIN_LETTER.findall(joined))

    frags = _attach_punctuation(_glue_decimals(sorted((list(f) for f in fragments), key=lambda f: f[0])))
    frags.sort(key=lambda f: f[0])

    # كلمات لاتينية متجاورة = مجموعة وحدة، ترتيبها داخلياً يسار←يمين حتى في السطر العربي
    units: list[list] = []  # [x, text, rank, is_latin]
    for x, _y, text, _size in frags:
        stripped = text.strip()
        is_latin = bool(_LATIN_LETTER.search(stripped)) and not _ARABIC_LETTER.search(stripped)
        if units and is_latin and units[-1][3]:
            units[-1][1] += " " + stripped
        else:
            units.append([x, stripped, 0 if _BRACKET_ONLY.match(stripped) else 1, is_latin])

    if rtl:  # عند تساوي الإحداثيات، القوس يروح للنهاية
        units.sort(key=lambda u: (u[0], u[2]), reverse=True)
    text = " ".join(u[1] for u in units)
    if rtl:
        text = text.translate(_MIRROR)
    text = re.sub(r"\s+([.,\u060c\u061b:\u061f!%)\]}])", r"\1", text)
    text = re.sub(r"([(\[{])\s+", r"\1", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _page_text(page) -> str:
    fragments: list[tuple] = []

    def visit(text, cm, tm, font_dict, font_size):
        if text and text.strip():
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            fragments.append((x, y, text, font_size or 12))

    page.extract_text(visitor_text=visit)
    if not fragments:
        return ""
    fragments.sort(key=lambda f: -f[1])  # من فوق لتحت
    lines: list[list[tuple]] = []
    for frag in fragments:
        if lines and abs(frag[1] - lines[-1][0][1]) <= frag[3] * 0.6:
            lines[-1].append(frag)
        else:
            lines.append([frag])
    return "\n".join(_line_text(line) for line in lines)


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise FileError("الملف محمي بكلمة سر. ارفع نسخة بدون حماية.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise FileError(f"الملف طويل ({len(reader.pages)} صفحة). الحد {MAX_PDF_PAGES} صفحة.")
        return "\n".join(_page_text(page) for page in reader.pages)
    except FileError:
        raise
    except Exception:  # ملف تالف أو شكل غير متوقع
        raise FileError("تعذّر قراءة ملف الـ PDF. تأكد أنه سليم وجرّب مرة ثانية.")


# ---------------- Word ----------------
def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(info.file_size for info in archive.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise FileError("الملف كبير بعد الفك. ارفع نسخة أصغر.")
        document = Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    except FileError:
        raise
    except Exception:
        raise FileError("تعذّر قراءة ملف Word. تأكد أنه سليم وجرّب مرة ثانية.")


# ---------------- تنظيف ----------------
# بعض الخطوط ترسم الحروف العربية بأشكال فارسية (ی ھ ک)، نرجعها للعربية عشان المطابقة تشتغل
_PERSIAN_TO_ARABIC = str.maketrans({"\u06cc": "\u064a", "\u06be": "\u0647", "\u06a9": "\u0643"})


def _clean(text: str) -> str:
    # NFKC يحوّل أشكال الحروف العربية المتصلة (presentation forms) للحروف الأساسية
    text = unicodedata.normalize("NFKC", text).translate(_PERSIAN_TO_ARABIC)
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def read_contract(filename: str, data: bytes) -> str:
    """يرجّع نص العقد النظيف، أو يرمي FileError برسالة عربية. ما يحفظ شي."""
    if not data:
        raise FileError("الملف فاضي.")
    if len(data) > MAX_FILE_BYTES:
        raise FileError(f"الملف كبير. الحد {MAX_FILE_BYTES // (1024 * 1024)} ميغابايت.")

    kind = _detect_kind(filename, data)
    text = _clean(_pdf_text(data) if kind == "pdf" else _docx_text(data))

    if len(text) < MIN_TEXT_CHARS:
        if kind == "pdf":
            raise FileError("الملف يبدو صورة (ممسوح ضوئياً) وما نقدر نقرأ نصه. ارفع نسخة نصية من العقد.")
        raise FileError("الملف ما فيه نص كافي للتحليل.")
    if len(text) > MAX_CONTRACT_CHARS:
        raise FileError(
            f"نص العقد طويل ({len(text)} حرف). الحد {MAX_CONTRACT_CHARS} حرف. ارفع الصفحات المهمة فقط."
        )
    return text
