"""واجهة عربية خاصة لفحص الدفعات والمنافسات: رفع ← متابعة ← مراجعة بالدليل ← تنزيل Excel واحد.

نسخة تجريبية خاصة: لا تعلن إقفالاً ولا دقة؛ كل بند غير محسوم يُحال للمراجع ويبقى في التقرير خلية فارغة وإقفالاً «يتطلب مراجعة».
المتغيرات: APP_PASSWORD (اختياري، رمز دخول)، AUDIT_DATA_DIR (مجلد المهام)، RETENTION_DAYS (مدة الاحتفاظ).

تصميم المتابعة (توجيه صاحب المشروع، 16 أكتوبر 2026): شريط تقدم يتحرك مع مراحل المهمة وزمنها، ولا وميض: المؤقّت لا يحدّث أي مكوّن
إلا إذا تغيّر محتواه فعلاً (توقيع محتوى لكل مكوّن)، والقائمة المنسدلة لا تُعاد بناؤها عند كل نبضة.
"""
from __future__ import annotations

import datetime as dt
import base64
import hashlib
import html
import io
import json
import math
import os
import subprocess
import sys
import threading
import time

import gradio as gr
import pypdfium2 as pdfium

import job_pipeline as JP
import landing as L

# العرض التقديمي داخل النظام: صفحة HTML مستقلة تُعرض في إطار، فلا يختلط كودها بكود الواجهة
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
PRES_FILE = next((p for p in (os.path.join(_APP_DIR, "static", "presentation.html"), os.path.join(_APP_DIR, "presentation.html"))
                  if os.path.exists(p)), None)
if PRES_FILE:
    gr.set_static_paths(paths=[PRES_FILE])
PRES_URL = None
if PRES_FILE:
    with open(PRES_FILE, "rb") as _pres_source:
        _pres_revision = hashlib.sha256(_pres_source.read()).hexdigest()[:12]
    PRES_URL = "/gradio_api/file=" + PRES_FILE.replace(os.sep, "/") + "?v=" + _pres_revision


def pres_link_html() -> str:
    return ("<div style='text-align:center;margin:.6rem 0'><a href='" + html.escape(PRES_URL) + "' target='_blank' rel='noopener' "
            "style='display:inline-block;padding:.7rem 1.4rem;border-radius:14px;background:#0f766e;color:#fff;font-weight:800;text-decoration:none'>"
            "🎬 العرض التقديمي للمشروع · Project presentation</a></div>") if PRES_URL else ""


def pres_tab_html() -> str:
    if not PRES_URL:
        return "<div class='hint'>ملف العرض التقديمي غير موجود في هذا التشغيل.</div>"
    u = html.escape(PRES_URL)
    return ("<div class='presentation-stage'>"
            "<iframe class='presentation-frame' src='" + u + "' title='العرض التقديمي للمشروع · Project presentation' "
            "allow='fullscreen' allowfullscreen></iframe></div>")


