import io
import logging
import zipfile
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app import files
from app.contract import normalize
from app.files import FileError, read_contract
from app.main import app

client = TestClient(app)

TEXT = (
    "مدة العقد 24 شهراً تبدأ من تاريخ استلام المحل. "
    "الإيجار السنوي 96,000 ريال يُدفع على دفعتين متساويتين. "
    "جوال المؤجر 0551234567."
)


def make_docx(*paragraphs, table_rows=()):
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=2)
        for i, (a, b) in enumerate(table_rows):
            table.rows[i].cells[0].text, table.rows[i].cells[1].text = a, b
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def blank_pdf(pages=1, password=None):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if password:
        writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------- Word ----------
def test_docx_text_and_tables_are_extracted():
    data = make_docx(TEXT, table_rows=[("الصيانة", "على المستأجر في الأعمال الدورية البسيطة")])
    text = read_contract("عقد.docx", data)
    assert "مدة العقد 24 شهراً" in text and "الإيجار السنوي 96,000 ريال" in text
    assert "الصيانة" in text and "على المستأجر" in text


def test_docx_without_enough_text_is_rejected():
    with pytest.raises(FileError, match="ما فيه نص"):
        read_contract("a.docx", make_docx("قصير"))


def test_docx_zip_bomb_is_rejected_before_opening():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/big.bin", b"\0" * (files.MAX_DOCX_UNCOMPRESSED_BYTES + 1024))
    with pytest.raises(FileError, match="كبير بعد الفك"):
        read_contract("a.docx", buf.getvalue())


def test_corrupt_docx_gives_arabic_error():
    with pytest.raises(FileError, match="تعذّر قراءة ملف Word"):
        read_contract("a.docx", b"PK\x03\x04 not really a zip")


# ---------- التحقق العام ----------
def test_empty_file():
    with pytest.raises(FileError, match="فاضي"):
        read_contract("a.pdf", b"")


def test_file_too_big():
    with pytest.raises(FileError, match="كبير"):
        read_contract("a.pdf", b"%PDF-" + b"0" * files.MAX_FILE_BYTES)


@pytest.mark.parametrize("name, data", [
    ("a.txt", b"hello world"),
    ("a.pdf", make_docx(TEXT)),              # الامتداد pdf لكن المحتوى docx
    ("a.docx", b"%PDF-1.4 ..."),              # العكس
    ("a.exe", b"MZ\x90\x00"),
    ("", b"%PDF-1.4"),
])
def test_unsupported_or_spoofed_types(name, data):
    with pytest.raises(FileError, match="غير مدعوم"):
        read_contract(name, data)


def test_old_doc_format_has_specific_message():
    with pytest.raises(FileError, match="docx"):
        read_contract("a.doc", b"\xd0\xcf\x11\xe0")


def test_text_longer_than_limit_is_rejected(monkeypatch):
    monkeypatch.setattr(files, "MAX_CONTRACT_CHARS", 100)
    with pytest.raises(FileError, match="طويل"):
        read_contract("a.docx", make_docx("ا" * 150))


# ---------- PDF ----------
def test_scanned_pdf_gets_clear_message():
    with pytest.raises(FileError, match="ممسوح ضوئياً"):
        read_contract("a.pdf", blank_pdf())


def test_corrupt_pdf():
    with pytest.raises(FileError, match="تعذّر قراءة ملف الـ PDF"):
        read_contract("a.pdf", b"%PDF-1.4 garbage garbage")


def test_encrypted_pdf():
    with pytest.raises(FileError, match="كلمة سر"):
        read_contract("a.pdf", blank_pdf(password="secret"))


def test_pdf_page_limit():
    with pytest.raises(FileError, match="صفحة"):
        read_contract("a.pdf", blank_pdf(pages=files.MAX_PDF_PAGES + 1))


# ---------- PDF عربي حقيقي (مولّد من Chrome) ----------
FIXTURES = Path(__file__).parent / "fixtures"


def pdf_text(name):
    return read_contract(name, (FIXTURES / name).read_bytes())


@pytest.mark.parametrize("phrase", [
    "مدة العقد 24 شهراً", "الإيجار السنوي 96,000 ريال", "يتجدد العقد تلقائياً",
    "قبل 60 يوماً", "يزداد الإيجار بنسبة 5% عند كل تجديد", "(نموذج تجريبي، بيانات وهمية)",
])
def test_arabic_pdf_numbers_stay_with_their_clauses(phrase):
    # قبل الإصلاح كانت الأرقام تنزاح عن بنودها ("24" تطلع بسطر ثاني)
    assert normalize(phrase) in normalize(pdf_text("contract_complete.pdf"))


def test_arabic_pdf_keeps_list_numbering_and_sentences_in_order():
    lines = pdf_text("contract_complete.pdf").splitlines()
    assert lines[1].startswith("1. مدة العقد 24 شهراً")
    assert lines[2].startswith("2. الإيجار السنوي 96,000 ريال")
    numbers = [int(l.split(".")[0]) for l in lines if l.split(".")[0].isdigit()]
    assert numbers == [1, 2, 3, 4, 5, 6, 7]  # البنود بترتيبها الصحيح


