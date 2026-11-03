// بصِيـــرة: حاضرة دايماً. قبل التحليل يشرح طريقة الاستخدام، وبعده يجاوب من التقرير والعقد.
import { $, el, icon, show, logoSvg } from "./dom.js";
import * as api from "./api.js";

const MAX_HISTORY = 6;
const WELCOME_GUIDE = "هلا! أنا بصِيـــرة. اسألني إذا حاب عن طريقة الاستخدام، وبعد ما ترفع عقدك أقدر أساعدك بالتحليل وأجاوبك من تقريرك وعقدك.";
const WELCOME_REPORT = "جاهز! حلّلت مشروعك وعقدك. اسألني عن أي بند، أو اضغط «اسأل بصِيـــرة» على أي خطر في التقرير.";
const GUIDE_CHIPS = ["وش أحتاج أجهّز؟", "وش الملفات المدعومة؟", "هل عقدي يتخزن؟"];
const REPORT_CHIPS = ["وش أخطر بند في تقريري؟", "كيف أفاوض على الزيادة؟", "وش أسأل المؤجر قبل التوقيع؟"];

const chat = { context: null, history: [], busy: false };   // context: { report, contractText, consent } أو null قبل التحليل

function scrollDown() {
  const box = $("messages");
  box.scrollTop = box.scrollHeight;
}

const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

function addMessage(kind, text, extra = {}) {
  const msg = el("div", `msg ${kind}`);
  const animate = extra.animate && !REDUCED && text.length > 0;
  const body = document.createTextNode(animate ? "" : text);
  msg.append(body);
  $("messages").append(msg);
  const finish = () => {
    if (extra.quote) {
      const quote = el("div", "quote");
      const label = el("b");
      label.append(icon("check"), document.createTextNode("موثّق من عقدك"));
      quote.append(label, document.createTextNode(extra.quote));
      msg.append(quote);
    }
    if (extra.label && !/AI/.test(extra.label)) msg.append(el("span", "tag", extra.label));
    scrollDown();
  };
  if (!animate) { finish(); } else {
    let shown = 0;   // الإجابة تنكتب حرف حرف
    const step = () => {
      shown = Math.min(text.length, shown + 3);
      body.nodeValue = text.slice(0, shown);
      scrollDown();
      if (shown < text.length) setTimeout(step, 14); else finish();
    };
    step();
  }
  scrollDown();
  return msg;
}

function typingBubble() {
  const msg = el("div", "msg bot");
  msg.setAttribute("aria-label", "بصِيـــرة تكتب");
  msg.append(logoSvg("typing-logo logo-anim"));
  $("messages").append(msg);
  scrollDown();
  return msg;
}

function renderSuggestions() {
  const box = $("suggest");
  box.replaceChildren();
  (chat.context ? REPORT_CHIPS : GUIDE_CHIPS).forEach((q) => {
    const b = el("button", "", q);
    b.type = "button";
    b.addEventListener("click", () => ask(q));
    box.append(b);
  });
  show(box, true);
}

/** نبدأ محادثة جديدة (عند فتح التطبيق أو تحليل جديد). */
export function resetChat() {
  chat.context = null;
  chat.history = [];
  $("messages").replaceChildren();
  addMessage("bot", WELCOME_GUIDE);
  renderSuggestions();
}

/** لما يطلع التقرير: بصِيـــرة تتحول من وضع الإرشاد لوضع الإجابة من التقرير والعقد. */
export function setReportContext(context) {
  chat.context = context;
  addMessage("bot", WELCOME_REPORT);
  renderSuggestions();
}

export async function ask(question) {
  question = question.trim();
  if (!question || chat.busy) return;
  chat.busy = true;
  $("chat").classList.add("busy");
  $("chat-send").disabled = true;
  show($("suggest"), false);
  addMessage("user", question);
  const typing = typingBubble();

  const ctx = chat.context;
  const result = await api.chat({
    question,
    history: chat.history.slice(-MAX_HISTORY),
    report: ctx ? ctx.report : {},
    contract_text: ctx && ctx.contractText ? ctx.contractText : null,
    consent: ctx ? ctx.consent : false,
  });
  typing.remove();
  if (result.ok) {
    const { answer, verified_quote: quote, label } = result.data;
    addMessage("bot", answer, { quote, label, animate: true });
    chat.history.push({ role: "user", content: question }, { role: "assistant", content: answer });
  } else {
    addMessage("error", result.errors[0]);
  }
  chat.busy = false;
  $("chat").classList.remove("busy");
  $("chat-send").disabled = false;
  $("chat-input").focus({ preventScroll: true });
}

export function initChat({ onAttach }) {
  resetChat();
  $("chat-attach").addEventListener("click", onAttach);
  $("composer").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const field = $("chat-input");
    const text = field.value;
    field.value = "";
    field.style.height = "";
    ask(text);
  });
  $("chat-input").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); $("composer").requestSubmit(); }
  });
  $("chat-input").addEventListener("input", (ev) => {
    ev.target.style.height = "auto";
    ev.target.style.height = `${Math.min(ev.target.scrollHeight, 120)}px`;
  });
}