# ---------------------------------------------------------------- المظهر
CSS = """
:root{--brand:#17365D;--brand2:#1F4E79;--soft:#E1EFFA;--soft2:#F3F8FD;--line:#9BB3C9;--ink:#17212F;--mut:#5B6778;--card:#FFFFFF;--track:#E9EEF4;
      --ok:#1E7B4B;--ok-bg:#E4F5EC;--warn:#B45309;--warn-bg:#FFF4E0;--bad:#B3261E;--bad-bg:#FDEAE8;--info:#1F4E79;--info-bg:#E1EFFA}
.dark{--brand:#A9CDF2;--brand2:#2F6FB0;--soft:#1E3550;--soft2:#1A2A3A;--line:#3F5A75;--ink:#E6EDF5;--mut:#9FB0C3;--card:#17232F;--track:#243546;
      --ok:#5FD39A;--ok-bg:#12382A;--warn:#F2B25C;--warn-bg:#3B2A10;--bad:#FF9A92;--bad-bg:#40191A;--info:#9CC9F5;--info-bg:#1E3550}
.gradio-container{direction:rtl;font-family:'Tahoma','Segoe UI',Arial,sans-serif !important;width:100%!important;max-width:1440px!important;margin-inline:auto!important;box-sizing:border-box;padding-inline:clamp(12px,2vw,28px)!important}
.gradio-container>main{width:100%;max-width:none!important;padding:16px 0!important;box-sizing:border-box}
.gradio-container .block,.gradio-container .form,.gradio-container .tabs,.gradio-container .tabitem{min-width:0;box-sizing:border-box}
#presentation-panel{padding:0!important;border:0!important;background:transparent!important;min-width:0;width:100%}
.presentation-stage{inline-size:100%;max-inline-size:100%;min-inline-size:0;margin:0;overflow:hidden;border:1px solid var(--line);border-radius:16px;background:#0b1020;box-shadow:0 8px 28px rgba(11,16,32,.14)}
.presentation-frame{display:block;inline-size:100%;max-inline-size:100%;block-size:clamp(480px,76svh,900px);border:0;background:#0b1020;direction:ltr}
.app-toolbar{justify-content:flex-start!important;gap:8px!important}
.app-toolbar>button{flex:0 1 auto!important;width:auto!important;min-width:120px!important;min-height:44px;border-radius:10px}
.tab-nav,[role=tablist]{max-width:100%;overflow-x:auto;flex-wrap:nowrap;scrollbar-width:thin}
.tab-nav button,[role=tablist] button{white-space:nowrap;min-height:44px;flex-shrink:0}
@media(max-width:640px){.presentation-stage{border-radius:12px}.presentation-frame{block-size:max(500px,76svh)}h1.app-title{font-size:1.15rem;line-height:1.65}.app-sub{font-size:.85rem;line-height:1.7}.secs{grid-template-columns:1fr}}
.gradio-container .prose,.gradio-container label,.gradio-container input,.gradio-container textarea{text-align:right}
h1.app-title{color:var(--brand);font-size:1.55rem;margin:.2rem 0 .1rem;font-weight:800}
.app-sub{color:var(--mut);margin:0 0 .6rem}
.note{background:var(--warn-bg);border:1px solid var(--warn);border-radius:10px;padding:8px 12px;font-size:.88rem}
.note,.note *{color:var(--ink) !important}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:.5rem 0;box-shadow:0 1px 3px rgba(23,54,93,.08)}
.card h3{margin:0 0 .5rem;color:var(--brand);font-size:1.05rem}
.card,.card *{color:var(--ink)}
.badge{display:inline-flex;align-items:center;gap:.4rem;border-radius:999px;padding:.28rem .85rem;font-weight:700;font-size:.95rem}
.badge.info{background:var(--info-bg);color:var(--info) !important}.badge.warn{background:var(--warn-bg);color:var(--warn) !important}
.badge.ok{background:var(--ok-bg);color:var(--ok) !important}.badge.bad{background:var(--bad-bg);color:var(--bad) !important}
.dot{width:.62rem;height:.62rem;border-radius:50%;background:currentColor;display:inline-block}
.dot.live{animation:pulse 1.3s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.7)}}
.pbar{position:relative;height:20px;background:var(--track);border-radius:999px;overflow:hidden;margin:.7rem 0 .3rem;border:1px solid var(--line);direction:ltr}
.pfill{height:100%;width:var(--to);border-radius:999px;background-image:linear-gradient(135deg,rgba(255,255,255,.28) 25%,transparent 25%,transparent 50%,rgba(255,255,255,.28) 50%,rgba(255,255,255,.28) 75%,transparent 75%);background-size:28px 28px}
.pfill.anim{animation:grow var(--dur) cubic-bezier(.12,.6,.25,1) forwards,stripes 1.2s linear infinite;animation-delay:calc(var(--el) * -1),0s}
@keyframes grow{from{width:var(--from)}to{width:var(--to)}}
@keyframes stripes{from{background-position:0 0}to{background-position:28px 0}}
.pfill.info{background-color:var(--brand2)}.pfill.warn{background-color:#D98324}.pfill.ok{background-color:#1E9B5E}.pfill.bad{background-color:#C8362D}
.stepper{display:flex;gap:.4rem;margin:.6rem 0 .2rem;direction:ltr}
.step{flex:1;text-align:center;font-size:.82rem;color:var(--mut)}
.step .c{width:28px;height:28px;margin:0 auto .25rem;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;border:2px solid var(--line);background:var(--card);color:var(--mut)}
.step.done .c{background:var(--ok);border-color:var(--ok);color:#fff}.step.on .c{background:var(--brand2);border-color:var(--brand2);color:#fff;box-shadow:0 0 0 4px rgba(31,78,121,.18)}
.step.on{color:var(--brand);font-weight:700}.step.done{color:var(--ok)}
.chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.6rem}
.chip{background:var(--soft2);border:1px solid var(--line);border-radius:10px;padding:.35rem .7rem;font-size:.86rem}
.chip b{color:var(--brand)}
.err{background:var(--bad-bg);border:1px solid var(--bad);border-radius:10px;padding:8px 12px;margin-top:.6rem}.err,.err *{color:var(--bad) !important}
.synth{background:#F1E9FF;border:1px solid #C9B2F2;border-radius:10px;padding:6px 10px;margin:.4rem 0}.synth,.synth *{color:#4A2B87 !important}
.hint{color:var(--mut);font-size:.85rem}
.sumline{font-weight:700;color:var(--brand);margin:.2rem 0 .5rem}
.tab-nav button{font-weight:700}
.lensbar{margin:.5rem 0}
.secs{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:1rem;margin:.5rem 0;align-items:start}
.secs.one{grid-template-columns:1fr}
.sec h4{margin:.2rem 0 .5rem;color:var(--brand);font-size:1.02rem;border-bottom:2px solid var(--line);padding-bottom:.25rem}
.sec{display:flex;flex-direction:column;gap:.8rem}
.pages figure,.sec figure{margin:0;border:1px solid var(--line);border-radius:12px;padding:.4rem;background:var(--card)}
.pages figure.focus,.sec figure.focus{border:2px solid var(--warn)}
.pages figcaption,.sec figcaption{font-weight:700;color:var(--brand);margin:.15rem .3rem .35rem}
.pages img.zoomable,.sec img.zoomable{width:100%;display:block;border-radius:6px;cursor:default;background:#fff}
button.lens-toggle{background:var(--soft);color:var(--brand);border:1px solid var(--line);border-radius:999px;padding:.3rem .9rem;font-weight:700;cursor:pointer;font-family:inherit}
button.lens-toggle:hover{background:var(--brand2);color:#fff}
.lens-toggle .st::before{content:"متوقفة"}
.lens-toggle.on{background:var(--brand2);color:#fff;border-color:var(--brand2)}
.lens-toggle.on .st::before{content:"مفعّلة"}
#lens{position:fixed;width:240px;height:240px;border-radius:50%;border:3px solid #2F6FB0;box-shadow:0 8px 28px rgba(0,0,0,.5);pointer-events:none;display:none;z-index:99999;background-repeat:no-repeat;background-color:#fff}
#lens-tag{position:fixed;z-index:100000;pointer-events:none;display:none;background:#17365D;color:#fff;font-size:.75rem;font-weight:700;padding:.1rem .5rem;border-radius:999px}
"""
CSS += L.LANDING_CSS

THEME = gr.themes.Soft(primary_hue=gr.themes.colors.blue, neutral_hue=gr.themes.colors.slate).set(button_primary_background_fill="#1F4E79",
                                                                               button_primary_background_fill_hover="#17365D",
                                                                               button_primary_text_color="#FFFFFF")
LENS_JS = """() => {
  if (window.__lensInstalled) return; window.__lensInstalled = true;
  const lens = document.createElement('div'); lens.id = 'lens'; document.body.appendChild(lens);
  const tag = document.createElement('div'); tag.id = 'lens-tag'; document.body.appendChild(tag);
  const ZS = [2.5, 4, 6]; let zi = 0, lastSrc = null, on = false; const R = 120;
  const hide = () => { lens.style.display = 'none'; tag.style.display = 'none'; };
  const sync = () => document.querySelectorAll('.lens-toggle').forEach(b => b.classList.toggle('on', on));      // حالة الزر على الزر نفسه (CSS الصفحة لا يصل إلى body)
  new MutationObserver(() => requestAnimationFrame(sync)).observe(document.body, {childList: true, subtree: true});
  document.addEventListener('mousemove', e => {
    if (!on) return;
    const img = e.target && e.target.closest ? e.target.closest('img.zoomable') : null;
    if (!img) { hide(); return; }
    const r = img.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, Z = ZS[zi];
    if (lastSrc !== img.src) { lens.style.backgroundImage = 'url(' + img.src + ')'; lastSrc = img.src; }
    lens.style.display = 'block';
    lens.style.left = (e.clientX - R) + 'px'; lens.style.top = (e.clientY - R) + 'px';
    lens.style.backgroundSize = (r.width * Z) + 'px ' + (r.height * Z) + 'px';
    lens.style.backgroundPosition = (R - x * Z) + 'px ' + (R - y * Z) + 'px';
    tag.textContent = '×' + Z; tag.style.display = 'block'; tag.style.left = (e.clientX + R - 36) + 'px'; tag.style.top = (e.clientY + R - 8) + 'px';
  }, {passive: true});
  document.addEventListener('click', e => {
    const t = e.target && e.target.closest ? e.target : null;
    if (!t) return;
    if (t.closest('.lens-toggle')) { on = !on; sync(); if (!on) hide(); return; }   // العدسة اختيارية: تُفعَّل بالزر فقط
    if (on && t.closest('img.zoomable')) zi = (zi + 1) % ZS.length;
  });
  document.addEventListener('scroll', hide, true);
}"""
LENS_JS = LENS_JS.replace("document.addEventListener('scroll', hide, true);", "document.addEventListener('scroll', hide, true);" + L.LANG_JS)
NOTE = ("نسخة تجريبية خاصة. لا يُحكم بإقفال ولا تُعلن دقة: كل ما لا تثبته المستندات يُحال للمراجعة بدليل الصفحة، "
        "ويبقى في Excel خلية فارغة وخلية الإقفال «يتطلب مراجعة». الحساب النهائي بقواعد العقد (Decimal) وليس بنموذج لغوي.")
