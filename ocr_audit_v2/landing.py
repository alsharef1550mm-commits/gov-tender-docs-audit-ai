"""هوية المشروع وصفحة الهبوط (ثنائية اللغة) التي تُعرض قبل الدخول إلى النظام.

الصفحة ثابتة (لا تُعاد رسمها)، ومفتاح اللغة (عربي | English | الاثنان) يعمل بسمة data-lang على الحاوية (انظر LANG_JS).
"""

PROJECT_AR = "نظام فحص مستندات المنافسات الحكومية بتقنيات الذكاء الاصطناعي والرؤية الحاسوبية"
TAGLINE_AR = "برمجة محاسبية متخصصة لتحسين الإنفاق الحكومي ودعم الرقابة المالية بأقل تكلفة ممكنة"
PROJECT_EN = "AI-Powered Government Tender Document Auditing"
TAGLINE_EN = "Specialized Accounting Software for Improving Public Spending and Supporting Financial Oversight at the Lowest Possible Cost"
AUTHOR_AR, AUTHOR_EN = "عبدالله محمد الجودي", "Abdullah Mohammed Al-Judi"
SUPERVISOR_AR, SUPERVISOR_EN = "الدكتور بهاء الدين حمودة", "Dr. Bahaa Eldin Hamouda"
INSTITUTION_AR, INSTITUTION_EN = "كليات الخليج", "Gulf Colleges"
PROGRAM_AR = "مشروع بحثي لنيل درجة الدبلوم العالي في الذكاء الاصطناعي"
PROGRAM_EN = "Research project for the Higher Diploma in Artificial Intelligence"

STEPS = [
    ("📄", "رفع المستندات", "Upload", "عقد المنافسة وربطات التعاميد وسندات الاستلام والفواتير (PDF أو ZIP).",
     "Tender contract and bundles of purchase orders, receipts and invoices (PDF or ZIP)."),
    ("🔎", "استخراج البيانات", "Extraction", "قراءة مباشرة للنص، أو OCR ونموذج رؤية ولغة للمستندات الممسوحة، مع دليل صفحة لكل قيمة.",
     "Direct text reading, or OCR plus a vision-language model for scanned pages, with page evidence for every value."),
    ("🧮", "التدقيق المحاسبي", "Accounting audit", "حساب بقواعد العقد (عمولة، ضريبة، غرامة) بمحرك حتمي، ومطابقة السند بالفاتورة والتعميد.",
     "Deterministic contract rules (commission, VAT, penalty) and matching of receipts to invoices and purchase orders."),
    ("👁️", "المراجعة البشرية", "Human review", "كل ما لا يثبته المستند يُحال للمراجع مع المعاملة كاملة: السند وفاتورته وتعميده.",
     "Anything the documents cannot prove is referred with the full transaction: receipt, invoice and purchase order."),
    ("📊", "تقرير Excel", "Excel report", "تقرير واحد بقالب معتمد، بنمط مراجعة واضح ونتائج صيغ محفوظة.",
     "One report in the approved template, with a clear review style and stored formula results."),
]
PRINCIPLES = [
    ("🎯", "الدقة قبل الأتمتة", "Accuracy before automation", "لا يمرّ خطأ غير مكتشف إلى تقرير معتمد؛ ما لا يُثبَت يُحال للمراجعة.",
     "No undetected error reaches an approved report; what cannot be proven is referred to a reviewer."),
    ("🧠", "الحساب لا يقرره نموذج لغوي", "Math is never decided by a language model", "النماذج تقرأ فقط؛ الحساب والأحكام بقواعد العقد ومحرك Decimal.",
     "Models only read; calculations and verdicts come from contract rules and a Decimal engine."),
    ("📎", "أدلة قابلة للتتبع", "Traceable evidence", "من كل بند تُفتح صفحات المصدر مع عدسة تقريب اختيارية.",
     "Every item opens its source pages, with an optional magnifier."),
    ("🔒", "تشغيل محلي وأمن البيانات", "Local deployment and data security", "كل المكونات مفتوحة المصدر وتعمل داخل الجهة (التطبيق، القراءة النصية وOCR، محرك القواعد، ونموذج الرؤية على وحدة معالجة محلية)؛ فلا حاجة لإرسال المستندات إلى خدمة خارجية، وتبقى مستندات المنافسات وبيانات الموردين تحت سيطرة الجهة.",
     "All components are open source and can run on-premises (the app, text reading and OCR, the rules engine and the vision model on a local GPU), so tender documents and supplier data need not leave the organization and stay under its control."),
    ("🔗", "الفاتورة مبرر مؤيد", "The invoice supports, it does not equal", "قد تؤيد الفاتورة الواحدة عدة سندات وتعاميد في ربطات مختلفة.",
     "One invoice may support several receipts and orders across different bundles."),
]
CHIPS = [("📑", "تعميد ← سند ← فاتورة", "Order → Receipt → Invoice"), ("🔍", "نص مباشر · OCR · رؤية ولغة", "Text · OCR · Vision-language"),
         ("⚖️", "قواعد عقد حتمية", "Deterministic contract rules"), ("🧾", "تقرير Excel معتمد", "Approved Excel report")]


