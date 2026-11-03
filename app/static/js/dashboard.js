// الداش بورد: ملخص (مقياس نصف دائري + أرقام) ثم المخاطر كبطاقات، والتفاصيل في نافذة.
// ألوان الحالة ثابتة (أحمر/كهرماني/أخضر) وتظهر دايماً مع أيقونة وكلمة، والنص بلون الحبر.
import { el, icon, fmt, countUp } from "./dom.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const SEV_LABEL = { high: "عالية", medium: "متوسطة", low: "منخفضة" };
const SEV_ORDER = ["high", "medium", "low"];
const CATEGORY = { financial: "مالي", contract: "عقد", operational: "تشغيلي" };
const TOP_VISIBLE = 4;            // عدد المخاطر الظاهرة قبل «عرض الكل»
const GAUGE_SCALE_FACTOR = 1.7;   // المقياس يمتد لما بعد الحد الأعلى بهالنسبة
const GAUGE = { w: 260, h: 150, cx: 130, cy: 128, r: 100 };

const severityOfRatio = (pct, t) => (pct >= t.high ? "high" : pct >= t.medium ? "medium" : "low");
const sevVar = (sev) => `var(--${sev === "high" ? "crit" : sev === "medium" ? "warn" : "good"})`;
const svg = (tag, attrs = {}) => {
  const node = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, String(v)));
  return node;
};

/** نقطة على القوس: 0 عند اليمين (نسبة منخفضة) و1 عند اليسار (مرتفعة)، لأن الصفحة من اليمين لليسار. */
const arcPoint = (f, r = GAUGE.r) => [GAUGE.cx + r * Math.cos(f * Math.PI), GAUGE.cy - r * Math.sin(f * Math.PI)];

function emptyState(box, message, action) {
  box.append(el("div", "empty", message));
  if (action) {
    const b = el("button", "btn sm", action.label);
    b.type = "button";
    b.style.marginTop = "8px";
    b.addEventListener("click", action.run);
    box.append(b);
  }
}

/** مقياس نصف دائري بثلاث مناطق (مريحة/حذرة/مرتفعة) وعلامة تتحرك لنسبتك. */
function gaugeBlock(pct, t, sev) {
  const scale = Math.max(Math.ceil((t.high * GAUGE_SCALE_FACTOR) / 10) * 10, Math.ceil((pct + 5) / 10) * 10);
  const f = (v) => Math.min(1, v / scale);
  const box = el("div", "gauge");
  const s = svg("svg", { viewBox: `0 0 ${GAUGE.w} ${GAUGE.h}`, role: "meter", "aria-valuemin": 0, "aria-valuemax": scale, "aria-valuenow": pct,
    "aria-valuetext": `${fmt(pct, 1)}% من الإيراد، ${SEV_LABEL[sev]}` });
  [["low", 0, t.medium], ["medium", t.medium, t.high], ["high", t.high, scale]].forEach(([zone, from, to]) => {
    const gap = 0.012;
    const [x1, y1] = arcPoint(f(from) + (from ? gap : 0));
    const [x2, y2] = arcPoint(f(to) - (to < scale ? gap : 0));
    s.append(svg("path", { class: `gz gz-${zone}`, d: `M ${x1} ${y1} A ${GAUGE.r} ${GAUGE.r} 0 0 0 ${x2} ${y2}` }));
  });
  [t.medium, t.high].forEach((v) => {
    const [x, y] = arcPoint(f(v), GAUGE.r + 22);
    const label = svg("text", { class: "gtick", x, y, "text-anchor": "middle", "dominant-baseline": "middle" });
    label.textContent = `${v}%`;
    s.append(label);
  });
  const marker = svg("circle", { class: "gmarker", r: 12 });
  const place = (frac) => { const [x, y] = arcPoint(frac); marker.setAttribute("cx", x); marker.setAttribute("cy", y); };
  place(0);
  s.append(marker);
  const target = f(pct);
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) place(target);
  else {
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - start) / 1000);
      place(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  box.append(s);

  const center = el("div", "gauge-center");
  const figure = el("div", "hero-figure");
  const num = el("span");
  countUp(num, pct, 1);
  figure.append(num, el("small", "", "%"));
  center.append(figure);
  box.append(center);
  return box;
}