_THREADS: dict[str, threading.Thread] = {}
_HERE = os.path.dirname(os.path.abspath(__file__))


def _orient_hint():
    """إرشاد الاتجاه في شاشة الرفع: صورة مصغرة لسند اصطناعي بالاتجاه الصحيح، وإحالة لأداة تصحيح الاتجاه."""
    try:
        example_path = os.path.join(_HERE, "assets", "orient_example.jpg")
        if not os.path.isfile(example_path):
            example_path = os.path.join(_HERE, "orient_example.jpg")  # يدعم تخطيط الملفات المسطح على Space
        with open(example_path, "rb") as f:
            src = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        src = ""
    items = [
        "<b>وضوح الطباعة:</b> أن تكون الأوراق مطبوعة وممسوحة بوضوح، خالية من الشوائب والظلال والكتابة فوق الأرقام، ليقرأها النموذج بدقة.",
        "<b>الاتجاه:</b> أن تكون كل الأوراق بالاتجاه الأفقي المطابق للصورة المصغرة (العنوان في الأعلى والنص مقروء دون تدوير). "
        "وإن كان في الملف صفحات مقلوبة أو مُدارة فاستعمل تبويب «🧭 أداة تصحيح الاتجاه» قبل الرفع.",
        "<b>الترتيب:</b> أن تُرتَّب المستندات بتسلسلها: التعميد، ثم سند الاستلام، وتحت كل سند الفاتورة التي تبرره.",
        "<b>العقد:</b> يُفضَّل رفع عقد المنافسة إن وُجد؛ فبه تُتحقق العمولة والضريبة والغرامة ومبلغ السداد وتُكتشف ملاحظات أكثر "
        "(وبدونه يُعتمد السند الأول مرجعاً).",
        "<b>فحص منافسة كاملة:</b> تُرفع ربطات المنافسة كلها (السندات والفواتير) في ملف مستقل أو عدة ملفات، ويُرفع العقد وحده في خانته.",
        "<b>الملفات الكبيرة:</b> يمكن ضغطها في ملف ZIP ورفعه مباشرة.",
    ]
    return ("<div class='card' style='display:flex;gap:1rem;align-items:flex-start;flex-wrap:wrap'>"
            + (f"<figure style='width:250px;max-width:100%;margin:0'><img src='{src}' alt='سند الاستلام الاصطناعي STO0000005253 من المنافسة MED-2026-339 بالاتجاه الصحيح' "
               "style='width:100%;border-radius:8px;border:1px solid #9BB3C9'><figcaption style='font-size:.75rem;line-height:1.6;margin-top:.35rem'>"
               "مثال سند استلام اصطناعي بالشكل المعتمد والاتجاه الصحيح</figcaption></figure>" if src else "")
            + "<div style='flex:1;min-width:260px'><b>شروط الرفع</b><ol style='margin:.4rem 0 0;padding-inline-start:1.3rem;line-height:1.9'>"
            + "".join(f"<li>{x}</li>" for x in items) + "</ol></div></div>")


def _spawn(job_id: str, mode: str = "run"):
    """الفحص في عملية مستقلة (job_runner.py) لا في خيط داخل الواجهة: يُلغى بقتلها بالكامل."""
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) if os.name == "nt" else 0
    p = subprocess.Popen([sys.executable, os.path.join(_HERE, "job_runner.py"), job_id, mode], cwd=_HERE, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=(os.name != "nt"))
    JP.Job(job_id).update(pid=p.pid)
    return p


def _kill_tree(pid: int):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:  # noqa: BLE001
        pass
STEPS = ["رفع الملفات", "استخراج البيانات", "التدقيق", "المراجعة"]
DECISION_OK = "سليم — يدخل التقرير"
DECISION_BAD = "فيه مشكلة — لا يدخل التقرير"
DECISION_AR = {"reject": "فيه مشكلة — مستبعد", "set_value": "أُدخلت قيمة", "confirm_blank": "تأكيد خلو المصدر", "verified_ok": "قراءة مطابقة", "cannot_decide": "تعذّر الحسم"}


# ---------------------------------------------------------------- حالة المهمة (نصوص معتمدة من صاحب المشروع)
def _unit(m):
    return "الدفعه" if m["mode"] == "batch" else "المنافسة"


def _since(m):
    """ثوانٍ منذ آخر تغيّر في الحالة (من أول مقطع في آخر سطر سجل)."""
    try:
        last = (m.get("log") or [""])[-1].split(" ", 1)[0]
        return max(0.0, (dt.datetime.now() - dt.datetime.fromisoformat(last)).total_seconds())
    except Exception:  # noqa: BLE001
        return 0.0