def _t(ar, en, tag="span", cls=""):
    """نص بلغتين: يُخفى أحدهما بحسب مفتاح اللغة."""
    return f"<{tag} class='ar {cls}'>{ar}</{tag}><{tag} class='en {cls}' dir='ltr'>{en}</{tag}>"


def hero_html() -> str:
    chips = "".join(f"<span class='chip2'><span class='ci'>{i}</span>{_t(a, e)}</span>" for i, a, e in CHIPS)
    return f"""
<div class='landing' data-lang='both'>
  <div class='topbar'>
    <div class='brand'><span class='logo'>🏛️</span><span class='bn'>{_t('رقابة مالية ذكية', 'Smart Financial Oversight')}</span></div>
    <div class='langsw' role='group' aria-label='language'>
      <button type='button' class='langbtn' data-l='ar'>العربية</button>
      <button type='button' class='langbtn on' data-l='both'>عربي · EN</button>
      <button type='button' class='langbtn' data-l='en'>English</button>
    </div>
  </div>
  <section class='hero'>
    <div class='hero-glow'></div>
    <div class='pillrow'><span class='pill'>{_t('مشروع بحثي', 'Research project')}</span><span class='pill'>{_t('نسخة تجريبية خاصة', 'Private prototype')}</span></div>
    <h1 class='h-ar ar'>{PROJECT_AR}</h1>
    <p class='s-ar ar'>{TAGLINE_AR}</p>
    <h2 class='h-en en' dir='ltr'>{PROJECT_EN}</h2>
    <p class='s-en en' dir='ltr'>{TAGLINE_EN}</p>
    <div class='chips2'>{chips}</div>
  </section>
</div>"""


def body_html() -> str:
    steps = "".join(
        f"<div class='lstep'><div class='sico'>{ic}</div><div class='snum'>{k}</div>"
        f"<div class='lt'>{_t('<b>' + ar + '</b>', '<b>' + en + '</b>', 'div')}</div>"
        f"<div class='ld'>{_t(dar, den, 'div')}</div></div>" for k, (ic, ar, en, dar, den) in enumerate(STEPS, 1))
    prin = "".join(
        f"<div class='lprin'><div class='pico'>{ic}</div><div><div class='lt'>{_t('<b>' + ar + '</b>', '<b>' + en + '</b>', 'div')}</div>"
        f"<div class='ld'>{_t(dar, den, 'div')}</div></div></div>" for ic, ar, en, dar, den in PRINCIPLES)
    return f"""
<div class='landing' data-lang='both' id='landing-body'>
  <section class='acad'>
    <div class='pcard'><div class='av'>ع</div><div><div class='pk'>{_t('إعداد', 'Prepared by')}</div>
      <div class='pv'>{_t(AUTHOR_AR, AUTHOR_EN, 'div')}</div></div></div>
    <div class='pcard'><div class='av dr'>د</div><div><div class='pk'>{_t('إشراف', 'Supervised by')}</div>
      <div class='pv'>{_t(SUPERVISOR_AR, SUPERVISOR_EN, 'div')}</div><div class='pi'>🎓 {_t(INSTITUTION_AR, INSTITUTION_EN)}</div></div></div>
    <div class='pcard wide'><div class='av pr'>🎓</div><div><div class='pk'>{_t('البرنامج', 'Program')}</div>
      <div class='pv sm'>{_t(PROGRAM_AR, PROGRAM_EN, 'div')}</div></div></div>
  </section>
  <h3 class='ltitle'>{_t('كيف يعمل النظام', 'How it works', 'span')}</h3>
  <section class='lsteps'>{steps}</section>
  <h3 class='ltitle'>{_t('مبادئ التصميم', 'Design principles', 'span')}</h3>
  <section class='lprins'>{prin}</section>
  <section class='lnote'><span class='nico'>⚠️</span><div>{_t('نموذج بحثي تجريبي: نتائجه مسودات مراجعة لا قرارات رقابية نهائية، ولا يُعلن إقفالاً ولا دقة قبل القياس المستقل والمراجعة البشرية.',
     'A research prototype: its outputs are review drafts, not final audit decisions; no closure or accuracy is claimed before independent measurement and human review.', 'div')}</div></section>
  <footer class='lfoot'>{_t('© مشروع بحثي — ' + INSTITUTION_AR + ' · الدبلوم العالي في الذكاء الاصطناعي', '© Research project — ' + INSTITUTION_EN + ' · Higher Diploma in Artificial Intelligence')}</footer>
</div>"""


