"""اختبارات وحدة لمحرك الحساب: قواعد الضريبة الخمس، الغرامة، وكشف الأخطاء المعروفة في 730.

تُشغَّل بـ:  python test_engine.py   (لا تحتاج ملفات PDF)
"""
from decimal import Decimal as D

import engine
from extract import Receipt, RItem, PO, POItem, Ev, Invoice

EV = Ev("t.pdf", 1, (0, 0, 1, 1))


def make(items, mode, date="2027-02-06", due="2027-02-10", printed=None, comm="0.04"):
    """items: [(code, qty, price, taxable)]"""
    rules = engine.Rules("MED-T", commission=D(comm), tax_mode=mode)
    po = PO("PON0000000001", "2027-01-20", 1, [POItem(i + 1, c, "EA", D(10000), D(p), D(0), D(15 if t else 0), D(0), due, EV)
                                              for i, (c, q, p, t) in enumerate(items)])
    r = Receipt("STO0000000001", pon=po.number, invoice_no=None, date=date, due=due)
    r.items = [RItem(i + 1, c, "EA", D(q), D(p), D(0), D(15 if t else 0), EV) for i, (c, q, p, t) in enumerate(items)]
    r.printed = printed or {}
    return rules, po, r


def run(items, mode, **kw):
    rules, po, r = make(items, mode, **kw)
    res = engine.check_receipt(r, rules, {po.number: po}, {}, {})
    return res


def codes(res):
    return {i.code for i in res.issues} - {"no_invoice", "line_total"}     # أسطر السند غير مبنية في الاختبار


def test_tax_modes():
    items = [("A", 10, "100", True), ("B", 10, "50", False)]      # net 1000 + 500
    exp = {
        "none": D("0.00"),
        "full_net": D("225.00"),             # 15% × 1500
        "full_net_comm": D("234.00"),        # 15% × 1560
        "partial_net": D("150.00"),          # 15% × 1000
        "partial_net_comm": D("156.00"),     # 15% × 1040
    }
    for mode, vat in exp.items():
        res = run(items, mode)
        assert res.net == D("1500.00") and res.commission == D("60.00"), mode
        assert res.vat == vat, (mode, res.vat)
        assert res.total == D("1560.00") + vat, mode


def test_penalty_730_cases():
    # 730: تأخر يوماً على صافي 3650 => 36.50 ؛ تأخر 10 أيام على 5100 => 102.00
    r1 = run([("A", 1, "3650", False)], "none", date="2027-02-11", due="2027-02-10")
    assert r1.penalty == D("36.50") and r1.late_days == 1, r1.penalty
    r2 = run([("A", 1, "5100", False)], "none", date="2027-02-20", due="2027-02-10")
    assert r2.penalty == D("102.00") and r2.late_days == 10, r2.penalty
    assert r2.payable == r2.total - D("102.00")


def test_penalty_week_or_part():
    # «أسبوع أو جزء منه»: 7 أيام = أسبوع، 8 أيام = أسبوعان
    base = [("A", 1, "1000", False)]
    assert run(base, "none", date="2027-02-17", due="2027-02-10").penalty == D("10.00")
    assert run(base, "none", date="2027-02-18", due="2027-02-10").penalty == D("20.00")


def test_penalty_cumulative_cap():
    # السقف 6% من إجمالي العقد (لا من الجزء المتأخر) ويوزَّع بتاريخ الاستلام ثم رقم السند
    rules = engine.Rules("MED-T", tax_mode="none", contract_total=D("1000"))      # السقف 60.00
    rs = []
    for sto, date in (("STO0000000002", "2027-06-10"), ("STO0000000001", "2027-06-10")):
        _, po, r = make([("A", 1, "1000", False)], "none", date=date, due="2027-02-10")
        r.sto = sto
        rs.append(engine.check_receipt(r, rules, {po.number: po}, {}, {}))
    assert all(x.penalty == D("180.00") for x in rs)            # 18 أسبوعاً × 1% × 1000 بلا سقف
    notes = engine.apply_cumulative_cap(rs, rules)
    by = {x.sto: x.penalty for x in rs}
    assert by["STO0000000001"] == D("60.00") and by["STO0000000002"] == D("0.00"), by
    assert any(n.code == "cap_applied" for n in notes)
    # بلا إجمالي عقد لا يُخفَّض شيء ويُعلَن
    rules2 = engine.Rules("MED-T", tax_mode="none")
    _, po, r = make([("A", 1, "1000", False)], "none", date="2027-06-10", due="2027-02-10")
    res = engine.check_receipt(r, rules2, {po.number: po}, {}, {})
    assert engine.apply_cumulative_cap([res], rules2)[0].code == "cap_unknown" and res.penalty == D("180.00")


def test_detects_730_style_errors():
    base = [("A", 8, "112.5", True), ("B", 12, "37.5", False), ("C", 16, "125", True), ("D", 20, "87.5", False)]
    good = run(base, "partial_net_comm")
    p = {"net": good.net, "nupco": good.commission, "vat": good.vat, "total": good.total, "penalty": D(0), "late_days": D(0),
         "final": good.total}
    assert not codes(run(base, "partial_net_comm", printed=dict(p)))
    for key, delta, expect in (("vat", "10", "vat"), ("nupco", "40", "commission"), ("net", "25", "net"), ("total", "-75", "total")):
        q = dict(p)
        q[key] = q[key] + D(delta)
        assert expect in codes(run(base, "partial_net_comm", printed=q)), (key, codes(run(base, "partial_net_comm", printed=q)))
    # غرامة مستحقة لم تُسجَّل
    late = run(base, "partial_net_comm", date="2027-02-11", due="2027-02-10", printed=dict(p))
    assert "penalty" in codes(late) or "late_days" in codes(late)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
