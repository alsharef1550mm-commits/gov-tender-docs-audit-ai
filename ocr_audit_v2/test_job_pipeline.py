"""اختبار مسار المهمة: مسار سليم (دفعة 318)، ومسار يحتاج مراجعة (منافسة 339 بثلاث ربطات فقط)، ومسار ممسوح."""
import glob
import io
import os
import shutil
import sys
import tempfile

import openpyxl

import job_pipeline as JP
import report_template as T
import report_writer as RW

R = T.ROOT


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    root = tempfile.mkdtemp()
    ex = os.path.join(R, "مثال فحص دفعه")
    # 1) مسار سليم
    j = JP.create_job("batch", os.path.join(ex, "عقد 318.pdf"), [os.path.join(ex, "MED-2026-318-01-001.pdf")], root)
    m = JP.run_job(j)
    print("1) الحالة:", m["state_ar"], "| بنود مفتوحة:", m.get("open_count"), "| مخرج:", os.path.basename(m["output"] or ""))
    assert m["state"] == "approved", m
    JP.approve_and_export(j)
    print("   بعد التصدير:", j.load()["state_ar"], "| فروق مقابل القالب:", len(RW.compare_workbooks(j.load()["output"], T.template_path("batch"))))
    # 2) مسار يحتاج مراجعة: ربطة 339 حُذفت منها صفحة الفاتورة 7 (فسندات تذكر فاتورة غير مرفقة)
    import pypdfium2 as pdfium
    folder = glob.glob(os.path.join(R, "المنافسات", "*MED-2026-339"))[0]
    srcp = os.path.join(folder, "MED-2026-339-01-001.pdf")
    src = pdfium.PdfDocument(srcp)
    keep = [i for i in range(len(src)) if i != 6]
    dst = pdfium.PdfDocument.new()
    dst.import_pages(src, keep)
    cut = os.path.join(tempfile.mkdtemp(), "MED-2026-339-01-001.pdf")
    dst.save(cut)
    j = JP.create_job("competition", os.path.join(folder, "العقد", "عقد المنافسة.pdf"), [cut], root)
    m = JP.run_job(j, workers=1)
    print("2) الحالة:", m["state_ar"], "| بنود:", len(m["pending"]), "| مفتوحة:", m["open_count"])
    assert m["state"] == "awaiting_review" and m["pending"]
    ws = openpyxl.load_workbook(m["output"])["تقرير المنافسة والأصناف"]
    cl = [c for c in ws["A"] if c.value == "حالة إقفال المنافسة"][0]
    print("   خلية الإقفال في المسودة:", ws.cell(cl.row, 2).value)
    assert ws.cell(cl.row, 2).value == "يتطلب مراجعة"
    for p in m["pending"][:2]:
        print("   مثال بند:", {k: p[k] for k in p if k != "decision"})
    for p in m["pending"]:
        JP.review(j, p["key"], "cannot_decide", note="اختبار")
    m = JP.run_job(j, workers=1)
    print("   بعد «تعذر الحسم»:", m["state_ar"])
    assert m["state"] == "awaiting_review"
    for p in m["pending"]:
        JP.review(j, p["key"], "confirm_blank", note="تحقق المراجع أن المصدر لا يطبع قيمة")
    m = JP.run_job(j, workers=1)
    print("   بعد تأكيد المراجع:", m["state_ar"])
    # 3) مسار ممسوح (OCR + إحالة): PDF صوري بلا طبقة نص
    import pypdfium2 as pdfium
    src = pdfium.PdfDocument(os.path.join(ex, "MED-2026-318-01-001.pdf"))
    imgs = [src[i].render(scale=1.2).to_pil().convert("RGB") for i in range(3)]
    sc = os.path.join(tempfile.mkdtemp(), "MED-2026-318-01-099.pdf")
    imgs[0].save(sc, save_all=True, append_images=imgs[1:])
    j = JP.create_job("batch", os.path.join(ex, "عقد 318.pdf"), [sc], root)
    m = JP.run_job(j)
    print("3) الحالة:", m["state_ar"], "| بنود:", [p["reason"] for p in m["pending"]][:1], "| مخرج:", m["output"])
    assert m["state"] == "awaiting_review" and any("ممسوحة" in p["reason"] for p in m["pending"]), m
    print("   مخرج المسودة:", bool(m["output"]), "| بنود:", len(m["pending"]))
    print("OK")


if __name__ == "__main__":
    main()
