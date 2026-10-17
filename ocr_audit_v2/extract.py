"""مستخرج ربطات PDF ذات النص المباشر: تعميد ← سند استلام ← فاتورة.

كل قيمة مستخرجة تُرجَع مع دليلها (الملف، الصفحة، مربع السطر) ولا يُستنتج رقم مفقود.
لا يحسب هذا الملف شيئاً ماليّاً؛ الحساب في engine.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation

import pdfx

D = Decimal
RE_STO = re.compile(r"^STO\d{10}$")
RE_PON = re.compile(r"^PON\d{10}$")
RE_INV = re.compile(r"^\d{10}$")
RE_CODE = re.compile(r"^[A-Z]{2,6}-[A-Z]?\d{2,3}$")
RE_NUM = re.compile(r"^-?[\d,]*\d(\.\d+)?$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UNITS = {"EA", "SET", "PACK", "BOX", "KIT", "BTL", "ROLL", "PC", "PCS", "CASE", "VIAL", "AMP", "TUBE", "BAG", "PAIR"}


def num(t: str) -> Decimal | None:
    t = t.replace(",", "").rstrip("%")
    try:
        return D(t)
    except InvalidOperation:
        return None


def norm_ar(s: str) -> str:
    for a, b in (("ی", "ي"), ("ھ", "ه"), ("ى", "ي"), ("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ـ", "")):
        s = s.replace(a, b)
    return s


@dataclass
class Ev:
    """دليل مصدر لقيمة أو صف."""
    file: str
    page: int
    box: tuple[float, float, float, float]


def line_box(line: pdfx.Line) -> tuple[float, float, float, float]:
    ws = line.words
    return (min(w.x0 for w in ws), min(w.top for w in ws), max(w.x1 for w in ws), max(w.bottom for w in ws))


# ---------------------------------------------------------------- تصنيف
def classify(p: pdfx.Page) -> str:
    txt = p.text
    if "PURCHASE ORDER" in txt:
        return "po"
    if "Tax Invoice" in txt:
        return "invoice"
    toks = {w.text for w in p.words}
    if any(re.match(r"^IN\d{10}$", t) for t in toks) and any(re.match(r"^DN\d{10}$", t) for t in toks):
        return "receipt"
    return "other"


def segments(line: pdfx.Line):
    """يقسم السطر إلى أزواج (قيمة، كلمات الوصف التي تليها بصرياً)."""
    segs: list[list] = []
    for w in sorted(line.words, key=lambda w: w.x0):
        t = w.text
        is_val = (RE_NUM.match(t) or RE_DATE.match(t)) and not t.startswith("%")
        if is_val:
            segs.append([t, []])
        elif segs:
            segs[-1][1].append(norm_ar(t))
    return segs


# ---------------------------------------------------------------- التعميد
@dataclass
class POItem:
    line_no: int
    code: str
    unit: str
    qty_ordered: Decimal
    unit_price: Decimal
    total: Decimal
    vat: Decimal
    final: Decimal
    due: str | None
    ev: Ev


@dataclass
class PO:
    number: str
    release_date: str | None
    quarter: int | None
    items: list[POItem] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)        # صفحات التعميد في الربطة (كل ظهور)


def parse_po_pages(pages: list[pdfx.Page], fname: str) -> list[PO]:
    pos: dict[str, PO] = {}
    for p in pages:
        pon = None
        date = None
        quarter = None
        for l in p.lines:
            t = l.text
            m = re.search(r"Purchase Order No : (PON\d{10})", t)
            if m:
                pon = m.group(1)
            m = re.search(r"Date Release : (\d{4}-\d{2}-\d{2})", t)
            if m:
                date = m.group(1)
            m = re.search(r"Quarter (\d+)", t)
            if m and quarter is None:
                quarter = int(m.group(1))
        if not pon:
            continue
        po = pos.setdefault(pon, PO(pon, date, quarter))
        po.pages.append(p.n)
        lines = p.lines
        for i, l in enumerate(lines):
            toks = [w.text for w in sorted(l.words, key=lambda w: w.x0)]
            if len(toks) < 14 or not toks[0].isdigit() or "DY:" not in toks:
                continue
            code = next((t for t in toks if RE_CODE.match(t) and not t.startswith("R-")), None)
            # آخر 9 أرقام: onhand ord bonus uprice disc netuprice total vat final
            tail = toks[-9:]
            vals = [num(t) for t in tail]
            if code is None or any(v is None for v in vals):
                continue
            unit = toks[-10]
            due = None
            for nxt in lines[i + 1:i + 4]:                       # «Due:» تحت البند، وقد يفصلهما سطر وصف ملتف
                m = re.search(r"Due: (\d{4}-\d{2}-\d{2})", nxt.text)
                if m:
                    due = m.group(1)
                    break
                if "DY:" in nxt.text:
                    break
            po.items.append(POItem(int(toks[0]), code, unit, vals[1], vals[3], vals[6], vals[7], vals[8], due,
                                   Ev(fname, p.n, line_box(l))))
    return list(pos.values())


# ---------------------------------------------------------------- سند الاستلام
@dataclass
class RItem:
    line_no: int
    code: str
    unit: str
    qty: Decimal
    unit_price: Decimal
    line_total: Decimal       # كما طُبع (شامل العمولة والضريبة)
    vat_rate: Decimal | None
    ev: Ev


@dataclass
class Receipt:
    sto: str
    pon: str | None = None
    invoice_no: str | None = None
    date: str | None = None
    competition: str | None = None
    items: list[RItem] = field(default_factory=list)
    printed: dict = field(default_factory=dict)      # net, nupco, vat, total, discount, shipping, penalty, late_days, final
    due: str | None = None
    quarter: int | None = None
    pages: list[int] = field(default_factory=list)
    summary_ev: Ev | None = None


LABELS = [
    ("final", lambda w: "النهائي" in w),
    ("total", lambda w: "شامل" in w),
    ("vat", lambda w: "ضريبه" in w and "الضريبه" in w and "الشحن" not in w and "اجمالي" in w),
    ("shipping_vat", lambda w: "الشحن" in w and "ضريبه" in w),
    ("shipping", lambda w: "الشحن" in w and "قيمه" in w),
    ("penalty", lambda w: "غرامه" in w),
    ("late_days", lambda w: "ايام" in w),
    ("discount", lambda w: "الخصم" in w),
    ("due", lambda w: "موعد" in w),
    ("quarter", lambda w: "الربع" in w and "التعاقدي:" in w),
    ("nupco", lambda w: "نوبكو" in w and "%4" in w),
    ("net", lambda w: "صافي" in w),
]


def _flat(words: list[str]) -> set[str]:
    out = set()
    for x in words:
        x = x.strip()
        out.add(x)
        out.add(x.rstrip(":"))
        # أزل ال التعريف ليطابق الجذر بصرف النظر عن الشكل
        for pre in ("ال", "ا"):
            pass
    return out


def label_key(words: list[str]) -> str | None:
    w = _flat(words)
    # توحيد: كلمات مثل (الاجمالي/اإلجمالي) و(الضريبة) تختلف بين الخطوط
    joined = " ".join(words)
    w2 = set(w)
    if "جمالي" in joined:
        w2.add("اجمالي")
    if "ضريب" in joined:
        w2.add("ضريبه")
        if "الضريب" in joined:
            w2.add("الضريبه")
    if "الشحن" in joined:
        w2.add("الشحن")
    if "شامل" in joined:
        w2.add("شامل")
    if "نهائي" in joined:
        w2.add("النهائي")
    if "غرامه" in joined or "غرامة" in joined:
        w2.add("غرامه")
    if "يام" in joined:
        w2.add("ايام")
    if "خصم" in joined:
        w2.add("الخصم")
    if "موعد" in joined:
        w2.add("موعد")
    if "ربع" in joined:
        w2.add("الربع")
        if "التعاقدي" in joined:
            w2.add("التعاقدي:")
    if "قيم" in joined and "الشحن" in joined:
        w2.add("قيمه")
    if "صافي" in joined and "صناف" in joined:
        w2.add("صافي")
    if "نوبكو" in joined:
        w2.add("نوبكو")
    for key, fn in LABELS:
        if fn(w2):
            return key
    return None


def parse_receipts(pages: list[pdfx.Page], fname: str) -> list[Receipt]:
    recs: dict[str, Receipt] = {}
    seq: list[Receipt] = []                 # السندات بترتيب ظهورها، وفيها النسخ المكررة كسندات مستقلة
    prev_sto = None
    for p in pages:
        sto = pon = None
        inv = None
        date = None
        comp = None
        for l in p.lines:
            toks = [w.text for w in l.words]
            for t in toks:
                if RE_STO.match(t) and sto is None:
                    sto = t
                if RE_PON.match(t) and pon is None:
                    pon = t
                if RE_INV.match(t) and l.top < 70 and inv is None:
                    inv = t
                m = re.match(r"^MED-[A-Z0-9]+-?\d*$", t)
                if m and comp is None and l.top < 100:
                    comp = t
            if date is None and l.top < 60:
                for t in toks:
                    if RE_DATE.match(t):
                        date = t
        if not sto:
            continue
        r = recs.get(sto)
        if r is None or (sto != prev_sto and r.pages):
            # رقم سند ظهر من قبل ثم بدأ بعده سند آخر: نسخة مكررة لا امتداد للسند نفسه؛ تُسجَّل سنداً مستقلاً فيلتقطها فحص التكرار
            dup = r is not None
            r = Receipt(sto)
            if dup:
                r.__dict__["duplicate_of_pages"] = list(recs[sto].pages)
            else:
                recs[sto] = r
            seq.append(r)
        prev_sto = sto
        r.pon = r.pon or pon
        r.invoice_no = r.invoice_no or inv
        r.date = r.date or date
        r.competition = r.competition or comp
        r.pages.append(p.n)
        lines = p.lines
        for i, l in enumerate(lines):
            toks = [w.text for w in sorted(l.words, key=lambda w: w.x0)]
            code_i = next((k for k, t in enumerate(toks) if RE_CODE.match(t)), None)
            if code_i is not None and 200 < l.top < 420 and toks and toks[-1].isdigit():
                # ... a b c d qty UNIT desc... CODE lineno
                unit_i = None
                for k in range(code_i - 1, -1, -1):
                    if re.match(r"^[A-Z]{2,6}$", toks[k]):
                        unit_i = k
                        break
                if unit_i is None or unit_i < 5:
                    continue
                qty = num(toks[unit_i - 1])
                nums = [num(t) for t in toks[unit_i - 5:unit_i - 1]]
                if qty is None or any(n is None for n in nums):
                    continue
                total = nums[0] + nums[1] / 100
                up = nums[2] + nums[3] / 100
                rate = None
                if i + 1 < len(lines):
                    m = re.search(r"%(\d+)", lines[i + 1].text)
                    if m:
                        rate = D(m.group(1))
                r.items.append(RItem(int(toks[-1]), toks[code_i], toks[unit_i], qty, up, total, rate,
                                     Ev(fname, p.n, line_box(l))))
            elif l.top > 400:
                for val, lab in segments(l):
                    key = label_key(lab)
                    if key is None:
                        continue
                    if key in ("due",):
                        r.due = val
                    elif key == "quarter":
                        r.quarter = int(num(val) or 0)
                    elif key in ("net", "nupco", "vat", "total", "discount", "shipping", "shipping_vat", "penalty", "late_days", "final"):
                        v = num(val)
                        if v is not None and key not in r.printed:
                            r.printed[key] = v
                            r.summary_ev = Ev(fname, p.n, line_box(l))
    return seq


# ---------------------------------------------------------------- الفاتورة
@dataclass
class IItem:
    sto: str
    line_no: int
    code: str
    batch: str
    unit_price: Decimal
    qty: Decimal
    net: Decimal
    nupco: Decimal
    discount: Decimal
    pre_vat: Decimal
    vat_rate: Decimal
    vat: Decimal
    total: Decimal
    ev: Ev
    expiry: str | None = None   # تاريخ الصلاحية المطبوع في صف الفاتورة
    copy: int = 0          # رقم نسخة الفاتورة داخل الربطة (تتحدد من ترقيم «Page 1 of N» المطبوع)


@dataclass
class Invoice:
    number: str
    items: list[IItem] = field(default_factory=list)
    allocations: dict = field(default_factory=dict)   # sto -> amount
    allocation_pon: dict = field(default_factory=dict)
    printed: dict = field(default_factory=dict)
    pages: list[int] = field(default_factory=list)
    receipt_count: int | None = None
    cur_copy: int = 0
    date: str | None = None                                   # تاريخ الفاتورة (Invoice Date)
    copy_pages: dict = field(default_factory=dict)            # رقم النسخة -> صفحاتها


def parse_invoices(pages: list[pdfx.Page], fname: str) -> list[Invoice]:
    invs: dict[str, Invoice] = {}
    order: list[str] = []
    for p in pages:
        number = None
        for l in p.lines:
            if l.top < 40:
                for w in l.words:
                    if RE_INV.match(w.text):
                        number = w.text
                        break
            if number:
                break
        if not number:
            continue
        inv = invs.get(number)
        if inv is None:
            inv = invs[number] = Invoice(number)
            order.append(number)
        # نسخة الفاتورة: «Page i of n» يعود إلى 1 عند بدء نسخة مكررة (يُعتمد الترقيم المطبوع لا تطابق الصفوف)
        mp = re.search(r"Page (\d+) of (\d+)", p.text)
        if mp and int(mp.group(1)) == 1 and inv.pages:
            inv.cur_copy += 1
        inv.pages.append(p.n)
        inv.copy_pages.setdefault(inv.cur_copy, []).append(p.n)
        cur_sto = None
        for l in p.lines:
            toks = [w.text for w in sorted(l.words, key=lambda w: w.x0)]
            joined = " ".join(toks)
            if inv.date is None and "Invoice Date" in joined:
                md = re.search(r"\d{4}-\d{2}-\d{2}", joined)
                if md:
                    inv.date = md.group(0)
            m = re.search(r"Receipt Count", joined)
            if m:
                for t in toks:
                    if t.isdigit() and len(t) <= 3:
                        inv.receipt_count = int(t)
            st = [t for t in toks if RE_STO.match(t)]
            pn = [t for t in toks if RE_PON.match(t)]
            if st and pn:
                nums_after = [num(t) for t in toks if "." in t and num(t) is not None and not RE_DATE.match(t)]
                idx_p = toks.index(pn[0])
                # صف توزيع على السندات: STO PON مبلغ
                if len(toks) <= 5 and nums_after:
                    inv.allocations[st[0]] = nums_after[-1]
                    inv.allocation_pon[st[0]] = pn[0]
                    continue
                cur_sto = st[0]
                continue
            # بند
            if len(toks) >= 14 and toks[0].isdigit():
                bi = next((k for k, t in enumerate(toks) if re.match(r"^T\d{5,}$", t)), None)
                code = next((t for t in toks if RE_CODE.match(t)), None)
                if bi is not None and code and len(toks) >= bi + 12:       # رقم السند في الفاتورة غير مشروط
                    v = toks[bi + 3: bi + 12]
                    n = [num(x) for x in v[:7]] if False else None
                    try:
                        up, q, net, nup, disc, pre = (num(x) for x in toks[bi + 3: bi + 9])
                        rate = num(toks[bi + 9])
                        vat = num(toks[bi + 10])
                        tot = num(toks[bi + 11])
                    except Exception:
                        continue
                    if None in (up, q, net, nup, disc, pre, rate, vat, tot):
                        continue
                    inv.items.append(IItem(cur_sto or "", int(toks[0]), code, toks[bi], up, q, net, nup, disc, pre, rate, vat, tot,
                                           Ev(fname, p.n, line_box(l)), copy=inv.cur_copy,
                                           expiry=(toks[bi + 2] if RE_DATE.match(toks[bi + 2]) else None)))
                    continue
            # ملخص الفاتورة: قيمة ثم وصف إنجليزي |
            if "|" in toks:
                bar = toks.index("|")
                head = toks[:bar]
                for k, t in enumerate(head):
                    pass
                lab = " ".join(head)
                # الشكل: "705.00 Net | ..." أو "0.00 VAT Base | ..."
                val = num(head[0]) if head else None
                if val is None:
                    continue
                key = {
                    "Net": "net", "NUPCO": "nupco", "Discount": "discount", "Pre-VAT": "pre_vat",
                    "VAT Base": "vat_base", "VAT": "vat", "Amount Due": "due",
                }.get(" ".join(head[1:]).strip())
                if key and key not in inv.printed:
                    inv.printed[key] = val
            elif len(toks) >= 2 and RE_NUM.match(toks[0]) and toks[1:] and " ".join(toks[1:]) in ("Net", "Discount", "Pre-VAT", "VAT Base", "VAT", "Amount Due"):
                pass
    return [invs[n] for n in order]


# ---------------------------------------------------------------- الربطة
@dataclass
class Bundle:
    file: str
    n_pages: int
    page_types: dict[int, str]
    pos: list[PO]
    receipts: list[Receipt]
    invoices: list[Invoice]
    source: str = "text"            # text = طبقة نص أصلية، ocr = قراءة OCR لصفحات ممسوحة (كل قيمة فيها غير موثّقة حتى تُراجَع)


def is_scanned(pages) -> bool:
    return bool(pages) and sum(1 for p in pages if len(p.words) < 15) > len(pages) / 2


def read_bundle(path: str, pages=None) -> Bundle:
    import os
    fname = os.path.basename(path)
    source = "text"
    if pages is None:
        pages = pdfx.read_pdf(path)
        if is_scanned(pages):
            if os.environ.get("VLM_URL"):                       # نموذج رؤية متاح: قراءة منظمة ثم تحقق حتمي
                import vlm_reader
                import progress_hook as PH
                return vlm_reader.read_bundle_vlm(path, progress=lambda k, n, stage="read": PH.report(stage, k, n, {"prep": "تجهيز الصفحات", "reread": "إعادة قراءة الصفحات المشتبه فيها"}.get(stage, "قراءة الصفحات بنموذج الرؤية")))
            import scan_reader
            import progress_hook as PH
            pages = scan_reader.ocr_pages(path, progress=lambda k, n: PH.report("ocr", k, n, "قراءة الصفحات بـOCR"))
            source = "ocr"
    types = {p.n: classify(p) for p in pages}
    po_pages = [p for p in pages if types[p.n] == "po"]
    r_pages = [p for p in pages if types[p.n] == "receipt"]
    i_pages = [p for p in pages if types[p.n] == "invoice"]
    return Bundle(fname, len(pages), types, parse_po_pages(po_pages, fname), parse_receipts(r_pages, fname),
                  parse_invoices(i_pages, fname), source)