def _bar(m):
    """معاملات حركة الشريط للمرحلة الحالية: (من %، إلى %، مدة الحركة ث، نص الحالة، لون، رقم الخطوة، حيّ).
    الحركة تجري كلها في المتصفح بـCSS خلال المرحلة، فلا يُعاد رسم أي شيء بين النبضات (لا وميض). الشريط لا يصل 100% قبل انتهاء الفحص."""
    s, pr = m.get("state"), m.get("progress") or {}
    u = _unit(m)
    if s == "uploaded":
        return 0, 12, 3, f"تم رفع ملفات {u}", "info", 0, True
    if s == "files_checked":
        return 12, 20, 3, f"تم رفع ملفات {u}", "info", 0, True
    real = pr.get("pct") is not None and s in ("extracting", "matching")
    if s == "extracting":
        if real:                                                          # تقدّم حقيقي: صفحات (أو ربطات) انتهت قراءتها فعلاً
            d, n, unit = pr.get("done") or 0, pr.get("total") or 0, pr.get("unit") or "صفحة"
            eta = pr.get("eta_s")
            what = pr.get("note") or "جاري استخراج البيانات المحاسبية"
            lab = (f"{what}: {d} من {n} {unit} ({round(pr['pct'])}%)" if n > 1 or d else f"جاري تحضير الملف للقراءة ({round(pr['pct'])}%)")
            if pr.get("bundle") and pr["bundle"] != "1/1":
                lab += f" — الربطة {pr['bundle']}"
            if eta:
                lab += f" — المتبقي نحو {max(1, round(eta / 60))} د" if eta >= 90 else f" — المتبقي نحو {eta} ث"
            return pr.get("from_pct", pr["pct"]), pr["pct"], 2, lab, "info", 1, True
        return 20, 45, 90, "جاري استخراج البيانات المحاسبيه", "info", 1, True        # النص المعتمد من صاحب المشروع
    if s == "matching":
        if real:                                                          # بعد القراءة: 80% ثم نمو بطيء حتى 96% أثناء التدقيق وكتابة التقرير
            return max(80, round(pr["pct"])), 96, 60, "تمت قراءة الصفحات وجاري التدقيق والمطابقة وكتابة التقرير", "info", 2, True
        if m.get("mode") == "batch":                                      # ربطة نصية: لا قراءة بطيئة، فيبدأ الشريط من بعد الرفع
            return 20, 95, 60, "تم استخراج البيانات المحاسبية وجاري العمل على تدقيقها", "info", 2, True
        return 62, 95, 70, "تم استخراج البيانات المحاسبية وجاري العمل على تدقيقها", "info", 2, True
    if s == "awaiting_review":
        return 100, 100, 0, f"تم التدقيق {u} تحتاج إلى مراجعة", "warn", 3, False
    if s in ("approved", "exported"):
        return 100, 100, 0, f"تم التدقيق {u} سليمه", "ok", 3, False
    if s == "failed":
        return 100, 100, 0, "تعذر إكمال الفحص", "bad", 1, False
    return 0, 0, 0, m.get("state_ar", ""), "info", 0, False


def _stage(m):
    """(نسبة الهدف، نص الحالة، لون، رقم الخطوة، حيّ) — واجهة مبسّطة تستعملها الاختبارات."""
    a, b, dur, label, tone, step, live = _bar(m)
    return b, label, tone, step, live


def _status_key(m):
    """مفتاح التغيّر الحقيقي للمتابعة؛ لا يحوي الزمن المنقضي حتى لا يُعاد رسم البطاقة بين النبضات."""
    return [m.get("state"), m.get("progress"), m.get("open_count"), m.get("error"), m.get("eval"), m.get("seconds"),
            [f.get("name") for f in m.get("files", [])], len((m.get("check") or {}).get("problems", [])), bool(m.get("synthetic"))]


def _esc(x):
    return html.escape(str(x if x is not None else ""))


def _ltr(x):
    """معرّفات وأسماء ملفات لاتينية داخل نص عربي: تُعزل حتى لا يختلط اتجاه الجملة."""
    return f"<bdi dir='ltr'>{_esc(x)}</bdi>"


def status_html(job_id):
    if not job_id:
        return "<div class='card'><h3>المتابعة</h3><span class='hint'>اختر مهمة أو ابدأ فحصاً جديداً من تبويب «رفع».</span></div>"
    m = JP.Job(job_id).load()
    a, b, dur, label, tone, step, live = _bar(m)
    finished = tone == "ok"
    steps = "".join(f"<div class='step {'done' if (i < step or (finished and i == step)) else ('on' if i == step else '')}'>"
                    f"<div class='c'>{'✓' if (i < step or (finished and i == step)) else i + 1}</div>{n}</div>" for i, n in enumerate(STEPS))
    pr = m.get("progress") or {}
    files = "، ".join(f"{_ltr(f['name'])} <span class='hint'>({_ltr(f['sha256'][:8])})</span>" for f in m.get("files", []) if f["kind"] != "truth")
    _ts = (m.get('progress') or {}).get('ts')
    elapsed = min(max(0.0, time.time() - _ts) if (_ts and m.get('state') == 'extracting') else _since(m), dur) if live else 0
    out = [f"<div class='card'><h3>{'فحص دفعة' if m['mode'] == 'batch' else 'فحص منافسة'} <span class='hint'>— {_ltr(job_id)}</span></h3>"]
    if m.get("synthetic"):
        out.append("<div class='synth'>⚠ ملف اختبار مصنّع — ليس ربطة حقيقية</div>")
    out.append(f"<span class='badge {tone}'><span class='dot {'live' if live else ''}'></span>{_esc(label)}</span>")
    if m.get("note_ar"):
        out.append(f"<div class='hint' style='margin-top:.5rem'>{_esc(m['note_ar'])}</div>")
    # شريط التقدم يظهر مرة واحدة في بطاقة المهمة أعلى الشاشة؛ هنا المراحل والتفاصيل فقط
    out.append(f"<div class='stepper'>{steps}</div>")
    chips = [f"<span class='chip'>البنود غير المحسومة: <b>{m.get('open_count', 0)}</b></span>"]
    if pr.get("total", 0) > 1 and pr.get("pct") is None:          # مع التقدّم الحقيقي يظهر العدّ في نص الشريط فلا يُكرَّر هنا
        chips.append(f"<span class='chip'>{'الصفحات' if pr.get('unit') == 'صفحة' else 'الربطات'}: <b>{pr.get('done', 0)}/{pr.get('total', 0)}</b> {_esc(pr.get('note', ''))}</span>")
    if m.get("seconds"):
        chips.append(f"<span class='chip'>زمن المعالجة: <b>{_esc(m['seconds'])}</b> ث</span>")
    out.append("<div class='chips'>" + "".join(chips) + "</div>")
    out.append(f"<div class='hint' style='margin-top:.6rem'>الملفات: {files}</div>")
    if m.get("error"):
        out.append(f"<div class='err'><b>خطأ:</b> {_esc(m['error'])}</div>")
    if m.get("eval"):
        out.append("<div class='hint' style='margin-top:.5rem'><b>تقييم مقابل المرجع النصي:</b> " + "، ".join(f"{_esc(k)}: {_esc(v)}" for k, v in m["eval"].items()) + "</div>")
    chk = m.get("check")
    if chk and chk.get("problems"):
        out.append("<div class='hint' style='margin-top:.5rem'>" + "<br>".join(f"({_esc(p['level'])}) {_esc(p['msg'])}" for p in chk["problems"]) + "</div>")
    out.append("</div>")
    return "".join(out)


