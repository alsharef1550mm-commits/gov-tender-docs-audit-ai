"""بند المراجعة يحمل المعاملة كاملة: صفحات السند مع نسخة فاتورته وتعميده (توجيه المالك)."""
import glob, io, os, sys, tempfile
os.environ.setdefault("AUDIT_DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract, job_pipeline as JP, report_template as T, report_writer as RW


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    folder = glob.glob(os.path.join(T.ROOT, "المنافسات", "*MED-2026-305"))[0]
    contract = glob.glob(os.path.join(folder, "العقد", "*.pdf"))[0]
    b1 = extract.read_bundle(os.path.join(folder, "MED-2026-305-01-001.pdf"))
    rel = RW.related_pages(b1, "STO0000002440")
    print({g["label"]: g["pages"] for g in rel})
    labels = [g["label"] for g in rel]
    assert labels == ["سند الاستلام", "الفاتورة", "التعميد"], labels
    inv = next(g for g in rel if g["label"] == "الفاتورة")["pages"]
    assert 63 in inv, inv                                       # صفحة سطر LAB-008 المنسوب للسند
    # فحص الدفعة 002 وحدها: الفاتورة المشتركة مبرر، فلا بنود مراجعة ويُقبل الملف آلياً (بنود السند 2488 الخارجي لا تُذكر)
    b2 = os.path.join(folder, "MED-2026-305-01-002.pdf")
    job = JP.create_job("batch", contract, [b2])
    m = JP.run_job(job)
    assert m["state"] == "approved" and not m["pending"], (m["state"], [p["reason"] for p in m["pending"]])
    print("002 وحدها:", m["state_ar"], "| بنود المراجعة:", len(m["pending"]))
    # حالة فيها بند فاتورة بلا سند (فحص المنافسة): تُعرض الفاتورة مع سنداتها المرتبطة
    rel2 = RW.related_pages(extract.read_bundle(b2), None, "5002601347", 95)
    got = {g["label"] for g in rel2}
    assert {"سند الاستلام STO0000002474", "سند الاستلام STO0000002487", "الفاتورة"} <= got, got
    print({g["label"]: g["pages"] for g in rel2})
    print("OK")


if __name__ == "__main__":
    main()
