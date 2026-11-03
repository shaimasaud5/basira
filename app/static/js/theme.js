// زر الوضع فاتح/غامق: الافتراضي وضع النظام، وإذا اختار المستخدم نحفظ اختياره بالمتصفح فقط.
import { $ } from "./dom.js";

const KEY = "bassira-theme";
const systemDark = matchMedia("(prefers-color-scheme: dark)");

const current = () => document.documentElement.dataset.theme || (systemDark.matches ? "dark" : "light");

function paint() {
  $("theme-toggle").dataset.mode = current();   // يعرض أيقونة الوضع اللي بنروح له: شمس بالغامق، قمر بالفاتح
}

export function initTheme() {
  paint();
  systemDark.addEventListener("change", paint);
  $("theme-toggle").addEventListener("click", () => {
    const next = current() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(KEY, next); } catch (e) { /* ما يهم لو ما انحفظ */ }
    paint();
  });
}
