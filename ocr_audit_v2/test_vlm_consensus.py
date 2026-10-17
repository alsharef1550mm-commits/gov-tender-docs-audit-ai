"""إجماع قارئين مستقلين: لا يُعتمد إلا ما اتفقا عليه؛ التعارض يُسقط الصف أو يُصفّر المعرّف ويُحال، ولا يُنسب لمستند سابق صامتاً."""
import copy, io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("VLM_URL", "http://x/v1")
import vlm_reader as V


def page():
    return {"page_type": "receipt", "ids": {"receipt_no": "STO0000006831", "po_no": "PON0000001265", "invoice_no": "5002603722"},
            "dates": {"document_date": "2027-03-12"},
            "items": [{"line_no": "1", "item_code": "GEN-065", "qty": "21", "unit_price": "15", "unit_price_halala": "00", "line_total": "376", "line_total_halala": "74"},
                      {"line_no": "2", "item_code": "GEN-207", "qty": "1", "unit_price": "5", "unit_price_halala": "00", "line_total": "5", "line_total_halala": "20"}],
            "totals": {"net_excl_vat": "320.00", "commission": "12.80", "vat": "49.14", "total": "381.94"}}


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    a = page()
    m = V.merge_preds(a, copy.deepcopy(a))                                     # اتفاق كامل
    assert len(m["items"]) == 2 and not m["_dropped"] and not m["_id_conflicts"] and m["ids"]["receipt_no"] == "STO0000006831"
    b = copy.deepcopy(a); b["items"][0]["line_total"] = "315"; b["items"][0]["line_total_halala"] = "00"   # قارئ ينسخ الصافي بدل الإجمالي
    m = V.merge_preds(a, b)
    assert [i["item_code"] for i in m["items"]] == ["GEN-207"] and m["_dropped"][0] == "GEN-065", m["_dropped"]       # الصف المختلف يُسقَط
    c = copy.deepcopy(a); c["ids"]["receipt_no"] = "STO0000006855"                                           # رقم سند مختلف
    h = copy.deepcopy(a); h["ids"]["customer_po_no"] = "IN1"                                                  # حقل غير حرج لا يُحال
    assert not V.merge_preds(a, h)["_id_conflicts"]
    k = copy.deepcopy(a); k["ids"]["invoice_no"] = "5002603799"                                               # رقم مرتبط: يُصفَّر ولا يُسقط السند
    mk = V.merge_preds(a, k)
    assert mk["ids"]["invoice_no"] is None and mk["ids"]["receipt_no"] == "STO0000006831"
    bk = V.bundle_from_preds("MED-2026-407-02-018.pdf", [mk])
    assert [r.sto for r in bk.receipts] == ["STO0000006831"] and bk.agree_issues[1]["kind"] == "link"
    m = V.merge_preds(a, c)
    assert m["ids"]["receipt_no"] is None and m["_id_conflicts"] == ["receipt_no"]
    d = copy.deepcopy(a); d["page_type"] = "invoice"
    assert V.merge_preds(a, d)["_type_conflict"]
    assert V.merge_preds(a, None)["_failed"]
    e = copy.deepcopy(a); e["totals"]["vat"] = "0.00"
    assert V.merge_preds(a, e)["totals"]["vat"] is None and V.merge_preds(a, e)["totals"]["total"] == "381.94"
    # تحكيم Tesseract: يُرجَّح المرشح الذي تظهر أرقامه في القراءة المستقلة إن ظهر واحد فقط
    mc = V.merge_preds(a, c)
    V._tess_digits10 = lambda img: {"0000006831"}
    r = V._arbitrate_ids(copy.deepcopy(mc), a, c, None)
    assert r["ids"]["receipt_no"] == "STO0000006831" and not r["_id_conflicts"] and r["_arbitrated"] == ["receipt_no"]
    V._tess_digits10 = lambda img: set()                                       # لا أحد يظهر: يبقى التعارض
    assert V._arbitrate_ids(copy.deepcopy(mc), a, c, None)["_id_conflicts"] == ["receipt_no"]
    V._tess_digits10 = lambda img: {"0000006831", "0000006855"}                # كلاهما يظهر: يبقى التعارض
    assert V._arbitrate_ids(copy.deepcopy(mc), a, c, None)["_id_conflicts"] == ["receipt_no"]
    # الصفحة ذات الهوية المتعارضة لا تُنسب لسند سابق ويُسجَّل لها بند
    good = V.merge_preds(a, copy.deepcopy(a))
    bad = V.merge_preds(a, c)
    bun = V.bundle_from_preds("MED-2026-407-02-018.pdf", [good, bad])
    assert [r.sto for r in bun.receipts] == ["STO0000006831"] and bun.receipts[0].pages == [1], [(r.sto, r.pages) for r in bun.receipts]
    assert bun.agree_issues == {2: {"kind": "identity", "why": "القارئان لم يتفقا على: receipt_no"}}, bun.agree_issues
    print("OK")


if __name__ == "__main__":
    main()
