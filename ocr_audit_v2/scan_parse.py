"""يقرأ مخرجات scan_ocr.py ويستخرج حقول سند الاستلام الممسوح (قالب 730 كخط أساس).

هذا خط أساس لقياس ما يقرؤه Tesseract وحده؛ لا يُعتمد كمنتج.
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HERE, "out", "scan")
RE_AMT = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})(?![\d])")
RE_STO = re.compile(r"STO\d{10}")
RE_STO_LOOSE = re.compile(r"[S$5][T7][O0Q]\s?\d{10}")


def page_lines(js: dict) -> list[str]:
    by = defaultdict(list)
    for w in js["words"]:
        by[tuple(w["line"])].append(w)
    out = []
    for k in sorted(by, key=lambda k: (min(x["y"] for x in by[k]) // 12, k)):
        ws = by[k]
        out.append(" ".join(x["t"] for x in ws))
    return out


def amounts(line: str) -> list[Decimal]:
    return [Decimal(m.replace(",", "")) for m in RE_AMT.findall(line)]


def parse_receipt_page(js: dict) -> dict | None:
    lines = page_lines(js)
    text = "\n".join(lines)
    band = js.get("id_band") or ""
    m = re.search(r"ST[O0Q]+\s?(\d{10})", band)          # شريط الهوية بقراءة لاتينية فقط (الأدق)
    if m:
        sto = "STO" + m.group(1)
        exact = True
    else:
        m = RE_STO.search(text) or RE_STO_LOOSE.search(text)
        exact = False
        if not m:
            return None
        sto = "STO" + re.sub(r"\D", "", m.group(0))[-10:]
    if "استلام" not in text:
        return None
    rec = {"sto": sto, "sto_exact": exact, "file": js["file"], "page": js["page"], "lines": lines}
    for ln in lines:
        a = amounts(ln)
        if not a:
            continue
        if "صافي" in ln and "قبل" in ln:
            rec["net"] = a[-1]
        elif "نوبكو بنسبة" in ln or ("نوبكو" in ln and "من الصافي" in ln):
            rec["commission"] = a[-1]
        elif "القيمة المضافة" in ln or "المضافة" in ln:
            rec["vat"] = a[-1]
        elif "شامل" in ln:
            rec["total"] = a[-1]
        elif "غرامة" in ln:
            rec["penalty"] = a[-1]
    inv = re.search(r"(?:TF|7[7F])?(\d{10})", " ".join(l for l in lines if "الفاتورة" in l))
    rec["invoice_digits"] = inv.group(1) if inv else None
    return rec


def load_all() -> list[dict]:
    recs = []
    for f in sorted(glob.glob(os.path.join(SCAN, "*", "p*.json"))):
        with open(f, encoding="utf-8") as fh:
            js = json.load(fh)
        r = parse_receipt_page(js)
        if r:
            recs.append(r)
    return recs


if __name__ == "__main__":
    for r in load_all()[:6]:
        print({k: str(v) for k, v in r.items() if k != "lines"})
