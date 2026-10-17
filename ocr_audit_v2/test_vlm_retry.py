"""إعادة القراءة الموجَّهة: بند السند الذي لا يطابق فاتورته المقروءة يُعاد قراءة صفحتيه بإعداد صورة مغاير، حتى مرتين، ويُقبل ما يتفق."""
import copy, io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("VLM_URL", "http://x/v1")
os.environ.pop("VLM2_URL", None)
import vlm_reader as V


def receipt():
    return {"page_type": "receipt", "ids": {"receipt_no": "STO0000006831", "po_no": "PON0000001265", "invoice_no": "5002603722"},
            "dates": {}, "items": [{"line_no": "1", "item_code": "GEN-065", "qty": "21", "unit_price": "15", "unit_price_halala": "00", "line_total": "376", "line_total_halala": "74"}],
            "totals": {}}


def invoice(code="GEN-065"):
    return {"page_type": "invoice", "ids": {"invoice_no": "5002603722"}, "dates": {},
            "items": [{"line_no": "1", "item_code": code, "qty": "21", "unit_price": "15.00", "line_total": "376.74", "commission": "12.60", "vat": "49.14"}], "totals": {}}


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    calls = []
    V.read_preds = lambda path, workers=4, progress=None: [receipt(), invoice("GEN-005")]        # القراءة الأولى: رمز الفاتورة مشوَّه
    def reread(path, pages, attempt, progress=None):
        calls.append((attempt, list(pages)))
        return {pg: (invoice("GEN-065") if pg == 2 else receipt()) for pg in pages}              # إعادة القراءة تُصحّح
    V._reread_pages = reread
    b = V.read_bundle_vlm("MED-2026-407-02-018.pdf")
    assert calls == [(1, [1, 2])], calls                                                         # صفحتا السند والفاتورة، مرة واحدة فقط (اتفقتا بعدها)
    assert b.invoices[0].items[0].code == "GEN-065" and not V.suspect_pages(b)
    assert b.retried_pages == {1: ["بند GEN-065 لا يطابق بنود الفاتورة 5002603722"], 2: ["بند GEN-065 لا يطابق بنود الفاتورة 5002603722"]}, b.retried_pages
    # إعادة القراءة لا تُصلح: تتوقف عند حدّ المحاولتين ولا تُخفي المشكلة
    calls.clear()
    V._reread_pages = lambda path, pages, attempt, progress=None: (calls.append(attempt), {pg: (invoice("GEN-005") if pg == 2 else receipt()) for pg in pages})[1]
    b2 = V.read_bundle_vlm("MED-2026-407-02-018.pdf")
    assert calls == [1, 2] and V.suspect_pages(b2), (calls, V.suspect_pages(b2))
    # صفحة سليمة: لا إعادة قراءة
    calls.clear()
    V.read_preds = lambda path, workers=4, progress=None: [receipt(), invoice("GEN-065")]
    b3 = V.read_bundle_vlm("MED-2026-407-02-018.pdf")
    assert calls == [] and b3.retried_pages == {}
    # فاتورة السند غير موجودة: يُعاد قراءة صفحة السند
    sus = V.suspect_pages(V.bundle_from_preds("x.pdf", [receipt()]))
    assert sus == {1: "فاتورة السند غير موجودة في الربطة"}, sus
    print("OK")


if __name__ == "__main__":
    main()