def _rows(m):
    rows = []
    for p in (m or {}).get("pending", []):
        d = p.get("decision") or {}
        rows.append([p["key"], p.get("reason", ""), p.get("sto", ""), p.get("invoice", ""), p.get("file", p.get("receipt_file", "")),
                     p.get("page", p.get("receipt_page", "")), DECISION_AR.get(d.get("action"), "—")])
    return rows


def _review_summary(rows):
    if not rows:
        return "<div class='sumline'>لا بنود للمراجعة في هذه المهمة.</div>"
    done = sum(1 for r in rows if r[6] in ("أُدخلت قيمة", "تأكيد خلو المصدر", "قراءة مطابقة", "فيه مشكلة — مستبعد"))
    return f"<div class='sumline'>بنود المراجعة: {len(rows)} — محسوم: {done} — متبقٍ: {len(rows) - done}</div>"


def _sig(x):
    return hashlib.md5(json.dumps(x, ensure_ascii=False, default=str).encode()).hexdigest()


def tick(job_id, sigs, force=False):
    """نبضة المتابعة: لا يُحدَّث أي مكوّن إلا إذا تغيّر توقيع محتواه (يمنع الوميض)."""
    sigs = dict(sigs or {})
    keys = {}
    if sigs.get("job") != job_id:
        sigs, force = {"job": job_id}, True
    if job_id:
        m = JP.Job(job_id).load()
        out = m.get("output") if m.get("output") and os.path.exists(m["output"]) else None
        if out:
            try:
                JP.ensure_review_style(out)                                  # مخرجات المهام الأقدم من النمط تُنسَّق قبل تنزيلها
            except Exception:  # noqa: BLE001
                pass
        rows = _rows(m)
        parts = {"status": status_html(job_id), "log": "\n".join(m.get("log", [])[-30:]), "rows": rows, "sum": _review_summary(rows),
                 "file": (out, os.path.getmtime(out)) if out else None, "card": job_card_html(job_id)}
        keys = {"status": _status_key(m), "log": len(m.get("log", [])), "card": _status_key(m)}     # توقيع التغيّر الحقيقي بلا الزمن المنقضي: مرور الزمن لا يعيد رسم البطاقة
    else:
        parts = {"status": status_html(None), "log": "", "rows": [], "sum": "", "file": None, "card": job_card_html(None)}
    res = []
    for k in ("status", "log", "rows", "sum", "file", "card"):
        s = _sig(keys.get(k, parts[k]))
        if force or sigs.get(k) != s:
            sigs[k] = s
            v = parts[k]
            res.append(v[0] if (k == "file" and v) else (None if k == "file" else v))
        else:
            res.append(gr.skip())
    return (*res, sigs)


def job_card_html(job_id):
    """بطاقة المهمة الحالية أعلى الشاشة: نوعها وملفاتها وحالتها وشريط تقدم مصغّر يتحرك مع الشريط الرئيسي (المصدر نفسه _bar)."""
    if not job_id:
        return "<div class='card jobcard'><b>لا فحص جارٍ</b> <span class='hint'>— ابدأ فحصاً من تبويب «رفع».</span></div>"
    m = JP.Job(job_id).load()
    a, b, dur, label, tone, step, live = _bar(m)
    _ts = (m.get("progress") or {}).get("ts")
    elapsed = min(max(0.0, time.time() - _ts) if (_ts and m.get("state") == "extracting") else _since(m), dur) if live else 0
    files = "، ".join(_ltr(f["orig"] if f.get("orig") else f["name"]) for f in m.get("files", []) if f["kind"] == "bundle")
    kind = "فحص دفعة" if m["mode"] == "batch" else "فحص منافسة"
    return (f"<div class='card jobcard'><div style='display:flex;justify-content:space-between;gap:.6rem;flex-wrap:wrap'>"
            f"<div><b>{kind}</b> <span class='hint'>— {files}</span></div><span class='hint'>{_ltr(job_id)}</span></div>"
            f"<span class='badge {tone}' style='margin-top:.4rem'><span class='dot {'live' if live else ''}'></span>{_esc(label)}</span>"
            f"<div class='pbar' style='height:10px;margin-top:.5rem'><div class='pfill {tone} {'anim' if live else ''}' "
            f"style='--from:{a}%;--to:{b}%;--dur:{dur}s;--el:{elapsed:.1f}s'></div></div></div>")


def _job_choices():
    return [(f"{m['id']} — {m['mode'] == 'batch' and 'دفعة' or 'منافسة'} — {m.get('state_ar', '')}", m["id"]) for m in JP.list_jobs()]


# ---------------------------------------------------------------- الإجراءات
def start(mode_ar, contract, batch_file, comp_files, who, synthetic=False, truth=None, context=None):
    mode = "batch" if mode_ar == "فحص دفعة" else "competition"
    import tempfile
    work = tempfile.mkdtemp(prefix="upload_")
    notes = []
    comp_paths, n1 = JP.expand_uploads([f if isinstance(f, str) else f.name for f in (comp_files or [])], os.path.join(work, "bundles"))
    ctx_paths, n2 = JP.expand_uploads([f if isinstance(f, str) else f.name for f in (context or [])], os.path.join(work, "context"))
    notes = n1 + n2
    context = ctx_paths
    batch_paths, n3 = JP.expand_uploads([batch_file if isinstance(batch_file, str) else batch_file.name] if (mode == "batch" and batch_file) else [], os.path.join(work, "batch"))
    notes += n3
    if mode == "batch" and len(batch_paths) > 1:
        return gr.skip(), (f"<div class='err'>الملف المضغوط يحوي {len(batch_paths)} ربطات؛ فحص الدفعة يتطلب ربطة واحدة. "
                           "ارفع الربطة المطلوبة، وضع الربطات المجاورة في «ربطات مجاورة للسياق».</div>"), gr.skip()
    bundles = batch_paths if mode == "batch" else comp_paths
    if not contract and mode == "competition":                      # فحص الدفعة يجوز بلا عقد (قواعد العقد حينئذ غير متحقق منها)
        return gr.skip(), "<div class='err'>ارفع عقد المنافسة أولاً.</div>", gr.skip()
    if not bundles:
        return gr.skip(), "<div class='err'>" + ("ارفع ملف الدفعه أولاً." if mode == "batch" else "ارفع ملفات المنافسة أولاً.") + "</div>", gr.skip()
    job = JP.create_job(mode, (contract if isinstance(contract, str) else contract.name) if contract else None,
                        [b if isinstance(b, str) else b.name for b in bundles], owner=who or "", synthetic=synthetic,
                        truth_path=(truth if isinstance(truth, str) else truth.name) if truth else None,
                        context_paths=[c if isinstance(c, str) else c.name for c in (context or [])] if mode == "batch" else None)
    chk = JP.check_files(job)
    if not chk["ok"]:
        job.set_state("failed", error="؛ ".join(p["msg"] for p in chk["problems"] if p["level"] == "error"))
        return gr.update(choices=_job_choices(), value=job.id), "<div class='err'>تعذر قبول الملفات؛ التفاصيل في تبويب «المتابعة».</div>", gr.Tabs(selected="follow")
    _spawn(job.id)
    unit = "الدفعه" if mode == "batch" else "المنافسة"
    extra = ("<div class='hint' style='margin-top:.4rem'>" + "<br>".join(_esc(n) for n in notes) + "</div>") if notes else ""
    return gr.update(choices=_job_choices(), value=job.id), f"<span class='badge ok'>✓ تم رفع ملفات {unit} — بدأ الفحص</span>{extra}", gr.Tabs(selected="follow")


