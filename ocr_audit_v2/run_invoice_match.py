"""يشغّل مطابقة «الفاتورة مبرر مؤيد» على منافسة كاملة (النص المباشر).

لا يستعمل ترويسة رقم السند داخل الفاتورة إطلاقاً: يجمع بنود الفاتورة خاماً، ويبدأ من رقم الفاتورة المذكور في السند،
ويطابق بنود كل السندات المشيرة إليها (عبر ربطات وتعاميد المنافسة) ببنود الفاتورة.
الاستعمال: python run_invoice_match.py <مجلد المنافسة> [workers]    المخرجات: out/invmatch_<رقم>.json (لا تُكتب في التقارير)
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time
from collections import defaultdict
from decimal import Decimal
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402
import invoice_match as M  # noqa: E402

OUT = os.path.join(HERE, "out")
D = Decimal


def work(path):
    try:
        b = extract.read_bundle(path)
        recs = [{"sto": r.sto, "invoice_no": r.invoice_no, "pon": r.pon, "file": b.file,
                 "lines": [{"code": i.code, "qty": str(i.qty), "price": str(i.unit_price), "page": i.ev.page, "file": b.file}
                           for i in r.items]} for r in b.receipts]
        invs = []
        for v in b.invoices:                              # كل نسخة (حسب الترقيم المطبوع) على حدة؛ رقم السند في الفاتورة غير مستعمل
            by_copy = {}
            for i in v.items:
                by_copy.setdefault(i.copy, []).append({"code": i.code, "qty": str(i.qty), "price": str(i.unit_price),
                                                       "amount": str(i.total), "page": i.ev.page, "file": b.file})
            for c, lines in sorted(by_copy.items()):
                invs.append({"number": v.number, "file": b.file, "copy": c, "lines": lines})
        return {"file": b.file, "receipts": recs, "invoices": invs}
    except Exception as e:  # noqa: BLE001
        return {"file": os.path.basename(path), "error": f"{type(e).__name__}: {e}"}


def conv(lines, with_amount=False):
    out = []
    for l in lines:
        d = {"code": l["code"], "qty": D(l["qty"]), "price": D(l["price"]), "page": l.get("page"), "file": l.get("file")}
        if with_amount:
            d["amount"] = D(l["amount"])
        out.append(d)
    return out


def main():
    folder = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    comp = re.search(r"(MED-[A-Z0-9]+-?\d*)\s*$", folder.rstrip("\\/")).group(1)
    bundles = sorted(glob.glob(os.path.join(folder, f"{comp}-*.pdf")))
    t0 = time.time()
    with Pool(workers) as p:
        res = list(p.imap_unordered(work, bundles))
    errs = [r for r in res if "error" in r]
    receipts, invoice_copies = {}, defaultdict(list)
    for r in res:
        for x in r.get("receipts", []):
            receipts.setdefault(x["sto"], x)                       # كل سند مرة واحدة (نسخ الربطات المكررة)
        for v in r.get("invoices", []):
            invoice_copies[v["number"]].append(v)
    by_inv = defaultdict(list)
    for r in receipts.values():
        if r["invoice_no"]:
            by_inv[r["invoice_no"]].append(r)
    stats = defaultdict(int)
    detail = {}
    reason_kinds = defaultdict(int)
    for num in sorted(set(by_inv) | set(invoice_copies)):
        cit = by_inv.get(num, [])
        cps = invoice_copies.get(num, [])
        if not cps:
            stats["سندات تشير إلى فاتورة غير موجودة"] += len(cit)
            detail[num] = {"status": "invoice_missing", "receipts": [r["sto"] for r in cit]}
            continue
        if not cit:
            stats["فواتير بلا سند يشير إليها"] += 1
            detail[num] = {"status": "no_citing_receipt"}
            continue
        others = [{"sto": r["sto"], "lines": conv(r["lines"])} for r in receipts.values() if r["invoice_no"] != num]
        out = M.match_invoice([{"sto": r["sto"], "invoice_no": num, "lines": conv(r["lines"])} for r in cit],
                              {"number": num, "copies": [conv(c["lines"], True) for c in cps]}, other_receipts=others)
        stats["فواتير فريدة مطابَقة"] += 1
        stats["مجموعة متسقة (كل البنود مطابقة)"] += out["group_consistent"]
        stats["مجموعة بها إحالات"] += (not out["group_consistent"])
        for sto, v in out["receipts"].items():
            stats["سندات مرتبطة بفاتورة"] += 1
            stats["سند بنوده منسوبة بوضوح"] += v["clear"]
            stats["سند بمبلغ بنود مطبوع محسوم"] += v["amount"] is not None
        for rv in out["review"]:
            reason_kinds[rv["reason"]] += 1
        detail[num] = {"status": "ok" if out["group_consistent"] else "review", "n_receipts": len(cit), "copies": len(cps),
                       "review": out["review"][:6], "amounts": {k: v["amount"] for k, v in out["receipts"].items()}}
    stats["سندات فريدة"] = len(receipts)
    stats["سندات بلا رقم فاتورة"] = sum(1 for r in receipts.values() if not r["invoice_no"])
    os.makedirs(OUT, exist_ok=True)
    json.dump({"competition": comp, "stats": dict(stats), "review_kinds": dict(reason_kinds), "errors": errs, "detail": detail},
              open(os.path.join(OUT, f"invmatch_{comp}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"== {comp} ({round(time.time() - t0)}s, أخطاء ملفات {len(errs)})")
    for k, v in stats.items():
        print(f"   {k}: {v}")
    for k, v in reason_kinds.items():
        print(f"   [إحالة] {k}: {v}")


if __name__ == "__main__":
    main()
