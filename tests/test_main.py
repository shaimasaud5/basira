import logging

from fastapi.testclient import TestClient

from app import llm
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


JS_MODULES = ["main", "api", "chat", "dashboard", "dom", "input", "progress"]


def test_landing_is_arabic_rtl_with_the_chosen_copy():
    page = client.get("/").text
    assert 'dir="rtl"' in page and "بصِيـــرة" in page
    assert "قبل ما توقّع عقد الإيجار" in page
    assert "مخاطر عقدك" in page and "قبل ما تلتزم بسنة أو سنتين" in page
    assert "ابدأ التحليل" in page
    assert "قراءة أولية وليست استشارة قانونية" in page


def test_logo_svg_has_separate_animatable_layers():
    r = client.get("/static/logo.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    for layer in ("frame", "l1", "l2", "l3", "hands"):
        assert f'<g id="{layer}">' in r.text
    assert "currentColor" in r.text  # يتبع الثيم (أسود بالفاتح وأبيض بالداكن)


def test_landing_background_uses_the_animated_logo_not_the_eye():
    page = client.get("/").text
    assert 'class="bg-logo"' in page and 'class="hands"' in page and "logo.svg#l1" in page
    assert "i-lens" not in page and 'class="lens"' not in page
    assert 'rel="icon"' in page and "/static/logo.svg" in page


def test_eyebrow_is_plain_text_without_icon():
    page = client.get("/").text
    assert '<span class="eyebrow">قبل ما توقّع عقد الإيجار</span>' in page


def test_landing_has_a_single_start_button_and_no_extra_copy():
    page = client.get("/").text
    assert page.count("ابدأ التحليل") == 1
    assert "كل شي بالأرقام وبالدليل" not in page
    assert '<span>قراءة أولية وليست استشارة قانونية</span>' in page  # بدون أيقونة مفتاح


def test_app_screen_copy():
    page = client.get("/").text
    assert "ادخل بيانات مشروعك" in page and 'placeholder="مثال: مطعم"' in page
    assert "بصِيـــرة" in page and "مستشار بصيرة" not in page
    for removed in ("الباقي يحسّن التحليل", "يرفع قيمة التحليل كثير"):
        assert removed not in page
    assert ">اختياري<" not in page.split('id="drop-area"')[0].split("عقد الإيجار")[-1]  # العقد أساسي


def test_landing_polish_v2():
    page, css = client.get("/").text, client.get("/static/styles.css").text
    assert ".hero h1 .accent::after" not in css and "@keyframes hue" in css   # بدون خط أصفر، ألوان متحركة
    assert "color: var(--brand);" in css.split(".step-arrow {")[1].split("}")[0]   # لون السهم مثل زر البدء
    assert 'class="brand-name">بصِيـــرة<' in page and "Aref+Ruqaa" in page
    assert 'id="nav-home"' in page and 'href="#/"' in page   # رجوع للصفحة الرئيسية


def test_home_interactivity_and_chat_composer():
    page = client.get("/").text
    for marker in ('id="progress"', 'data-for="activity"', 'data-for="city"', 'id="ratio-live"', 'class="pill-input"', "chat-logo logo-anim"):
        assert marker in page


def test_live_ratio_thresholds_match_the_backend():
    import re
    from app.report import HIGH_RATIO_PCT, MEDIUM_RATIO_PCT
    js = client.get("/static/js/progress.js").text
    m = re.search(r"const MEDIUM = (\d+), HIGH = (\d+);", js)
    assert (int(m.group(1)), int(m.group(2))) == (MEDIUM_RATIO_PCT, HIGH_RATIO_PCT)


def test_landing_has_no_login_or_signup():
    page = client.get("/").text.lower()
    for word in ("login", "sign up", "signup", "تسجيل الدخول", "إنشاء حساب"):
        assert word not in page


def test_app_screen_has_the_always_present_chat_and_upload():
    page = client.get("/").text
    assert 'id="chat"' in page and 'id="composer"' in page and 'id="dropzone"' in page
    assert "pdf" in page.lower() and "docx" in page.lower()
    assert 'id="contract_text"' not in page  # ما فيه لصق نص، رفع ملف فقط


def test_static_assets_are_served_with_correct_types():
    css = client.get("/static/styles.css")
    assert css.status_code == 200 and "--brand" in css.text
    for name in JS_MODULES:
        r = client.get(f"/static/js/{name}.js")
        assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert client.get("/static/missing.js").status_code == 404


def test_frontend_never_injects_html():
    # نصوص العقد والموديل لازم تدخل الصفحة بـ textContent فقط (حماية من XSS)
    for name in JS_MODULES:
        js = client.get(f"/static/js/{name}.js").text
        for unsafe in (".innerHTML", ".outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            assert unsafe not in js, f"{unsafe} in {name}.js"


def test_every_module_imported_by_main_exists():
    import re
    main_js = client.get("/static/js/main.js").text
    for rel in re.findall(r'from "\./([a-z]+)\.js"', main_js):
        assert client.get(f"/static/js/{rel}.js").status_code == 200


def test_analyze_returns_report_with_cards():
    r = client.post(
        "/analyze",
        json={"activity": "كوفي", "city": "الرياض", "monthly_rent": 8000,
              "monthly_revenue": 40000, "lease_months": 24},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["top"]) == 2
    assert body["top"][0]["trust_label"] == "محسوب بالكود"
    assert body["disclaimer"] == "قراءة أولية وليست استشارة قانونية."


def test_analyze_minimal_input_has_missing_info():
    r = client.post("/analyze", json={"activity": "كوفي", "city": "جدة"})
    assert r.status_code == 200
    assert r.json()["top"] == [] and r.json()["missing_info"]


def test_empty_input_gives_arabic_errors():
    r = client.post("/analyze", json={})
    assert r.status_code == 422
    assert "نوع النشاط مطلوب." in r.json()["errors"]
    assert "المدينة مطلوبة." in r.json()["errors"]


def test_bad_number_gives_arabic_error():
    r = client.post("/analyze", json={"activity": "كوفي", "city": "جدة", "monthly_rent": "abc"})
    assert r.status_code == 422
    assert "الإيجار الشهري لازم يكون رقم." in r.json()["errors"]


def test_contract_without_consent_rejected():
    r = client.post("/analyze", json={"activity": "كوفي", "city": "جدة", "contract_text": "بند"})
    assert r.status_code == 422
    assert any("توافق" in m for m in r.json()["errors"])


def test_malformed_body_gives_arabic_error():
    r = client.post("/analyze", json=[1, 2])
    assert r.status_code == 422
    assert all("المدخلات" in m for m in r.json()["errors"])


CONTRACT_BODY = {
    "activity": "كوفي", "city": "الرياض", "monthly_revenue": 40000,
    "contract_text": "الإيجار السنوي 96,000 ريال. يزداد الإيجار بنسبة 5% عند كل تجديد. جوال المؤجر 0501234567.",
    "consent": True,
}


def test_contract_text_never_logged(monkeypatch, caplog):
    secret = "بند سري جداً 12345"
    monkeypatch.setattr(llm, "chat_json", lambda s, u: {})
    with caplog.at_level(logging.DEBUG):
        client.post("/analyze", json={"activity": "كوفي", "city": "جدة",
                                      "contract_text": secret, "consent": True})
    assert secret not in caplog.text
    assert "contract_len=" in caplog.text


def test_analyze_with_contract_returns_contract_cards(monkeypatch):
    fake = {
        "rent": {"value": 96000, "period": "yearly", "quote": "الإيجار السنوي 96,000 ريال"},
        "increase_pct": {"value": 5, "quote": "يزداد الإيجار بنسبة 5% عند كل تجديد"},
    }
    monkeypatch.setattr(llm, "chat_json", lambda s, u: fake)
    body = client.post("/analyze", json=CONTRACT_BODY).json()
    titles = [c["title"] for c in body["top"] + body["more"]]
    assert any("يزيد" in t for t in titles)          # بطاقة الزيادة
    assert any("نسبة الإيجار" in t or "الإيجار يأخذ" in t for t in titles)  # مالية من إيجار العقد
    assert body["warnings"] == []


def test_phone_number_is_redacted_before_reaching_the_model(monkeypatch):
    seen = {}

    def chat_json(system, user):
        seen["user"] = user
        return {}

    monkeypatch.setattr(llm, "chat_json", chat_json)
    client.post("/analyze", json=CONTRACT_BODY)
    assert "0501234567" not in seen["user"] and "[جوال]" in seen["user"]


def test_model_failure_still_returns_financial_report_with_warning(monkeypatch):
    def boom(system, user):
        raise llm.LLMError("انتهت مهلة الاتصال بخدمة التحليل.")

    monkeypatch.setattr(llm, "chat_json", boom)
    body = dict(CONTRACT_BODY, monthly_rent=8000)
    r = client.post("/analyze", json=body)
    assert r.status_code == 200
    assert any("تعذّر تحليل العقد" in w and "مهلة" in w for w in r.json()["warnings"])
    assert r.json()["top"]  # التقرير المالي ما ضاع


def test_fabricated_quote_never_reaches_report(monkeypatch):
    fake = {"increase_pct": {"value": 10, "quote": "يزداد الإيجار بنسبة 10% كل سنة"}}
    monkeypatch.setattr(llm, "chat_json", lambda s, u: fake)
    body = client.post("/analyze", json=dict(CONTRACT_BODY, monthly_rent=8000)).json()
    assert not any("زيادة" in c["title"] or "يزيد" in c["title"] for c in body["top"] + body["more"])


def test_analyze_runs_both_model_calls_in_parallel(monkeypatch):
    """لو الطلبان تسلسليين، الحاجز ما يكتمل ويفشل الاختبار بالمهلة."""
    import threading

    from app import main as app_main
    from app.contract import ContractFacts

    barrier = threading.Barrier(2, timeout=5)

    def fake_extract(text):
        barrier.wait()
        return ContractFacts()

    def fake_request(project, text, *args, **kwargs):
        barrier.wait()
        return []

    monkeypatch.setattr(app_main, "extract_contract", fake_extract)
    monkeypatch.setattr(app_main, "request_suggestions", fake_request)
    r = client.post("/analyze", json=CONTRACT_BODY)
    assert r.status_code == 200 and r.json()["warnings"] == []