def mode_changed(mode_ar):
    b = mode_ar == "فحص دفعة"
    lbl = "ارفع عقد المنافسة (اختياري في فحص الدفعة؛ بدونه لا تُتحقق قواعد العقد)" if b else "ارفع عقد المنافسة (إلزامي في فحص المنافسة)"
    return gr.update(visible=b), gr.update(visible=not b), gr.update(visible=b), gr.update(label=lbl)


def _page_range(pages):
    pages = sorted(set(pages))
    out, run = [], []
    for p in pages:
        if run and p == run[-1] + 1:
            run.append(p)
        else:
            if run:
                out.append(run)
            run = [p]
    if run:
        out.append(run)
    return "، ".join(f"{r[0]}" if len(r) == 1 else f"{r[0]}–{r[-1]}" for r in out)


MAX_GALLERY = 10


def show_item(job_id, key):
    """بند المراجعة مع **المعاملة كاملة**: صفحات السند المرتبط بفاتورته وتعميده معاً، وصفحة الملاحظة مميّزة."""
    if not job_id or not key:
        return "", ""
    job = JP.Job(job_id)
    m = job.load()
    p = next((x for x in m.get("pending", []) if x["key"] == key), None)
    if not p:
        return "", ""
    fname = p.get("file") or p.get("receipt_file")
    page = p.get("page") or p.get("receipt_page")
    fm = next((f for f in m.get("files", []) if f["name"] == fname), None)
    related = p.get("related") or []
    parts = []
    if m.get("synthetic"):
        parts.append("<div class='synth'>⚠ ملف اختبار مصنّع — ليس ربطة حقيقية</div>")
    parts.append(f"<div class='card'><h3>{_esc(p.get('reason', ''))}</h3>")
    parts.append(f"<div class='chips'><span class='chip'>السند: <b>{_ltr(p.get('sto') or '—')}</b></span>"
                 f"<span class='chip'>الفاتورة: <b>{_ltr(p.get('invoice') or '—')}</b></span>"
                 f"<span class='chip'>الصنف: <b>{_ltr(p.get('code') or '—')}</b></span>"
                 f"<span class='chip'>الملف: <b>{_ltr(fname or '—')}</b></span><span class='chip'>صفحة الملاحظة: <b>{_ltr(page or '—')}</b></span></div>")
    if related:
        parts.append("<div class='chips'>" + "".join(f"<span class='chip'>{_esc(g['label'])}: <b>{_ltr(_page_range(g['pages']))}</b></span>" for g in related) + "</div>")
    if fm:
        parts.append(f"<div class='hint' style='margin-top:.4rem'>SHA-256: {_ltr(fm['sha256'])}</div>")
    if p.get("why"):
        parts.append(f"<div style='margin-top:.5rem'><b>سبب الإحالة:</b> {_esc(p['why'])}</div>")
    docs = {}
    groups = {"receipt": [], "invoice": [], "po": [], "other": []}      # السندات لحالها والفواتير لحالها والتعميد لحاله
    seen = set()

    def kind_of(label):
        return "receipt" if label.startswith(("سند", "الظهور المكرر")) else ("invoice" if label.startswith("الفاتورة") else ("po" if label.startswith("التعميد") else "other"))

    for g in related:
        for pg in g["pages"]:
            if (g["file"], pg) not in seen:
                seen.add((g["file"], pg))
                groups[kind_of(g["label"])].append((g["file"], pg, g["label"], bool(fname == g["file"] and page and int(page) == pg)))
    if fname and page and (fname, int(page)) not in seen:                # صفحة الملاحظة خارج المعاملة المعروفة: تُعرض وحدها
        groups["other"].append((fname, int(page), "صفحة الملاحظة", True))
    count = [0]

    def figure(f, pg, label, focus):
        if count[0] >= MAX_GALLERY:
            return ""
        path = os.path.join(job.dir, "input", f)
        if not os.path.exists(path):
            return ""
        try:
            doc = docs.get(path) or docs.setdefault(path, pdfium.PdfDocument(path))
            im = doc[pg - 1].render(scale=2.0).to_pil().convert("RGB")
            im.thumbnail((1500, 1500))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
            count[0] += 1
            cap = f"{label} — ص{pg}" + ("  ◀ صفحة الملاحظة" if focus else "")
            return (f"<figure class='{'focus' if focus else ''}'><figcaption>{_esc(cap)}</figcaption>"
                    f"<img class='zoomable' alt='{_esc(cap)}' src='data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}'></figure>")
        except Exception as e:  # noqa: BLE001
            parts.append(f"<div class='hint'>(تعذّر عرض {_esc(label)} ص{pg}: {_esc(type(e).__name__)})</div>")
            return ""

    def section(title, items):
        figs = "".join(figure(*x) for x in items)
        return f"<section class='sec'><h4>{title} <span class='hint'>({len(items)})</span></h4>{figs}</section>" if figs else ""

    total = sum(len(v) for v in groups.values())
    secs = section("السندات", groups["receipt"]) + section("الفواتير", groups["invoice"])
    rest = section("التعميد", groups["po"]) + section("صفحات أخرى", groups["other"])
    if total > MAX_GALLERY:
        parts.append(f"<div class='hint'>عُرضت أول {MAX_GALLERY} صفحات من {total}؛ افتح الملف الأصلي للبقية.</div>")
    parts.append("</div>")
    pages_html = ("<div class='lensbar'><button type='button' class='lens-toggle'>🔍 عدسة التقريب: <span class='st'></span></button> "
                  "<span class='hint'>فعّلها بالضغط، ثم مرّر المؤشر فوق أي صفحة؛ وانقر على الصورة لتغيير القوة (×2.5 ← ×4 ← ×6).</span></div>"
                  f"<div class='secs'>{secs}</div>" + (f"<div class='secs one'>{rest}</div>" if rest else "")) if (secs or rest) else ""
    return pages_html, "".join(parts)


