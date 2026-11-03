// تفاعل شاشة الإدخال: شريط التقدم، اختيارات سريعة، ونسبة الإيجار من الإيراد لحظياً.
import { $, el, icon, show, fmt } from "./dom.js";
import { hasContract } from "./input.js";

const MEDIUM = 10, HIGH = 15;   // نفس عتبات الباك اند (report.py)، يحرسها اختبار
const ACTIVITIES = ["مطعم", "كوفي", "صالة رياضية", "ورشة سيارات", "متجر", "صالون"];
const CITIES = ["الرياض", "جدة", "الدمام", "مكة", "المدينة", "الخبر"];
const SEV_LABEL = { high: "عالية", medium: "متوسطة", low: "منخفضة" };

function mountChips(field, values) {
  const box = document.querySelector(`.chips[data-for="${field}"]`);
  values.forEach((value) => {
    const chip = el("button", "", value);
    chip.type = "button";
    chip.addEventListener("click", () => { $(field).value = value; $(field).dispatchEvent(new Event("input")); });
    box.append(chip);
  });
}

function updateRatio() {
  const rent = parseFloat($("monthly_rent").value), revenue = parseFloat($("monthly_revenue").value);
  const box = $("ratio-live");
  if (!(rent > 0 && revenue > 0)) { show(box, false); return; }
  const pct = (rent / revenue) * 100;
  const sev = pct >= HIGH ? "high" : pct >= MEDIUM ? "medium" : "low";
  box.className = `ratio-live sev-${sev}`;
  box.replaceChildren(icon(sev), document.createTextNode(`إيجارك ${fmt(pct, 1)}% من إيرادك (${SEV_LABEL[sev]}). تقدير مبدئي قبل التحليل.`));
}

function updateProgress() {
  const dataOk = Boolean($("activity").value.trim() && $("city").value.trim());
  const contractOk = hasContract();
  const state = [dataOk ? "done" : "active", contractOk ? "done" : dataOk ? "active" : "", dataOk && contractOk ? "active" : ""];
  document.querySelectorAll("#progress li").forEach((li, i) => { li.className = state[i]; });
  $("progress").style.setProperty("--p", String((Number(dataOk) + Number(contractOk)) / 2));
  $("analyze").classList.toggle("ready", dataOk && contractOk);
}

export function initProgress() {
  mountChips("activity", ACTIVITIES);
  mountChips("city", CITIES);
  const update = () => { updateProgress(); updateRatio(); };
  ["activity", "city", "monthly_rent", "monthly_revenue"].forEach((id) => $(id).addEventListener("input", update));
  document.addEventListener("bassira:input", update);
  update();
}