function stat(label, valueNode, sub) {
  const row = el("div", "stat");
  row.append(el("span", "label", label), valueNode);
  if (sub) row.append(sub);
  return row;
}

function bigValue(to, digits, unit) {
  const value = el("div", "value");
  const num = el("span");
  countUp(num, to, digits);
  value.append(num, el("small", "", unit));
  return value;
}

/** بطاقة الملخص: المقياس على جنب، وأرقام العقد على الجنب الثاني. */
function summaryCard(metrics, cards, onEdit) {
  const box = el("section", "summary");
  box.setAttribute("aria-label", "ملخص التقرير");

  const left = el("div", "sum-gauge");
  left.append(el("span", "label", "نسبة الإيجار من إيرادك"));
  const pct = metrics.rent_to_revenue_pct;
  if (pct == null) {
    emptyState(left, "أضف الإيجار والإيراد الشهري لعرض النسبة.", { label: "أضف البيانات", run: onEdit });
  } else {
    const t = metrics.ratio_thresholds;
    const sev = severityOfRatio(pct, t);
    box.style.setProperty("--meter", sevVar(sev));
    const state = el("div", `state sev-${sev}`);
    state.append(icon(sev), document.createTextNode(`نسبة ${SEV_LABEL[sev]}`));
    const caption = el("div", "hero-caption");
    caption.append(el("b", "", `${fmt(metrics.monthly_rent)} ريال`), document.createTextNode(" إيجار شهري من "),
      el("b", "", `${fmt(metrics.monthly_revenue)} ريال`), document.createTextNode(" إيراد شهري"));
    left.append(gaugeBlock(pct, t, sev), state, caption);
  }

  const right = el("div", "sum-stats");
  if (metrics.total_commitment == null) {
    const empty = el("div", "stat");
    empty.append(el("span", "label", "إجمالي التزام الإيجار"));
    emptyState(empty, "أضف الإيجار ومدة العقد.", { label: "أضف البيانات", run: onEdit });
    right.append(empty);
  } else {
    right.append(stat("إجمالي التزام الإيجار", bigValue(metrics.total_commitment, 0, "ريال"),
      el("div", "sub", `على مدى ${fmt(metrics.lease_months)} شهر`)));
  }
  if (metrics.rent_after_increase == null) {
    const none = el("div", "stat");
    none.append(el("span", "label", "الإيجار بعد الزيادة"), el("div", "empty", "ما لقينا بند زيادة مؤكد في العقد."));
    right.append(none);
  } else {
    const sub = el("div", "sub");
    sub.append(icon("trend"), document.createTextNode(
      `+${fmt(metrics.monthly_extra_after_increase, 2)} شهرياً (${fmt(metrics.increase_pct, 1)}%)`));
    right.append(stat("الإيجار بعد الزيادة", bigValue(metrics.rent_after_increase, 2, "ريال/شهر"), sub));
  }

  const counts = el("div", "stat counts");
  counts.append(el("span", "label", "المخاطر في عقدك"));
  const row = el("div", "count-row");
  SEV_ORDER.forEach((sev) => {
    const n = cards.filter((c) => c.severity === sev).length;
    const item = el("span", `cnt sev-${sev}`);
    const ico = el("span", "sev-ico");
    ico.append(icon(sev));
    item.append(ico, el("b", "", String(n)), el("span", "", SEV_LABEL[sev]));
    row.append(item);
  });
  counts.append(row);
  right.append(counts);

  box.append(left, right);
  return box;
}

const SEV_LEVEL = { high: 3, medium: 2, low: 1 };
const showTrust = (card, isAi) => !isAi && Boolean(card.trust_label) && card.trust_label.includes("موثّق");   // نعرض علامة «موثّق» فقط

function firstSentence(text, limit = 130) {
  const first = String(text).split(/(?<=[.!؟])\s/)[0].trim();
  return first.length > limit ? first.slice(0, limit - 1).trimEnd() + "…" : first;
}

/** ثلاث شرائح تُملأ حسب الخطورة (3 عالية، 2 متوسطة، 1 منخفضة). */
function levelBars(severity) {
  const bars = el("span", "levelbars");
  bars.setAttribute("aria-hidden", "true");
  for (let i = 1; i <= 3; i += 1) bars.append(el("i", i <= SEV_LEVEL[severity] ? "on" : ""));
  return bars;
}

