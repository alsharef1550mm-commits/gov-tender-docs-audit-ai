"""Label/value pairs reading for one page (enabled by VLM_FORMAT=pairs).

The model transcribes printed [label, value] pairs; pairs_mapper assigns fields
by label text only. safety_gate flags fields for review. A cell printed in most
rows but missing from one is re-read on zoomed top/bottom crops and filled only
from a consistent reading of the same item; nothing is ever computed.
A printed value whose label maps to no field gets the same second look: it is
filled only when the zoomed reading names an empty field for that exact value.
"""
import base64
import io
import json
import os
import urllib.request

from pairs_mapper import _own_id, clean, parse, to_schema
from safety_gate import amount, flags

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT = os.path.join(HERE, "vlm", "prompt_pairs.txt")
READING_REASONS = {"withheld", "missing", "format"}
# Item cells that no audit figure uses; an unread description or unit alone does not hold a page.
NON_CRITICAL = {"description", "unit", "batch", "line_no"}


def needs_review(gate):
    """True when a reading reason touches a field the audit uses."""
    return any(set(why) & READING_REASONS and not (path.startswith("items.") and path.split(".")[-1] in NON_CRITICAL)
               for path, why in gate.items())


def _ask(img, base_url, model):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=92)
    body = {"model": model, "temperature": 0, "max_tokens": 6000, "seed": 104729,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}},
                {"type": "text", "text": open(PROMPT, encoding="utf-8").read()}]}],
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def _same(a, b):
    """Two readings of one cell: equal as printed numbers («226000» and «226,000»), else equal as text."""
    x, y = amount(a), amount(b)
    return x == y if x is not None and y is not None else str(a).strip() == str(b).strip()


def fill_missing(pred, crop_schemas):
    """Fill only gate-flagged missing cells from a consistent crop reading of the same item."""
    filled = []
    for path, why in flags(pred).items():
        if "missing" not in why:
            continue
        _, j, k = path.split(".")
        item = pred["items"][int(j)]
        if k == "item_code":
            # The code of a row is filled only from a zoomed reading of the same row: every printed value the row
            # has (quantity, price, line total) equal, and one single code among all such rows.
            keys = [x for x in ("qty", "unit_price", "line_total") if amount(item.get(x)) is not None]
            codes = {cand["item_code"] for c in crop_schemas for cand in c.get("items", [])
                     if cand.get("item_code") and keys and all(amount(cand.get(x)) == amount(item[x]) for x in keys)}
            if len(keys) >= 2 and len(codes) == 1:
                item["item_code"] = codes.pop()
                filled.append(path)
            continue
        if not item.get("item_code"):
            continue
        found = set()
        for c in crop_schemas:
            for cand in c.get("items", []):
                if cand.get("item_code") != item["item_code"] or cand.get(k) is None:
                    continue
                if all(_same(item[x], cand[x]) for x in item if item[x] is not None and cand.get(x) is not None):
                    found.add(cand[k])
        if len(found) == 1:
            item[k] = found.pop()
            filled.append(path)
    return filled


def _flat(schema):
    """Every filled non-item field of a schema reading as {(section, key): value}."""
    return {(sec, k): v for sec in ("ids", "dates", "totals", "inspection") for k, v in (schema.get(sec) or {}).items()
            if v is not None}


def fill_unmapped(pred, unmapped, crop_schemas):
    """A value printed under a label the first reading could not map: fill the one empty field that every
    zoomed reading containing that exact value assigns it to. The value itself is never changed."""
    filled = []
    for u in unmapped:
        if u.get("section") not in ("header", "total") or u.get("value") is None:
            continue
        homes = set()
        for c in crop_schemas:
            for path, v in _flat(c).items():
                # Inspection fields belong to an inspection notice only (a receipt's «0.00» is not a penalty).
                if path[0] == "inspection" and pred.get("page_type") != "inspection":
                    continue
                if v == u["value"] and pred.get(path[0], {}).get(path[1], "x") is None:
                    homes.add(path)
        if len(homes) == 1:
            sec, key = homes.pop()
            pred[sec][key] = u["value"]
            if sec == "ids" and key == "receipt_no" and pred.get("page_type") == "inspection":
                pred["inspection"]["receipt_no"] = u["value"]
            filled.append(f"{sec}.{key}")
    return filled


