"""يولّد البوستر: يشغّل خادمًا محليًا مؤقتًا (عشان بطاقات المثال تُرسم بنفس كود الموقع) ثم يصوّر الصفحة.
التشغيل:  python3 docs/poster/render.py
"""
import pathlib, shutil, subprocess, tempfile, time, socket

root = pathlib.Path(__file__).resolve().parents[2]
here = root / "docs/poster"
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

tmp = pathlib.Path(tempfile.mkdtemp())
(tmp / "static").symlink_to(root / "app/static")
for name in ("poster.html", "demo-embed.html"):
    shutil.copy(here / name, tmp / name)
for extra in here.glob("*.svg"):
    shutil.copy(extra, tmp / extra.name)

s = socket.socket(); s.bind(("", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen(["python3", "-m", "http.server", str(port)], cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=3",
                    "--window-size=2000,1045", "--virtual-time-budget=20000", "--force-prefers-reduced-motion",
                    f"--screenshot={here / 'basira-poster.png'}", f"http://localhost:{port}/poster.html"],
                   check=True, capture_output=True)
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=20000",
                    "--force-prefers-reduced-motion", f"--print-to-pdf={here / 'basira-poster.pdf'}",
                    f"http://localhost:{port}/poster.html"], check=True, capture_output=True)
finally:
    srv.terminate()
print("تم:", here / "basira-poster.png")