/** بطاقة خطر: أيقونة وخطورة وعنوان وسطر واحد، والتفاصيل في نافذة. */
function riskCard(card, isAi, openDetail) {
  const box = el("article", `rcard sev-${card.severity}`);
  const top = el("div", "rc-top");
  const ico = el("span", "sev-ico");
  ico.append(icon(card.severity));
  const word = el("span", "sev-chip");
  word.append(levelBars(card.severity), document.createTextNode(SEV_LABEL[card.severity] || card.severity));
  top.append(ico, word);
  top.append(el("span", "pill cat", CATEGORY[card.category] || card.category));

  const more = el("button", "rc-more");
  more.type = "button";
  more.append(document.createTextNode("التفاصيل"), icon("arrow"));
  more.addEventListener("click", () => openDetail(card, isAi));

  const foot = el("div", "rc-foot");
  if (showTrust(card, isAi)) {
    const trust = el("span", "trust");
    trust.append(icon("check"), document.createTextNode(card.trust_label));
    foot.append(trust);
  }
  foot.append(more);
  box.append(top, el("h3", "", card.title), el("p", "rc-why", firstSentence(card.why)), foot);
  return box;
}

/** نافذة التفاصيل: ليش هو خطر، وش أسوي، الدليل من العقد. */
function detailDialog(onAsk) {
  const dlg = el("dialog", "risk-dialog");
  dlg.setAttribute("aria-label", "تفاصيل الخطر");
  dlg.addEventListener("click", (ev) => { if (ev.target === dlg) dlg.close(); });
  const fill = (card, isAi) => {
    dlg.replaceChildren();
    dlg.className = `risk-dialog sev-${card.severity}`;
    const head = el("div", "dlg-head");
    const ico = el("span", "sev-ico lg");
    ico.append(icon(card.severity));
    const titles = el("div");
    const sev = el("span", "sev-chip");
    sev.append(levelBars(card.severity), document.createTextNode(`خطورة ${SEV_LABEL[card.severity] || card.severity} · ${CATEGORY[card.category] || card.category}`));
    titles.append(sev, el("h3", "", card.title));
    const close = el("button", "btn ghost icon-btn");
    close.type = "button";
    close.setAttribute("aria-label", "إغلاق");
    close.append(icon("x"));
    close.addEventListener("click", () => dlg.close());
    head.append(ico, titles, close);

    const why = el("section", "dlg-block");
    why.append(el("h4", "", "ليش هو خطر"), el("p", "", card.why));
    const act = el("section", "dlg-block act");
    act.append(el("h4", "", "وش أسوي"), el("p", "", card.recommendation));
    const proof = el("section", "dlg-block");
    proof.append(el("h4", "", "الدليل"), el("blockquote", "evidence", card.evidence));

    const foot = el("div", "dlg-foot");
    if (showTrust(card, isAi)) {
      const trust = el("span", "trust");
      trust.append(icon("check"), document.createTextNode(card.trust_label));
      foot.append(trust);
    }
    const ask = el("button", "btn primary", "اسأل بصِيـــرة عن هذا الخطر");
    ask.type = "button";
    ask.prepend(icon("chat"));
    ask.addEventListener("click", () => { dlg.close(); onAsk(`اشرح لي خطر «${card.title}» وكيف أتعامل معه؟`); });
    foot.append(ask);
    dlg.append(head, why, act, proof, foot);
  };
  return { dlg, open(card, isAi) { fill(card, isAi); dlg.showModal(); } };
}

/** قسم بعنوان واضح: أيقونة + عنوان + عدد + سطر شرح (وأدوات اختيارية على الجانب). */
function section(iconName, title, count, hint, tools) {
  const box = el("section", "dsec");
  const head = el("header", "dsec-head");
  const ico = el("span", "dsec-ico");
  ico.append(icon(iconName));
  const text = el("div", "dsec-text");
  const h = el("h2", "", title);
  if (count !== null) h.append(el("span", "count", String(count)));
  text.append(h);
  if (hint) text.append(el("p", "hint", hint));
  head.append(ico, text);
  if (tools) head.append(tools);
  const body = el("div", "dsec-body");
  box.append(head, body);
  return { box, body };
}

