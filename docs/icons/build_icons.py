"""يولّد أيقونات التبويب (PNG) من الشعار: Safari وبعض المتصفحات ما تعرض favicon بصيغة SVG بشكل موثوق.
التشغيل:  python3 docs/icons/build_icons.py
"""
import pathlib, re, subprocess, tempfile
root = pathlib.Path(__file__).resolve().parents[2]
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
svg = (root / "app/static/logo.svg").read_text()
svg = re.sub(r"<style>.*?</style>", "", svg, flags=re.S)
inner = svg.split(">", 1)[1].rsplit("</svg>", 1)[0]
VB = "104 206 816 599"

def page(size, bg, pad):
    inset = int(size * pad)
    return f"""<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:{bg};width:{size}px;height:{size}px;overflow:hidden}}
svg{{position:absolute;left:{inset}px;top:{inset}px;width:{size-2*inset}px;height:{size-2*inset}px;color:#0284c7}}</style>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VB}" preserveAspectRatio="xMidYMid meet">{inner}</svg>"""

jobs = [("favicon-32.png", 32, "transparent", 0.04), ("favicon-192.png", 192, "transparent", 0.06),
        ("apple-touch-icon.png", 180, "#ffffff", 0.16), ("icon-512.png", 512, "#ffffff", 0.16)]
out = root / "app/static/icons"
for name, size, bg, pad in jobs:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page(size, bg, pad)); path = f.name
    args = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
            f"--window-size={size},{size}", f"--screenshot={out / name}", f"file://{path}"]
    if bg == "transparent":
        args.insert(2, "--default-background-color=00000000")
    subprocess.run(args, check=True, capture_output=True)
    print("تم", name)
