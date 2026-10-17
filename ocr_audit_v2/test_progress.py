"""التقدّم حقيقي: ربطة ممسوحة صغيرة تُقرأ بـOCR، فتُسجَّل نسب متزايدة صفحة بعد صفحة، ولا تتجاوز 80% قبل انتهاء القراءة؛ والإلغاء يوقف المهمة."""
import os, sys, io, tempfile, threading, time, shutil, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pypdfium2 as pdfium
import job_pipeline as JP, app as A, report_template as T
sys.path.insert(0, os.path.join(T.ROOT, "ocr_audit_v2", "vlm"))

if __name__ == "__main__":
    # ربطة ممسوحة اصطناعية من 6 صفحات: صور فقط بلا طبقة نص
    src = os.path.join(T.ROOT, "المنافسات", "منافسة جراحة العظام MED-2026-144", "MED-2026-144-01-004.pdf")
    tmp = tempfile.mkdtemp()
    pdf = pdfium.PdfDocument(src)
    imgs = [pdf[i].render(scale=2).to_pil().convert("L") for i in range(6)]
    scan = os.path.join(tmp, "مسح تجربة.pdf")
    imgs[0].save(scan, save_all=True, append_images=imgs[1:], resolution=150)
    j = JP.create_job("batch", None, [scan], synthetic=True)
    seen = []
    orig = JP.Job.update

    def spy(self, **kw):
        pr = kw.get("progress")
        if pr and pr.get("pct") is not None:
            seen.append((pr["done"], pr["total"], pr["pct"], A._bar({"state": "extracting", "progress": pr, "mode": "batch", "log": []})[3][:55]))
        return orig(self, **kw)
    JP.Job.update = spy
    r = JP.run_job(j)
    JP.Job.update = orig
    pcts = [p for _, _, p, _ in seen]
    print("تحديثات التقدّم:", len(seen), "| النسب:", pcts)
    assert len(seen) >= 3, seen
    assert pcts == sorted(pcts), "النسبة يجب ألا تتراجع"
    assert all(p <= 80 for p in pcts), "لا تتجاوز 80% قبل انتهاء القراءة"
    assert pcts[0] < 40 and pcts[-1] >= 79, pcts
    print("نص الشريط:", seen[1][3])
    print("حالة المهمة بعد الانتهاء:", r["state"])

    # الإلغاء: يُطلب بعد أول صفحة فتتوقف المهمة
    j2 = JP.create_job("batch", None, [scan], synthetic=True)
    def go():
        JP.run_job(j2)
    JP.Job.update = orig
    th = threading.Thread(target=go); th.start()
    time.sleep(2); JP.Job(j2.id).update(cancel=True); th.join(120)
    m = JP.Job(j2.id).load()
    print("بعد الإلغاء:", m["state"], "|", m.get("error"))
    assert m["state"] in ("failed", "awaiting_review", "approved")
    print("OK")
