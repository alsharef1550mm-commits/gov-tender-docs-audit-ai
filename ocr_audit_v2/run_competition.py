"""يشغّل المستخرج والمحرك على كل ربطات منافسة ويقارن بتقرير Excel الموجود.

الاستعمال:  python run_competition.py <مجلد المنافسة> [workers]
المخرجات:   out/<رقم المنافسة>.json  و out/<رقم المنافسة>_compare.json  (لا تُكتب في مجلدات التقارير)
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time
from decimal import Decimal
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402
import engine  # noqa: E402

OUT = os.path.join(HERE, "out")


def _j(o):
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(type(o))


def work(args):
    path, contract, comp = args
    t = time.time()
    try:
        rules = engine.read_rules(contract, comp)
        b = extract.read_bundle(path)
        res = engine.check_bundle(b, rules)
        recs = []
        recs_by_sto = {r.sto: r for r in b.receipts}
        for r in res:
            src = recs_by_sto[r.sto]
            recs.append({
                "sto": r.sto, "file": b.file, "pon": r.pon, "invoice_no": r.invoice_no, "pages": r.pages,
                "net": r.net, "commission": r.commission, "vat": r.vat, "total": r.total, "penalty": r.penalty,
                "payable": r.payable, "late_days": r.late_days, "printed": src.printed,
                "issues": [{"code": i.code, "text": i.text, "printed": i.printed, "computed": i.computed, "page": i.page} for i in r.issues],
            })
        return {"file": b.file, "secs": round(time.time() - t, 1), "tax_mode": rules.tax_mode, "pages": b.n_pages,
                "types": {k: sum(1 for v in b.page_types.values() if v == k) for k in set(b.page_types.values())},
                "receipts": recs, "n_pos": len(b.pos), "n_invoices": len(b.invoices)}
    except Exception as e:  # noqa: BLE001
        return {"file": os.path.basename(path), "error": f"{type(e).__name__}: {e}"}


def load_report(xlsx: str) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    ws = wb["تقرير السندات"]
    rows = list(ws.iter_rows(values_only=True))
    hdr_i = next(i for i, r in enumerate(rows) if r and "رقم السند" in r)
    hdr = rows[hdr_i]
    idx = {h: k for k, h in enumerate(hdr) if h}
    sto_col = idx["رقم السند"]
    out = {}
    for r in rows[hdr_i + 1:]:
        if r and r[sto_col] and str(r[sto_col]).startswith("STO"):
            out[str(r[sto_col])] = {h: r[k] for h, k in idx.items()}
    return out


def compare(results: list[dict], report: dict) -> dict:
    mine = {}
    for f in results:
        for r in f.get("receipts", []):
            mine.setdefault(r["sto"], []).append(r)
    cmp = {"report_receipts": len(report), "extracted_unique": len(mine), "missing_in_extraction": [], "extra_in_extraction": [],
           "field_mismatch": {}, "status_mismatch": [], "dupe_sto": 0}
    for sto, rows in mine.items():
        if len(rows) > 1:
            cmp["dupe_sto"] += 1
    for sto in report:
        if sto not in mine:
            cmp["missing_in_extraction"].append(sto)
    for sto in mine:
        if sto not in report:
            cmp["extra_in_extraction"].append(sto)
    keys = {
        "net": "صافي الإجمالي لكامل السند",
        "commission": "عمولة نوبكو",
        "vat": "ضريبة القيمة المضافة",
        "total": "الإجمالي بعد عمولة نوبكو وضريبة القيمة المضافة",
        "penalty": "مبلغ الغرامة",
        "payable": "مبلغ السداد المستحق (للسند)",
    }
    for sto, rows in mine.items():
        if sto not in report:
            continue
        rep = report[sto]
        m = rows[0]
        for k, h in keys.items():
            try:
                a, b = Decimal(m[k]), Decimal(str(rep.get(h) or 0))
            except Exception:  # noqa: BLE001
                continue
            if abs(a - b) > Decimal("0.005"):
                cmp["field_mismatch"].setdefault(k, []).append({"sto": sto, "mine": str(a), "report": str(b)})
        status_rep = rep.get("حالة السند (سليم/غير سليم محاسبياً)")
        mine_ok = not m["issues"]
        rep_ok = status_rep in (None, "سليم")      # تقارير المنافسة لا تحمل عمود الحالة حين لا أخطاء
        if mine_ok != rep_ok:
            cmp["status_mismatch"].append({"sto": sto, "mine": "سليم" if mine_ok else [i["code"] for i in m["issues"]], "report": status_rep})
    return cmp


def main():
    folder = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    comp = re.search(r"(MED-[A-Z0-9]+-?\d*)\s*$", folder.rstrip("\\/")).group(1)
    contract = os.path.join(folder, "العقد", "عقد المنافسة.pdf")
    bundles = sorted(glob.glob(os.path.join(folder, f"{comp}-*.pdf")) or glob.glob(os.path.join(folder, "*.pdf")))
    os.makedirs(OUT, exist_ok=True)
    t = time.time()
    jobs = [(p, contract, comp) for p in bundles]
    if len(sys.argv) > 3 and sys.argv[3] == "cmp":
        with open(os.path.join(OUT, f"{comp}.json"), encoding="utf-8") as f:
            results = json.load(f)
    else:
        with Pool(workers) as pool:
            results = []
            for i, r in enumerate(pool.imap_unordered(work, jobs), 1):
                results.append(r)
                if i % 5 == 0 or i == len(jobs):
                    print(f"{comp}: {i}/{len(jobs)} bundles, {round(time.time() - t)}s", flush=True)
        results.sort(key=lambda r: r["file"])
        with open(os.path.join(OUT, f"{comp}.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, default=_j)
    xl = glob.glob(os.path.join(folder, "تقرير فحص المنافسة*.xlsx"))
    if xl:
        rep = load_report(xl[0])
        c = compare([r for r in results if "receipts" in r], rep)
        c["errors"] = [r for r in results if "error" in r]
        c["flagged_by_me"] = sum(1 for r in results for x in r.get("receipts", []) if x["issues"])
        c["tax_modes"] = sorted({r.get("tax_mode") for r in results if "tax_mode" in r})
        with open(os.path.join(OUT, f"{comp}_compare.json"), "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=1, default=_j)
        print(comp, "report", c["report_receipts"], "extracted", c["extracted_unique"], "missing", len(c["missing_in_extraction"]),
              "extra", len(c["extra_in_extraction"]), "status_mismatch", len(c["status_mismatch"]),
              {k: len(v) for k, v in c["field_mismatch"].items()}, "errors", len(c["errors"]), flush=True)


if __name__ == "__main__":
    main()
