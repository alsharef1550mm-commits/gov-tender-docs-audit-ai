"""انحدار الفاتورة المشتركة (توجيه المالك): الفاتورة 5002601347 في الربطة MED-2026-305-01-002 تضم بنوداً تخص السند STO0000002488 في 01-003.
  - فحص 01-002 وحدها: الفاتورة مبرر يكفي أن ترد فيه بنود سندات الدفعة؛ بنود السند الآخر لا تُذكر ولا تُحال ولا تُنسب لسندات الدفعة ولا يدخل مبلغها فيها.
  - فحص المنافسة (002 + 003): تُطابَق مع سندها STO0000002488 قبل الحكم، ولا يُسجَّل «بند بلا سند»."""
import glob
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import competition_writer as CW  # noqa: E402
import report_template as T  # noqa: E402
import report_writer as RW  # noqa: E402

INV = "5002601347"


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    folder = glob.glob(os.path.join(T.ROOT, "المنافسات", "*MED-2026-305"))[0]
    contract = glob.glob(os.path.join(folder, "العقد", "*.pdf"))[0]
    b2, b3 = (os.path.join(folder, f"MED-2026-305-01-00{i}.pdf") for i in (2, 3))
    d = RW.collect_batch(b2, contract)
    mine = [u for u in d["unresolved"] if u.get("invoice") == INV]
    assert mine == [], mine                                          # فحص الدفعة: الفاتورة مبرر؛ بنود سند آخر لا تُذكر ولا تُحال
    amounts = {s: d["attribution"][s]["amount"] for s in ("STO0000002474", "STO0000002487")}
    assert amounts == {"STO0000002474": "52.00", "STO0000002487": "1352.00"}, amounts   # لا مبلغ للبنود الغريبة داخل سندات الدفعة
    assert all("STO0000002488" not in str(d["attribution"][s]) for s in amounts)
    print("فحص 002 وحدها: لا بند مراجعة للفاتورة المشتركة، ومبالغ السندات بلا تلوث:", amounts)
    c = CW.collect_competition([b2, b3], contract, {}, 1, None, None)
    assert not [u for u in c["unresolved"] if u.get("invoice") == INV], [u for u in c["unresolved"] if u.get("invoice") == INV]
    a = {s: c["attribution"][s] for s in ("STO0000002474", "STO0000002487", "STO0000002488")}
    assert all(v["clear"] for v in a.values()) and a["STO0000002488"]["amount"] == "5886.40", {k: (v["clear"], v["amount"]) for k, v in a.items()}
    assert not any("بلا سند" in u.get("reason", "") for u in c["unresolved"] if u.get("invoice") == INV)
    print("فحص المنافسة 002+003: 0 بنود، السند STO0000002488 مطابَق بمبلغ", a["STO0000002488"]["amount"])
    print("OK")


if __name__ == "__main__":
    main()