OWN = {"receipt": "receipt_no", "invoice": "invoice_no", "purchase_order": "po_no"}


def critical_empty(pred):
    """A field the audit cannot do without is still empty: the page's own number, or an inspection penalty.
    Only then can a second look at an unmapped label change the result."""
    own = OWN.get(pred.get("page_type"))
    if own and not (pred.get("ids") or {}).get(own):
        return True
    return pred.get("page_type") == "inspection" and (pred.get("inspection") or {}).get("amount") is None


def _crops(img, base_url, model):
    w, h = img.size
    out = []
    for box in ((0, 0, w, int(h * .6)), (0, int(h * .4), w, h)):
        try:
            out.append(to_schema(parse(_ask(img.crop(box), base_url, model)))[0])
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
    return out


def link_invoice_rows(pred, pairs, evidence):
    """An invoice row may print the receipt (and PO) it belongs to; keep them beside the row for linking only."""
    if pred.get("page_type") == "invoice":
        from pairs_mapper import lookup, _pairs as pair_list
        source = pairs.get("items") or []
        group = {}
        for item, c_index in zip(pred.get("items") or [], evidence.get("cards_kept") or range(len(source))):
            card = source[c_index]
            # A receipt number is always STO + 10 digits and a PO number PON + 10 digits (owner's rule): found by
            # format, so swapped «سند الاستلام» / «التعميد» labels cannot link a line to the wrong document.
            refs = ({clean(v) for label, v in pair_list(card) if _own_id(v) == "receipt_no"} or
                    {clean(v) for label, v in pair_list(card) if lookup(label, "header") == "receipt_no" and clean(v)})
            pos = {clean(v) for label, v in pair_list(card) if _own_id(v) == "po_no"}
            # A group heading («سند الاستلام STO… · التعميد PON…») is printed once above its lines and is read into the
            # first line's card; the lines below it belong to the same receipt until the next heading. Two numbers on
            # one line are ambiguous: that line and the ones below it stay unlinked.
            if refs:
                group = {"_receipt_no": refs.pop()} if len(refs) == 1 else {}
                if group and len(pos) == 1:
                    group["_po_no"] = pos.pop()
            elif len(pos) == 1:
                (group or item)["_po_no"] = pos.pop()
            item.update(group)


def read_page(img, base_url=None, model=None):
    """Return the schema reading with '_pairs', '_safety_flags' and review markers."""
    base_url = base_url or os.environ["VLM_URL"]
    model = model or os.environ.get("VLM_MODEL", "Qwen/Qwen3.5-9B")
    pairs = None
    # An answer that is not valid JSON is asked once more on a slightly smaller rendering of the same page
    # (the first answer is deterministic, so the same image would give the same broken text).
    for attempt in (img, img.resize((img.width * 5 // 6, img.height * 5 // 6))):
        try:
            pairs = parse(_ask(attempt, base_url, model))
            pred, evidence = to_schema(pairs)
            break
        except (ValueError, KeyError, TypeError, AttributeError):
            pairs = None
    if pairs is None:
        return None
    valued = [u for u in evidence["unmapped"] if u.get("section") in ("header", "total") and u.get("value") is not None]
    if any("missing" in why for why in flags(pred).values()) or (valued and critical_empty(pred)):
        crops = _crops(img, base_url, model)
        pred["_zoom_filled"] = fill_missing(pred, crops) + fill_unmapped(pred, valued, crops)
    gate = flags(pred)
    # An inspection notice whose penalty is still not placed is never accepted on the first reading alone.
    if pred.get("page_type") == "inspection" and pred["inspection"].get("amount") is None:
        gate.setdefault("inspection.amount", []).append("withheld")
    link_invoice_rows(pred, pairs, evidence)
    pred["_pairs"] = pairs
    pred["_unmapped_labels"] = evidence["unmapped"]
    pred["_safety_flags"] = gate
    if needs_review(gate) or evidence.get("malformed"):
        pred["_reading_review"] = True
    if evidence.get("malformed"):
        pred["_malformed_pairs"] = evidence["malformed"]
    return pred
