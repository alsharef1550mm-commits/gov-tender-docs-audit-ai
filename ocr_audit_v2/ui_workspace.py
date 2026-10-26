"""Presentation only: Arabic workspace styles and evidence viewer. No audit or model operations."""

CSS = r"""
/* Workspace design tokens. All selectors are scoped to this application. */
.gradio-container{--brand:#e8e8e6;--brand2:#2a9d8f;--soft:#1f2022;--soft2:#161718;--line:#2c2e31;--ink:#ececea;--mut:#9b9ea4;--card:#161718;--track:#26282b;--shadow:none;font-family:'Segoe UI',Tahoma,Arial,sans-serif!important;line-height:1.75!important;background:#0e0f10!important;max-width:1600px!important;padding:20px clamp(12px,3vw,44px)!important}
.dark,.dark .gradio-container,.gradio-container.dark{--brand:#e8e8e6;--brand2:#2a9d8f;--soft:#1f2022;--soft2:#161718;--line:#2c2e31;--ink:#ececea;--mut:#9b9ea4;--card:#161718;--track:#26282b;--shadow:none}
body,.dark body,gradio-app{background:#0e0f10!important}
*{box-sizing:border-box}
.prose,.block[dir=ltr]{direction:rtl}
.prose{padding:0!important}
.workspace-panel>.block:not(.upload-zone){background:transparent!important;border:0!important}
#workspace-tabs>.tab-wrapper{min-height:66px;height:auto!important}
#workspace-tabs [role=tablist]{height:auto!important;min-height:66px}
#workspace-tabs .tab-container button{min-height:48px;padding:10px 22px}
.inline-feedback:has(.prose:empty){display:none!important}
:is(button,input,textarea,select):focus-visible,[tabindex]:focus-visible{outline:3px solid #2a9d8f!important;outline-offset:3px!important}
button{min-height:44px;touch-action:manipulation}
input,textarea{line-height:1.7!important;font-size:16px!important}
:is(h1,h2,h3,h4){text-wrap:balance}
bdi{unicode-bidi:isolate;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.block{border-radius:14px!important}
.card{border-color:var(--line);border-radius:18px;padding:22px;box-shadow:var(--shadow);margin:0}
.hint{color:var(--mut);line-height:1.8}
.workspace-header{display:flex;align-items:center;gap:16px;padding:8px 0 18px;border-bottom:1px solid var(--line)}
.workspace-mark{display:none}
.eyebrow{color:var(--mut);font-size:.8rem;font-weight:400;margin:0 0 3px}
h1.app-title{font-size:clamp(1.2rem,2vw,1.65rem);line-height:1.6;color:var(--ink);margin:0}
.app-sub{font-size:.88rem;margin:3px 0 0}
.app-toolbar{align-items:center;padding:4px 0;gap:12px!important}
.model-switch{border:1px solid var(--line);padding:10px 14px;border-radius:14px;background:var(--card);flex-wrap:wrap;max-width:100%}
.model-switch .label{color:var(--ink)!important}
.model-switch .state{color:var(--mut)!important}
.model-switch.off .label{color:var(--ink)!important}
.jobcard{padding:14px 20px;border:1px solid var(--line);border-inline-start:3px solid var(--line);border-radius:8px!important;background:var(--card)}
.workspace-panel :is(.styler,.form,.block:not(.upload-zone)){background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.jobcard .badge{font-size:.85rem}
#workspace-tabs [role=tablist]{padding:8px;background:var(--card);border:1px solid var(--line);border-radius:16px;gap:6px;box-shadow:var(--shadow)}
#workspace-tabs [role=tablist] button{padding:10px 22px;border-radius:10px!important;border:none!important;font-weight:600;color:var(--mut);min-height:48px}
#workspace-tabs [role=tablist] button.selected{background:var(--soft)!important;color:var(--ink)!important;box-shadow:inset 0 -2px var(--brand2)}
#workspace-tabs>.tabitem{border:0!important;padding:24px 0 0!important;background:transparent!important}
.section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin:0 0 12px}
.section-heading h2{margin:0;color:var(--ink);font-size:1.4rem;font-weight:700}
.section-heading p{color:var(--mut);margin:5px 0 0;font-size:.92rem}
.section-kicker{color:var(--mut);font-size:.8rem;margin-bottom:4px}
.step-title{display:flex;align-items:center;gap:10px;margin:0 0 4px;color:var(--ink);font-weight:700;font-size:1.04rem}
.step-num{display:grid;place-items:center;width:28px;height:28px;flex:none;border-radius:6px;border:1px solid var(--line);color:var(--mut);font-size:.85rem;font-variant-numeric:tabular-nums}
.workspace-panel{background:var(--card)!important;border:1px solid var(--line)!important;border-radius:18px!important;padding:20px!important;box-shadow:var(--shadow);gap:14px!important;min-width:0!important}
.upload-grid{gap:20px!important;align-items:stretch!important}
.upload-zone{border:1.5px dashed var(--line)!important;background:var(--soft2)!important;border-radius:14px!important;transition:border-color .15s,background .15s}
.upload-zone:hover,.upload-zone:focus-within{border-color:var(--brand2)!important;background:var(--soft)!important}
.upload-zone button{min-height:138px}
.upload-zone .file-preview button{min-height:44px}
.mode-choice label{min-height:48px;padding:12px 20px!important;border-radius:12px!important}
.upload-footer{border-top:1px solid var(--line);padding-top:18px;align-items:center!important;gap:16px!important}
.primary-action{min-height:48px!important;border-radius:8px!important;box-shadow:none!important}
.empty-state{padding:38px 24px;text-align:center;background:var(--card);border:1px dashed var(--line);border-radius:18px;color:var(--mut)}
.empty-state strong{display:block;color:var(--ink);font-size:1.05rem;margin:8px 0}
.empty-symbol{display:inline-grid;place-items:center;width:40px;height:40px;border-radius:8px;border:1px solid var(--line);color:var(--mut);font-size:18px}
.review-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 12px}
.review-metric{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 20px;color:var(--mut);font-size:.85rem}
.review-metric b{display:block;font-size:1.8rem;line-height:1.5;color:var(--ink);font-variant-numeric:tabular-nums}
.review-metric.pending{border-inline-start:3px solid var(--warn)}
#review-table{overflow-x:auto;max-width:100%}
#review-table th{background:var(--card)!important;color:var(--mut)!important;font-weight:600;border-bottom:1px solid var(--line)!important}
#review-table tbody tr,#review-table tbody tr:nth-child(odd),#review-table tbody tr:nth-child(even){background:transparent!important}
#review-table td{border-bottom:1px solid var(--line)!important}
#review-table :is(th,td){padding:12px!important;text-align:start!important;line-height:1.6}
#review-table tbody tr:hover{background:var(--soft)!important;cursor:pointer}
#review-table :is(th,td):is(:nth-child(1),:nth-child(3),:nth-child(4),:nth-child(5)){direction:ltr;unicode-bidi:isolate;text-align:start!important}
.review-navigation{align-items:end!important;gap:10px!important}
.review-layout{gap:20px!important;align-items:start!important}
.decision-panel{position:sticky;top:18px;align-self:flex-start!important;flex-shrink:0!important}
.decision-panel textarea{min-height:48px}
.decision-panel textarea[rows="4"]{min-height:110px}
.decision-panel .block{background:transparent!important}
.decision-panel label{line-height:1.7}
.evidence-meta{overflow-wrap:anywhere}
.evidence-meta .chips{gap:8px}
.evidence-meta .chip{background:var(--soft2);padding:7px 10px}
.source-fingerprint{margin-top:12px;font-size:.75rem;overflow-wrap:anywhere;color:var(--mut)}
.lensbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:12px;background:var(--card);border:1px solid var(--line);border-radius:12px}
.lensbar .hint{flex:1;min-width:180px}
.lens-toggle{min-height:44px}
.secs{gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr))}
.sec figure{padding:8px;border-radius:14px;box-shadow:var(--shadow)}
.sec figcaption{font-size:.85rem;display:flex;gap:8px;justify-content:space-between;align-items:center;flex-wrap:wrap;padding:4px 2px 8px}
.page-open{border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:8px;padding:7px 12px;font-family:inherit;font-size:.8rem;cursor:pointer;min-height:44px}
.stepper{direction:rtl;gap:8px;padding:20px 0;overflow-x:auto}
.step{min-width:80px;line-height:1.7}
.step .c{width:36px;height:36px;margin-bottom:10px}
.report-note{display:flex;gap:16px;align-items:start}
.report-note .empty-symbol{flex:none}
.landing .langbtn{min-height:40px}
.gradio-container footer{display:none!important}
.landing-actions{display:flex!important;flex-wrap:wrap;align-items:center!important;gap:20px!important;max-width:1120px;margin:0 auto 8px!important;width:100%}
.landing-actions>.enter-btn{flex:0 0 auto!important;width:auto!important;min-width:min(100%,280px)!important;max-width:100%;min-height:52px;padding:12px 28px!important;white-space:normal;background:var(--brand2)!important;color:#fff!important;border:0!important;font-size:1rem!important;font-weight:600!important;line-height:1.5!important;border-radius:8px!important;box-shadow:none!important;transition:background .15s}
.landing-actions>.enter-btn:hover{background:#238a7e!important}
.landing-actions>.presentation-entry{flex:0 0 auto!important;width:auto!important;padding:0!important;min-width:0!important;background:transparent!important;border:0!important}
.presentation-entry .html-container,.presentation-entry .prose{padding:0!important}
.presentation-entry-link{display:inline-flex;align-items:center;min-height:44px;padding:8px 4px;color:var(--ink)!important;font-weight:500;font-size:.95rem!important;text-decoration:underline!important;text-decoration-color:var(--line)!important;text-underline-offset:6px}
.presentation-entry-link:hover{text-decoration-color:var(--ink)!important}
.presentation-entry-link:focus-visible{outline:3px solid var(--brand2);outline-offset:4px}
@media(max-width:600px){.landing-actions>.enter-btn{width:100%!important;flex:1 1 100%!important}}
/* Native modal: works with touch, keyboard, pinch/scroll and RTL text. */
#audit-page-dialog{width:min(96vw,1440px);height:94dvh;max-height:94dvh;max-width:96vw;padding:0;border:1px solid #2c2e31;border-radius:10px;background:#161718;color:#ececea;overflow:hidden;font-family:'Segoe UI',Tahoma,sans-serif;direction:rtl;box-shadow:0 20px 80px #0008}
#audit-page-dialog::backdrop{background:#000c}
#audit-page-dialog .viewer-toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid #2c2e31}
#audit-page-dialog .viewer-title{flex:1;min-width:160px;font-weight:600;font-size:14px}
#audit-page-dialog button{min-width:44px;min-height:44px;border:1px solid #2c2e31;border-radius:8px;background:#1f2022;color:#ececea;font:inherit;cursor:pointer;padding:8px 12px}
#audit-page-dialog button:focus-visible{outline:3px solid #2a9d8f;outline-offset:2px}
#audit-page-dialog .viewer-scroll{height:calc(100% - 84px);overflow:auto;direction:ltr;padding:16px;background:#0e0f10}
#audit-page-dialog img{display:block;max-width:none;height:auto;margin:0 auto;background:white}
@media(max-width:1000px){.review-layout{flex-direction:column!important}.decision-panel{position:static;width:100%!important;flex-basis:auto!important}.review-layout>.evidence-column{width:100%!important;flex-basis:auto!important}}
@media(max-width:600px){.upload-grid{flex-direction:column!important}.upload-grid>.workspace-panel{width:100%!important;min-width:0!important}.gradio-container{padding:12px!important}.workspace-header{align-items:flex-start;gap:10px}.workspace-mark{width:36px;height:42px;border-radius:10px;font-size:20px}.app-sub{font-size:.8rem}.workspace-panel{padding:16px!important}.card{padding:16px}#workspace-tabs [role=tablist] button{padding:8px 16px}.review-metric{padding:12px 10px;font-size:.77rem}.review-metric b{font-size:1.45rem}.section-heading h2{font-size:1.2rem}.review-navigation>button{flex:1!important}.review-navigation>.block{flex-basis:100%!important}.upload-footer{flex-direction:column!important}.upload-footer>button{width:100%!important}.model-switch{gap:9px;font-size:.83rem}.stepper{padding:12px 0}.secs{grid-template-columns:1fr}#audit-page-dialog .viewer-scroll{height:calc(100% - 132px)}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;scroll-behavior:auto!important;transition:none!important}}
"""

