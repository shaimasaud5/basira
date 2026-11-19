// لوحة المراقبة: نعرض كل شي بـ textContent فقط.
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const fmtTime = (ts) => new Date(ts * 1000).toLocaleTimeString("ar-SA", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const fmtDate = (ts) => new Date(ts * 1000).toLocaleString("ar-SA", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
const sec = (ms) => (ms == null ? "—" : (ms / 1000).toFixed(1) + " ث");
const get = async (url) => (await fetch(url, { credentials: "same-origin" })).json();
let days = 7;

// ترحيب باسم صاحبة اللوحة (يُحفظ في متصفحها فقط)
function hello() {
  let name = ""; try { name = localStorage.getItem("admin_name") || ""; } catch (e) { /* بدون تخزين */ }
  const h = $("hello"); h.replaceChildren();
  if (name) {
    h.append(`أهلًا ${name}`);
    const change = el("button", "btn sm", "غيّر الاسم"); change.type = "button"; change.style.marginInlineStart = "12px"; change.style.fontSize = ".8rem";
    change.addEventListener("click", () => { try { localStorage.removeItem("admin_name"); } catch (e) { /* */ } hello(); });
    h.append(change); return;
  }
  h.append("لوحة المراقبة");
  const box = el("div", "hello-in"); const first = el("input"); first.placeholder = "الاسم الأول"; const last = el("input"); last.placeholder = "الاسم الأخير";
  const ok = el("button", "btn sm", "حفظ"); ok.type = "button";
  ok.addEventListener("click", () => { const n = `${first.value.trim()} ${last.value.trim()}`.trim(); if (!n) return; try { localStorage.setItem("admin_name", n); } catch (e) { /* */ } hello(); });
  box.append(first, last, ok); h.append(box);
}

function kpi(value, label, bad = false) { const k = el("div", "kpi" + (bad ? " bad" : "")); k.append(el("div", "v", String(value)), el("div", "l", label)); return k; }
function table(id, heads, rows, onClick) {
  const t = $(id); t.replaceChildren();
  const head = el("tr"); heads.forEach((h) => head.append(el("th", "", h))); t.append(head);
  rows.forEach((cells, i) => { const r = el("tr", onClick ? "v" : ""); cells.forEach((x) => r.append(el("td", "", String(x ?? "—")))); if (onClick) r.addEventListener("click", () => onClick(i)); t.append(r); });
  if (!rows.length) { const r = el("tr"); const c = el("td", "note", "ما فيه بيانات بعد"); c.colSpan = heads.length; r.append(c); t.append(r); }
}

function renderOverview(o) {
  const s = o.summary, h = o.health;
  const st = $("storage"); st.hidden = false; st.replaceChildren();
  st.append(el("b", o.storage === "postgres" ? "ok-t" : "warn-t", o.storage === "postgres" ? "التخزين دائم: كل البيانات محفوظة ولا تُحذف." : "تنبيه: التخزين مؤقت ويتصفّر مع كل نشر. فعّلي DATABASE_URL (Neon) لحفظ دائم."));
  const rate = s.analyses ? Math.round((s.analyses_failed / s.analyses) * 100) : 0;
  $("kpis").replaceChildren(
    kpi(s.visitors_total, "زائر"), kpi(s.identified, "عرّفوا بأسمائهم"), kpi(s.page_views, "فتح الصفحة"), kpi(s.uploads, "عقد مرفوع"),
    kpi(s.analyses_ok, "تحليل ناجح"), kpi(s.analyses_failed, `تحليل فاشل (${rate}%)`, s.analyses_failed > 0),
    kpi(sec(s.analysis_ms.p50), "زمن التحليل (متوسط)"), kpi(sec(s.analysis_ms.p95), "زمن التحليل (الأبطأ 5%)"),
    kpi(s.chats, "رسالة للمساعد"), kpi(h.llm_bad, "طلبات الموديل المرفوضة", h.llm_bad > 0), kpi(s.errors, "أخطاء", s.errors > 0));

  // صحة الموديل
  const m = $("model"); m.replaceChildren();
  const verdict = el("p", h.llm_bad ? "warn-t" : "ok-t", h.llm_total ? (h.llm_bad ? `وقف الموديل ${h.llm_bad} مرة من ${h.llm_total} طلب` : `ما وقف الموديل أبدًا (${h.llm_total} طلب ناجح)`) : "ما فيه طلبات للموديل بعد");
  m.append(verdict);
  const nowRow = el("div", "row"); nowRow.append(el("span", "", "حالة المفاتيح الحين"));
  nowRow.append(el("b", "", o.keys_now.length ? o.keys_now.map((k) => `مفتاح ${k.key}: ${k.ready ? "جاهز" : `راحة ${k.wait_s} ث`}`).join(" · ") : "ما فيه مفاتيح")); m.append(nowRow);
  const kt = el("table"); const sc = el("div", "scroll"); sc.append(kt); m.append(sc);
  const rows = h.keys.map((k) => [`مفتاح ${k.key}`, k.ok, k.limited, k.rejected, k.other, sec(k.avg_ms)]);
  const head = el("tr"); ["المفتاح", "نجح", "رُفض (زحمة)", "مرفوض (401)", "أخطاء أخرى", "متوسط الاستجابة"].forEach((x) => head.append(el("th", "", x))); kt.append(head);
  rows.forEach((c) => { const r = el("tr"); c.forEach((x) => r.append(el("td", "", String(x)))); kt.append(r); });
  if (h.blocked_people.length) {
    m.append(el("p", "note", "من تأثّر برفض الموديل:"));
    h.blocked_people.forEach(([who, n]) => { const r = el("div", "row"); r.append(el("span", "", who), el("b", "bad-t", `${n} مرة`)); m.append(r); });
    m.append(el("p", "note", "آخر الحالات:"));
    h.blocked_events.slice(0, 8).forEach((e) => { const r = el("div", "row"); r.append(el("span", "", `${e.who} — ${e.what || "الموديل"}`), el("span", "bad-t", e.status === 429 ? "زحمة 429" : e.status === 401 ? "مفتاح مرفوض" : String(e.status)), el("span", "note", fmtDate(e.time))); m.append(r); });
  }

  // القمع
  const f = $("funnel"); f.replaceChildren(); const top = Math.max(1, ...o.funnel.map((x) => x[1]));
  o.funnel.forEach(([k, v]) => { const r = el("div", "row"); r.append(el("span", "", k), el("b", "", String(v))); f.append(r); const b = el("div", "fbar"); b.style.width = Math.max(2, (v / top) * 100) + "%"; f.append(b); });

  // الأداء
  table("endpoints", ["الخطوة", "العدد", "أخطاء", "متوسط", "الأبطأ 5%", "الأقصى"], h.endpoints.map((e) => [e.label, e.n, e.err, sec(e.p50), sec(e.p95), sec(e.max)]));

  const max = Math.max(1, ...s.hourly_requests);
  $("hourly").replaceChildren(...s.hourly_requests.map((v, i) => { const b = el("i"); b.style.height = Math.max(2, (v / max) * 100) + "%"; b.title = `قبل ${23 - i} ساعة: ${v}`; return b; }));
  const box = (title, list) => { const b = el("div", "box"); b.append(el("h2", "", title)); if (!list.length) b.append(el("p", "note", "ما فيه بيانات")); list.forEach(([k, v]) => { const r = el("div", "row"); r.append(el("span", "", String(k)), el("b", "", String(v))); b.append(r); }); return b; };
  $("tops").replaceChildren(box("المصادر", s.top_sources), box("الأجهزة", s.top_devices), box("الدول", s.top_countries));
  const errs = $("errors"); errs.replaceChildren();
  if (!s.recent_errors.length) errs.append(el("p", "note", "ما فيه أخطاء"));
  s.recent_errors.forEach((e) => { const r = el("div", "row"); r.append(el("span", "", `${e.path}`), el("span", "bad-t", String(e.status)), el("span", "note", fmtDate(e.time))); errs.append(r); });
}

let peopleList = [], visitorList = [];
function renderPeople(list) {
  peopleList = list;
  table("people", ["الاسم", "أيام الاستخدام", "فتح", "رفع عقد", "تحليل (ناجح)", "محادثة", "أخطاء", "وقف الموديل عليه", "متوسط زمن تحليله", "الجهاز", "آخر نشاط"],
    list.map((p) => [p.name, p.days, p.views, p.uploads, `${p.analyses} (${p.analyses_ok})`, p.chats, p.errors, p.model_blocked, sec(p.avg_analysis_ms), p.device || "—", fmtDate(p.last)]),
    (i) => showSteps(`رحلة ${peopleList[i].name}`, `/admin/api/person?name=${encodeURIComponent(peopleList[i].name)}`));
}
function renderVisitors(list) {
  visitorList = list.filter((v) => !v.name);
  table("visitors", ["الزائر", "اليوم", "آخر نشاط", "المصدر", "الجهاز", "الدولة", "فتح", "رفع", "تحليل", "محادثة", "أخطاء"],
    visitorList.map((v) => [v.id, v.day, fmtDate(v.last), v.source || "—", v.device || "—", v.country || "—", v.views, v.uploads, v.analyses, v.chats, v.errors]),
    (i) => showSteps(`رحلة الزائر ${visitorList[i].id} (${visitorList[i].day})`, `/admin/api/visitor/${encodeURIComponent(visitorList[i].id)}`));
}

async function showSteps(title, url) {
  const steps = await get(url);
  $("journey-title").textContent = title;
  const ul = $("journey"); ul.replaceChildren();
  let lastDay = "";
  steps.forEach((s) => {
    const d = new Date(s.time * 1000).toLocaleDateString("ar-SA", { weekday: "long", month: "long", day: "numeric" });
    if (d !== lastDay) { lastDay = d; const li = el("li"); li.append(el("b", "", d)); ul.append(li); }
    const li = el("li", s.tone || "");
    li.append(el("time", "", fmtTime(s.time)), el("span", s.tone === "bad" ? "bad-t" : "", s.label), el("span", "note", s.ms != null ? sec(s.ms) : ""));
    ul.append(li);
  });
  if (!steps.length) ul.append(el("li", "note", "ما فيه خطوات"));
  $("journey-box").hidden = false; $("journey-box").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function load() {
  renderOverview(await get(`/admin/api/overview?days=${days}`));
  renderPeople(await get("/admin/api/people"));
  renderVisitors(await get("/admin/api/visitors?limit=200"));
}

[[1, "اليوم"], [7, "7 أيام"], [30, "30 يوم"], [3650, "الكل"]].forEach(([d, label]) => {
  const b = el("button", "", label); b.type = "button"; b.setAttribute("aria-pressed", String(d === days));
  b.addEventListener("click", () => { days = d; document.querySelectorAll("#range button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); load(); });
  $("range").append(b);
});
const refresh = el("button", "", "تحديث"); refresh.type = "button"; refresh.addEventListener("click", load); $("range").append(refresh);
$("reset").addEventListener("click", async () => {
  if (!confirm("تصفير اللوحة يمسح كل الزوار والأحداث نهائيًا ولا يمكن التراجع. نزّلتِ نسخة CSV؟ تكملين؟")) return;
  if (prompt("للتأكيد اكتبي: تصفير") !== "تصفير") return;
  const r = await fetch("/admin/api/reset", { method: "POST", credentials: "same-origin" });
  if (r.ok) { $("journey-box").hidden = true; load(); }
});
hello();
load();
setInterval(load, 30000);