export function renderDashboard(root, report, project, hooks) {
  root.replaceChildren();
  const m = report.metrics || {};
  // المخاطر الأساسية + توصيات الذكاء الاصطناعي في قائمة وحدة، الأخطر أولاً
  const cards = [...report.top, ...report.more, ...(report.ai_suggestions || [])]
    .map((card, i) => [card, i])
    .sort((a, b) => SEV_ORDER.indexOf(a[0].severity) - SEV_ORDER.indexOf(b[0].severity) || a[1] - b[1])
    .map(([card]) => card);
  const detail = detailDialog(hooks.onAsk);

  // الرأس
  const head = el("div", "dash-head");
  head.append(el("h1", "", "تقرير مخاطر عقدك"));
  const edit = el("button", "btn sm", "تعديل البيانات");
  edit.type = "button";
  edit.addEventListener("click", hooks.onEdit);
  head.append(edit);
  root.append(head);

  (report.warnings || []).forEach((w) => {
    const banner = el("div", "banner note");
    banner.append(icon("medium"), el("span", "", w));
    root.append(banner);
  });

  root.append(summaryCard(m, cards, hooks.onEdit));

  // المخاطر (أهم 4 تظهر، والباقي بزر، وفلتر حسب الخطورة)
  const counts = Object.fromEntries(SEV_ORDER.map((s) => [s, cards.filter((c) => c.severity === s).length]));
  const filters = el("div", "filters");
  filters.setAttribute("role", "group");
  filters.setAttribute("aria-label", "تصفية المخاطر حسب الخطورة");
  const risks = section("shield", cards.length > TOP_VISIBLE ? "أهم المخاطر" : "المخاطر", cards.length,
    "المخاطر اللي لقيناها في عقدك، الأخطر أولاً. اضغط «التفاصيل» لتعرف وش تسوي.", filters);
  const grid = el("div", "risk-grid");
  risks.body.append(grid);
  let active = null;
  let expanded = false;
  const draw = () => {
    grid.replaceChildren();
    const shown = active ? cards.filter((c) => c.severity === active) : cards;
    if (!shown.length) {
      const empty = el("div", "empty-state wide");
      empty.append(icon("low"), el("b", "", cards.length ? `ما فيه مخاطر بخطورة ${SEV_LABEL[active]}` : "ما قدرنا نطلع مخاطر من البيانات الحالية"),
        el("span", "", cards.length ? "هذا خبر زين. تقدر تشوف بقية المخاطر من الزر تحت." : "أضف الإيجار والإيراد أو ارفع العقد وأعد التحليل."));
      if (cards.length) {
        const all = el("button", "btn sm", "عرض كل المخاطر");
        all.type = "button";
        all.addEventListener("click", () => filters.querySelector(".fchip").click());
        empty.append(all);
      }
      grid.append(empty);
    }
    const visible = active || expanded ? shown : shown.slice(0, TOP_VISIBLE);
    visible.forEach((c) => grid.append(riskCard(c, false, detail.open)));
    if (visible.length < shown.length) {
      const more = el("button", "showall wide", `عرض كل المخاطر (${shown.length})`);
      more.type = "button";
      more.addEventListener("click", () => { expanded = true; draw(); });
      grid.append(more);
    }
  };
  const chips = [[null, "الكل", cards.length], ...SEV_ORDER.map((sev) => [sev, SEV_LABEL[sev], counts[sev]])];
  chips.forEach(([sev, label, n]) => {
    const chip = el("button", `fchip${sev ? ` sev-${sev}` : ""}`);
    chip.type = "button";
    chip.setAttribute("aria-pressed", String(sev === null));
    if (sev) chip.append(icon(sev));
    chip.append(document.createTextNode(`${label} ${n}`));
    chip.addEventListener("click", () => {
      active = sev;
      filters.querySelectorAll(".fchip").forEach((c) => c.setAttribute("aria-pressed", String(c === chip)));
      draw();
    });
    filters.append(chip);
  });
  root.append(risks.box);
  draw();

  root.append(el("div", "disclaimer", report.disclaimer), detail.dlg);
}
