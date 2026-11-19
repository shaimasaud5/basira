// معاينة الداشبورد في الصفحة الرئيسية: نفس كود الداشبورد الحقيقي (renderDashboard) ببيانات مثال.
// البيانات بنفس شكل رد /analyze؛ بطاقة النسبة نصها من الباك إند نفسه، وبطاقة الصيانة مثال توضيحي.
import { renderDashboard } from "./dashboard.js";

const DEMO_REPORT = {
  top: [
    {
      title: "الإيجار يأخذ جزء كبير من الإيراد", category: "financial", severity: "high",
      why: "الإيجار التزام ثابت يُدفع كل شهر سواء بعت أو لا. كل ما كانت نسبته من الإيراد أعلى، قلّ الهامش اللي يتحمل نزول المبيعات.",
      recommendation: "إيجارك 15,000 ريال يمثل 25% من إيرادك المتوقع (60,000 ريال). قبل التوقيع: اسأل عن فترة سماح في أول أشهر، وفاوض على الإيجار، وراجع توقع الإيراد بأرقام واقعية.",
      evidence: "15,000 ÷ 60,000 × 100 = 25%. سيناريو: لو الإيراد الفعلي أقل بـ20% من توقعك (48,000 ريال) تصير النسبة 31.25%.",
      trust_label: "محسوب بالكود",
    },
    {
      title: "الصيانة على المستأجر", category: "contract", severity: "medium",
      why: "تكلفة الصيانة تنزل من أرباحك لو كانت عليك، وما تظهر في الإيجار.",
      recommendation: "اسأل المؤجر: هل فيه سقف للصيانة؟ وهل الأعطال الإنشائية عليه؟ وثّق الجواب في العقد.",
      evidence: "«يتحمل المستأجر جميع أعمال الصيانة والإصلاحات خلال مدة العقد.»",
      trust_label: "موثّق",
    },
  ],
  more: [],
  ai_suggestions: [],
  warnings: [],
  metrics: {
    monthly_rent: 15000, monthly_revenue: 60000, lease_months: 12, rent_to_revenue_pct: 25,
    ratio_thresholds: { medium: 10, high: 15 }, total_commitment: 180000,
    increase_pct: 7.5, rent_after_increase: 16125, monthly_extra_after_increase: 1125, yearly_extra_after_increase: 13500,
  },
};

export function mountDemo(root) {
  if (!root) return;
  const toApp = () => { location.hash = "#/app"; };
  renderDashboard(root, DEMO_REPORT, { activity: "مطعم", city: "الدمام" }, { onAsk: toApp, onEdit: toApp });
}
