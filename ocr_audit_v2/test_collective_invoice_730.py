"""انحدار منافسة 730 بالتصميم الموحد (19 أكتوبر 2026): الفاتورة الجماعية تُقرأ من طبقة النص وتُنسب لها السندات بسطورها،
والأخطاء المعروفة تُكشف دون إنذار كاذب، والسند الذي يذكر فاتورة غير موجودة لا يظهر «سليماً»."""
import os
import tempfile

import extract
import report_writer as RW

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "المنافسات", "منافسة الفواتير الجماعية MED-HOLDOUT-730")
CONTRACT = os.path.join(B, "العقد", "عقد المنافسة.pdf")


def _verdicts(n):
    out = os.path.join(tempfile.mkdtemp(), "r.xlsx")
    RW.write_batch_report(os.path.join(B, f"MED-HOLDOUT-730-01-{n:03d}.pdf"), CONTRACT, out)
    d = RW.LAST_DATA
    held = set(d["review_stos"])
    return {s: ("held" if s in held else "ok" if r.ok else "bad") for s, r in d["results"].items()}, d


def test_collective_invoice_parsed():
    b = extract.read_bundle(os.path.join(B, "MED-HOLDOUT-730-01-002.pdf"))
    inv = {v.number: v for v in b.invoices}["TF2702050002"]
    assert getattr(inv, "collective", False) and not inv.items
    assert {k: str(v) for k, v in inv.allocations.items()} == {"STO0073000005": "3650.00", "STO0073000006": "5100.00",
                                                              "STO0073000007": "4800.00", "STO0073000008": "3750.00"}
    assert all(r.invoice_no == "TF2702050002" for r in b.receipts)


def test_known_errors_no_false_flags():
    v, d = _verdicts(2)
    assert v == {"STO0073000005": "bad", "STO0073000006": "bad", "STO0073000007": "ok", "STO0073000008": "ok"}, v
    assert not d["unresolved"], d["unresolved"]


def test_missing_invoice_is_held_not_sound():
    v, d = _verdicts(8)
    assert v["STO0073000029"] == "held" and v["STO0073000030"] == "bad", v
    assert sum(1 for x in v.values() if x == "ok") == 14
    why = [u for u in d["unresolved"] if u.get("sto") == "STO0073000029"][0]["why"]
    assert "TF2702050008" in why


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
