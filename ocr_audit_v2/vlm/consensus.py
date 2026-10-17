"""مسار الإجماع: قارئون مستقلون ← تطبيع بالصيغة ← قبول عند اتفاق اثنين على الأقل وإلا إحالة للمراجع.

القرّاء: tesseract (OCR محلي + قص الهوية) | paddle (PaddleOCR-VL، ناتج محفوظ) | qwen (Qwen3.5-9B، ناتج محفوظ).
لا يخمّن ولا يصحح: القيمة التي لا يتفق عليها قارئان تبقى «للمراجعة» مع كل مرشحاتها.

تطبيع بالصيغة (يعالج تبديل الخانات الذي لوحظ عند Qwen): أي نص يطابق STO\\d{10} يُسند لرقم السند بغضّ النظر عن الخانة
التي وضعه فيها النموذج، وكذلك PON\\d{10} للتعميد، وTF\\d{10} أو 5\\d{9} للفاتورة.
"""
import json
import os
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import paddle_parse  # noqa: E402
import scan_parse  # noqa: E402

RE_STO = re.compile(r"STO\d{10}")
RE_PON = re.compile(r"PON\d{10}")
RE_INV = re.compile(r"TF\d{10}|(?<!\d)5\d{9}(?!\d)")
FIELDS = ("receipt_no", "po_no", "invoice_no", "net", "commission", "vat", "total", "date", "penalty")
AMOUNT_FIELDS = {"net", "commission", "total", "vat", "penalty"}


def dec(x):
    try:
        return Decimal(str(x).replace(",", "").strip()).normalize()
    except (InvalidOperation, AttributeError):
        return None


