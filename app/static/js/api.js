// الاتصال بالسيرفر. كل دالة ترجّع { ok, data } أو { ok: false, errors } برسائل عربية جاهزة للعرض.
const GENERIC_ERROR = "صار خطأ غير متوقع في السيرفر. جرّب مرة ثانية بعد شوي.";
const NETWORK_ERROR = "تعذّر الاتصال بالسيرفر. تأكد من الإنترنت وجرّب مرة ثانية.";

async function send(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (e) {
    return { ok: false, errors: [NETWORK_ERROR] };
  }
  let data = null;
  try { data = await response.json(); } catch (e) { /* رد غير JSON */ }
  if (response.ok && data) return { ok: true, data };
  return { ok: false, errors: (data && data.errors) || [GENERIC_ERROR] };
}

const postJSON = (path, body) =>
  send(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const analyze = (payload) => postJSON("/analyze", payload);
export const chat = (payload) => postJSON("/chat", payload);
export const redactText = (text) => postJSON("/contract/redact", { text });

export function previewFile(file) {
  const form = new FormData();
  form.append("file", file);
  return send("/contract/preview", { method: "POST", body: form });
}

