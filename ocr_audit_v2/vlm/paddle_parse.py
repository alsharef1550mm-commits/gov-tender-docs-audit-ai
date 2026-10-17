"""يحوّل ناتج PaddleOCR-VL (Markdown + جداول HTML) إلى نفس مخطط الحقول لـQwen، لمقارنة عادلة بالحقل لا بالحضور.

لا يخمّن: ما لا يجده بوسم صريح يبقى None. لا يصحح قراءة النموذج ولا يعيد ترتيب خلايا مزاحة (الإزاحة تُحسب خطأً، وهذا مقصود).
"""
import html
import re

TD = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TR = re.compile(r"<tr>(.*?)</tr>", re.S)
TABLE = re.compile(r"<table.*?</table>", re.S)


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s.replace("\\n", " ")))).strip()


def tables(md):
    out = []
    for t in TABLE.findall(md):
        rows = [[strip(c) for c in TD.findall(r)] for r in TR.findall(t)]
        out.append(rows)
    return out


def num(s):
    m = re.search(r"-?\d[\d,]*\.?\d*", s or "")
    return m.group(0) if m else None


def empty_items():
    return {k: None for k in ("line_no", "item_code", "description", "unit", "qty", "unit_price", "unit_price_halala", "line_total",
                              "line_total_halala", "commission", "vat", "batch", "rate", "net")}


