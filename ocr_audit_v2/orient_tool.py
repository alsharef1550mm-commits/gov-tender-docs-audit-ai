"""أداة جانبية سريعة: تصحيح اتجاه كل صفحات ملف PDF ممسوح وحفظ نسخة مصححة.

التصحيح بلا فقد للجودة: يُضبط حقل الدوران (/Rotate) لكل صفحة في PDF نفسه، ولا تُعاد رسم الصورة.
كشف الاتجاه بالدالة نفسها التي يستعملها النظام قبل الاستخراج (scan_reader.correct_orientation: Tesseract OSD مع تحقق بالقراءة).

  سطر الأوامر:  python orient_tool.py <ملف.pdf> [ملف_الناتج.pdf]
  واجهة صغيرة:  python orient_tool.py --ui            (http://127.0.0.1:7862)
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pypdfium2 as pdfium

import scan_reader

RENDER_SCALE = 2.5          # نحو 2100 بكسل لصفحة A4: دون ذلك تضعف ثقة OSD على المسح الفعلي وتخطئ


def verify_pdf(path: str, workers: int = 8, progress=None):
    """يتحقق من نسخة مصححة: يكشف اتجاه كل صفحة فيها من جديد. يعيد قائمة الصفحات المشكوك فيها [(رقم، سبب)]."""
    doc = pdfium.PdfDocument(path)
    imgs = [doc[i].render(scale=RENDER_SCALE).to_pil() for i in range(len(doc))]
    doc.close()

    def one(i):
        o = scan_reader._osd(imgs[i].convert("L"))
        if not o:
            return i, "تعذر كشف الاتجاه"
        if o[1] < 1.5:
            return i, f"ثقة الكشف منخفضة ({o[1]})"
        if o[0] % 360:
            return i, f"ما زالت مُدارة {o[0]}°"
        return i, None
    bad = []
    with ThreadPoolExecutor(workers) as ex:
        for k, (i, why) in enumerate(ex.map(one, range(len(imgs))), 1):
            if why:
                bad.append((i + 1, why))
            if progress:
                progress(k, len(imgs))
    return sorted(bad)


def fix_pdf(src: str, dst: str | None = None, workers: int = 8, progress=None):
    """يعيد (مسار الناتج، قائمة [(رقم الصفحة، زاوية التصحيح بالدرجات مع عقارب الساعة)]، الزمن بالثواني)."""
    t0 = time.time()
    dst = dst or os.path.splitext(src)[0] + " - مصحح الاتجاه.pdf"
    doc = pdfium.PdfDocument(src)
    n = len(doc)
    imgs = [doc[i].render(scale=RENDER_SCALE).to_pil() for i in range(n)]       # التصيير تسلسلي (pdfium غير آمن مع الخيوط)
    angles = [0] * n

    def one(i):
        _img, a = scan_reader.correct_orientation(imgs[i])      # a: زاوية PIL (عكس عقارب الساعة)
        return i, a

    with ThreadPoolExecutor(workers) as ex:                       # Tesseract عملية مستقلة لكل صفحة: يتوازى بأمان
        for k, (i, a) in enumerate(ex.map(one, range(n)), 1):
            angles[i] = a
            if progress:
                progress(k, n)
    changes = []
    for i, a in enumerate(angles):
        if a:
            cw = (360 - a) % 360                                  # PIL يدير عكس عقارب الساعة و/Rotate مع عقاربها
            page = doc[i]
            page.set_rotation((page.get_rotation() + cw) % 360)
            changes.append((i + 1, cw))
    doc.save(dst)
    doc.close()
    return dst, changes, round(time.time() - t0, 1)


def fix_and_verify(src, dst=None, prog=None):
    """تصحيح ثم تحقق من النسخة الناتجة نفسها. يعيد (الناتج، التغييرات، الصفحات المشكوك فيها بعد التصحيح، الزمن)."""
    t0 = time.time()
    out, ch, _s = fix_pdf(src, dst, progress=(lambda k, n: prog(0.6 * k / n, f"كشف اتجاه الصفحات وتصحيحه: {k} من {n}")) if prog else None)
    bad = verify_pdf(out, progress=(lambda k, n: prog(0.6 + 0.4 * k / n, f"التحقق من النسخة المصححة: {k} من {n}")) if prog else None)
    return out, ch, bad, round(time.time() - t0, 1)


def summary(ch, bad, secs):
    s = (f"صُحّح اتجاه {len(ch)} صفحة" + (": " + "، ".join(f"ص{p} ({a}°)" for p, a in ch[:30]) + ("…" if len(ch) > 30 else "") if ch else "") if ch
         else "كل الصفحات كانت سليمة الاتجاه")
    v = ("التحقق من النسخة المصححة: كل الصفحات مستقيمة." if not bad else
         "التحقق: " + str(len(bad)) + " صفحة تحتاج نظرة يدوية: " + "، ".join(f"ص{p} ({w})" for p, w in bad[:20]))
    return f"{s}. {v} (الزمن {secs} ث)"


def ui(port=7862):
    import gradio as gr

    def run(f, prog=gr.Progress()):
        if not f:
            return None, "ارفع ملف PDF أولاً."
        path = f if isinstance(f, str) else f.name
        out, ch, bad, secs = fix_and_verify(path, os.path.join(os.path.dirname(path), os.path.splitext(os.path.basename(path))[0] + " - مصحح الاتجاه.pdf"),
                                            prog=lambda x, d: prog(x, desc=d))
        return out, summary(ch, bad, secs)

    with gr.Blocks(title="تصحيح اتجاه الصفحات") as demo:
        gr.Markdown("## تصحيح اتجاه صفحات PDF\nارفع ملفاً ممسوحاً، فيُكشف اتجاه كل صفحة ويُصحَّح دون إعادة رسم الصورة (بلا فقد جودة)، ثم نزّل النسخة المصححة.")
        f = gr.File(label="ملف PDF", file_types=[".pdf"], type="filepath")
        b = gr.Button("صحّح الاتجاه", variant="primary")
        out = gr.File(label="النسخة المصححة")
        msg = gr.Markdown()
        b.click(run, f, [out, msg])
    demo.queue().launch(server_name="127.0.0.1", server_port=port)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--ui":
        ui()
    elif len(sys.argv) > 1:
        dst, ch, secs = fix_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
        print(f"{dst}\nصفحات صُحّحت: {len(ch)} في {secs} ث: {ch}")
    else:
        print(__doc__)
