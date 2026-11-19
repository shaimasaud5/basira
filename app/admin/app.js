// لوحة المراقبة: نعرض كل شي بـ textContent فقط.
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const fmtTime = (ts) => new Date(ts * 1000).toLocaleTimeString("ar-SA", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const fmtDate = (ts) => new Date(ts * 1000).toLocaleString("ar-SA", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
const sec = (ms) => (ms == null ? "—" : (ms / 1000).toFixed(1) + " ث");
const get = async (url) => (await fetch(url, { credentials: "same-origin" })).json();
let days = 7;

function kpi(value, label, bad = false) { const k = el("div", "kpi" + (bad ? " bad" : "")); k.append(el("div", "v", String(value)), el("div", "l", label)); return k; }

function renderSummary(s) {
  const rate = s.analyses ? Math.round((s.analyses_failed / s.analyses) * 100) : 0;
  $("kpis").replaceChildren(
    kpi(s.visitors_total, "زائر"), kpi(s.identified, "عرّفوا بأسمائهم"), kpi(s.page_views, "فتح الصفحة"), kpi(s.uploads, "عقد مرفوع"),
    kpi(s.analyses_ok, "تحليل ناجح"), kpi(s.analyses_failed, `تحليل فاشل (${rate}%)`, s.analyses_failed > 0),
    kpi(sec(s.analysis_ms.p50), "زمن التحليل (متوسط)"), kpi(sec(s.analysis_ms.p95), "زمن التحليل (الأبطأ 5%)"),
    kpi(s.chats, "رسالة للمساعد"), kpi(s.llm_rate_limited, "مرّات رفض Groq (زحمة)", s.llm_rate_limited > 0), kpi(s.errors, "أخطاء", s.errors > 0));
  const max = Math.max(1, ...s.hourly_requests);
  $("hourly").replaceChildren(...s.hourly_requests.map((v, i) => { const b = el("i"); b.style.height = Math.max(2, (v / max) * 100) + "%"; b.title = `قبل ${23 - i} ساعة: ${v}`; return b; }));
  const box = (title, rows) => { const b = el("div", "box"); b.append(el("h2", "", title)); if (!rows.length) b.append(el("p", "note", "ما فيه بيانات")); rows.forEach(([k, v]) => { const r = el("div", "row"); r.append(el("span", "", String(k)), el("b", "", String(v))); b.append(r); }); return b; };
  const keys = Object.entries(s.llm_keys_used).map(([k, v]) => [`مفتاح ${k}`, v]);
  $("tops").replaceChildren(box("المصادر", s.top_sources), box("الأجهزة", s.top_devices), box("الدول", s.top_countries), box("استخدام المفاتيح", keys));
  const errs = $("errors"); errs.replaceChildren();
  if (!s.recent_errors.length) errs.append(el("p", "note", "ما فيه أخطاء 🎉".replace(" 🎉", "")));
  s.recent_errors.forEach((e) => { const r = el("div", "row"); r.append(el("span", "", `${e.path}`), el("span", "bad-t", String(e.status)), el("span", "note", fmtDate(e.time))); errs.append(r); });
}

function renderVisitors(list) {
  const t = $("visitors"); t.replaceChildren();
  const head = el("tr"); ["الاسم", "الزائر", "اليوم", "آخر نشاط", "المصدر", "الجهاز", "الدولة", "فتح", "رفع", "تحليل", "محادثة", "أخطاء"].forEach((h) => head.append(el("th", "", h)));
  t.append(head);
  list.forEach((v) => {
    const r = el("tr", "v");
    [v.name || "—", v.id, v.day, fmtDate(v.last), v.source || "—", v.device || "—", v.country || "—", v.views, v.uploads, v.analyses, v.chats, v.errors].forEach((x) => r.append(el("td", "", String(x))));
    r.addEventListener("click", () => showJourney(v));
    t.append(r);
  });
}

async function showJourney(v) {
  const steps = await get(`/admin/api/visitor/${encodeURIComponent(v.id)}`);
  $("journey-title").textContent = `رحلة الزائر ${v.id} (${v.day})`;
  const ul = $("journey"); ul.replaceChildren();
  steps.forEach((s) => {
    const li = el("li"); const bad = (s.status || 0) >= 400;
    li.append(el("time", "", fmtTime(s.time)), el("span", bad ? "bad-t" : "", s.label + (bad ? ` (فشل ${s.status})` : "")), el("span", "note", s.ms != null ? sec(s.ms) : ""));
    ul.append(li);
  });
  $("journey-box").hidden = false; $("journey-box").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function load() {
  renderSummary(await get(`/admin/api/summary?days=${days}`));
  renderVisitors(await get("/admin/api/visitors?limit=60"));
}

[[1, "اليوم"], [7, "7 أيام"], [30, "30 يوم"]].forEach(([d, label]) => {
  const b = el("button", "", label); b.type = "button"; b.setAttribute("aria-pressed", String(d === days));
  b.addEventListener("click", () => { days = d; document.querySelectorAll("#range button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); load(); });
  $("range").append(b);
});
const refresh = el("button", "", "تحديث"); refresh.type = "button"; refresh.addEventListener("click", load); $("range").append(refresh);
load();
setInterval(load, 30000);