def save_decision(job_id, key, action_ar, value, note, who):
    """قراران فقط: «سليم» يدخل السند التقرير، و«فيه مشكلة» يُستبعد من التقرير. الملاحظة واسم المراجع إلزاميان."""
    if not (job_id and key):
        return "<div class='err'>اختر بنداً من الجدول أولاً.</div>"
    action = {DECISION_OK: "verified_ok", DECISION_BAD: "reject"}.get(action_ar)
    if not action:
        return "<div class='err'>اختر القرار: سليم أو فيه مشكلة.</div>"
    if not (note or "").strip():
        return "<div class='err'>ملاحظة المراجع إلزامية: اكتب سبب القرار.</div>"
    if not (who or "").strip():
        return "<div class='err'>اسم المراجع إلزامي.</div>"
    try:
        JP.review(JP.Job(job_id), key, action, None, note.strip(), who.strip())
    except Exception as e:  # noqa: BLE001
        return f"<div class='err'>تعذّر حفظ القرار: {_esc(e)}</div>"
    return "<span class='badge ok'>✓ حُفظ القرار — اضغط «إعادة بناء التقرير» بعد إنهاء المراجعة</span>"


def rebuild(job_id):
    if not job_id:
        return "<div class='err'>اختر مهمة.</div>"
    if JP.Job(job_id).load().get("state") in ("uploaded", "files_checked", "extracting", "matching"):
        return "<div class='err'>الفحص ما زال جارياً لهذه المهمة؛ انتظر اكتماله ثم أعد البناء.</div>"
    _spawn(job_id, "export")
    return "<span class='badge info'><span class='dot live'></span>بدأت إعادة البناء — تابع الحالة في تبويب «المتابعة»</span>"


