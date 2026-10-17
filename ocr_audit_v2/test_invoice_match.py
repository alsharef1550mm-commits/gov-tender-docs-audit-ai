"""اختبارات مطابقة الفاتورة كمبرر مؤيد: مشتركة بين سندات وتعاميد، بلا رقم سند على الفاتورة، انقسام بند، بند زائد، دقة السعر، خريطة رموز، نسخ مكررة."""
from decimal import Decimal as D

import invoice_match as M


def rl(code, qty, price):
    return {"code": code, "qty": D(str(qty)), "price": D(str(price))}


def il(code, qty, price, amount):
    return {"code": code, "qty": D(str(qty)), "price": D(str(price)), "amount": D(str(amount)) if amount is not None else None}


def rec(sto, *lines, inv="INV1"):
    return {"sto": sto, "invoice_no": inv, "lines": list(lines)}


def test_one_invoice_two_receipts_different_pos_no_receipt_number_on_invoice():
    r1 = rec("STO1", rl("A", 2, "10"), rl("B", 1, "5"))
    r2 = rec("STO2", rl("A", 3, "10"))                      # تعميد آخر في المنافسة نفسها
    inv = {"number": "INV1", "copies": [[il("A", 2, "10", "20.80"), il("B", 1, "5", "5.20"), il("A", 3, "10", "31.20")]]}
    out = M.match_invoice([r1, r2], inv)
    assert out["group_consistent"] and not out["review"]
    assert out["receipts"]["STO1"]["amount"] == "26.00"     # مجموع بنود السند المنسوبة فقط، لا إجمالي الفاتورة
    assert out["receipts"]["STO2"]["amount"] == "31.20"


def test_never_compares_whole_invoice_total_to_one_receipt():
    r1 = rec("STO1", rl("A", 2, "10"))
    inv = {"number": "INV1", "copies": [[il("A", 2, "10", "20.80"), il("C", 7, "9", "65.52")]]}     # بند C لسند آخر لا يذكر الفاتورة
    other = [rec("STO9", rl("C", 7, "9"), inv="INV2")]
    out = M.match_invoice([r1], inv, other_receipts=other)
    assert out["receipts"]["STO1"]["amount"] == "20.80"     # لا ننسب 86.32 (كامل الفاتورة) للسند
    assert not out["group_consistent"]
    ex = [r for r in out["review"] if r.get("code") == "C"][0]
    assert ex["candidate_stos_not_citing_invoice"] == ["STO9"]      # مرشح للمراجع فقط، لا ربط تلقائي


def test_split_line_between_two_receipts_is_review_not_guess():
    r1 = rec("STO1", rl("A", 4, "10"))
    r2 = rec("STO2", rl("A", 6, "10"))
    inv = {"number": "INV1", "copies": [[il("A", 10, "10", "104.00")]]}
    out = M.match_invoice([r1, r2], inv)
    assert out["receipts"]["STO1"]["amount"] is None and out["receipts"]["STO2"]["amount"] is None
    assert any("انقسام" in r["reason"] for r in out["review"])


def test_price_display_precision_and_unit_code_map():
    r1 = rec("STO1", rl("5110153800100", 1200, "0.95"))
    inv = {"number": "INV1", "copies": [[il("5110153800110", 1200, "0.9500", "1185.60")]]}
    bad = M.match_invoice([r1], inv)                         # رمزان مختلفان بلا خريطة: إحالة لا تخمين
    assert bad["receipts"]["STO1"]["amount"] is None and bad["review"]
    good = M.match_invoice([r1], inv, code_map={"5110153800110": "5110153800100"})
    assert good["receipts"]["STO1"]["amount"] == "1185.60" and good["group_consistent"]
    r2 = rec("STO2", rl("A", 14940, "129.08"))
    inv2 = {"number": "INV1", "copies": [[il("A", 14940, "129.0750", "2005515.72")]]}      # 129.08 مقابل 129.0750
    assert M.match_invoice([r2], inv2)["receipts"]["STO2"]["amount"] == "2005515.72"


