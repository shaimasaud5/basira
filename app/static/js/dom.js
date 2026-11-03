// أدوات صغيرة لبناء الواجهة. كل النصوص (من المستخدم أو الموديل) تدخل بـ textContent فقط، ما نستخدم HTML جاهز.
const SVG_NS = "http://www.w3.org/2000/svg";

export const $ = (id) => document.getElementById(id);

export function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

/** أيقونة من الـ sprite في index.html (مثل icon("high")). */
export function icon(name, cls = "i") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", cls);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

const LOGO_PARTS = [["", "frame"], ["t t1", "l1"], ["t t2", "l2"], ["t t3", "l3"], ["hands", "hands"]];

/** شعار بصيرة بطبقاته (للتحريك). */
export function logoSvg(cls) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", cls);
  svg.setAttribute("viewBox", "23 55 491 591");
  svg.setAttribute("aria-hidden", "true");
  LOGO_PARTS.forEach(([c, id]) => {
    const use = document.createElementNS(SVG_NS, "use");
    if (c) use.setAttribute("class", c);
    use.setAttribute("href", `/static/logo.svg#${id}`);
    svg.append(use);
  });
  return svg;
}

/** يعدّ الرقم من الصفر للقيمة النهائية (بدون حركة لو المستخدم يفضّل تقليلها). */
export function countUp(node, to, digits = 0, ms = 800) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { node.textContent = fmt(to, digits); return; }
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min(1, (now - start) / ms);
    node.textContent = fmt(to * (1 - Math.pow(1 - t, 3)), digits);
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

export const show = (node, visible = true) => node.classList.toggle("hidden", !visible);

/** أرقام لاتينية مفصولة بفواصل (نفس شكل أرقام التقرير). */
export const fmt = (n, digits = 0) =>
  Number(n).toLocaleString("en-US", { maximumFractionDigits: digits });
