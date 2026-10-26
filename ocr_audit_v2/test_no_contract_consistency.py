"""Audits without a contract: one treatment per item across receipts; contradictions are referred, not decided."""
from decimal import Decimal as D

import engine
from extract import Ev, Receipt, RItem

EV = Ev("t.pdf", 1, (0, 0, 0, 0))


def receipt(sto, lines, rate=D("0.04"), vat_on_comm=True):
    """lines: (code, qty, price, vat_rate). Printed totals follow the given commission and tax base."""
    r = Receipt(sto)
    net = comm = vat = D(0)
    for k, (code, qty, price, vr) in enumerate(lines, 1):
        n = engine.r2(D(qty) * D(price))
        c = engine.r2(n * rate)
        v = engine.r2((n + (c if vat_on_comm else 0)) * vr)
        net, comm, vat = net + n, comm + c, vat + v
        r.items.append(RItem(k, code, "EA", D(qty), D(price), n + c + v, vr, EV))
    r.printed = {"net": net, "nupco": comm, "vat": vat, "total": net + comm + vat}
    return r


def codes(found, sto):
    return sorted(i.code for i in found.get(sto, []))


def test_consistent_receipts_have_no_issue():
    rs = [receipt(f"S{k}", [("A", 2, "10.00", D("0.15")), ("B", 1, "5.00", D(0))]) for k in range(4)]
    assert engine.consistency_issues(rs) == {}


def test_item_taxed_in_one_receipt_refers_all_its_receipts():
    rs = [receipt("S1", [("A", 2, "10.00", D("0.15"))]), receipt("S2", [("A", 1, "10.00", D("0.15"))]),
          receipt("S3", [("A", 3, "10.00", D(0))]), receipt("S4", [("B", 1, "5.00", D(0))])]
    found = engine.consistency_issues(rs)
    for s in ("S1", "S2", "S3"):
        assert "tax_status_inconsistent" in codes(found, s), (s, found)
    assert "S4" not in found


def test_price_outlier_against_strict_majority():
    rs = [receipt(f"S{k}", [("A", 1, "10.00", D(0))]) for k in range(3)] + [receipt("S9", [("A", 1, "12.00", D(0))])]
    found = engine.consistency_issues(rs)
    assert codes(found, "S9") == ["price_inconsistent"] and all(f"S{k}" not in found for k in range(3)), found


def test_price_split_without_majority_refers_all():
    rs = [receipt("S1", [("A", 1, "10.00", D(0))]), receipt("S2", [("A", 1, "12.00", D(0))])]
    found = engine.consistency_issues(rs)
    assert codes(found, "S1") == codes(found, "S2") == ["price_inconsistent"], found


def test_commission_rate_outlier():
    rs = [receipt(f"S{k}", [("A", 10, "10.00", D(0))]) for k in range(3)] + [receipt("S9", [("A", 10, "10.00", D(0))], rate=D("0.05"))]
    found = engine.consistency_issues(rs)
    assert codes(found, "S9") == ["commission_rate_inconsistent"], found


def test_majority_rules_for_competition():
    rs = [receipt(f"S{k}", [("A", 10, "10.00", D("0.15"))], vat_on_comm=False) for k in range(3)]
    rs.append(receipt("S9", [("A", 10, "10.00", D("0.15"))], vat_on_comm=True))
    rules = engine.infer_rules_from_receipts(rs, engine.Rules("T", tax_mode="inferred", no_contract=True))
    assert rules.tax_mode == "partial_net" and rules.commission == D("0.040"), (rules.tax_mode, rules.commission)
    results = engine.check_bundle(type("B", (), {"receipts": rs, "pos": [], "invoices": []})(), rules)
    bad = {r.sto for r in results if any(i.code == "vat" for i in r.issues)}
    assert bad == {"S9"}, bad


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