def fixed(d):
    """نص عشري ثابت (بلا صيغة علمية 1.4E+5) وبلا أصفار زائدة."""
    s = format(d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def norm_field(name, val):
    if val is None or val == "":
        return None
    if name in AMOUNT_FIELDS:
        d = dec(val)
        return fixed(d) if d is not None else None
    return str(val).strip()


def detect_type(text):
    """نوع الصفحة بكلمات دالة بعد توحيد أشكال الحروف العربية/الفارسية."""
    t = text
    for a, b in (("ک", "ك"), ("ھ", "ه"), ("ہ", "ه"), ("ة", "ه"), ("ی", "ي"), ("ى", "ي"), ("أ", "ا"), ("إ", "ا")):
        t = t.replace(a, b)
    low = t.lower()
    if "tax invoice" in low or "invoice details" in low or "total amount due" in low or "فاتوره ضريب" in t or "فاتوره جماعيه" in t \
            or "فاتوره توريد" in t:
        return "invoice"
    if "purchase order" in low or "امر تعميد" in t or "امر شراء" in t and "po method" in low:
        return "purchase_order"
    if ("مذكره استلام" in t or "سند استلام" in t or ("نموذج رقم" in t and "استلام" in t)) and "فاتوره ضريب" not in t:
        return "receipt"
    return None


def ids_from(strings):
    """يسند المعرّفات بحسب صيغتها لا بحسب الخانة التي وضعها فيها القارئ."""
    blob = " ".join(s for s in strings if s)
    sto = RE_STO.findall(blob)
    pon = RE_PON.findall(blob)
    inv = RE_INV.findall(blob)
    return {"receipt_no": sto[0] if len(set(sto)) == 1 else None,      # أكثر من معرّف مختلف = صفحة فواتير جماعية لا سند
            "po_no": pon[0] if len(set(pon)) == 1 else None,
            "invoice_no": inv[0] if len(set(inv)) == 1 else None}


def slots_from(ids):
    """أي خانة وضع فيها القارئ كل معرّف (دليل العنوان/الموضع): {field: {slot,...}}"""
    out = {"receipt_no": set(), "po_no": set(), "invoice_no": set()}
    for slot, v in (ids or {}).items():
        if not v:
            continue
        for fld, rx in (("receipt_no", RE_STO), ("po_no", RE_PON), ("invoice_no", RE_INV)):
            if rx.search(str(v)):
                out[fld].add(slot)
    return out


def reading_from_parsed(p):
    if not p:
        return None
    ids = p.get("ids") or {}
    r = ids_from([ids.get(k) for k in ("receipt_no", "po_no", "invoice_no", "customer_po_no", "tender_no")])
    r["slots"] = slots_from(ids)
    t = p.get("totals") or {}
    r.update({"type": p.get("page_type"), "net": norm_field("net", t.get("net_excl_vat")),
              "commission": norm_field("commission", t.get("commission")), "total": norm_field("total", t.get("total")),
              "vat": norm_field("vat", t.get("vat")), "penalty": norm_field("penalty", t.get("penalty")),
              "date": (p.get("dates") or {}).get("document_date"), "items_full": p.get("items") or [],
              "listing": p.get("listing") or []})
    r["items"] = [(i.get("item_code"), norm_field("qty", i.get("qty")), norm_field("unit_price", i.get("unit_price")))
                  for i in (p.get("items") or []) if i.get("item_code")]
    return r


def reading_tesseract(m):
    f = os.path.join(ROOT, "out", "scan", m["file"], f"p{m['page']}.json")
    js = json.load(open(f, encoding="utf-8"))
    lines = scan_parse.page_lines(js)
    text = " ".join(lines) + " " + (js.get("id_band") or "")
    r = ids_from([text])
    band = ids_from([js.get("id_band") or ""])     # شريط الهوية المقصوص بقراءة لاتينية = دليل موضع لرقم السند
    r["slots"] = {"receipt_no": {"receipt_no"} if band["receipt_no"] and band["receipt_no"] == r["receipt_no"] else set(),
                  "po_no": set(), "invoice_no": set()}
    md = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    mp = re.search(r"غرامة التأخير المسجلة:?\s*([\d,]+\.?\d*)", text)
    r.update({"type": detect_type(text), "net": None, "commission": None, "total": None, "vat": None, "items": [],
              "date": md.group(1) if md else None, "penalty": norm_field("penalty", mp.group(1)) if mp else None,
              "items_full": [], "listing": [{"sto": s} for s in sorted(set(RE_STO.findall(text)))] if "جماعي" in text else []})
    for ln in lines:                       # بيانات مجاميع بالعلامات (قالب 730 وسند/فاتورة نوبكو)
        a = scan_parse.amounts(ln)
        if not a:
            continue
        a = fixed(a[-1].normalize())
        if "صافي" in ln and "قبل" in ln or "بدون ضريبة" in ln or "Amount (Excl" in ln or "Amount (Excluding" in ln:
            r["net"] = r["net"] or a
        elif "نوبكو بنسبة" in ln or ("Commission" in ln and "Amount" not in ln and "Taxable" not in ln):
            r["commission"] = r["commission"] or a
        elif "شامل" in ln or "Total Amount Due" in ln or "Total Price" in ln:
            r["total"] = r["total"] or a
        elif "القيمة المضافة" in ln and "ضريبة" in ln:
            r["vat"] = r["vat"] or a
    return r


def load_reader(kind, m):
    if kind == "tesseract":
        return reading_tesseract(m)
    f = os.path.join(HERE, "results", kind, m["id"] + ".json")
    if not os.path.exists(f):
        return None
    js = json.load(open(f, encoding="utf-8"))
    parsed = js.get("parsed") if kind == "qwen" else paddle_parse.parse(js.get("markdown", ""))
    r = reading_from_parsed(parsed)
    if kind == "paddle" and r is not None and r.get("type") in (None, "other"):
        r["type"] = detect_type(js.get("markdown", "")) or r.get("type")
    return r


def consensus_page(readings):
    """readings: {reader: dict|None} -> (accepted {field: value}, review {field: candidates})"""
    acc, review = {}, {}
    for f in FIELDS + ("type",):
        cands = {k: (r.get(f) if r else None) for k, r in readings.items()}
        votes = Counter(v for v in cands.values() if v)
        if not votes:
            review[f] = {"candidates": cands, "why": "لم يقرأه أحد"}
            continue
        v, n = votes.most_common(1)[0]
        if n >= 2:
            acc[f] = v
        else:
            review[f] = {"candidates": cands, "why": "قارئ واحد أو تعارض"}
    return acc, review


READERS = ("tesseract", "paddle", "qwen")


def run(set_name):
    man = [m for m in json.load(open(os.path.join(HERE, "pages", "manifest.json"), encoding="utf-8")) if m["set"] == set_name]
    out = {}
    for m in man:
        rd = {k: load_reader(k, m) for k in READERS}
        acc, rev = consensus_page(rd)
        out[m["id"]] = {"file": m["file"], "page": m["page"], "readings": rd, "accepted": acc, "review": rev}
    return out


if __name__ == "__main__":
    res = run(sys.argv[1] if len(sys.argv) > 1 else "real")
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    dst = os.path.join(ROOT, "out", f"consensus_{sys.argv[1] if len(sys.argv) > 1 else 'real'}.json")
    json.dump(res, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(dst, len(res))
