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

/* ---------- مساعد بصيرة على الصفحة الرئيسية: يفتح بجنب الصفحة بدون تنقّل ---------- */
function openAssistant() {
  $("lp-drawer").appendChild($("chat"));   // نفس المحادثة (بكل ما فيها) تنتقل مؤقتًا للدرج
  show($("lp-drawer"), true);
  show($("lp-ask"), false);
  $("chat-input").focus();
}
function closeAssistant() {
  const grid = $("home-grid");
  if ($("chat").parentNode !== grid) grid.insertBefore($("chat"), grid.firstChild);   // ترجع مكانها في التطبيق
  show($("lp-drawer"), false);
  show($("lp-ask"), true);
}

/* ---------- التنقل: الصفحة الرئيسية (#/) والتطبيق (#/app) ---------- */
function route() {
  const inApp = location.hash === "#/app";
  show($("view-landing"), !inApp);
  show($("view-home"), inApp);
  show($("nav-home"), inApp);
  show($("lp-nav"), !inApp);
  show($("lp-top-cta"), !inApp);
  if (inApp) closeAssistant();
  window.scrollTo({ top: 0 });
}

/* ---------- الصفحة الرئيسية: تمرير ناعم للأقسام وظهور تدريجي هادي ---------- */
function initLanding() {
  mountDemo($("lp-demo"));
  // فقاعة المساعد: تظهر كل شوي بجملة مختلفة وتختفي (ما تظهر والدرج مفتوح)
  const ask = $("lp-ask");
  ask.addEventListener("click", (ev) => { ev.preventDefault(); openAssistant(); });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !$("lp-drawer").classList.contains("hidden")) closeAssistant(); });
  const hints = ["عندك سؤال عن عقدك؟", "وش البنود الخطرة؟", "اسأل بصيرة"];
  const bubble = ask.querySelector(".lp-ask-bubble");
  let n = 0;
  const peek = () => {
    if (!$("lp-drawer").classList.contains("hidden")) return;
    bubble.textContent = hints[n++ % hints.length];
    ask.classList.add("peek");
    setTimeout(() => ask.classList.remove("peek"), 4200);
  };
  setTimeout(peek, 2500);
  setInterval(peek, 12000);
  document.querySelectorAll("[data-scroll]").forEach((link) => {
    link.addEventListener("click", (ev) => {
      const target = document.getElementById(link.dataset.scroll);
      if (!target) return;
      ev.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  if (!("IntersectionObserver" in window)) return;
  document.documentElement.classList.add("lp-js");
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
  }, { rootMargin: "0px 0px -8% 0px" });
  document.querySelectorAll(".lp-reveal").forEach((n) => io.observe(n));
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
$("chat-close").addEventListener("click", () => { if ($("lp-drawer").contains($("chat"))) closeAssistant(); else setChat(false); });
$("chat-open").addEventListener("click", () => setChat(true));
$("tab-work").addEventListener("click", () => setTab("work"));
$("tab-chat").addEventListener("click", () => setTab("chat"));

$("back-to-report").addEventListener("click", () => setStage("dash"));
initChat({ onAttach: () => { closeAssistant(); if (location.hash !== "#/app") location.hash = "#/app"; setStage("input"); openFilePicker(); } });
initInput({ onSubmit: submit });
initProgress();
initTheme();
initLanding();
route();