def landing_html() -> str:
    return hero_html() + body_html()


# مفتاح اللغة: يضبط data-lang على كل حاويات الصفحة (تُدمج مع LENS_JS في التطبيق)
LANG_JS = """
  document.addEventListener('click', e => {
    const b = e.target && e.target.closest ? e.target.closest('.langbtn') : null;
    if (!b) return;
    const l = b.dataset.l;
    document.querySelectorAll('.landing').forEach(x => x.setAttribute('data-lang', l));
    document.querySelectorAll('.langbtn').forEach(x => x.classList.toggle('on', x.dataset.l === l));
  });
"""

LANDING_CSS = """
.landing{direction:rtl;width:100%;max-width:100%;min-width:0;margin:0 auto;box-sizing:border-box;animation:lfade .5s ease both}
.landing *{box-sizing:border-box;min-width:0}
@keyframes lfade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.landing[data-lang="en"]{direction:ltr}
.landing[data-lang="ar"] .en,.landing[data-lang="en"] .ar{display:none !important}
.landing[data-lang="both"] .en{opacity:.85}
.landing[data-lang="both"] span.ar + span.en::before{content:" · ";opacity:.7}
.topbar{display:flex;justify-content:space-between;align-items:center;margin:.2rem 0 .8rem;gap:.6rem;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:.5rem;color:var(--brand);font-weight:800}
.logo{font-size:1.5rem}
.langsw{display:inline-flex;background:var(--soft);border:1px solid var(--line);border-radius:999px;padding:3px;gap:2px}
.langbtn{border:0;background:transparent;color:var(--brand);font-weight:700;font-family:inherit;font-size:.85rem;padding:.3rem .85rem;border-radius:999px;cursor:pointer;transition:background .15s,color .15s}
.langbtn:hover{background:rgba(31,78,121,.14)}
.langbtn.on{background:var(--brand2);color:#fff}
.hero{position:relative;overflow:hidden;background:linear-gradient(135deg,#102A4A 0%,#1F4E79 55%,#2F6FB0 100%);border-radius:22px;padding:30px 28px 26px;color:#fff;box-shadow:0 12px 34px rgba(16,42,74,.35)}
.hero-glow{position:absolute;width:420px;height:420px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.18),transparent 65%);top:-170px;left:-120px;pointer-events:none}
.hero *{color:#fff !important}
.pillrow{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1rem}
.pill{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.38);border-radius:999px;padding:.22rem .85rem;font-size:.82rem;font-weight:700;backdrop-filter:blur(3px)}
.h-ar{font-size:1.9rem;line-height:1.55;margin:.2rem 0;font-weight:800;letter-spacing:-.2px}
.s-ar{font-size:1.12rem;margin:.3rem 0 1rem;opacity:.96}
.h-en{font-size:1.2rem;margin:.5rem 0 0;font-weight:700;text-align:left}
.s-en{font-size:.95rem;margin:.25rem 0 0;opacity:.92;text-align:left}
.chips2{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.2rem}
.chip2{display:inline-flex;align-items:center;gap:.4rem;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);border-radius:12px;padding:.35rem .75rem;font-size:.84rem;font-weight:600}
.landing[data-lang="ar"] .h-ar,.landing[data-lang="both"] .h-ar{display:block}
.acad{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:.9rem;margin:1.1rem 0 .4rem}
.pcard{display:flex;align-items:center;gap:.9rem;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px;box-shadow:0 1px 4px rgba(23,54,93,.08);transition:transform .18s,box-shadow .18s}
.pcard:hover{transform:translateY(-3px);box-shadow:0 8px 20px rgba(23,54,93,.16)}
.pcard.wide{grid-column:1/-1}
.av{flex:none;width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#1F4E79,#2F6FB0);color:#fff;display:flex;align-items:center;justify-content:center;font-size:1.4rem;font-weight:800}
.av.dr{background:linear-gradient(135deg,#1E7B4B,#38A169)}.av.pr{background:linear-gradient(135deg,#B45309,#D98324);font-size:1.3rem}
.pk{color:var(--mut);font-size:.78rem;font-weight:700;margin-bottom:.15rem}
.pv{color:var(--brand);font-size:1.12rem;font-weight:800;line-height:1.5}.pv.sm{font-size:1rem}
.pv .en{color:var(--ink);font-weight:600;font-size:.95rem;text-align:left}
.pi{color:var(--ink);margin-top:.2rem;font-weight:700;font-size:.92rem}
.ltitle{display:flex;align-items:center;gap:.6rem;color:var(--brand);font-size:1.2rem;font-weight:800;margin:1.6rem 0 .7rem}
.ltitle::after{content:"";flex:1;height:2px;background:linear-gradient(90deg,var(--line),transparent)}
.landing[data-lang="en"] .ltitle::after{background:linear-gradient(270deg,var(--line),transparent)}
.lsteps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:.8rem;position:relative}
.lstep,.lprin{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px;position:relative;transition:transform .18s,box-shadow .18s,border-color .18s}
.lstep:hover,.lprin:hover{transform:translateY(-4px);box-shadow:0 10px 24px rgba(23,54,93,.18);border-color:var(--brand2)}
.sico{font-size:1.6rem;margin-bottom:.3rem}
.snum{position:absolute;top:10px;left:12px;width:26px;height:26px;border-radius:50%;background:var(--brand2);color:#fff;font-weight:800;font-size:.82rem;display:flex;align-items:center;justify-content:center}
.landing[data-lang="en"] .snum{left:auto;right:12px}
.lt{color:var(--brand);margin-bottom:.25rem}
.ld{color:var(--ink);font-size:.88rem;line-height:1.75}.ld .en{color:var(--mut);font-size:.8rem;text-align:left;margin-top:.2rem}
.lt .en{color:var(--mut);font-size:.82rem;text-align:left}
.lprins{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,430px),1fr));gap:.8rem}
.lprin{display:flex;gap:.8rem;align-items:flex-start}
.pico{flex:none;width:44px;height:44px;border-radius:12px;background:var(--soft);display:flex;align-items:center;justify-content:center;font-size:1.4rem}
.lnote{display:flex;gap:.7rem;align-items:flex-start;margin:1.5rem 0 .6rem;padding:12px 16px;border-radius:14px;background:var(--warn-bg);border:1px solid var(--warn);color:var(--ink);font-size:.86rem;line-height:1.8}
.lnote .en{color:var(--mut);margin-top:.2rem;text-align:left;font-size:.82rem}
.nico{font-size:1.2rem}
.lfoot{text-align:center;color:var(--mut);font-size:.8rem;margin:.9rem 0 .4rem;padding-top:.7rem;border-top:1px solid var(--line)}
.lfoot .en{text-align:center}
.enter-btn button,button.enter-btn{font-size:1.1rem !important;font-weight:800 !important;padding:.85rem 1rem !important;border-radius:14px !important;box-shadow:0 6px 18px rgba(31,78,121,.35);transition:transform .15s,box-shadow .15s}
.enter-btn button:hover,button.enter-btn:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(31,78,121,.45)}
@media (max-width:640px){.h-ar{font-size:1.4rem}.hero{padding:22px 18px}}
"""