JS = r"""
  // Read-only evidence viewer; never starts a model, alters an audit or sends files.
  let pageDialog, pageImage, pageScale = 100, previousFocus;
  const resizePage = () => { if(pageImage) pageImage.style.width = pageScale + '%'; };
  const closePage = () => { if(pageDialog) pageDialog.close(); };
  document.addEventListener('click', e => {
    const open = e.target.closest && e.target.closest('.page-open');
    if (!open) return;
    const source = open.closest('figure').querySelector('img.zoomable');
    if (!source) return;
    previousFocus = open;
    if (!pageDialog) {
      pageDialog = document.createElement('dialog'); pageDialog.id = 'audit-page-dialog';
      pageDialog.setAttribute('aria-labelledby','audit-page-title');
      pageDialog.innerHTML = `<div class="viewer-toolbar"><span class="viewer-title" id="audit-page-title"></span><button type="button" data-view="out" aria-label="تصغير الصفحة">−</button><button type="button" data-view="in" aria-label="تكبير الصفحة">+</button><button type="button" data-view="fit">ملاءمة العرض</button><button type="button" data-view="close" aria-label="إغلاق عرض الصفحة">إغلاق ×</button></div><div class="viewer-scroll" tabindex="0" aria-label="صفحة المستند؛ مرر لمشاهدة التفاصيل"><img alt=""></div>`;
      document.body.appendChild(pageDialog); pageImage = pageDialog.querySelector('img');
      pageDialog.addEventListener('click', ev => {
        const b = ev.target.closest('[data-view]'); if (!b) return;
        if(b.dataset.view === 'close') { closePage(); return; }
        pageScale = b.dataset.view === 'fit' ? 100 : Math.max(50,Math.min(300,pageScale+(b.dataset.view === 'in'?25:-25))); resizePage();
      });
      pageDialog.addEventListener('close', () => { pageImage.removeAttribute('src'); if(previousFocus && previousFocus.isConnected) previousFocus.focus(); });
    }
    pageDialog.querySelector('.viewer-title').textContent = source.alt;
    pageImage.src = source.src; pageImage.alt = source.alt; pageScale = 100; resizePage();
    pageDialog.showModal(); pageDialog.querySelector('.viewer-scroll').scrollTo(0,0);
    pageDialog.querySelector('[data-view="close"]').focus();
  });
"""


def heading(kicker, title, description):
    return f"<header class='section-heading'><div><div class='section-kicker'>{kicker}</div><h2>{title}</h2><p>{description}</p></div></header>"


def step(number, title):
    return f"<div class='step-title'><span class='step-num'>{number}</span>{title}</div>"


def empty(title, description, symbol="◇"):
    return f"<div class='empty-state'><span class='empty-symbol' aria-hidden='true'>{symbol}</span><strong>{title}</strong><span>{description}</span></div>"
