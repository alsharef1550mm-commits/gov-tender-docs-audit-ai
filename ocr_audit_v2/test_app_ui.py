"""اختبار منطق واجهة المتابعة: مراحل التقدم والنصوص المعتمدة، وعدم تحديث أي مكوّن إذا لم يتغير محتواه (منع الوميض)."""
import os, re, sys, tempfile, io
os.environ.setdefault("AUDIT_DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gradio as gr
import app, job_pipeline as JP


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    base = {"mode": "batch", "files": [], "log": [], "progress": {"done": 0, "total": 1, "note": ""}, "open_count": 0}
    exp = {"uploaded": "تم رفع ملفات الدفعه", "files_checked": "تم رفع ملفات الدفعه", "extracting": "جاري استخراج البيانات المحاسبيه",
           "matching": "تم استخراج البيانات المحاسبية وجاري العمل على تدقيقها", "awaiting_review": "تم التدقيق الدفعه تحتاج إلى مراجعة",
           "approved": "تم التدقيق الدفعه سليمه"}
    last = -1
    for st, text in exp.items():
        pct, label, tone, step, live = app._stage({**base, "state": st})
        assert label == text, (st, label)
        assert pct >= last, (st, pct, last)                       # التقدم لا يتراجع بين المراحل
        last = pct
        print(f"{st:16s} {pct:3d}%  {tone:5s} خطوة {step}  {label}")
    assert app._stage({**base, "mode": "competition", "state": "approved"})[1] == "تم التدقيق المنافسة سليمه"
    # وميض: بعد أول نبضة لا يُحدَّث شيء إذا لم يتغير المحتوى
    f = tempfile.mkdtemp()
    job = JP.create_job("batch", __file__, [__file__.replace("test_app_ui", "test_engine")])
    job.set_state("approved")
    r1 = app.tick(job.id, {}, False)
    sigs = r1[-1]
    r2 = app.tick(job.id, sigs, False)
    skipped = sum(1 for v in r2[:-1] if v is gr.skip() or (isinstance(v, dict) and v.get("__type__") == "update" and len(v) == 1))
    print("نبضة ثانية بلا تغيير: مكوّنات متجاوَزة", skipped, "من", len(r2) - 1)
    assert skipped == len(r2) - 1
    # أثناء المرحلة الجارية: مرور الزمن وحده لا يغيّر شيئاً (لا إعادة رسم)
    job.set_state("extracting", progress={"done": 0, "total": 1, "note": ""})
    sg = app.tick(job.id, sigs, False)[-1]
    import time as _t
    _t.sleep(2.2)
    r_run = app.tick(job.id, sg, False)
    assert all(v is gr.skip() or (isinstance(v, dict) and len(v) == 1) for v in r_run[:-1]), "مرور الزمن أعاد رسم المتابعة (وميض)"
    print("أثناء الاستخراج ومرور الزمن: لا تحديثات (لا وميض)")
    job.set_state("awaiting_review")
    r3 = app.tick(job.id, sigs, False)
    assert not (r3[0] is gr.skip() or (isinstance(r3[0], dict) and len(r3[0]) == 1)), "تغيّر الحالة يجب أن يحدّث العرض"
    print("OK")


if __name__ == "__main__":
    main()
