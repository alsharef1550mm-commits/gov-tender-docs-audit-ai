"""هوية المشروع وصفحة الهبوط (ثنائية اللغة) التي تُعرض قبل الدخول إلى النظام.

الصفحة ثابتة (لا تُعاد رسمها)، ومفتاح اللغة (عربي | English | الاثنان) يعمل بسمة data-lang على الحاوية (انظر LANG_JS).
"""

PROJECT_AR = "نظام فحص مستندات المنافسات الحكومية بتقنيات الذكاء الاصطناعي والرؤية الحاسوبية"
TAGLINE_AR = "برمجة محاسبية دقيقة ومتخصصة عبر الرؤية الحاسوبية وOCR وقواعد التوجيه، تدعم الحوكمة وكفاءة الإنفاق الحكومي"
PROJECT_EN = "AI-Powered Government Tender Document Auditing"
TAGLINE_EN = "Computer vision, OCR and contract-based rules supporting financial governance and efficient public spending"
AUTHOR_AR, AUTHOR_EN = "عبدالله محمد الجودي", "Abdullah Mohammed Aljoudi"
SUPERVISOR_AR, SUPERVISOR_EN = "الدكتور بهاء الدين حمودة", "Dr. Bahaa Eldin Hamouda"
INSTITUTION_AR, INSTITUTION_EN = "كليات الخليج", "Gulf Colleges"
PROGRAM_AR = "مشروع بحثي لنيل درجة الدبلوم العالي في الذكاء الاصطناعي"
PROGRAM_EN = "Research project for the Higher Diploma in Artificial Intelligence"

STEPS = [
    ("رفع المستندات", "Upload", "عقد المنافسة وربطات التعاميد وسندات الاستلام والفواتير (PDF أو ZIP).",
     "Tender contract and bundles of purchase orders, receipts and invoices (PDF or ZIP)."),
    ("استخراج البيانات", "Extraction", "قراءة مباشرة للنص، أو OCR ونموذج رؤية ولغة للمستندات الممسوحة، مع دليل صفحة لكل قيمة.",
     "Direct text reading, or OCR plus a vision-language model for scanned pages, with page evidence for every value."),
    ("التدقيق المحاسبي", "Accounting audit", "حساب بقواعد العقد (عمولة، ضريبة، غرامة) بمحرك حتمي، ومطابقة السند بالفاتورة والتعميد.",
     "Deterministic contract rules (commission, VAT, penalty) and matching of receipts to invoices and purchase orders."),
    ("المراجعة البشرية", "Human review", "كل ما لا يثبته المستند يُحال للمراجع مع المعاملة كاملة: السند وفاتورته وتعميده.",
     "Anything the documents cannot prove is referred with the full transaction: receipt, invoice and purchase order."),
    ("تقرير Excel", "Excel report", "تقرير واحد بقالب معتمد، بنمط مراجعة واضح ونتائج صيغ محفوظة.",
     "One report in the approved template, with a clear review style and stored formula results."),
]
PRINCIPLES = [
    ("الدقة قبل الأتمتة", "Accuracy before automation", "ما لا تثبته المستندات يُحال للمراجعة مع دليل الصفحة، مع الفصل بين القراءة والحساب.",
     "Unsubstantiated fields are referred for review with page evidence; extraction and calculation remain separate."),
    ("الحساب لا يقرره نموذج لغوي", "Math is never decided by a language model", "النماذج تقرأ فقط؛ الحساب والأحكام بقواعد العقد ومحرك Decimal.",
     "Models only read; calculations and verdicts come from contract rules and a Decimal engine."),
    ("أدلة قابلة للتتبع", "Traceable evidence", "من كل بند تُفتح صفحات المصدر مع عدسة تقريب اختيارية.",
     "Every item opens its source pages, with an optional magnifier."),
    ("مسار واضح للمراجعة", "A clear review workflow", "المستند هو مرجع القراءة؛ يراجع المستخدم الأدلة ويوثّق قراره قبل اعتماد المخرجات.",
     "Source documents remain the reference. The reviewer checks the evidence and records a decision before approving the output."),
    ("الفاتورة مبرر مؤيد", "The invoice supports, it does not equal", "قد تؤيد الفاتورة الواحدة عدة سندات وتعاميد في ربطات مختلفة.",
     "One invoice may support several receipts and orders across different bundles."),
]
CHIPS = [("تعميد ← سند ← فاتورة", "Order → Receipt → Invoice"), ("نص مباشر · OCR · رؤية ولغة", "Text · OCR · Vision-language"),
         ("قواعد عقد حتمية", "Deterministic contract rules"), ("تقرير Excel معتمد", "Approved Excel report")]


