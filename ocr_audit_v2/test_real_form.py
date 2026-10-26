"""The 49-page final evaluation file in the official NUPCO layout: reading rules added 2026-10-26, no model calls.
Every case is a model reading seen on that file's pages, verified against the page images."""
from decimal import Decimal as D

import engine as E
import vlm_reader as V
from number_reading import amount_reading, page_separator, quantity_reading
from pairs_mapper import parse, to_schema

INVOICE = {"page_type": "invoice", "title": "Tax Invoice - فاتورة ضريبية",
           "header": [["الرقم الفاتورة / Invoice No", "5001228493"], ["منافسة - Tender", "NPT0020/22"],
                      ["رقم أمر الشراء للعميل - Customer PO", "(NPT0020/22)"], ["أوامر الشراء : PO NO.", "4600063564"]],
           "items": [[["S. No", "1"], ["Material Code", "5110181100001"], ["Material Desc.", "DROF 2% SHAMPOO DEEF PHARMA"],
                      ["Unit Price", "7.7400"], ["Quantity / UOM", "4,200"],
                      ["(Amount (Excl. VAT (غير شامل ضريبة القيمة المضافة)", "32,508.00"], ["Commission 4%", "1,300.32"],
                      ["Total Taxable Amount", "33,808.32"], ["Tax Rate %", "0"], ["Tax Amount", "0"],
                      ["Item Subtotal (Including (شامل ضريبة القيمة المضافة) VAT", "33,808.32"]]],
           "totals": [["Amount (Excluding VAT)", "32,508.00"], ["Commission 4 %", "1,300.32"],
                      ["Total Taxable Amount (Excluding VAT) / إجمالي الضريبة القابل", "33,808.32"],
                      ["Total VAT Amount", "0.00"], ["Total Amount Due", "33,808.32"]]}
RECEIPT = {"page_type": "receipt", "title": "مذكرة استلام",
           "header": [["تاريخ الاستلام", "15-04-2025"], ["رقم الفاتورة", "5001220401"], ["أمر الشراء", "Nupco Warehouse(8) - 0801 مستودع"]],
           "items": [[["إشعار استلام مؤقت / الرقم", "STO0000007228"], ["إشعار استلام مؤقت / التاريخ", "24-03-2025"],
                      ["أمر الشراء / الرقم", "PON0000007596"], ["أمر الشراء / التاريخ", "28-07-2024"], ["الرقم", "1"],
                      ["رقم الصنف", "5118240000100"], ["الكمية", "7860"], ["سعر الوحدة / ريال", "28.00"], ["سعر الوحدة / هللة", "0.00"],
                      ["مجموع القيمة / ريال", "228883.20"], ["مجموع القيمة / هللة", "0.20"]]],
           "totals": [["الإجمالي بدون ضريبة", "220,080.00"], ["إجمالي الضريبة", "0.00"], ["الإجمالي", "228,883.20"],
                      ["Total Price", "228,883.20"]]}


def test_nupco_invoice_labels():
    o, e = to_schema(INVOICE)
    it = o["items"][0]
    assert (it["item_code"], it["qty"], it["unit_price"], it["line_net"], it["line_total"], it["commission"], it["vat"]) == \
        ("5110181100001", "4,200", "7.7400", "32,508.00", "33,808.32", "1,300.32", "0")
    t = o["totals"]
    assert (t["net_excl_vat"], t["commission"], t["vat"], t["total"]) == ("32,508.00", "1,300.32", "0.00", "33,808.32")
    assert o["ids"]["po_no"] is None and o["ids"]["tender_no"] == "NPT0020/22"     # «Customer PO» is not a PON number
    assert not o["unreadable_fields"]


def test_receipt_reference_table_inside_item_row():
    o, e = to_schema(RECEIPT)
    assert o["ids"]["receipt_no"] == "STO0000007228" and o["ids"]["po_no"] == "PON0000007596"
    assert o["dates"]["document_date"] == "15-04-2025"                              # the notice's own date is not it
    assert len(o["items"]) == 1 and o["items"][0]["item_code"] == "5118240000100"
    assert (o["totals"]["net_excl_vat"], o["totals"]["total_incl"], o["totals"]["total"]) == ("220,080.00", "228,883.20", "228,883.20")
    assert not o["unreadable_fields"]


def test_purchase_order_tender_and_totals_commission():
    o, _ = to_schema({"page_type": "purchase_order", "title": "PURCHASE ORDER", "header": [["NUPCO", "NPT0020/22"], ["REF", None],
                      ["Purchase Order No", "PON0000007610"]], "items": [], "totals": [["NUPCO 4%", "2,732.40"]]})
    assert o["ids"]["tender_no"] == "NPT0020/22" and o["totals"]["commission"] == "2,732.40" and not o["unreadable_fields"]


def test_json_punctuation_repair_keeps_values():
    bad = '{"items": [[["(Amount (Excl. VAT", "1,928,380.50"), ["Commission 4%", "77,135.22"]], [[["S. No", "2"]]], "x": 1}'
    p = parse(bad)
    assert p["items"][0][0] == ["(Amount (Excl. VAT", "1,928,380.50"] and p["items"][1] == [["S. No", "2"]]
    try:
        parse('{"a": [1, 2}')
        raise AssertionError("other broken text must still fail")
    except ValueError:
        pass


def test_page_convention_and_amount_agreement():
    page = {"items": [{"qty": "1,320", "line_total": "22,486.46"}]}
    assert page_separator(page) == "." and quantity_reading("1,320", page_separator(page)) == D("1320")
    assert quantity_reading("1,320") is None                                       # alone it stays ambiguous
    assert amount_reading("33808.32", "0.32") == D("33808.32") and amount_reading("33808.32", "0.33") is None
    assert V._code("5110157700000 E.D.Date :") == "5110157700000" and V._code("PR24/0000009000 DY : 804") == "PR24/0000009000 DY : 804"


def test_rounded_price_and_implied_commission():
    assert E._rounded_print(D("129.08"), D("129.07500")) and not E._rounded_print(D("129.07"), D("129.07500"))
    r = type("R", (), {})()
    r.printed = {"net": D("32508.00"), "vat": D("0.00"), "total": D("33808.32")}
    assert E._printed_commission(r) == D("1300.32")
    r.printed["nupco"] = D("1300.00")
    assert E._printed_commission(r) == D("1300.00")                                 # a printed commission always wins


def test_competition_is_the_first_purchase_order_tender():
    import report_writer as RW
    assert RW.clean_tender("NUPCO : (NPT0020/22)") == "NPT0020/22" and RW.clean_tender("NUPCO : MED-2026-327") == "MED-2026-327"
    b = type("B", (), {})()
    b.page_types = {1: "po", 3: "receipt", 13: "invoice", 15: "po"}
    b.receipts, b.pos, b.invoices, b.file = [], [], [], "evaluation.pdf"
    pages = [(1, "NUPCO : (NPT0020/22)"), (13, "NDP1074-24"), (15, "NPT0020/22")]
    assert RW.first_po_tender(b, pages) == "NPT0020/22"              # not the file name
    issues = RW.tender_issues(b, RW.first_po_tender(b, pages), pages)
    assert [u["page"] for u in issues] == [13]                         # the other documents are checked against it


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
