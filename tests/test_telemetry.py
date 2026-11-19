import json
import sqlite3

from fastapi.testclient import TestClient

from app import telemetry
from app.main import app

client = TestClient(app)
UA_PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605 Version/17 Mobile Safari/604"


def test_page_views_and_api_calls_are_recorded_without_ip(monkeypatch):
    client.get("/?utm_source=linkedin", headers={"user-agent": UA_PHONE})
    client.post("/analyze", json={"activity": "كوفي", "city": "جدة"}, headers={"user-agent": UA_PHONE})
    s = telemetry.summary(1)
    assert s["page_views"] == 1 and s["analyses"] == 1 and s["visitors_total"] == 1
    assert s["top_sources"] == [["linkedin", 1]] and s["top_devices"] == [["جوال", 1]]
    raw = sqlite3.connect(telemetry.DB_PATH).execute("SELECT group_concat(visitor || path || meta, ' ') FROM events").fetchone()[0]
    assert "testclient" not in raw and "127.0.0.1" not in raw          # الـIP ما ينحفظ


def test_static_health_and_admin_are_not_tracked():
    client.get("/static/styles.css")
    client.get("/health")
    client.get("/admin")
    assert telemetry.summary(1)["visitors_total"] == 0


def test_contract_text_never_reaches_the_telemetry_db():
    secret = "بند سري جداً 987654"
    client.post("/analyze", json={"activity": "كوفي", "city": "جدة", "contract_text": secret, "consent": True})
    dump = json.dumps(sqlite3.connect(telemetry.DB_PATH).execute("SELECT * FROM events").fetchall(), ensure_ascii=False)
    assert secret not in dump


def test_visitor_id_is_stable_per_day_and_differs_per_user():
    a = telemetry.visitor_id("1.2.3.4", "ua", ts=1_700_000_000)
    assert a == telemetry.visitor_id("1.2.3.4", "ua", ts=1_700_000_000)
    assert a != telemetry.visitor_id("1.2.3.5", "ua", ts=1_700_000_000)
    assert a != telemetry.visitor_id("1.2.3.4", "ua", ts=1_700_000_000 + 86400)   # يتغيّر كل يوم


def test_admin_is_disabled_without_password(monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert client.get("/admin/api/summary").status_code == 404


def test_admin_requires_the_right_password(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    assert client.get("/admin/api/summary").status_code == 401
    assert client.get("/admin/api/summary", auth=("x", "wrong")).status_code == 401
    ok = client.get("/admin/api/summary", auth=("x", "s3cret"))
    assert ok.status_code == 200 and "visitors_total" in ok.json()
    assert "لوحة المراقبة" in client.get("/admin", auth=("x", "s3cret")).text


def test_journey_lists_steps_in_order(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    client.get("/", headers={"user-agent": UA_PHONE})
    client.post("/chat", json={"question": "هلا"}, headers={"user-agent": UA_PHONE})
    vid = client.get("/admin/api/visitors", auth=("x", "s3cret")).json()[0]["id"]
    steps = client.get(f"/admin/api/visitor/{vid}", auth=("x", "s3cret")).json()
    assert [s["label"] for s in steps] == ["فتح الصفحة", "رسالة للمساعد"]


def test_name_is_linked_to_the_visitor_in_the_admin_only(monkeypatch, caplog):
    import logging
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    with caplog.at_level(logging.DEBUG):
        client.post("/analyze", json={"first_name": "سارة", "last_name": "العتيبي", "activity": "كوفي", "city": "جدة"},
                    headers={"user-agent": UA_PHONE})
    assert "سارة" not in caplog.text and "العتيبي" not in caplog.text      # ما ينكتب بالسجلات
    row = client.get("/admin/api/visitors", auth=("x", "s3cret")).json()[0]
    assert row["name"] == "سارة العتيبي"
    steps = client.get(f"/admin/api/visitor/{row['id']}", auth=("x", "s3cret")).json()
    assert any(s["label"] == "عرّف بنفسه: سارة العتيبي" for s in steps)
    assert client.get("/admin/api/summary", auth=("x", "s3cret")).json()["identified"] == 1


def test_overlong_name_is_rejected_with_arabic_error():
    r = client.post("/analyze", json={"first_name": "ا" * 61, "activity": "كوفي", "city": "جدة"})
    assert r.status_code == 422 and any("الاسم" in m for m in r.json()["errors"])
