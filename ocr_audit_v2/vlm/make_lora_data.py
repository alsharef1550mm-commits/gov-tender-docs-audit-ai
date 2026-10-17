"""بيانات ضبط LoRA: صفحات مُفسَدة اصطناعياً من منافسات train فقط (318/305/144/231)، والمرجع من طبقة النص نفسها.

لا تدخل منافسات val/test (327/339/407) ولا 730 ولا مجموعة الصفحات الـ49 ولا أي تقرير قديم. الصور تمرّ بالمعالجة نفسها التي تمرّ بها
في القراءة الفعلية (تصغير إلى 1600 ثم تكبير 1.5× وشحذ وتباين) حتى يتطابق التدريب مع الاستعمال.
المخرج: <out>/images/*.jpg و <out>/train.jsonl (سطر لكل صفحة: image, target).
الاستعمال: python make_lora_data.py <out_dir> [صفحات لكل منافسة=220]
"""
from __future__ import annotations

import glob
import json
import os
import random
import sys
from decimal import Decimal

import pypdfium2 as pdfium

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import extract  # noqa: E402
import report_template as T  # noqa: E402
import vlm_reader as V  # noqa: E402
from make_synthetic_scans import SEVERITY, degrade  # noqa: E402

TRAIN = ("318", "305", "144", "231")


def _s(x, nd=None):
    if x is None:
        return None
    if nd is not None:
        return f"{Decimal(x):.{nd}f}"
    return format(x, "f")


def _split(x):
    """مبلغ -> (ريال، هللة) كما تُطبع خانتا الريال والهللة في السند."""
    x = Decimal(x).quantize(Decimal("0.01"))
    r = int(x)
    return str(r), f"{int(round((x - r) * 100)):02d}"


def target_for(b, n):
    ty = {"po": "purchase_order", "purchase_order": "purchase_order", "receipt": "receipt", "invoice": "invoice"}.get(b.page_types.get(n), "other")
    ids = {"receipt_no": None, "po_no": None, "invoice_no": None, "customer_po_no": None, "tender_no": None}
    dates = {"document_date": None, "po_date": None, "due_date": None}
    items, totals = [], {"net_excl_vat": None, "commission": None, "discount": None, "vat": None, "total_incl": None, "total": None, "shipping": None, "penalty": None}
    if ty == "receipt":
        for r in b.receipts:
            if n not in r.pages:
                continue
            ids.update(receipt_no=r.sto, po_no=r.pon, invoice_no=r.invoice_no)
            dates.update(document_date=r.date, due_date=r.due)
            for it in r.items:
                if it.ev.page == n:
                    up, uph = _split(it.unit_price)
                    lt, lth = _split(it.line_total)
                    items.append({"line_no": str(it.line_no), "item_code": it.code, "description": None, "unit": it.unit, "qty": _s(it.qty),
                                  "unit_price": up, "unit_price_halala": uph, "line_total": lt, "line_total_halala": lth,
                                  "commission": None, "vat": None, "batch": None})
            if r.summary_ev is not None and r.summary_ev.page == n:
                p = r.printed
                totals.update(net_excl_vat=_s(p.get("net"), 2), commission=_s(p.get("nupco"), 2), vat=_s(p.get("vat"), 2),
                              total_incl=_s(p.get("total"), 2), total=_s(p.get("final"), 2), discount=_s(p.get("discount"), 2),
                              shipping=_s(p.get("shipping"), 2), penalty=_s(p.get("penalty"), 2))
    elif ty == "invoice":
        for v in b.invoices:
            if n not in v.pages:
                continue
            ids["invoice_no"] = v.number
            dates["document_date"] = v.date
            for it in v.items:
                if it.ev.page == n:
                    ids["receipt_no"] = ids["receipt_no"] or it.sto or None
                    items.append({"line_no": str(it.line_no), "item_code": it.code, "description": None, "unit": None, "qty": _s(it.qty),
                                  "unit_price": _s(it.unit_price, 2), "unit_price_halala": None, "line_total": _s(it.total, 2),
                                  "line_total_halala": None, "commission": _s(it.nupco, 2), "vat": _s(it.vat, 2), "batch": it.batch or None})
    elif ty == "purchase_order":
        for p in b.pos:
            if n not in p.pages:
                continue
            ids["po_no"] = p.number
            dates["po_date"] = p.release_date
            for it in p.items:
                if it.ev.page == n:
                    dates["due_date"] = dates["due_date"] or it.due
                    items.append({"line_no": str(it.line_no), "item_code": it.code, "description": None, "unit": it.unit, "qty": _s(it.qty_ordered),
                                  "unit_price": _s(it.unit_price, 2), "unit_price_halala": None, "line_total": _s(it.total, 2),
                                  "line_total_halala": None, "commission": None, "vat": _s(it.vat, 2), "batch": None})
    return {"page_type": ty, "ids": ids, "dates": dates, "items": items, "totals": totals, "unreadable_fields": []}


def one_comp(args):
    comp, per_comp, seed, out = args
    rng = random.Random(f"{seed}-{comp}")
    folder = glob.glob(os.path.join(T.ROOT, "المنافسات", f"*MED-2026-{comp}"))[0]
    bundles = sorted(glob.glob(os.path.join(folder, f"MED-2026-{comp}-*.pdf")))
    picks = rng.sample(bundles, min(len(bundles), 14))
    pool = {"receipt": [], "invoice": [], "purchase_order": []}
    for path in picks:
        b = extract.read_bundle(path)
        for n in range(1, b.n_pages + 1):
            t = target_for(b, n)
            if t["page_type"] in pool and t["items"] and all(i["item_code"] and i["qty"] for i in t["items"]):
                pool[t["page_type"]].append((path, n, t))
    quota = {"receipt": int(per_comp * 0.42), "invoice": int(per_comp * 0.42), "purchase_order": int(per_comp * 0.16)}
    rows = []
    for ty, lst in pool.items():
        for path, n, t in rng.sample(lst, min(quota[ty], len(lst))):
            sev = rng.choice(["mild", "medium", "severe"])
            scale = rng.choice([1.4, 2.0, 3.0])
            img = pdfium.PdfDocument(path)[n - 1].render(scale=scale).to_pil()
            img = degrade(img, SEVERITY[sev], rng)
            img.thumbnail((1600, 1600))
            img = V._prep_up(img)
            fn = f"{comp}_{os.path.basename(path)[:-4].split('-')[-1]}_{n:03d}_{sev}.jpg"
            img.save(os.path.join(out, "images", fn), "JPEG", quality=92)
            rows.append({"image": fn, "competition": comp, "bundle": os.path.basename(path), "page": n, "severity": sev, "target": t})
    return rows


def main(out, per_comp=220, seed=21):
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    parts = [one_comp((c, per_comp, seed, out)) for c in TRAIN]               # تسلسلي: Pool يفشل على ويندوز هنا (PermissionError)
    rows = [r for p in parts for r in p]
    random.Random(seed).shuffle(rows)
    with open(os.path.join(out, "train.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print("الإجمالي", len(rows), Counter(r["target"]["page_type"] for r in rows), Counter(r["competition"] for r in rows))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 220)