@pytest.mark.parametrize("phrase", [
    "7,500.50 ريال", "زيادة 7.5% سنوياً", "غرامة قدرها 2% من قيمة", "2026/01/15", "1447/07/26",
    "Al-Noor Trading Co.", "Riyadh Park", "ريال سعودي (SAR) في أول كل شهر", "الصيانة على المستأجر",
])
def test_arabic_pdf_mixed_english_decimals_dates_and_tables(phrase):
    assert normalize(phrase) in normalize(pdf_text("contract_mixed.pdf"))


def test_font_using_persian_letter_shapes_still_matches_arabic_text():
    # هذا الخط يرسم ي و ه و ك بأشكال فارسية، ونرجعها للعربية
    text = pdf_text("contract_tricky.pdf")
    assert normalize("الإيجار السنوي 120,000 ريال يُدفع مقدماً") in normalize(text)
    assert normalize("يزداد الإيجار بنسبة 10% في كل سنة") in normalize(text)
    assert not any(ch in text for ch in "یھک")


def test_pdf_goes_through_the_full_preview_endpoint():
    data = (FIXTURES / "contract_mixed.pdf").read_bytes()
    r = client.post("/contract/preview", files={"file": ("عقد.pdf", data, "application/pdf")})
    assert r.status_code == 200 and "7,500.50" in r.json()["text"]


def test_glue_decimals_joins_split_number_in_reading_order():
    frags = [[179.4, 700.0, "7,500", 15], [204.7, 700.0, " .", 15], [208.0, 700.0, " 50", 15]]
    assert [f[2] for f in files._glue_decimals(frags)] == ["7,500.50"]


def test_sentence_final_period_is_not_glued_into_the_next_number():
    frags = [[111.1, 700.0, " ريال يُدفع", 15], [114.6, 700.0, ".", 15], [429.9, 700.0, "96,000", 15]]
    assert [f[2] for f in files._glue_decimals(frags)] == [" ريال يُدفع", ".", "96,000"]


# ---------- التنظيف ----------
def test_clean_maps_persian_letter_shapes_to_arabic():
    assert files._clean("ریال شھراً کتابیاً") == "ريال شهراً كتابياً"



def test_clean_normalizes_arabic_presentation_forms_and_whitespace():
    shaped = "ﺍﻷﺑﺎﺑ"  # أشكال متصلة
    cleaned = files._clean(f"  {shaped}   كلمة\x00 \n\n\n\n بعد  ")
    assert "\x00" not in cleaned and "\n\n\n" not in cleaned
    assert all(not ("ﹰ" <= ch <= "﻿") for ch in cleaned)  # ما بقي أشكال presentation


# ---------- المسار /contract/preview ----------
def upload(name, data, content_type="application/octet-stream"):
    return client.post("/contract/preview", files={"file": (name, data, content_type)})


def test_preview_returns_redacted_text_and_counts():
    r = upload("عقد.docx", make_docx(TEXT))
    assert r.status_code == 200
    body = r.json()
    assert "0551234567" not in body["text"] and "[جوال]" in body["text"]
    assert body["redacted"]["mobile"] == 1 and body["chars"] == len(body["text"])


def test_preview_unsupported_type_is_arabic_422():
    r = upload("a.txt", b"hello")
    assert r.status_code == 422 and "غير مدعوم" in r.json()["errors"][0]


def test_preview_without_file_is_arabic_422():
    r = client.post("/contract/preview")
    assert r.status_code == 422 and r.json()["errors"] == ["اختر ملف العقد أول."]


def test_redact_endpoint_hides_sensitive_data_only():
    r = client.post("/contract/redact", json={"text": TEXT})
    body = r.json()
    assert r.status_code == 200 and "[جوال]" in body["text"] and "96,000" in body["text"]
    assert body["redacted"]["mobile"] == 1


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": "   "}])
def test_redact_endpoint_rejects_empty_text(payload):
    r = client.post("/contract/redact", json=payload)
    assert r.status_code == 422 and "النص فاضي" in r.json()["errors"][0]


def test_redact_endpoint_rejects_too_long_text():
    r = client.post("/contract/redact", json={"text": "ا" * 20001})
    assert r.status_code == 422 and "أطول من الحد" in r.json()["errors"][0]


def test_preview_is_rate_limited(monkeypatch):
    from app import ratelimit
    monkeypatch.setattr(ratelimit, "extract_limiter", ratelimit.RateLimiter(1, 60))
    assert upload("a.txt", b"x").status_code == 422
    assert upload("a.txt", b"x").status_code == 429


def test_preview_never_logs_contract_content(caplog):
    with caplog.at_level(logging.DEBUG):
        upload("عقد.docx", make_docx(TEXT))
    assert "96,000" not in caplog.text and "0551234567" not in caplog.text
    assert "preview: chars=" in caplog.text
