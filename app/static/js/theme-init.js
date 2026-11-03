// يطبّق الوضع المحفوظ قبل رسم الصفحة (يمنع وميض الوضع الخاطئ). بدون موديول عشان يشتغل فوراً.
try {
  const saved = localStorage.getItem("bassira-theme");
  if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
} catch (e) { /* التخزين غير متاح: نتبع وضع النظام */ }