def test_coincidental_match_across_receipts_is_ambiguous_not_clear():
    # مثال الربطة 04: بند السند 20 يطابق صفاً يعود لسند آخر لا يذكر الفاتورة، وصف الفاتورة 16 يبقى بلا سند
    r13 = rec("STO13", rl("A", 20, "112.50"), rl("B", 20, "37.50"))
    r15 = rec("STO15", rl("A", 4, "112.50"), rl("B", 8, "37.50"))
    inv = {"number": "INV1", "copies": [[il("A", 16, "112.50", "2152.80"), il("B", 20, "37.50", "780.00"),
                                         il("A", 4, "112.50", "538.20"), il("B", 8, "37.50", "312.00"),
                                         il("A", 20, "112.50", "2691.00")]]}          # الصف الأخير لسند آخر (STO14)
    other = [rec("STO14", rl("A", 20, "112.50"), inv="INV9")]
    out = M.match_invoice([r13, r15], inv, other_receipts=other)
    assert not out["group_consistent"]
    assert out["receipts"]["STO13"]["amount"] is None and out["receipts"]["STO15"]["amount"] is None      # لا مبلغ مصطنع
    assert not out["receipts"]["STO13"]["clear"] and "التباس" in out["receipts"]["STO13"]["why"]
    # الصف الفائض هو A بكمية 16 (لا A بكمية 20 الذي التقطه STO13 مصادفة) فيُحال بلا مرشحين مطابقين
    left = [r for r in out["review"] if r.get("code") == "A" and r.get("qty") == "16"]
    assert left and left[0]["reason"] == "بند في الفاتورة بلا سند يذكرها"


def test_unrelated_receipt_stays_clear_when_conflict_is_on_other_items():
    r1 = rec("STO1", rl("A", 2, "10"))
    r2 = rec("STO2", rl("B", 3, "5"))
    inv = {"number": "INV1", "copies": [[il("A", 2, "10", "20.80"), il("B", 3, "5", "15.60"), il("Z", 1, "99", "102.96")]]}   # Z بلا سند
    out = M.match_invoice([r1, r2], inv)
    assert out["receipts"]["STO1"]["amount"] == "20.80" and out["receipts"]["STO2"]["amount"] == "15.60"
    assert not out["group_consistent"] and any(r.get("code") == "Z" for r in out["review"])


def test_receipt_quantity_exceeds_invoice_is_review():
    r1 = rec("STO1", rl("A", 20, "10"))
    inv = {"number": "INV1", "copies": [[il("A", 16, "10", "166.40")]]}
    out = M.match_invoice([r1], inv)
    assert out["receipts"]["STO1"]["amount"] is None and not out["receipts"]["STO1"]["clear"]
    assert any(r.get("sto") == "STO1" for r in out["review"])


def test_duplicate_invoice_copies_counted_once_and_differences_flagged():
    r1 = rec("STO1", rl("A", 2, "10"))
    one = [il("A", 2, "10", "20.80")]
    out = M.match_invoice([r1], {"number": "INV1", "copies": [one, list(one), list(one)]})
    assert out["receipts"]["STO1"]["amount"] == "20.80" and out["group_consistent"] and out["lines"] == 1
    diff = M.match_invoice([r1], {"number": "INV1", "copies": [one, [il("A", 3, "10", "31.20")]]})
    assert any("تختلف" in r["reason"] for r in diff["review"])


def test_amount_unresolved_when_item_amounts_not_printed():
    r1 = rec("STO1", rl("A", 2, "10"))
    out = M.match_invoice([r1], {"number": "INV1", "copies": [[il("A", 2, "10", None)]]})
    assert out["receipts"]["STO1"]["clear"] and out["receipts"]["STO1"]["amount"] is None
    assert out["receipts"]["STO1"]["why"] == "مبالغ البنود غير مطبوعة"


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
