r"""Tender-number identity across a bundle's documents (any tender format, e.g. NPT2323\23)."""
from types import SimpleNamespace as N

import report_writer as RW
from pairs_mapper import lookup, to_schema


def bundle(*tenders):
    receipts = [N(sto="STO1", pages=[2], pon="PON1", invoice_no="I1"), N(sto="STO2", pages=[4], pon="PON1", invoice_no="I1")]
    return N(file="x.pdf", page_types={1: "po", 2: "receipt", 4: "receipt"}, receipts=receipts,
             pos=[N(number="PON1", pages=[1])], invoices=[], tender_pages=list(zip((1, 2, 4), tenders)))


def test_same_tender_written_with_different_separators():
    assert RW._tender_key("NPT2323\\23") == RW._tender_key("npt 2323/23") == RW._tender_key("NPT2323-23")
    assert RW._tender_key("NPT2323\\23") != RW._tender_key("NPT2328\\23")


def test_document_with_another_tender_is_held_against_the_file_name():
    out = RW.tender_issues(bundle("NPT2323\\23", "NPT2323/23", "NPT2328\\23"), "NPT2323-23")
    assert [(u["page"], u["_holds"]) for u in out] == [(4, ["STO2"])]


def test_majority_is_the_reference_when_the_file_name_does_not_follow_the_rule():
    out = RW.tender_issues(bundle("MED-2026-339", "MED-2026-339", "MED-2026-321"))
    assert [(u["page"], u["_holds"]) for u in out] == [(4, ["STO2"])]


def test_tender_printed_inside_a_longer_value():
    out = RW.tender_issues(bundle("NUPCO : MED-2026-327", "MED-2026-327", "MED-2026-3271"), "MED-2026-327")
    assert [u["page"] for u in out] == [4]                     # MED-2026-3271 is a different number


def test_sto_value_is_the_receipt_number_even_beside_a_form_title():
    out, _ = to_schema({"page_type": "receipt", "title": "سند استلام", "items": [], "totals": [],
                        "header": [["نموذج رقم (2)", "STO0000004623"], ["رقم الفاتورة", "5002602538"]]})
    assert out["ids"]["receipt_no"] == "STO0000004623"


def test_no_majority_holds_every_document():
    assert len(RW.tender_issues(bundle("A1", "B2", "C3"))) == 3


def test_nupco_invoice_label_is_the_nupco_document_not_the_supplier_invoice():
    for label in ("فاتورة نوبكو", "رقم فاتورة نوبكو", "مستند نوبكو"):
        assert lookup(label, "header") == "customer_po_no", label
    assert lookup("رقم الفاتورة", "header") == "invoice_no"


def test_pon_value_is_the_po_number_whatever_its_label():
    out, _ = to_schema({"page_type": "purchase_order", "title": "أمر شراء", "items": [], "totals": [],
                        "header": [["المرجع", "MED-2026-318"], ["رقم المنافسة", "PON0000000703"]]})
    assert out["ids"]["po_no"] == "PON0000000703" and out["ids"]["tender_no"] is None
    assert "ids.tender_no" in out["unreadable_fields"]


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
