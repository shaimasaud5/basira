// نقطة الدخول: التنقل بين الصفحات والمراحل، وربط الوحدات ببعض.
import { $, show } from "./dom.js";
import * as api from "./api.js";
import { initChat, resetChat, setReportContext, ask } from "./chat.js";
import { initInput, openFilePicker, resetInput, showErrors } from "./input.js";
import { renderDashboard } from "./dashboard.js";
import { initProgress } from "./progress.js";
import { initTheme } from "./theme.js";
import { mountDemo } from "./demo.js";

const STAGES = { input: "stage-input", loading: "stage-loading", dash: "stage-dash" };
const app = { report: null, project: null };

/* ---------- التنقل: الصفحة الرئيسية (#/) والتطبيق (#/app) ---------- */
function route() {
  const inApp = location.hash === "#/app";
  show($("view-landing"), !inApp);
  show($("view-home"), inApp);
  show($("nav-home"), inApp);
  show($("lp-nav"), !inApp);
  show($("lp-top-cta"), !inApp);
  window.scrollTo({ top: 0 });
}

/* ---------- الصفحة الرئيسية: تمرير ناعم للأقسام وظهور تدريجي هادي ---------- */
function initLanding() {
  mountDemo($("lp-demo"));
  document.querySelectorAll("[data-scroll]").forEach((link) => {
    link.addEventListener("click", (ev) => {
      const target = document.getElementById(link.dataset.scroll);
      if (!target) return;
      ev.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  // شريط المميزات المتحرك على الجوال: نسخة ثانية من البطاقات لتكرار سلس (تظهر بالـCSS على الشاشات الصغيرة فقط)
  const feats = document.querySelector("#features .lp-feats");
  if (feats) [...feats.children].forEach((li) => {
    const c = li.cloneNode(true);
    c.classList.remove("lp-reveal");
    c.classList.add("lp-clone");
    c.setAttribute("aria-hidden", "true");
    feats.appendChild(c);
  });
  autoScrollFeatures(feats);
  if (!("IntersectionObserver" in window)) return;
  document.documentElement.classList.add("lp-js");
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
  }, { rootMargin: "0px 0px -8% 0px" });
  document.querySelectorAll(".lp-reveal").forEach((n) => io.observe(n));
}

/* شريط المميزات على الجوال: يتحرك لحاله، ويوقف إذا لمسه المستخدم (وهو قابل للسحب دائمًا) */
function autoScrollFeatures(el) {
  if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const small = matchMedia("(max-width: 1000px)");
  let pos = 0, paused = false, timer = 0;
  const pause = () => { paused = true; clearTimeout(timer); };
  const resume = () => { clearTimeout(timer); timer = setTimeout(() => { pos = el.scrollLeft; paused = false; }, 1800); };
  ["pointerdown", "touchstart", "wheel"].forEach((ev) => el.addEventListener(ev, pause, { passive: true }));
  ["pointerup", "touchend", "touchcancel", "pointerleave"].forEach((ev) => el.addEventListener(ev, resume, { passive: true }));
  let last = performance.now();
  setInterval(() => {
    const now = performance.now(), dt = Math.min(now - last, 200);   // بالزمن الحقيقي: السرعة ثابتة
    last = now;
    if (!small.matches || paused) return;
    const half = el.scrollWidth / 2;
    pos += dt * 0.03;                                                // ~30 بكسل بالثانية
    if (pos >= half) pos -= half;
    el.scrollLeft = pos;
  }, 33);
}

/* ---------- مراحل شاشة التطبيق ---------- */
function setStage(name) {
  Object.entries(STAGES).forEach(([key, id]) => show($(id), key === name));
  setTab("work");
}

function setTab(tab) {
  $("home-grid").dataset.tab = tab;
  $("tab-work").setAttribute("aria-selected", String(tab === "work"));
  $("tab-chat").setAttribute("aria-selected", String(tab === "chat"));
}

async function submit(payload) {
  setStage("loading");
  const result = await api.analyze(payload);
  if (!result.ok) { setStage("input"); return result; }

  app.report = result.data;
  app.project = { activity: payload.activity, city: payload.city };
  renderDashboard($("stage-dash"), app.report, app.project, {
    onAsk: (question) => { setTab("chat"); ask(question); },
    onEdit: () => { setStage("input"); },
  });
  setStage("dash");
  show($("back-to-report"), true);
  setReportContext({ report: app.report, contractText: payload.contract_text, consent: payload.consent });
  return result;
}

function newAnalysis() {
  app.report = null;
  show($("back-to-report"), false);
  resetInput();
  resetChat();
  setStage("input");
  showErrors([]);
  if (location.hash !== "#/app") location.hash = "#/app";
}

/* ---------- تشغيل ---------- */
window.addEventListener("hashchange", route);
$("nav-reset").addEventListener("click", newAnalysis);
function setChat(open) {
  $("home-grid").dataset.chat = open ? "open" : "closed";
}
$("chat-close").addEventListener("click", () => setChat(false));
$("chat-open").addEventListener("click", () => setChat(true));
$("tab-work").addEventListener("click", () => setTab("work"));
$("tab-chat").addEventListener("click", () => setTab("chat"));

$("back-to-report").addEventListener("click", () => setStage("dash"));
initChat({ onAttach: () => { setStage("input"); openFilePicker(); } });
initInput({ onSubmit: submit });
initProgress();
initTheme();
initLanding();
route();
