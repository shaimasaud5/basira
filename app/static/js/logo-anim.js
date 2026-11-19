// مصافحة شعار الخلفية: نثني المسار نفسه بدل ما نقصّه (لا حواف مقصوصة بالذراعين).
// منطقة اليدين تتحرك أكثر شي، والتأثير يخف تدريجيًا باتجاه نهايات الذراعين.
const CYCLE_MS = 5000;
const CX = 502, CY = 515, SIGMA = 165;          // مركز المصافحة بإحداثيات الشعار
const T = [0, 0.08, 0.16, 0.24, 0.32, 0.40, 0.48, 0.62, 1];
const DY = [0, -22, 10, -19, 9, -12, 4, 0, 0];  // ارتفاع/نزول
const DEG = [0, -3, 2.5, -2.5, 2, -1.5, 1, 0, 0]; // دوران خفيف
const FPS_MS = 1000 / 30;

function ease(a, b, u) { u = u * u * (3 - 2 * u); return a + (b - a) * u; }
function sample(vals, t) {
  for (let i = 0; i < T.length - 1; i++) {
    if (t >= T[i] && t <= T[i + 1]) return ease(vals[i], vals[i + 1], (t - T[i]) / (T[i + 1] - T[i]));
  }
  return vals[vals.length - 1];
}

function parse(d) {
  return d.split("M").filter(Boolean).map((chunk) => {
    const nums = chunk.match(/-?\d+(?:\.\d+)?/g).map(Number);
    return Float32Array.from(nums);
  });
}

function build(subs, weights, dy, deg) {
  const rad = (deg * Math.PI) / 180, out = [];
  for (let s = 0; s < subs.length; s++) {
    const p = subs[s], w = weights[s];
    let str = "";
    for (let i = 0, j = 0; i < p.length; i += 2, j++) {
      const k = w[j], x = p[i] - CX, y = p[i + 1] - CY, a = rad * k, c = Math.cos(a), sn = Math.sin(a);
      str += `${i ? "L" : "M"}${(x * c - y * sn + CX).toFixed(1)} ${(x * sn + y * c + CY + dy * k).toFixed(1)}`;
    }
    out.push(str + "Z");
  }
  return out.join("");
}

export async function initLogoAnim() {
  const svg = document.querySelector(".bg-logo");
  if (!svg || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  let d;
  try {
    const txt = await (await fetch("/static/logo.svg")).text();
    d = (txt.match(/<g id="frame"[^>]*><path[^>]*\sd="([^"]*)"/) || [])[1];
  } catch { return; }
  if (!d) return;

  const subs = parse(d);
  const weights = subs.map((p) => {
    const w = new Float32Array(p.length / 2);
    for (let i = 0, j = 0; i < p.length; i += 2, j++) {
      const dx = p[i] - CX, dyy = p[i + 1] - CY;
      w[j] = Math.exp(-(dx * dx + dyy * dyy) / (2 * SIGMA * SIGMA));
    }
    return w;
  });

  // نبدّل طبقتي الجسم الثابتتين بمسار واحد قابل للثني
  svg.querySelectorAll("use.frame, use.hands").forEach((u) => u.remove());
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("fill", "currentColor");
  path.setAttribute("fill-rule", "evenodd");
  path.setAttribute("d", build(subs, weights, 0, 0));
  svg.insertBefore(path, svg.firstChild);

  const t0 = performance.now();
  let last = 0, resting = true;
  const tick = (now) => {
    requestAnimationFrame(tick);
    if (document.hidden || now - last < FPS_MS) return;
    last = now;
    const t = ((now - t0) % CYCLE_MS) / CYCLE_MS;
    if (t > T[T.length - 3]) {                    // فترة الراحة
      if (!resting) { path.setAttribute("d", build(subs, weights, 0, 0)); resting = true; }
      return;
    }
    resting = false;
    path.setAttribute("d", build(subs, weights, sample(DY, t), sample(DEG, t)));
  };
  requestAnimationFrame(tick);
}
