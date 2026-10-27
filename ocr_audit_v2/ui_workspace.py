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

/* Google Stitch editorial direction, adapted to the existing Gradio controls.
   Presentation only: no handlers, request paths, model states or data transforms. */
.gradio-container,.dark .gradio-container,.gradio-container.dark{
 --brand:#eff2f5;--brand2:#35b99a;--soft:#1a2631;--soft2:#111b25;
 --line:#2d3a47;--ink:#eff2f5;--mut:#aab7c5;--card:#121c27;--track:#243341;
 --ok:#72d8a9;--ok-bg:#123027;--warn:#f0c17c;--warn-bg:#302819;--bad:#ffaaa3;--bad-bg:#352025;--info:#a9cbd9;--info-bg:#182c39;
 --body-background-fill:#0a1018;--body-background-fill-dark:#0a1018;
 --background-fill-primary:#121c27;--background-fill-primary-dark:#121c27;
 --background-fill-secondary:#1a2631;--background-fill-secondary-dark:#1a2631;
 --input-background-fill:#0d1620;--input-background-fill-dark:#0d1620;
 --border-color-primary:#2d3a47;--border-color-primary-dark:#2d3a47;
 --block-background-fill:#121c27;--block-background-fill-dark:#121c27;
 --body-text-color:#eff2f5;--body-text-color-dark:#eff2f5;
 --body-text-color-subdued:#aab7c5;--body-text-color-subdued-dark:#aab7c5;
 --button-primary-background-fill:#35b99a;--button-primary-background-fill-dark:#35b99a;
 --button-primary-text-color:#071d18;--button-primary-text-color-dark:#071d18;
 background:#0a1018!important;max-width:1440px!important;padding:24px clamp(16px,3.8vw,56px)!important;
 font-family:'Segoe UI',Tahoma,Arial,sans-serif!important;color:var(--ink);color-scheme:dark
}
body,.dark body,gradio-app{background:#0a1018!important}
.gradio-container>main{padding:0!important}
.landing{max-width:1200px;text-align:start}
.landing .topbar{padding:8px 0 22px;border-bottom:1px solid #62717d;gap:20px}
.landing .brand{display:flex;align-items:center;gap:14px;font-size:1.08rem;line-height:1.5}
.brand small{display:block;margin-top:5px;font-size:.72rem;font-weight:400;color:var(--mut)}
.landing .langsw{border-radius:6px;padding:3px;gap:3px;background:#111b25;border-color:var(--line)}
.landing .langbtn{border:0;border-radius:4px;padding:6px 12px;min-height:44px}
.landing .langbtn.on{background:#263b3d;color:#b2f1de}
.landing .hero{position:relative;padding:48px 0 0;margin-bottom:0}
.landing .hero-meta{display:flex;align-items:center;gap:14px;margin:0 0 24px;color:#9dbcb8;font-size:.86rem}
.journal-index{display:inline-block;direction:ltr;unicode-bidi:isolate;font-family:Consolas,monospace;color:#73cdb7;font-size:.8rem;font-weight:400;letter-spacing:1px;flex:none}
.landing .h-ar{font-size:clamp(2rem,4.1vw,3.35rem);line-height:1.5;font-weight:650;max-width:100%;letter-spacing:-.7px;text-wrap:balance}
.landing .h-ar em{font-style:normal;color:#97dfca;font-weight:500}
.landing .s-ar{font-size:1.05rem;line-height:2;max-width:74ch;margin-top:20px}
.landing .h-en{font-size:clamp(1.2rem,2.3vw,1.85rem);line-height:1.5;max-width:820px;margin-top:18px}
.landing .s-en{line-height:1.8;max-width:80ch}
.journal-abstract{border-inline-start:2px solid #57766e;padding-inline-start:18px;margin:24px 0 0;max-width:76ch;color:#c4ced7;font-size:.91rem;line-height:1.9}
.journal-abstract p{margin:0}
.landing .facts{margin-top:32px;background:transparent;border:0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);border-radius:0;gap:0}
.landing .facts>*{background:transparent;padding:15px 16px;font-size:.83rem;border-inline-end:1px solid var(--line)}
.landing .facts>*:last-child{border-inline-end:0}
.landing .facts li .en{font-size:.73rem;color:var(--mut)}
.landing-actions{max-width:1200px;margin:12px auto 18px!important;gap:12px!important;justify-content:flex-start!important}
.landing-actions>.enter-btn{min-width:260px!important;min-height:54px!important;background:#35b99a!important;color:#071d18!important;border-radius:6px!important;font-weight:700!important;padding:12px 24px!important}
.landing-actions>.enter-btn:hover{background:#76d7be!important}
.presentation-entry-link{justify-content:center;min-height:54px;padding:12px 24px!important;border:1px solid #526775!important;border-radius:6px;color:#e3eaf0!important;text-decoration:none!important;background:#111b25;font-size:.94rem!important;transition:background .15s,border-color .15s}
.presentation-entry-link:hover{border-color:#8fcbbb!important;background:#1b2e36}
.landing .acad{grid-template-columns:1.1fr 1.1fr .7fr 1.6fr;background:transparent;border:0;border-block:1px solid var(--line);border-radius:0;margin-top:14px;gap:0}
.landing .acad>*{background:transparent;padding:20px 16px;border-inline-end:1px solid var(--line)}
.landing .acad>*:last-child{border-inline-end:0}
.landing .acad dt{font-size:.73rem;letter-spacing:.4px;margin-bottom:7px}
.landing .acad dd{font-weight:500;font-size:.9rem;line-height:1.9}
.landing .ltitle{display:flex;align-items:center;gap:16px;font-size:1.4rem;line-height:1.6;margin:46px 0 20px;padding-bottom:12px;border-bottom:1px solid var(--line)}
.landing .lsteps{grid-template-columns:repeat(5,minmax(0,1fr));background:transparent;gap:14px;border:0;border-radius:0;overflow:visible}
.landing .lstep{background:#111b25;border:1px solid #2d3a47;padding:20px 16px!important;border-radius:6px}
.landing .snum{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border:1px solid #39564f;color:#9addc9;margin-bottom:20px;font-family:Consolas,monospace}
.landing .lt{font-size:.97rem;margin-bottom:10px}
.landing .ld{font-size:.85rem;color:#afbdc9;line-height:1.95}
.landing .lprin{padding:20px 4px;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:24px}
.landing .lfoot{display:block!important;font-size:.78rem;padding-top:22px;margin-top:40px}
.workspace-header{padding:12px 0 24px;border-bottom:1px solid #536472;gap:18px}
.workspace-mark{display:grid;place-items:center;flex:none;width:48px;height:54px;border:1px solid #52776d;color:#96dfca;border-radius:4px;font-size:25px}
.workspace-header .eyebrow{color:#88c6b6;font-size:.8rem;letter-spacing:.5px}
.workspace-header p{margin:0!important}
.workspace-header h1{margin:2px 0!important}
.section-heading p{margin:6px 0 0!important}
h1.app-title{font-weight:650;font-size:clamp(1.35rem,2.1vw,1.9rem);line-height:1.7;margin:0}
.app-sub{max-width:86ch;font-size:.88rem;line-height:1.9}
.app-toolbar{padding:6px 0!important;gap:14px!important}
.app-toolbar>button{background:#111b25!important;border:1px solid var(--line)!important;color:#cbd6de!important;border-radius:6px!important}
.model-switch{padding:12px 18px;border-radius:8px;background:#111b25;border-color:#344552}
.model-switch .state{font-size:.82rem}
.jobcard{padding:18px 22px!important;border-radius:6px!important;background:#111b25;border-inline-start:3px solid #5d9288}
#workspace-tabs [role=tablist]{border:0;border-bottom:1px solid #40515e;border-radius:0;padding:0 0 8px;gap:8px;background:transparent}
#workspace-tabs [role=tablist] button{border-radius:5px!important;padding:12px 22px;min-height:48px;color:#b4c2cf;font-size:.94rem}
#workspace-tabs [role=tablist] button.selected{background:#17332f!important;color:#baf1e0!important;box-shadow:inset 0 -2px #60c9ac}
#workspace-tabs [role=tablist] button:hover{background:#1a2934!important;color:#fff}
#workspace-tabs>.tabitem{padding-top:26px!important}
.section-heading{margin:0 0 18px;padding-bottom:16px;border-bottom:1px solid #243642}
.section-heading h2{font-size:1.55rem;font-weight:600;line-height:1.7}
.section-heading p{font-size:.9rem;line-height:1.9;margin-top:7px;max-width:90ch}
.section-kicker{color:#88c6b6;font-size:.76rem;letter-spacing:.4px;margin-bottom:6px}
.workspace-panel{padding:24px!important;border-radius:8px!important;border:1px solid #2e414e!important;background:#121c27!important;gap:16px!important}
.step-title{font-size:1.06rem;gap:12px;line-height:1.7}
.step-num{width:30px;height:30px;border-radius:4px;border-color:#38584f;color:#a5e0cf;background:#162b28}
.workspace-panel .hint{font-size:.87rem;color:#afbdc9;line-height:1.95}
.upload-grid{gap:18px!important}
.upload-zone{border:1px dashed #59737e!important;border-radius:6px!important;background:#0d1721!important;min-height:170px}
.upload-zone:hover,.upload-zone:focus-within{border-color:#87dac1!important;background:#132824!important}
.upload-zone button{min-height:150px;color:#c7d7de}
.upload-zone .file-preview button{min-height:44px}
.mode-choice label{border:1px solid #40535f!important;background:#0e1822!important;padding:12px 28px!important;min-height:50px;border-radius:5px!important}
.mode-choice label:has(input:checked){border-color:#63c4aa!important;background:#1b3933!important;color:#d6f9ed!important}
.mode-choice input{accent-color:#7fd7bf}
.preparation-guide{border-inline-start:3px solid #74948b!important;background:#101c25!important}
.preparation-guide h3{font-size:1.02rem!important;margin:0!important;font-weight:600!important;color:#dbe7e9!important}
.primary-action{min-height:52px!important;border-radius:6px!important;font-weight:700!important}
.upload-footer{padding-top:22px;border-top:1px solid #415360}
.review-metric{border-radius:6px;padding:20px 24px;background:#121c27;border-color:#2e414e;font-size:.86rem;color:#b6c4cf}
.review-metric b{font-size:2.1rem;font-weight:500;color:#e3eee9;margin-bottom:3px}
.review-metric.pending{border-inline-start:3px solid #e9b96d}
#review-table th{background:#192936!important;color:#d6e1e7!important;font-size:.85rem}
#review-table :is(th,td){padding:14px!important;border-color:#2c404d!important}
#review-table tbody tr:hover{background:#1c343c!important}
.empty-state{background:#101b25;border:1px dashed #415863;border-radius:8px;padding:48px 20px;color:#a9bcc9}
.empty-symbol{border-color:#426156;border-radius:5px;width:48px;height:48px;color:#9dddc8;background:#142a25;font-size:22px}
.empty-state strong{margin:16px 0 8px;font-size:1.15rem;font-weight:600}
.decision-panel{border-top:2px solid #6ac6aa!important}
.gradio-container input[type=password]{direction:ltr;text-align:left}
.gradio-container :is(input,textarea){caret-color:#88d8bd}
.gradio-container :is(button,a,input,textarea,select,[tabindex]):focus-visible{outline:2px solid #a4ebd4!important;outline-offset:3px!important}
.gradio-container button:disabled{opacity:.55;cursor:not-allowed}
.secs .sec h4{font-weight:500;border-bottom:1px solid #395260;padding-bottom:12px}
.secs figure{border-radius:6px;padding:12px;background:#121c27}
.lensbar{background:#15232e;border-color:#3b515d;border-radius:6px}
.page-open{border-color:#4b6874;border-radius:4px}
.report-note{padding:26px;border-radius:8px}
@media(max-width:700px){.app-toolbar>.block{flex-basis:100%!important;min-width:0!important}.app-toolbar .model-switch{justify-content:flex-start;gap:12px;width:100%}.app-toolbar>button{min-width:0!important}}
@media(min-width:1100px){.landing .hero{padding-inline-end:20%}.landing .hero::after{content:'OCR / AI';position:absolute;inset-inline-end:0;top:62px;font:12px Consolas,monospace;letter-spacing:3px;color:#78908f;border-top:2px solid #66877d;padding-top:14px;width:13%}.landing .facts{width:125%}}
@media(max-width:1100px){.landing .lsteps{grid-template-columns:repeat(3,minmax(0,1fr))}.landing .acad{grid-template-columns:repeat(2,minmax(0,1fr))}.landing .acad>*{border-bottom:1px solid var(--line)}}
@media(max-width:700px){.landing .topbar{align-items:flex-start}.landing .brand{font-size:.95rem}.landing .langsw{width:100%;justify-content:space-between}.landing .langbtn{flex:1}.landing .hero{padding-top:30px}.landing .h-ar{font-size:2.05rem;letter-spacing:0}.landing .hero-meta{font-size:.76rem;line-height:1.9;gap:10px}.landing .facts{grid-template-columns:repeat(2,minmax(0,1fr))}.landing .facts>*{border-bottom:1px solid var(--line);padding:13px 10px;font-size:.78rem}.landing .facts>*:nth-child(even){border-inline-end:0}.landing .s-ar{font-size:.94rem}.landing .lsteps{grid-template-columns:1fr}.landing .lstep{display:grid;grid-template-columns:36px 1fr;column-gap:14px}.landing .snum{grid-row:span 2;margin:0}.landing .lt{margin-bottom:5px}.landing .ld{grid-column:2}.landing .lprin{grid-template-columns:1fr;gap:8px}.landing .acad{grid-template-columns:repeat(2,minmax(0,1fr))}.landing .acad>*{padding:16px 10px}.landing .acad dd{font-size:.8rem}.landing .ltitle{font-size:1.2rem;margin-top:32px}.landing-actions{gap:10px!important}.landing-actions>.enter-btn{min-width:0!important;width:100%!important;flex:1 1 100%!important}.landing-actions>.presentation-entry{width:100%!important;flex:1 1 100%!important}.presentation-entry-link{width:100%}.workspace-mark{display:none}.workspace-panel{padding:18px!important}.review-metric{padding:16px 10px;font-size:.75rem}.review-metric b{font-size:1.7rem}.gradio-container{padding:16px!important}.workspace-header{padding-top:4px}.section-heading h2{font-size:1.3rem}#workspace-tabs [role=tablist] button{padding:10px 16px}}

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