def parse(md):
    p = {"page_type": "other",
         "ids": {"receipt_no": None, "po_no": None, "invoice_no": None, "customer_po_no": None, "tender_no": None},
         "dates": {"document_date": None, "po_date": None, "due_date": None}, "items": [],
         "totals": {k: None for k in ("net_excl_vat", "commission", "discount", "vat", "total", "shipping", "penalty")}}
    m = re.search(r"STO\d{10}", md)
    p["ids"]["receipt_no"] = m.group(0) if m else None
    m = re.search(r"PON\d{10}", md)
    p["ids"]["po_no"] = m.group(0) if m else None
    low = md.lower()
    if "tax invoice" in low or "فاتورة ضريب" in md or "فاتوره ضريب" in md or "فاتورة جماعية" in md \
            or len(set(re.findall(r"STO\d{10}", md))) > 1:
        p["page_type"] = "invoice"          # الفاتورة الجماعية تسرد عدة سندات: لا تُعدّ سنداً
    elif "سند استلام" in md or "مذكرة استلام" in md or "مذکره استلام" in md or p["ids"]["receipt_no"]:
        p["page_type"] = "receipt"
    elif "purchase order" in low:
        p["page_type"] = "purchase_order"
    tbs = tables(md)
    for rows in tbs:
        flat = " | ".join(" ".join(r) for r in rows)
        # صف رؤوس الأصناف
        for ri, r in enumerate(rows):
            joined = " ".join(r)
            if "Material Code" in joined and "Batch" in joined:           # فاتورة نوبكو
                hdr = r
                col = {}
                for ci, h in enumerate(hdr):
                    if h.startswith("Material Code"):
                        col["item_code"] = ci
                    elif h.startswith("Batch"):
                        col["batch"] = ci
                    elif h.startswith("Unit Price"):
                        col["unit_price"] = ci
                    elif h.startswith("Quantity"):
                        col["qty"] = ci
                    elif h.startswith("Commlssion") or h.startswith("Commission"):
                        col["commission"] = ci
                    elif h.startswith("Tax Amount"):
                        col["vat"] = ci
                    elif h.startswith("Material Desc"):
                        col["description"] = ci
                    elif h.startswith("Item Subtotal"):
                        col["line_total"] = ci
                    elif h.startswith("(Amount") or h.startswith("Amount"):
                        col["amount"] = ci
                for dr in rows[ri + 1:]:
                    if dr and dr[0].strip().isdigit() and len(dr) >= len(hdr) - 1:
                        it = empty_items()
                        it["line_no"] = dr[0]
                        for k, ci in col.items():
                            if ci < len(dr) and k != "amount":
                                it[k] = dr[ci] if k in ("item_code", "batch", "description") else num(dr[ci])
                        p["items"].append(it)
            elif "رقم الصنف" in joined and "الكمية" in joined and "سعر الوحدة" in joined:   # سند 730
                col = {}
                for ci, h in enumerate(r):
                    if "رقم الصنف" in h:
                        col["item_code"] = ci
                    elif "وصف" in h:
                        col["description"] = ci
                    elif "الكمية" in h:
                        col["qty"] = ci
                    elif "سعر الوحدة" in h:
                        col["unit_price"] = ci
                    elif "نوبكو" in h:
                        col["commission"] = ci
                    elif "نسبة" in h and "الضريبة" in h:
                        col["rate"] = ci
                    elif h.strip() == "الصافي":
                        col["net"] = ci
                    elif h.strip() == "الضريبة":
                        col["vat"] = ci
                    elif "الاجمالي" in h or "الإجمالي" in h:
                        col["line_total"] = ci
                for dr in rows[ri + 1:]:
                    if len(dr) == len(r) and re.match(r"^[A-Z]{2,6}-[A-Z]?\d+", dr[col["item_code"]]):
                        it = empty_items()
                        for k, ci in col.items():
                            it[k] = dr[ci] if k in ("item_code", "description") else num(dr[ci])
                        p["items"].append(it)
        # ملخص بأزواج (قيمة، بيان) أو (بيان إنجليزي، بيان عربي، قيمة)
        for r in rows:
            if len(r) >= 2:
                label = " ".join(r[:-1]) + " " + r[-1]
                val = num(r[-1]) if re.fullmatch(r"[\d,]*\.?\d+", r[-1].replace(" ", "")) else (num(r[0]) if re.fullmatch(r"[\d,]*\.?\d+", r[0].replace(" ", "")) else None)
                if val is None:
                    continue
                t = p["totals"]
                if "Amount (Excluding VAT)" in label or "صافي الأصناف قبل" in label:
                    t["net_excl_vat"] = t["net_excl_vat"] or val
                elif label.startswith("Commission") or "نوبكو بنسبة" in label:
                    t["commission"] = t["commission"] or val
                elif label.startswith("Discount"):
                    t["discount"] = t["discount"] or val
                elif "Total VAT" in label or "ضريبة القيمة المضافة" in label and "Total" not in label:
                    t["vat"] = t["vat"] or val
                elif "Total Amount Due" in label or "الإجمالي شامل" in label:
                    t["total"] = t["total"] or val
            if len(r) == 2 and re.match(r"^Invoice No", r[0]):
                m = re.search(r"\d{10}", r[1])
                p["ids"]["invoice_no"] = m.group(0) if m else None
            if len(r) == 2 and re.match(r"^PO NO", r[0]):
                m = re.search(r"\d{6,}", r[1])
                p["ids"]["customer_po_no"] = m.group(0) if m else None
            if len(r) == 2 and r[0].startswith("Date"):
                p["dates"]["document_date"] = r[1]
    if not p["ids"]["invoice_no"]:
        m = re.search(r"(TF\d{10})", md) or re.search(r"رقم الفاتورة\s*\n+\s*(\d{10})", md)
        if m:
            p["ids"]["invoice_no"] = m.group(1)
    if not p["dates"]["document_date"]:
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", md)
        if m:
            p["dates"]["document_date"] = m.group(1)
    m = re.search(r"غرامة التأخير المسجلة:\s*([\d,]+\.?\d*)", md)
    if m:
        p["totals"]["penalty"] = m.group(1)
    # جدول السندات في الفاتورة الجماعية: (رقم المنافسة، رقم التعميد، رقم الاستلام، صافي السند)
    p["listing"] = []
    for rows in tbs:
        for r in rows:
            cells = " ".join(r)
            sto, pon = re.search(r"STO\d{10}", cells), re.search(r"PON\d{10}", cells)
            amt = [c for c in r if re.fullmatch(r"[\d,]+\.\d{2}", c.replace(" ", ""))]
            if sto and amt:
                p["listing"].append({"sto": sto.group(0), "pon": pon.group(0) if pon else None, "net": num(amt[0])})
    return p


if __name__ == "__main__":
    import json
    import sys
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(json.dumps(parse(d["markdown"]), ensure_ascii=False, indent=1))