# ---------------------------------------------------------------- الواجهة
def build():
    with gr.Blocks(css=CSS, theme=THEME, title=L.PROJECT_AR, js=LENS_JS) as demo:
        with gr.Column(visible=True) as landing:                                  # صفحة التعريف بالمشروع قبل الدخول
            gr.HTML(L.hero_html())
            enter = gr.Button("الدخول إلى النظام · Enter the system  ←", variant="primary", size="lg", elem_classes="enter-btn")
            gr.HTML(L.body_html())
            gr.HTML(pres_link_html())
        with gr.Column(visible=False) as main:
            gr.HTML("<h1 class='app-title'>"+L.PROJECT_AR+"</h1><p class='app-sub'>"+L.TAGLINE_AR+" · <bdi dir='ltr'>"+L.PROJECT_EN+"</bdi></p>")
            gr.HTML(f"<div class='note'>{NOTE}</div>")
            with gr.Row(elem_classes="app-toolbar"):
                about = gr.Button("عن المشروع · About", size="sm", scale=0)
            job_card = gr.HTML(job_card_html(None))
            job_dd = gr.Dropdown(label="المهمة", choices=_job_choices(), value=None, visible=False)   # حامل المهمة الجارية (مخفي): إدارة المهام في الخلفية، والمستخدم يرى فحصه الحالي فقط
            sigs = gr.State({})
            with gr.Tabs(selected="upload") as tabs:
                with gr.Tab("رفع", id="upload"):
                    mode = gr.Radio(["فحص دفعة", "فحص منافسة"], value="فحص دفعة", label="نوع الفحص")
                    with gr.Row():
                        with gr.Column():
                            contract = gr.File(label="ارفع عقد المنافسة (اختياري في فحص الدفعة؛ بدونه لا تُتحقق قواعد العقد)", file_types=[".pdf"], type="filepath")
                        with gr.Column():
                            batch_file = gr.File(label="ارفع ملف الدفعه (PDF أو ملف مضغوط ZIP يحوي ربطة واحدة)", file_types=[".pdf", ".zip"], file_count="single", type="filepath", visible=True)
                            comp_files = gr.File(label="ارفع ملفات المنافسة (ملفات PDF أو ملف مضغوط ZIP)", file_types=[".pdf", ".zip"], file_count="multiple", type="filepath", visible=False)
                    gr.HTML("<div class='hint'>يُقبل أي اسم للملف؛ وإن اتبع الصيغة رقم المنافسة-رقم الدفعة-رقم الربطة.pdf فستُملأ خانتا رقم الدفعة والربطة في التقرير.</div>")
                    gr.HTML(_orient_hint())
                    with gr.Accordion("خيارات اختيارية (يمكن تجاهلها)", open=False):
                        gr.HTML("<div class='hint'><b>اسم المراجع:</b> يُكتب في سجل المهمة لمعرفة من شغّل الفحص.<br><b>ربطات مجاورة:</b> في فحص الدفعة فقط، إن كانت فاتورة الدفعة مشتركة مع سندات في ربطات أخرى من المنافسة نفسها، ارفع تلك الربطات هنا فتُستعمل لمطابقة الفاتورة فقط ولا تدخل سنداتها في التقرير.</div>")
                        who = gr.Textbox(label="اسم المراجع", placeholder="اختياري")
                        context = gr.File(label="ربطات مجاورة من المنافسة نفسها للسياق (اختياري، فحص الدفعة فقط؛ PDF أو ZIP): تُقرأ لمطابقة الفاتورة المشتركة بين ربطات ولا تدخل صفوف التقرير",
                                          file_types=[".pdf", ".zip"], file_count="multiple", type="filepath", visible=True)
                        with gr.Accordion("أدوات القياس (للباحث فقط)", open=False):
                            gr.HTML("<div class='hint'>لقياس دقة النظام على ملفات اختبار مصنّعة: علّم الملف بأنه مصنّع، وارفع نسخته النصية الأصلية لمقارنة القراءة بها. لا تُستعمل مع الملفات الفعلية.</div>")
                            synth = gr.Checkbox(label="ملف اختبار مصنّع (ليس ربطة حقيقية)", value=False)
                            truth = gr.File(label="نسخة نصية مرجعية للقياس فقط (اختياري، لملفات الاختبار المصنّعة)", file_types=[".pdf"], type="filepath")
                    go = gr.Button("ابدأ الفحص", variant="primary", size="lg")
                    msg = gr.HTML()
                with gr.Tab("المتابعة", id="follow"):
                    status = gr.HTML(status_html(None))
                    cancel_btn = gr.Button("إلغاء الفحص وإيقافه فوراً", variant="stop", size="sm")
                    cancel_msg = gr.HTML()
                    with gr.Accordion("سجل المهمة", open=False):
                        log = gr.Textbox(show_label=False, lines=8, interactive=False)
                with gr.Tab("المراجعة", id="review"):
                    summ = gr.HTML()
                    table = gr.Dataframe(headers=["المفتاح", "السبب", "السند", "الفاتورة", "الملف", "الصفحة", "القرار"], interactive=False, wrap=True)
                    key_dd = gr.Textbox(label="مفتاح البند (يُملأ باختيار صف من الجدول)")
                    show_btn = gr.Button("اعرض الدليل")
                    info = gr.HTML()
                    img = gr.HTML()
                    with gr.Group():
                        action = gr.Radio([DECISION_OK, DECISION_BAD], value=None, label="القرار")
                        value = gr.Textbox(visible=False)          # لم يعد يُستعمل: قراران فقط
                        note = gr.Textbox(label="ملاحظة المراجع (إلزامية)")
                        reviewer = gr.Textbox(label="اسم المراجع (إلزامي)")
                    save = gr.Button("احفظ القرار", variant="primary")
                    saved = gr.HTML()
                    rebuild_btn = gr.Button("إعادة بناء التقرير بعد المراجعة", variant="primary")
                    rebuilt = gr.HTML()
                with gr.Tab("التقرير", id="report"):
                    gr.HTML("<div class='card'><h3>تقرير <bdi dir='ltr'>Excel</bdi></h3><span class='hint'>المسودة تُنزَّل في أي وقت وتحمل «يتطلب مراجعة» في خلية الإقفال ما دامت بنود مفتوحة؛ التصدير النهائي لا يتم إلا بعد حسم كل البنود.</span></div>")
                    file_out = gr.File(label="ملف التقرير (Excel)")
                with gr.Tab("🧭 أداة تصحيح الاتجاه", id="orient"):
                    gr.HTML("<div class='card' style='border:2px solid #D98324;background:rgba(217,131,36,.08)'><h3 style='margin:0 0 .3rem'>🧭 أداة تصحيح الاتجاه — خارج عملية التدقيق</h3><span class='hint'>أداة مستقلة تُستعمل <b>قبل</b> الرفع للفحص: ارفع ملف PDF ممسوحاً فيُكشف اتجاه كل صفحة ويُصحَّح دون إعادة رسم الصورة (بلا فقد جودة)، ثم نزّل النسخة المصححة وارفعها في تبويب «رفع». لا تُنشئ مهمة فحص ولا تقريراً.</span></div>")
                    o_in = gr.File(label="ملف PDF", file_types=[".pdf"], type="filepath")
                    o_btn = gr.Button("صحّح الاتجاه", variant="primary")
                    o_out = gr.File(label="النسخة المصححة")
                    o_msg = gr.HTML()
                with gr.Tab("🎬 العرض التقديمي", id="present"):
                    gr.HTML(pres_tab_html(), elem_id="presentation-panel")

        enter.click(lambda: (gr.update(visible=False), gr.update(visible=True)), None, [landing, main])
        about.click(lambda: (gr.update(visible=True), gr.update(visible=False)), None, [landing, main])
        demo.load(lambda: gr.update(choices=_job_choices(), value=None), None, job_dd, show_progress="hidden")      # قائمة المهام تُجدَّد عند كل فتح للصفحة
        def orient_run(f, prog=gr.Progress()):
            import orient_tool as OT
            if not f:
                return None, "<div class='err'>ارفع ملف PDF أولاً.</div>"
            path = f if isinstance(f, str) else f.name
            dst = os.path.join(os.path.dirname(path), os.path.splitext(os.path.basename(path))[0] + " - مصحح الاتجاه.pdf")
            out, ch, bad, secs = OT.fix_and_verify(path, dst, prog=lambda x, d: prog(x, desc=d))
            txt = OT.summary(ch, bad, secs)
            return out, f"<span class='badge {'ok' if not bad else 'warn'}'>{_esc(txt)}</span>"
        o_btn.click(orient_run, o_in, [o_out, o_msg])
        mode.change(mode_changed, mode, [batch_file, comp_files, context, contract])
        go.click(start, [mode, contract, batch_file, comp_files, who, synth, truth, context], [job_dd, msg, tabs])
        outs = [status, log, table, summ, file_out, job_card, sigs]

        def cancel_job(job_id):
            """يطلب إلغاء الفحص الجاري: تتوقف القراءة عند الصفحة التالية وتصير الحالة «تعذر إكمال الفحص» بسبب الإلغاء."""
            if not job_id:
                return "<span class='hint'>اختر مهمة أولاً.</span>"
            job = JP.Job(job_id)
            m = job.load()
            if m.get("state") not in ("uploaded", "files_checked", "extracting", "matching"):
                return "<span class='hint'>لا فحص جارٍ لهذه المهمة.</span>"
            job.update(cancel=True)
            if m.get("pid"):
                _kill_tree(int(m["pid"]))                  # إيقاف كامل: تُقتل عملية الفحص وكل ما تحتها فوراً
            job.set_state("failed", error="أُلغي الفحص بطلب المستخدم (أُوقفت العملية بالكامل)", cancelled=True)
            return "<span class='badge warn'>أُلغي الفحص وأُوقفت العملية بالكامل</span>"
        cancel_btn.click(cancel_job, job_dd, cancel_msg)
        show_btn.click(show_item, [job_dd, key_dd], [img, info])

        def pick(evt: gr.SelectData, df):
            try:
                return df.iloc[evt.index[0], 0]
            except Exception:  # noqa: BLE001
                return ""
        table.select(pick, table, key_dd).then(show_item, [job_dd, key_dd], [img, info])
        save.click(save_decision, [job_dd, key_dd, action, value, note, reviewer], saved)
        rebuild_btn.click(rebuild, job_dd, rebuilt)
        job_dd.change(lambda j, s: tick(j, s, True), [job_dd, sigs], outs, show_progress="hidden")
        gr.Timer(2).tick(tick, [job_dd, sigs], outs, show_progress="hidden")
    return demo


def main():
    pw = os.environ.get("APP_PASSWORD")
    os.makedirs(JP.ROOT, exist_ok=True)
    JP.cleanup()
    demo = build()
    demo.queue().launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", "7860")),
                        auth=(("user", pw) if pw else None), max_file_size=f"{max(JP.MAX_FILE_MB, JP.MAX_ZIP_MB)}mb")


if __name__ == "__main__":
    main()