def _t(ar, en, tag="span", cls=""):
    """نص بلغتين: يُخفى أحدهما بحسب مفتاح اللغة."""
    return f"<{tag} class='ar {cls}'>{ar}</{tag}><{tag} class='en {cls}' dir='ltr'>{en}</{tag}>"


def hero_html() -> str:
    facts = "".join(f"<li>{_t(a, e)}</li>" for a, e in CHIPS)
    return f"""
<div class='landing' data-lang='ar'>
  <div class='topbar'>
    <div class='brand'><span class='journal-mark' aria-hidden='true'>ر</span><span>{_t('رقابة مالية ذكية', 'Smart Financial Oversight')}<small>{_t('كليات الخليج · الذكاء الاصطناعي التطبيقي', 'Gulf Colleges · Applied AI')}</small></span></div>
    <div class='langsw' role='group' aria-label='اللغة · Language'>
      <button type='button' class='langbtn on' data-l='ar'>العربية</button>
      <button type='button' class='langbtn' data-l='both'>عربي · EN</button>
      <button type='button' class='langbtn' data-l='en'>English</button>
    </div>
  </div>
  <section class='hero'>
    <p class='hero-meta'><span class='journal-index' aria-hidden='true'>01 /</span>{_t('الرؤية الحاسوبية في خدمة التدقيق المحاسبي', 'Computer vision for financial document auditing')}</p>
    <h1 class='h-ar ar'>فحص مستندات<br><em>المنافسات الحكومية</em></h1>
    <p class='s-ar ar'>{TAGLINE_AR}</p>
    <h2 class='h-en en' dir='ltr'>{PROJECT_EN}</h2>
    <p class='s-en en' dir='ltr'>{TAGLINE_EN}</p>
    <div class='journal-abstract'>{_t('من مستند المصدر إلى تقرير موثّق؛ قراءة للبيانات، وحساب بقواعد العقد، ومراجعة بشرية للأدلة.', 'From source documents to a traceable report: data extraction, contract-based calculation and human evidence review.', 'p')}</div>
    <ul class='facts'>{facts}</ul>
  </section>
</div>"""


