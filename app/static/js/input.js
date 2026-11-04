// مرحلة الإدخال: بيانات المشروع + رفع العقد + معاينة "وش بنرسل".
import { $, el, icon, show } from "./dom.js";
import * as api from "./api.js";

const MAX_BYTES = 5 * 1024 * 1024;
const REDACTION_LABELS = { mobile: "جوال", iban: "آيبان", national_id: "هوية أو إقامة", email: "إيميل" };
const FIELDS = ["activity", "city", "monthly_rent", "monthly_revenue", "lease_months"];

const input = { fileName: "", previewText: "" };   // الحالة بالذاكرة فقط
const notify = () => document.dispatchEvent(new Event("bassira:input"));
export const hasContract = () => Boolean(input.previewText.trim());

export function showErrors(messages, kind = "error") {
  const box = $("input-errors");
  box.replaceChildren();
  if (!messages || !messages.length) { show(box, false); return; }
  const banner = el("div", `banner ${kind}`);
  banner.append(icon(kind === "error" ? "high" : "medium"));
  const list = el("ul");
  messages.forEach((m) => list.append(el("li", "", m)));
  banner.append(list);
  box.append(banner);
  show(box, true);
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function sizeLabel(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} ميغابايت` : `${Math.max(1, Math.round(bytes / 1024))} كيلوبايت`;
}

const REDACTION_TAGS = { mobile: "[جوال]", iban: "[آيبان]", national_id: "[هوية]", email: "[بريد]" };
const TAG_SPLIT = /(\[(?:جوال|آيبان|هوية|بريد)\])/;
const MAX_SNIPPETS = 6;
const SNIPPET_CHARS = 90;

const countOf = (text, tag) => text.split(tag).length - 1;

/** سطر من النص حول العلامة، مع تمييز العلامة نفسها (بدون HTML جاهز). */
function snippetOf(line, tag) {
  const at = line.indexOf(tag);
  const from = Math.max(0, at - Math.floor((SNIPPET_CHARS - tag.length) / 2));
  const end = from + SNIPPET_CHARS;
  const slice = `${from > 0 ? "… " : ""}${line.slice(from, end).trim()}${end < line.length ? " …" : ""}`;
  const box = el("span", "ctx");
  slice.split(TAG_SPLIT).forEach((part) => {
    box.append(TAG_SPLIT.test(part) ? el("mark", "", part) : document.createTextNode(part));
  });
  return box;
}

/** الملخص كله يُحسب من النص نفسه، فيتحدث تلقائياً لو عدّل المستخدم. */
function drawSummary() {
  const text = $("preview-text").value;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const found = Object.entries(REDACTION_TAGS)
    .map(([kind, tag]) => [kind, tag, countOf(text, tag)])
    .filter(([, , n]) => n > 0);
  const total = found.reduce((sum, [, , n]) => sum + n, 0);

  $("ss-line").textContent = total
    ? `نرسل عقدك (${words.toLocaleString("en-US")} كلمة) بعد إخفاء ${total} من البيانات الشخصية.`
    : `نرسل عقدك (${words.toLocaleString("en-US")} كلمة). ما لقينا جوال أو آيبان أو هوية ظاهرة.`;

  const stats = $("preview-stats");
  stats.replaceChildren();
  found.forEach(([kind, , n]) => {
    const pill = el("span", "pill ok", `${n} ${REDACTION_LABELS[kind]}`);
    pill.prepend(icon("check"));
    stats.append(pill);
  });

  const list = $("redact-list");
  list.replaceChildren();
  let shown = 0;
  let extra = 0;
  text.split("\n").forEach((line) => {
    const kinds = found.filter(([, tag]) => line.includes(tag));
    if (!kinds.length) return;
    if (shown >= MAX_SNIPPETS) { extra += 1; return; }
    const row = el("li");
    row.append(el("span", "kind", kinds.map(([kind]) => REDACTION_LABELS[kind]).join(" + ")), snippetOf(line, kinds[0][1]));
    list.append(row);
    shown += 1;
  });
  if (extra) list.append(el("li", "more", `و${extra} مواضع أخرى`));
  show($("redact-block"), total > 0);
}

function renderPreview(data) {
  input.previewText = data.text;
  $("preview-text").value = data.text;
  drawSummary();
  show($("preview"), true);
  show($("trustline"), true);
  notify();
}

function resetFile() {
  input.fileName = "";
  input.previewText = "";
  $("consent").checked = false;
  $("file-input").value = "";
  $("preview-text").value = "";
  show($("file-area"), false);
  show($("drop-area"), true);
  show($("preview"), false);
  show($("trustline"), false);
  notify();
}

function beginFile(name) {
  input.fileName = name;
  $("file-name").textContent = name;
  $("file-state").textContent = "جاري قراءة الملف وإخفاء البيانات الحساسة...";
  show($("drop-area"), false);
  show($("file-area"), true);
  show($("preview"), false);
  show($("trustline"), false);
}

async function handleFile(file) {
  showErrors([]);
  const name = file.name.toLowerCase();
  if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
    showErrors(["نوع الملف غير مدعوم. ارفع PDF أو Word (بصيغة docx)."]);
    return;
  }
  if (file.size > MAX_BYTES) {
    showErrors(["الملف كبير. الحد 5 ميغابايت."]);
    return;
  }
  beginFile(file.name);
  const result = await api.previewFile(file);
  if (!result.ok) { resetFile(); showErrors(result.errors); return; }
  $("file-state").textContent = `${sizeLabel(file.size)} · جاهز للتحليل`;
  renderPreview(result.data);
}

function payload() {
  const body = Object.fromEntries(FIELDS.map((id) => [id, $(id).value.trim()]));
  const text = $("preview-text").value.trim();
  // الموافقة صريحة: المستخدم يؤشر على سياسة الإرسال قبل التحليل
  return { ...body, contract_text: text, consent: Boolean(text) && $("consent").checked };
}

export function openFilePicker() { $("file-input").click(); }
export function attachFile(file) { return handleFile(file); }

export function resetInput() {
  FIELDS.forEach((id) => { $(id).value = ""; });
  resetFile();
  showErrors([]);
}

export async function initInput({ onSubmit }) {
  // الرفع: ضغط، سحب وإفلات، أو لوحة المفاتيح
  const zone = $("dropzone");
  zone.addEventListener("click", openFilePicker);
  zone.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openFilePicker(); } });
  ["dragover", "dragenter"].forEach((t) => zone.addEventListener(t, (ev) => { ev.preventDefault(); zone.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => zone.addEventListener(t, () => zone.classList.remove("over")));
  zone.addEventListener("drop", (ev) => { ev.preventDefault(); const f = ev.dataTransfer.files[0]; if (f) handleFile(f); });
  $("file-input").addEventListener("change", (ev) => { const f = ev.target.files[0]; if (f) handleFile(f); });
  $("file-remove").addEventListener("click", resetFile);
  $("preview-text").addEventListener("input", () => { input.previewText = $("preview-text").value; drawSummary(); notify(); });

  $("analyze").addEventListener("click", async () => {
    showErrors([]);
    const body = payload();
    const missing = [];
    if (!body.activity) missing.push("نوع النشاط مطلوب.");
    if (!body.city) missing.push("المدينة مطلوبة.");
    if (!body.contract_text) missing.push("ارفع عقد الإيجار أول، هو أساس التحليل.");
    else if (!body.consent) missing.push("وافق على سياسة إرسال العقد للتحليل قبل المتابعة.");
    if (missing.length) { showErrors(missing); return; }
    const result = await onSubmit(body);
    if (!result.ok) showErrors(result.errors);
  });
}
