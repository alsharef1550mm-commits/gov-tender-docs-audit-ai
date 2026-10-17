"""اختبار تحويل قراءات نموذج الرؤية إلى Bundle: نبني القراءات من مرجع طبقة النص (قراءة مثالية) ونتحقق أن محرك الحساب يعطي النتائج نفسها."""
import glob
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlm"))
import engine
import extract
import report_template as T
import vlm_reader
from make_synthetic_scans import page_truth


def to_pred(t):
    ty = t["page_type"]
    ids = {"receipt_no": None, "po_no": None, "invoice_no": None, "customer_po_no": None, "tender_no": None}
    ids.update(t.get("ids") or {})
    items = []
    for it in t["items"]:
        items.append({"line_no": str(it.get("line_no")), "item_code": it.get("item_code"), "unit": it.get("unit"), "qty": it.get("qty"),
                      "unit_price": it.get("unit_price"), "line_total": it.get("line_total"), "commission": it.get("commission"),
                      "vat": it.get("vat"), "batch": it.get("batch")})
    tot = t.get("totals") or {}
    totals = {"net_excl_vat": tot.get("net"), "commission": tot.get("nupco"), "vat": tot.get("vat"), "total_incl": tot.get("total"),
              "total": tot.get("final"), "penalty": tot.get("penalty")}
    return {"page_type": ty, "ids": ids, "dates": {"document_date": t.get("date") if ty != "purchase_order" else None,
                                                   "po_date": t.get("date") if ty == "purchase_order" else None, "due_date": None},
            "items": items, "totals": totals}


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    src = os.path.join(T.ROOT, "مثال فحص دفعه", "MED-2026-318-01-001.pdf")
    rules = engine.read_rules(os.path.join(T.ROOT, "مثال فحص دفعه", "عقد 318.pdf"), "MED-2026-318")
    b = extract.read_bundle(src)
    preds = [to_pred(page_truth(b, n)) if page_truth(b, n)["page_type"] != "other" else {"page_type": "other", "ids": {}, "items": []}
             for n in range(1, b.n_pages + 1)]
    vb = vlm_reader.bundle_from_preds(os.path.basename(src), preds)
    ra = {r.sto: r for r in engine.check_bundle(b, rules)}
    rb = {r.sto: r for r in engine.check_bundle(vb, rules)}
    same = sum(1 for s in ra if s in rb and (ra[s].net, ra[s].commission, ra[s].total, ra[s].payable) == (rb[s].net, rb[s].commission, rb[s].total, rb[s].payable))
    print("سندات نص", len(ra), "| سندات من القراءة المثالية", len(rb), "| متطابقة الأرقام", same, "| مع مشاكل:", sum(1 for r in rb.values() if r.issues))
    for r in list(rb.values())[:3]:
        if r.issues:
            print("  ", r.sto, [i.text for i in r.issues][:2])
    assert same == len(ra) and len(ra) == len(rb)
    print("OK")


if __name__ == "__main__":
    main()