def body_html() -> str:
    steps = "".join(
        f"<li class='lstep'><span class='snum'>{k:02d}</span>"
        f"<div class='lt'>{_t('<b>' + ar + '</b>', '<b>' + en + '</b>', 'div')}</div>"
        f"<div class='ld'>{_t(dar, den, 'div')}</div></li>" for k, (ar, en, dar, den) in enumerate(STEPS, 1))
    prin = "".join(
        f"<li class='lprin'><div class='lt'>{_t('<b>' + ar + '</b>', '<b>' + en + '</b>', 'div')}</div>"
        f"<div class='ld'>{_t(dar, den, 'div')}</div></li>" for ar, en, dar, den in PRINCIPLES)
    return f"""
<div class='landing' data-lang='ar' id='landing-body'>
  <dl class='acad'>
    <div><dt>{_t('إعداد', 'Prepared by')}</dt><dd>{_t(AUTHOR_AR, AUTHOR_EN, 'div')}</dd></div>
    <div><dt>{_t('إشراف', 'Supervised by')}</dt><dd>{_t(SUPERVISOR_AR, SUPERVISOR_EN, 'div')}</dd></div>
    <div><dt>{_t('الجهة', 'Institution')}</dt><dd>{_t(INSTITUTION_AR, INSTITUTION_EN, 'div')}</dd></div>
    <div><dt>{_t('البرنامج', 'Program')}</dt><dd>{_t(PROGRAM_AR, PROGRAM_EN, 'div')}</dd></div>
  </dl>
  <h3 class='ltitle'><span class='journal-index' aria-hidden='true'>02 /</span>{_t('منهجية العمل', 'Methodology', 'span')}</h3>
  <ol class='lsteps'>{steps}</ol>
  <h3 class='ltitle'><span class='journal-index' aria-hidden='true'>03 /</span>{_t('مبادئ التصميم', 'Design principles', 'span')}</h3>
  <ul class='lprins'>{prin}</ul>
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
.landing{direction:rtl;width:100%;max-width:1120px;min-width:0;margin:0 auto;box-sizing:border-box;color:var(--ink)}
.landing *{box-sizing:border-box;min-width:0}
.landing[data-lang="en"]{direction:ltr}
.landing[data-lang="ar"] .en,.landing[data-lang="en"] .ar{display:none !important}
.landing[data-lang="both"] .en{color:var(--mut)}
.landing[data-lang="both"] span.ar + span.en{margin-right:.6em;padding-right:.6em;border-right:1px solid var(--line)}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:4px 0 14px;border-bottom:1px solid var(--line)}
.brand{color:var(--ink);font-weight:700;font-size:.95rem}
.langsw{display:inline-flex;gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.langbtn{border:0;border-inline-start:1px solid var(--line);background:transparent;color:var(--mut);font-family:inherit;font-size:.85rem;font-weight:600;padding:6px 14px;cursor:pointer;min-height:40px}
.langbtn:first-child{border-inline-start:0}
.langbtn:hover{color:var(--ink);background:var(--soft2)}
.langbtn.on{color:var(--ink);background:var(--soft)}
.hero{padding:clamp(40px,8vw,96px) 0 clamp(28px,5vw,48px)}
.hero-meta{color:var(--mut);font-size:.85rem;margin:0 0 18px}
.h-ar{font-size:clamp(1.6rem,3.4vw,2.6rem);line-height:1.5;margin:0;font-weight:700;color:var(--ink);max-width:28ch;text-wrap:balance}
.s-ar{font-size:clamp(1rem,1.4vw,1.15rem);line-height:1.9;margin:16px 0 0;color:var(--mut);max-width:60ch}
.h-en{font-size:clamp(1.05rem,1.8vw,1.35rem);margin:28px 0 0;font-weight:600;color:var(--ink);text-align:left}
.s-en{font-size:.95rem;margin:6px auto 0 0;color:var(--mut);text-align:left;max-width:70ch}
.acad dt{color:var(--mut);font-size:.8rem;margin:0 0 4px}
.acad dd{margin:0;color:var(--ink);font-weight:600;line-height:1.6}
.ltitle{color:var(--ink);font-size:1.15rem;font-weight:700;margin:56px 0 16px}
.snum{display:block;color:var(--mut);font-size:.8rem;font-variant-numeric:tabular-nums;margin-bottom:10px;direction:ltr;text-align:start}
.lt{color:var(--ink);margin-bottom:6px}
.lt .en{font-size:.85rem;text-align:start}
.ld{color:var(--mut);font-size:.9rem;line-height:1.8}
.ld .en{font-size:.82rem;margin-top:4px;text-align:start;opacity:.85}
.lfoot{color:var(--mut);font-size:.8rem;margin:48px 0 8px;padding-top:16px;border-top:1px solid var(--line)}
.landing[data-lang="en"] .en,.landing[data-lang="en"] .s-en,.landing[data-lang="en"] .h-en{text-align:left}
/* Ruled grids: 1px gaps over the line colour draw every rule; column counts always divide the items evenly. */
.facts,.acad,.lsteps{list-style:none;margin:0;padding:0;display:grid;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:8px;overflow:hidden}
.facts>*,.acad>*,.lsteps>*{background:#0e0f10;padding:16px 18px;margin:0!important}
.facts{margin-top:36px;grid-template-columns:repeat(4,minmax(0,1fr))}
.acad{grid-template-columns:repeat(4,minmax(0,1fr))}
.lsteps{grid-template-columns:repeat(5,minmax(0,1fr))}
.facts li{font-size:.9rem;color:var(--ink)}
.facts li .en,.landing[data-lang="both"] .facts span.ar + span.en{display:block;margin:2px 0 0;padding:0;border:0;font-size:.82rem}
.acad dd .en{font-weight:400;font-size:.88rem}
.lstep{padding-bottom:20px}
.lprins{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
.lprin{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:8px 32px;padding:18px 0;border-bottom:1px solid var(--line)}
.lprin .lt{margin:0}
/* In the bilingual view every English line keeps the Arabic edge, so each block reads from one alignment line. */
.landing[data-lang="both"] :is(.lt,.ld,.acad dd) .en,.landing[data-lang="both"] :is(.h-en,.s-en){text-align:right}
.landing[data-lang="both"] .s-en{margin:6px 0 0 auto}
@media (max-width:1000px){.lsteps{grid-template-columns:1fr}.facts,.acad{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.landing[data-lang="both"] .hero-meta span.en{display:block;margin:2px 0 0;padding:0;border:0}.hero{padding:32px 0 24px}.ltitle{margin-top:40px}.facts,.acad{grid-template-columns:1fr}.lprin{grid-template-columns:1fr}}
"""
