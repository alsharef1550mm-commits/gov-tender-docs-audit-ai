"""Second look for a value whose label maps to no field: filled only by a consistent zoomed reading."""
import copy

import pairs_reader as R
from pairs_mapper import to_schema

FIRST = {"page_type": "inspection", "title": "محضر مخالفة", "items": [], "totals": [],
         "header": [["رقم المحضر", "NC-47-7"], ["رقم سند الاستلام", "STO0000612204"], ["الغرامة المشتبة", "33.00"]]}


def page(*header):
    return to_schema({"page_type": "inspection", "title": "محضر مخالفة", "items": [], "totals": [], "header": list(header)})[0]


def first():
    pred, evidence = to_schema(FIRST)
    return copy.deepcopy(pred), evidence["unmapped"]


def test_zoomed_label_fills_the_empty_field_with_the_same_value():
    pred, unmapped = first()
    assert R.fill_unmapped(pred, unmapped, [page(["الغرامة المثبتة", "33.00"])]) == ["inspection.amount"]
    assert pred["inspection"]["amount"] == "33.00"


def test_a_different_value_is_never_used():
    pred, unmapped = first()
    assert R.fill_unmapped(pred, unmapped, [page(["الغرامة المثبتة", "34.00"])]) == []
    assert pred["inspection"]["amount"] is None


def test_crops_that_disagree_on_the_field_fill_nothing():
    pred, unmapped = first()
    crops = [page(["الغرامة المثبتة", "33.00"]), page(["الوحدات المخالفة", "33.00"])]
    assert R.fill_unmapped(pred, unmapped, crops) == [] and pred["inspection"]["amount"] is None


def test_a_filled_field_is_never_replaced():
    pred, unmapped = first()
    pred["inspection"]["amount"] = "30.00"
    assert R.fill_unmapped(pred, unmapped, [page(["الغرامة المثبتة", "33.00"])]) == []
    assert pred["inspection"]["amount"] == "30.00"


def test_receipt_number_letter_o_read_as_zero():
    import vlm_reader as V
    assert V._clean_id("ST00000004932", V.RE_STO) == "STO0000004932"
    assert V._clean_id("ST0000004932", V.RE_STO) is None          # wrong length is never repaired
    assert V._clean_id("ST00000004932", V.RE_PON) is None         # the rule is for receipt numbers only


def _invoice(*rows):
    pairs = {"page_type": "invoice", "title": "فاتورة ضريبية", "header": [["رقم الفاتورة", "5002602586"]], "totals": [],
             "items": [[["رقم الصنف", code], ["الكمية", "1"], ["سعر الوحدة", "10.00"]] + extra for code, extra in rows]}
    pred, evidence = to_schema(pairs)
    R.link_invoice_rows(pred, pairs, evidence)
    return [(i.get("_receipt_no"), i.get("_po_no")) for i in pred["items"]]


def test_group_heading_links_the_lines_below_it():
    # 327 invoice: the heading «سند الاستلام · التعميد» (labels swapped by the model) is read into the first line's card.
    head = [["سند الاستلام", "PON0000000888"], ["التعميد", "STO0000004720"]]
    links = _invoice(("EYE-001", head), ("EYE-006", []), ("EYE-009", []))
    assert links == [("STO0000004720", "PON0000000888")] * 3, links
    # A second heading starts a new group; a line with two receipt numbers is ambiguous and ends the group.
    links = _invoice(("A", [["سند الاستلام", "STO0000000001"]]), ("B", []), ("C", [["سند الاستلام", "STO0000000002"]]), ("D", []),
                     ("E", [["سند", "STO0000000003"], ["سند", "STO0000000004"]]), ("F", []))
    assert links == [("STO0000000001", None)] * 2 + [("STO0000000002", None)] * 2 + [(None, None)] * 2, links
    # No heading: lines stay unlinked.
    assert _invoice(("A", []), ("B", [])) == [(None, None)] * 2


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
