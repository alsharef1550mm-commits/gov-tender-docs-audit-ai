"""Deterministic page-level review flags; a reading error no flag covers is SILENT.

Checks never change a value. Each failing check flags every field it involves:
  withheld   - field listed in unreadable_fields (conflict or unreadable)
  item_net   - qty x unit price != printed line net
  item_gross - line net + commission + VAT != printed line total
  item_vat   - VAT != rate x net, and != rate x (net + commission)
  sums       - item nets / commissions / VAT do not add up to the totals block
  totals     - net + commission + VAT != total before penalties; payable != that minus deductions
  missing    - a field printed in most item rows of the page is absent from one row
  format     - PO/receipt id not 3 letters + 10 digits; invoice not 10 digits (optional TF)
Contract arithmetic (commission %, tax base) is checked later by the audit engine;
this gate only uses relations printed on the same page.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import re

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
CENT = Decimal("0.01")


def amount(text):
    if text is None:
        return None
    s = str(text).translate(DIGITS).replace("٬", ",").replace("٫", ".").replace(" ", "").replace("%", "")
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?|\d+(\.\d+)?", s):
        s = s.replace(",", "")
    elif re.fullmatch(r"\d+,\d{1,3}", s):
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def money(x):
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def item_value(it, key):
    v = amount(it.get(key))
    h = it.get(key + "_halala")
    if v is not None and h is not None and amount(h) is not None:
        v = v + amount(h) / 100
    return v


def flags(pred):
    """Return {path: [reasons]} for every field that must go to review."""
    out = {}

    def flag(paths, why):
        for p in paths:
            out.setdefault(p, []).append(why)

    for p in pred.get("unreadable_fields") or []:
        flag([p], "withheld")
    items = pred.get("items") or []
    present = {}
    for j, it in enumerate(items):
        for k, v in it.items():
            if v is not None:
                present[k] = present.get(k, 0) + 1
    for j, it in enumerate(items):
        P = lambda *ks: [f"items.{j}.{k}" for k in ks] + \
            [f"items.{j}.{k}_halala" for k in ks if k in ("unit_price", "line_total")]
        qty, price = amount(it.get("qty")), item_value(it, "unit_price")
        net, comm, vat = amount(it.get("line_net")), amount(it.get("commission")), amount(it.get("vat"))
        gross, rate = item_value(it, "line_total"), amount(it.get("vat_rate"))
        if qty is not None and price is not None and net is not None and money(qty * price) != net:
            flag(P("qty", "unit_price", "line_net"), "item_net")
        base = net if net is not None else (money(qty * price) if qty is not None and price is not None else None)
        # The line total includes NUPCO's commission; when a template does not print the commission on the
        # line (the original receipt and NUPCO purchase order), the reading cannot be checked this way and the
        # engine's printed-versus-contract line check decides instead.
        if base is not None and gross is not None and comm is not None:
            if base + comm + (vat or 0) != gross:
                flag(P("qty", "unit_price", "line_net", "commission", "vat", "line_total"), "item_gross")
        if base is not None and vat is not None and rate is not None:
            r = rate / 100
            if vat != money(base * r) and (comm is None or vat != money((base + comm) * r)):
                flag(P("vat", "vat_rate", "line_net", "commission"), "item_vat")
        for k, n in present.items():
            if it.get(k) is None and n >= max(2, (len(items) + 1) // 2) and n < len(items):
                flag([f"items.{j}.{k}"], "missing")
        # An item row with a quantity or price but no item code cannot be matched to its order or invoice; a coded row
        # missing one of its three audited figures cannot be computed. Both are asked again on a zoomed reading.
        if it.get("item_code") is None and (qty is not None or price is not None) and f"items.{j}.item_code" not in out:
            flag([f"items.{j}.item_code"], "missing")
        if it.get("item_code") is not None and (qty is not None or price is not None):
            for k, v in (("qty", qty), ("unit_price", price), ("line_total", gross)):
                if v is None and it.get(k) is None and f"items.{j}.{k}" not in out:
                    flag([f"items.{j}.{k}"], "missing")
    t = pred.get("totals") or {}
    T = {k: amount(v) for k, v in t.items()}
    for key, field in (("line_net", "net_excl_vat"), ("commission", "commission"), ("vat", "vat")):
        vals = [amount(it.get(key)) for it in items]
        if items and T.get(field) is not None and all(v is not None for v in vals) and sum(vals) != T[field]:
            flag([f"totals.{field}"] + [f"items.{j}.{key}" for j in range(len(items))], "sums")
    # As on the line: a form that prints no commission total (the NUPCO «مذكرة استلام») cannot be checked this way.
    if T.get("total_incl") is not None and T.get("net_excl_vat") is not None and T.get("commission") is not None:
        if T["net_excl_vat"] + (T.get("commission") or 0) + (T.get("vat") or 0) != T["total_incl"]:
            flag(["totals.net_excl_vat", "totals.commission", "totals.vat", "totals.total_incl"], "totals")
    if T.get("total") is not None and T.get("total_incl") is not None:
        deductions = sum((T.get(k) or 0) for k in ("penalty", "other_penalty", "discount"))
        if T["total_incl"] - deductions + (T.get("shipping") or 0) != T["total"]:
            flag(["totals.total", "totals.total_incl", "totals.penalty", "totals.other_penalty",
                  "totals.discount", "totals.shipping"], "totals")
    ids = pred.get("ids") or {}
    for key in ("po_no", "receipt_no"):
        v = ids.get(key)
        if v is not None and not re.fullmatch(r"[A-Z]{3}\d{10}", str(v)):
            flag([f"ids.{key}"], "format")
    v = ids.get("invoice_no")
    if v is not None and not re.fullmatch(r"(TF)?\d{10}", str(v)):
        flag(["ids.invoice_no"], "format")
    return out
