import re, pathlib
root = pathlib.Path(__file__).resolve().parents[2]
logo = (root / "app/static/logo.svg").read_text()
logo = re.sub(r"<style>.*?</style>", "", logo, flags=re.S)
logo = logo.replace('<svg ', '<svg class="logo" ', 1)
logo_small = logo.replace('class="logo"', 'class="logo-s"', 1)

html = """<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>بوستر بصِيـــرة</title>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&family=Lalezar&display=swap" rel="stylesheet">
<style>
:root { --teal:#1f6f66; --ink:#14201e; --mint:#e7f3f0; --glow:#f2faf8; --bg:#eceef1; --surface:#ffffff; --surface2:#f4f5f7; --line:#dadde2; --ink-d:#14201e; --ink2:#4a5560; --ink3:#7a858f; --brand:#3fc1b3; --onbrand:#06201d; }
* { box-sizing: border-box; margin:0; padding:0; }
html, body { width: 2000px; height: 1045px; background: var(--mint); font-family: "Tajawal", sans-serif; overflow: hidden; }
.poster { position: relative; width: 2000px; height: 1045px; background: radial-gradient(900px 600px at 1450px 300px, var(--glow), transparent 70%), var(--mint); }

/* ---- الجهة اليمنى: الهوية ---- */
.logo { position:absolute; left: 1230px; top: 70px; width: 440px; height: auto; color: var(--teal); }
.logo-s { color: var(--brand); height: 34px; width: auto; }
.word { position:absolute; right: 70px; left: 980px; top: 360px; text-align: center; font-family: "Lalezar", sans-serif; font-size: 330px; line-height: 1.05; color: var(--teal); letter-spacing: 0; }
.tag { position:absolute; right: 70px; left: 980px; top: 760px; text-align:center; font-weight: 800; font-size: 52px; color: var(--ink); line-height: 1.3; }
.sub { position:absolute; right: 70px; left: 980px; top: 925px; text-align:center; white-space: nowrap; font-weight: 500; font-size: 29px; color: #5b6b68; line-height: 1.5; }

/* ---- الجوالات ---- */
.phone { position:absolute; width: 400px; height: 820px; border-radius: 62px; background: #d6dadf; padding: 14px; box-shadow: 0 30px 60px rgba(20,40,60,.18), 0 0 0 2px #c3c8ce inset; }
.phone .scr { position:relative; width:100%; height:100%; border-radius: 50px; overflow:hidden; background: var(--bg); color: var(--ink-d); direction: rtl; }
.island { position:absolute; top: 14px; left: 50%; transform: translateX(-50%); width: 120px; height: 34px; border-radius: 20px; background:#000; z-index: 5; }
.status { position:absolute; top: 18px; left: 30px; right: 30px; display:flex; justify-content: space-between; font-size: 17px; font-weight: 700; direction: ltr; z-index: 4; }
.bar { position:absolute; top: 62px; left:0; right:0; height: 58px; display:flex; align-items:center; gap: 10px; padding: 0 22px; border-bottom: 1px solid var(--line); }
.bar .nm { font-family: "Lalezar", sans-serif; font-size: 30px; color: var(--brand); line-height: 1; }
.body { position:absolute; top: 134px; left: 18px; right: 18px; bottom: 18px; display:flex; flex-direction: column; gap: 12px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 22px; padding: 16px 18px; box-shadow: 0 2px 8px rgba(20,40,60,.06); }
.card h4 { font-size: 15px; font-weight: 700; color: var(--ink2); text-align:center; margin-bottom: 4px; }
.big { font-size: 40px; font-weight: 800; line-height: 1.1; }
.big small { font-size: 17px; font-weight: 600; color: var(--ink2); margin-inline-start: 6px; }
.lbl { font-size: 15px; font-weight: 700; color: var(--ink2); margin-bottom: 4px; }
.note { font-size: 14px; color: var(--ink3); margin-top: 2px; }
.gauge { display:block; margin: 0 auto; width: 250px; }
.pct { text-align:center; font-size: 48px; font-weight: 800; margin-top: -58px; position: relative; }
.pct small { font-size: 20px; font-weight: 700; color: var(--ink2); }
.sev { text-align:center; font-size: 16px; font-weight: 700; margin: 6px 0 4px; color: var(--ink-d); }
.sub2 { text-align:center; font-size: 14px; color: var(--ink2); }
.risk { border-inline-start: 5px solid #c0524a; }
.risk .chip { display:inline-flex; gap:8px; align-items:center; font-size: 14px; font-weight: 700; color:#b8443d; }
.risk h5 { font-size: 20px; font-weight: 800; margin: 6px 0 4px; line-height: 1.4; }
.risk p { font-size: 14px; color: var(--ink2); line-height: 1.7; }

/* الشات */
.msgs { flex:1; display:flex; flex-direction: column; gap: 12px; padding-top: 8px; }
.m { max-width: 88%; padding: 12px 16px; border-radius: 20px; font-size: 18px; line-height: 1.65; }
.m.bot { align-self: flex-end; background: var(--surface); border: 1px solid var(--line); border-inline-start: 4px solid var(--brand); border-end-end-radius: 6px; }
.m.user { align-self: flex-start; background: var(--brand); color: var(--onbrand); font-weight: 700; border-end-start-radius: 6px; }
.chips { display:flex; gap:8px; flex-wrap: wrap; justify-content: flex-end; }
.chips span { border: 1px solid var(--line); background: var(--surface); border-radius: 999px; padding: 8px 14px; font-size: 15px; font-weight: 700; color: var(--ink2); }
.comp { display:flex; align-items:center; gap: 10px; border: 1.5px solid color-mix(in srgb, var(--brand) 60%, transparent); border-radius: 999px; background: var(--surface); padding: 8px 10px 8px 14px; }
.comp .in { flex:1; font-size: 16px; color: var(--ink3); }
.comp .snd { width: 38px; height: 38px; border-radius: 50%; background: var(--brand); display:grid; place-items:center; color: var(--onbrand); }
.dot { width:8px; height:8px; border-radius:50%; background:#5fd07f; display:inline-block; margin-inline-end:6px; }
.hsub { font-size: 13px; color: var(--ink2); }
.home { position:absolute; bottom: 8px; left: 50%; transform: translateX(-50%); width: 130px; height: 5px; border-radius: 3px; background: #9aa1a9; opacity:.8; }
</style></head><body>
<div class="poster">

  __LOGO__
  <div class="word">بصِيـــرة</div>
  <div class="tag">مساعد رواد الأعمال الذكي<br>لفهم عقد الإيجار قبل التوقيع</div>
  <div class="sub">يكشف لك المخاطر والالتزامات المالية بالأرقام وبأدلة من بنود العقد</div>

  <!-- جوال 1: التقرير -->
  <div class="phone" style="left: 90px; top: 110px;">
    <div class="scr">
      <div class="island"></div>
      <div class="status"><span>9:41</span><span>5G ▮▮▮</span></div>
      <div class="bar">__LOGO_S__<span class="nm">بصِيـــرة</span></div>
      <div class="body">
        <div class="card">
          <h4>نسبة الإيجار من إيرادك</h4>
          <svg class="gauge" viewBox="0 0 250 135">
            <path d="M25 125 A100 100 0 0 1 90 31" fill="none" stroke="#dc9b97" stroke-width="22"/>
            <path d="M99 28 A100 100 0 0 1 150 28" fill="none" stroke="#f0cd72" stroke-width="22"/>
            <path d="M159 31 A100 100 0 0 1 225 125" fill="none" stroke="#86c987" stroke-width="22"/>
            <circle cx="46" cy="92" r="11" fill="#c8453f" stroke="#ffffff" stroke-width="4"/>
          </svg>
          <div class="pct">25<small>%</small></div>
          <div class="sev">نسبة عالية</div>
          <div class="sub2"><b>15,000 ريال</b> إيجار شهري من <b>60,000 ريال</b> إيراد شهري</div>
        </div>
        <div class="card"><div class="lbl">إجمالي التزام الإيجار</div><div class="big">360,000<small>ريال</small></div><div class="note">على مدى 24 شهر</div></div>
        <div class="card"><div class="lbl">الإيجار بعد الزيادة</div><div class="big">16,125<small>ريال/شهر</small></div><div class="note">+1,125 شهريًا (7.5%)</div></div>
        <div class="card risk"><span class="chip">▮▮▯ خطورة عالية</span><h5>الإيجار يأخذ جزء كبير من الإيراد</h5><p>الإيجار ثابت يُدفع كل شهر سواء بعت أو لا.</p></div>
      </div>
      <div class="home"></div>
    </div>
  </div>

  <!-- جوال 2: المحادثة -->
  <div class="phone" style="left: 520px; top: 110px;">
    <div class="scr">
      <div class="island"></div>
      <div class="status"><span>5:26</span><span>5G ▮▮▮</span></div>
      <div class="bar">__LOGO_S__<div><div class="nm">بصِيـــرة</div></div><span class="hsub" style="margin-inline-start:auto"><i class="dot"></i>جاهز يجاوبك</span></div>
      <div class="body">
        <div class="msgs">
          <div class="m bot">هلا! أنا بصِيـــرة، مساعدك في عقد إيجار مشروعك.</div>
          <div class="m user">هل يحتوي عقدي على مخاطر؟</div>
          <div class="m bot">لاحظت وجود بند يستحق المراجعة قبل التوقيع: الإيجار يرتفع 7.5% عند كل تجديد، وهذا مثبّت في العقد.</div>
          <div class="m user">وش أسوي عشان أخفف الخطر؟</div>
          <div class="m bot">تفاوض على سقف للزيادة قبل التوقيع، وبعدها نحسب أثرها على إيرادك بالأرقام.</div>
        </div>
        <div class="chips"><span>وش أحتاج أجهّز؟</span><span>هل عقدي يتخزن؟</span></div>
        <div class="comp"><div class="snd">➤</div><div class="in">اكتب سؤالك هنا...</div></div>
      </div>
      <div class="home"></div>
    </div>
  </div>

</div></body></html>
"""
html = html.replace("__LOGO__", logo).replace("__LOGO_S__", logo_small)
PALETTES = {
    # السماوي المعتمد: نفس ألوان الموقع (فاتح: #0284c7 / غامق: #7dd3fc)
    "": dict(teal="#0284c7", mint="#e6f3fb", glow="#f3faff", brand="#0284c7", onbrand="#ffffff"),
}
for name, c in PALETTES.items():
    h = html
    for k, v in c.items():
        h = re.sub(r"(--%s:)#[0-9a-fA-F]{6}" % k, lambda m: m.group(1) + v, h, count=1)
    (root / "docs/poster/basira-poster.html").write_text(h)
print("ok")
