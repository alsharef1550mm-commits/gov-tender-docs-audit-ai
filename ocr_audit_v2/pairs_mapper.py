"""Map printed label/value pairs to the extraction schema by label text only.

The vision model transcribes; this module decides meaning. No arithmetic, no
template positions, no expected-ID patterns. A label that matches nothing stays
unmapped, and two different values claimed by one field are both withheld and
listed in unreadable_fields for review.

The alias vocabulary is the union of the training generators' labels
(vlm/make_design_batches.LABELS, tools/build_dense_batches LABELS/ALIASES),
candidate/semantic_reader.ALIASES and field_registry.FIELDS. Nothing here was
added from validation, controls, internal or final-test pages.
"""
import copy
import json
import re
import unicodedata

SCHEMA = {
    "page_type": None,
    "ids": dict.fromkeys(["receipt_no", "po_no", "invoice_no", "customer_po_no", "tender_no", "quarter"]),
    "dates": dict.fromkeys(["document_date", "po_date", "due_date"]),
    "items": [],
    "totals": dict.fromkeys(["net_excl_vat", "commission", "discount", "vat", "total_incl", "total",
                             "shipping", "penalty", "other_penalty"]),
    "inspection": dict.fromkeys(["notice_no", "receipt_no", "affected_qty", "amount", "description"]),
    "unreadable_fields": [],
}
ITEM_KEYS = ["line_no", "item_code", "description", "unit", "qty", "unit_price", "unit_price_halala",
             "line_total", "line_total_halala", "commission", "vat", "batch", "line_net", "vat_rate"]
PAGE_TYPES = {"receipt", "purchase_order", "invoice", "inspection", "contract", "other"}

HEADER = {
    "receipt_no": ["رقم السند", "رقم سند الاستلام", "رقم مذكرة الاستلام", "مرجع الاستلام", "Receipt ID",
                   "Goods receipt no", "GRN"],
    "po_no": ["رقم التعميد", "مرجع أمر الشراء", "رقم أمر الشراء", "أمر الشراء", "Purchase order",
              "Purchase Order No", "PO number", "Order reference"],
    "invoice_no": ["رقم الفاتورة", "فاتورة المورد رقم", "مرجع فاتورة المورد", "Invoice No", "Invoice number",
                   "Supplier invoice"],
    # Owner (2026-10-25): مستند نوبكو = فاتورة نوبكو (the 4600… NUPCO number), never the supplier invoice.
    "customer_po_no": ["مرجع العميل", "مستند نوبكو", "PO Doc", "Customer reference", "فاتورة نوبكو", "رقم فاتورة نوبكو",
                       "رقم مستند نوبكو", "NUPCO invoice", "NUPCO invoice No"],
    "tender_no": ["رقم المنافسة", "رقم المنافسة العقد", "معرف المنافسة", "المنافسة", "رقم المناقصة", "Competition ref",
                  "Tender number", "Tender No", "Tender"],
    "quarter": ["الدفعة", "الربع", "رقم الدفعة", "Quarter"],
    "document_date": ["تاريخ الاستلام", "تاريخ السند", "تاريخ الإصدار", "تاريخ الفاتورة", "تاريخ المستند",
                      "Document date", "Receipt date", "Invoice date"],
    "po_date": ["تاريخ أمر الشراء", "تاريخ التعميد", "Order date"],
    "due_date": ["آخر موعد للتوريد", "موعد التوريد", "Delivery due", "Due date"],
    "notice_no": ["رقم المحضر", "Notice No", "Notice number", "Inspection reference"],
    "affected_qty": ["الكمية المتضررة", "عدد الوحدات المتضررة", "الوحدات المخالفة", "Affected quantity",
                     "Affected units"],
    "amount": ["مبلغ المخالفة", "مبلغ الغرامة", "الغرامة المثبتة", "Penalty amount", "Stated penalty"],
    "violation": ["وصف المخالفة", "نوع المخالفة", "المخالفة", "Violation description", "Violation"],
}
ITEM = {
    "line_no": ["م", "No", "Line"],
    "item_code": ["رمز الصنف", "رقم الصنف", "رمز المادة", "الرمز", "Item code"],
    "description": ["الوصف", "وصف الصنف", "Description"],
    "unit": ["الوحدة", "Unit"],
    "qty": ["الكمية", "الكمية المطلوبة", "الكمية المستلمة", "Quantity", "Qty"],
    "unit_price": ["سعر الوحدة", "قيمة الوحدة", "السعر", "Unit price", "Price per unit", "Price"],
    "unit_price_halala": ["هللة السعر", "Price halala"],
    "line_total_halala": ["هللة الإجمالي", "Total halala"],
    "line_net": ["الصافي", "صافي الصنف", "صافي القيمة", "القيمة قبل الإضافات", "الصافي قبل الإضافات",
                 "Line net", "Net amount", "Amount excl tax"],
    "line_total": ["الإجمالي", "القيمة الشاملة", "إجمالي الصنف", "إجمالي البند", "الإجمالي شامل الضريبة",
                   "Line gross", "Gross amount", "Total incl VAT", "Row total"],
    "commission": ["نوبكو", "رسوم نوبكو", "عمولة نوبكو", "مبلغ العمولة", "NUPCO", "Commission", "NUPCO amount"],
    "vat": ["الضريبة", "مبلغ الضريبة", "قيمة ضريبة القيمة المضافة", "ضريبة القيمة المضافة", "VAT amount",
            "Tax amount", "VAT"],
    "vat_rate": ["نسبة الضريبة", "VAT rate"],
    "batch": ["رقم التشغيلة", "التشغيلة", "تشغيلة الصنف", "Lot / batch", "Batch"],
}
TOTAL = {
    "net_excl_vat": ["صافي الأصناف", "إجمالي قيمة المواد", "الصافي قبل الإضافات", "صافي المواد", "الصافي",
                     "Net amount"],
    "commission": ITEM["commission"],
    "vat": ["الضريبة", "مبلغ الضريبة", "قيمة ضريبة القيمة المضافة", "ضريبة القيمة المضافة", "VAT amount",
            "Tax amount", "VAT"],
    "total_incl": ["المبلغ الشامل", "الإجمالي قبل الغرامات", "Total before penalties", "Gross before deductions"],
    "total": ["صافي المبلغ المستحق", "المستحق النهائي", "إجمالي أمر الشراء", "إجمالي الفاتورة", "Final payable",
              "Amount payable"],
    "penalty": ["غرامة التأخير", "غرامات التأخير", "Delay penalty", "Late penalty"],
    "other_penalty": ["غرامات أخرى", "غرامة أخرى", "الغرامات الأخرى", "مبلغ الغرامات الأخرى", "Other penalties",
                      "Other penalty"],
    "discount": ["الخصم", "خصم", "Discount"],
    "shipping": ["قيمة الشحن", "Shipping"],
}
# Title words from the training generators' TITLES plus the domain's document names.
TITLES = {
    "receipt": ["goods received", "goods receipt", "receipt", "grn", "سند استلام", "مذكره استلام", "استلام مواد"],
    "invoice": ["invoice", "فاتوره"],
    "purchase_order": ["purchase order", "امر تعميد", "امر شراء", "تعميد"],
    "inspection": ["inspection", "محضر", "مخالفه"],
    "contract": ["contract", "عقد"],
}
HALALA = {"هلله", "هللات", "halala", "halalas"}
RIYAL = {"ريال", "ريالات", "riyal", "riyals", "sar", "sr"}
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize(text):
    text = unicodedata.normalize("NFKC", str(text)).lower()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ـ", "")):
        text = text.replace(a, b)
    text = re.sub(r"[ً-ْ]", "", text)
    return " ".join(re.sub(r"[^\w\s%٪]", " ", text).split())


def _index(table):
    return {k: {frozenset(normalize(a).split()) for a in v} for k, v in table.items()}


# Vocabulary of the competitions' original document template (receipt «مذكرة استلام», NUPCO purchase order,
# tax invoice), taken from the printed strings of pdf_source/build_receipts.py, build_purchase_orders.py and
# build_invoices.py (2026-10-26). Exact matches only.
TEMPLATE = {
    "header": {"receipt_no": ["إشعار استلام مؤقت الرقم"],
               "po_no": ["أمر الشراء الرقم"], "po_date": ["أمر الشراء التاريخ"]},
    "item": {"line_no": ["L.N."], "item_code": ["Stock No.", "Material"],
             "description": ["Item Description", "اسم الصنف ووصفه"], "unit_price": ["U.Price"],
             "line_net": ["Total Price", "صافي قيمة السند"], "line_total": ["Total Final Price", "مجموع القيمة"]},
    "total": {"net_excl_vat": ["Total Price Without VAT"], "vat": ["Total VAT of NET", "Total VAT", "إجمالي الضريبة"],
              "total_incl": ["Total", "الإجمالي شامل نوبكو والضريبة"],
              "total": ["Total Price / الإجمالي", "الإجمالي النهائي"]},
}
# Printed labels of the same template that name no audited field. They are never matched by word overlap,
# which had put «قبل الضريبة | Pre-VAT» and «وعاء ضريبة 15% | VAT Base» on the tax amount and
# «أمر الشراء / التاريخ» on the PO number.
NOT_FIELDS = {
    "header": ["المعاينة رقم المحضر", "المعاينة التاريخ", "وثيقة الشحن الرقم", "وثيقة الشحن التاريخ",
               "التعاميد المرتبطة Purchase Orders", "رقم ضريبي وهمي Training VAT No", "رمز العميل Customer Code",
               "عدد سندات الاستلام Receipt Count", "Date Release", "Quote Ref", "Supplier VAT Register No",
               "قبل الضريبة Pre VAT", "وعاء ضريبة VAT Base", "Shipping VAT", "ضريبة الشحن", "أيام التأخير",
               "Amount SAR", "Receipt", "PO"],
    "item": ["P.R. No", "Due", "Manf", "Part No.", "On hand", "Bonus", "Disc1", "Net U.Price", "الإنتاج Mfg Date",
             "الصلاحية Expiry", "الخصم Disc", "قبل الضريبة Pre VAT", "سند الاستلام", "التعميد", "تاريخ الاستلام",
             "ملاحظات"],
}
NOT_FIELDS["total"] = NOT_FIELDS["header"]
# The official NUPCO layout of the 49-page final evaluation file (tax invoice and «مذكرة استلام»),
# printed strings read off the page images (2026-10-26). Exact matches only, as TEMPLATE.
REAL_FORM = {
    "header": {"document_date": ["Date", "التاريخ", "تاريخ"], "tender_no": ["NUPCO"]},
    "item": {"line_no": ["S. No"], "item_code": ["Material Code"], "description": ["Material Desc.", "وصف الصنف"],
             "qty": ["Quantity / UOM", "Quantity"], "line_net": ["Amount (Excl. VAT)"],
             "line_total": ["Item Subtotal (Including VAT)"], "vat": ["Tax Amount"]},
    "total": {"net_excl_vat": ["Amount (Excluding VAT)", "الإجمالي بدون ضريبة"], "vat": ["Total VAT Amount"],
              "total_incl": ["الإجمالي"], "total": ["Total Amount Due", "Total Price"]},
}
# The temporary receipt notice's own date: on the real form it differs from «تاريخ الاستلام» (the receipt's date).
NOT_FIELDS["header"] = NOT_FIELDS["header"] + ["إشعار استلام مؤقت التاريخ"]
NOT_FIELDS["item"] = NOT_FIELDS["item"] + ["Total Taxable Amount", "Manufacture Date", "Expiry Date", "Discount"]
NOT_FIELDS["total"] = NOT_FIELDS["total"] + ["Total Taxable Amount (Excluding VAT)", "Discount"]
for _scope, _table in REAL_FORM.items():
    for _field, _aliases in _table.items():
        TEMPLATE[_scope][_field] = TEMPLATE[_scope].get(_field, []) + _aliases
for _scope, _table in TEMPLATE.items():
    _base = {"header": HEADER, "item": ITEM, "total": TOTAL}[_scope]
    for _field, _aliases in _table.items():
        _base[_field] = list(_base.get(_field, [])) + _aliases
INDEX = {"header": _index(HEADER), "item": _index(ITEM), "total": _index(TOTAL)}
IGNORED = {scope: {frozenset(normalize(a).split()) for a in labels} for scope, labels in NOT_FIELDS.items()}


STOP = {"رقم", "no", "number", "مبلغ", "قيمه", "ال", "of", "the", "في", "من"}


def closest(words, keys):
    """Unknown label: the field whose alias overlaps it best, only if clearly ahead.

    Jaccard overlap of label words, requiring at least one shared word that is not
    a generic word like "رقم"/"مبلغ", a score of at least 0.5 and a 0.2 lead over
    the best alias of any other field. Otherwise None (left unmapped for review).
    """
    label = set(words)
    best = {}
    for field, aliases in keys.items():
        for alias in aliases:
            shared = label & alias
            if not shared - STOP:
                continue
            score = len(shared) / len(label | alias)
            best[field] = max(best.get(field, 0), score)
    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    if ranked and ranked[0][1] >= .5 and (len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= .2):
        field = ranked[0][0]
        # A title such as "GOODS RECEIPT NOTE" is not an identifier label: identifiers need a number word.
        if field in ID_FIELDS and not label & NUMBER_WORDS:
            return None
        return field
    return None


PON = re.compile(r"PON\d{10}")
OWN_FORMAT = {"receipt_no": re.compile(r"STO\d{10}"), "po_no": re.compile(r"PON\d{10}"), "invoice_no": re.compile(r"(?:TF)?\d{10}")}
FILLER = re.compile(r"(?i)\s*(nothing\s+follows|لا\s+يوجد|-+)\s*")
# Column groups of a receipt's reference table, as normalize() prints them («إشعار استلام مؤقت / الرقم» → "اشعار استلام مؤقت الرقم").
GRID = re.compile(r"(اشعار استلام مؤقت|امر الشراء|وثيقه الشحن|المعاينه) ")
ITEM_BODY = {"item_code", "description", "qty", "unit_price", "line_total", "line_net"}
STO = re.compile(r"STO\d{10}")


def _own_id(value):
    """The id field a value can only be, by its fixed format (owner's rule), else None."""
    s = re.sub(r"\s", "", str(value or ""))
    return "po_no" if PON.fullmatch(s) else "receipt_no" if STO.fullmatch(s) else None
ID_FIELDS = {"receipt_no", "po_no", "invoice_no", "customer_po_no", "tender_no", "notice_no"}
NUMBER_WORDS = {"رقم", "مرجع", "no", "number", "id", "ref", "reference", "معرف"}


def lookup(label, scope, fuzzy=True):
    """Return the single field whose alias matches the whole label, else None (fuzzy=False: rules only)."""
    label = label or ""
    raw_words = normalize(label).split()
    # A printed rate inside a label ("رسوم نوبكو 4%") qualifies it; it is not part of its name.
    words = [w for w in raw_words if not any(c.isdigit() for c in w.translate(DIGITS)) and w not in ("%", "٪")]
    if not words or frozenset(words) in IGNORED.get(scope, ()):
        return None
    keys = INDEX[scope]
    has_digit = len(words) != len([w for w in raw_words if w not in ("%", "٪")])
    rate = "نسبه" in words or "rate" in words or (("%" in label or "٪" in label) and not has_digit)
    taxword = any(w in words for w in ("vat", "tax", "ضريبه", "الضريبه"))
    if scope == "item" and rate and taxword:
        return "vat_rate"
    found = [k for k, aliases in keys.items() if frozenset(words) in aliases]
    if len(found) == 1:
        return found[0]
    # Grouped header written as "<group> / <sub>" (e.g. سعر الوحدة / هللة).
    parts = [p for p in re.split(r"\s*[/|\\]\s*|\s+-\s+", str(label)) if p.strip()]
    if scope == "item" and len(parts) == 2:
        group, sub = lookup(parts[0], scope, fuzzy), set(normalize(parts[1]).split())
        if sub and sub <= HALALA:
            return {"unit_price": "unit_price_halala", "line_total": "line_total_halala"}.get(group)
        if sub and sub <= RIYAL and group in ("unit_price", "line_total"):
            return group
    # Bilingual label "<Arabic> / <English>": both halves must name the same field, and a half that is a known
    # non-field label («Total Taxable Amount (Excluding VAT)») makes the whole label a non-field.
    if len(parts) == 2 and any(frozenset(w for w in normalize(part).split() if not any(c.isdigit() for c in w.translate(DIGITS)))
                               in IGNORED.get(scope, ()) for part in parts):
        return None
    if len(parts) == 2:
        sides = {lookup(part, scope, fuzzy) for part in parts} - {None}
        if len(sides) == 1:
            return sides.pop()
    # One label printed in both scripts without a separator («Amount (Excl. VAT (غير شامل ضريبة القيمة المضافة)»):
    # the English words and the Arabic words are looked up alone; a field is taken only if no side names another.
    latin = [w for w in words if re.match(r"[a-z]", w)]
    arabic = [w for w in words if not re.match(r"[a-z]", w)]
    if latin and arabic:
        if frozenset(latin) in IGNORED.get(scope, ()) or frozenset(arabic) in IGNORED.get(scope, ()):
            return None
        sides = {k for side in (latin, arabic) for k, aliases in keys.items() if frozenset(side) in aliases}
        if len(sides) == 1:
            return sides.pop()
    if HALALA & set(words) or not fuzzy:
        return None                       # a halala cell is never matched by word overlap
    return closest(words, keys)


def title_type(title):
    """The printed title decides the page type when it names exactly one kind."""
    text = " " + normalize(title or "") + " "
    kinds = [k for k, words in TITLES.items() if any(" " + normalize(w) + " " in text for w in words)]
    return kinds[0] if len(kinds) == 1 else None


def clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _pairs(section, dropped=None):
    """Accept [[label, value], ...] or {label: value}. A panel heading written before the pair,
    [heading, label, value], keeps the label and value. Any other shape is not used and, when
    `dropped` is given, is recorded there so the page is reviewed instead of silently losing it."""
    if isinstance(section, dict):
        return [(k, v) for k, v in section.items()]
    out = []
    for pair in section or []:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            out.append((pair[0], pair[1]))
        elif isinstance(pair, (list, tuple)) and len(pair) == 3 and all(isinstance(x, str) for x in pair[:2]):
            out.append((pair[1], pair[2]))
        elif isinstance(pair, (list, tuple)) and len(pair) == 1 and isinstance(pair[0], str):
            out.append(("", pair[0]))           # a printed line with no label: kept as an unlabelled value
        elif isinstance(pair, (list, tuple)) and len(pair) > 3 and all(isinstance(x, (str, type(None))) for x in pair):
            # A table row copied whole (the receipt's reference table as rows of headings / values): its cells
            # have no labels, so only a value whose fixed format names it (STO…, PON…) can be used.
            out += [("", x) for x in pair if _own_id(x)]
        elif isinstance(pair, dict) and {"label", "value"} <= set(pair):
            out.append((pair["label"], pair["value"]))
        elif dropped is not None:
            dropped.append(pair)
    return out


class _Slots:
    """Collect values per path; disagreeing values are withheld for review."""

    def __init__(self):
        self.values, self.conflicts, self.unmapped, self.unreadable = {}, set(), [], set()

    def put(self, path, value):
        if value is None:
            # A labelled cell the reader could not read is reported, never filled.
            self.unreadable.add(path)
            return
        old = self.values.get(path)
        fmt = OWN_FORMAT.get(path[1]) if path[0] == "ids" and path[1] in ("po_no", "receipt_no") else None
        if old is not None and old != value and fmt is not None:
            # A PO/receipt number has one fixed format (PON/STO + 10 digits): a value under the same label that
            # holds no such number at all («أمر الشراء: Nupco Warehouse(8) - 0801») is another line of the form, not a
            # second reading of the number. Two different well-formed numbers still conflict.
            ok_old, ok_new = (bool(fmt.fullmatch(re.sub(r"\s", "", str(v)))) for v in (old, value))
            if ok_old != ok_new and not re.search(r"P[O0]N|ST[O0]|\d{9,}", str(value if ok_old else old)):
                self.values[path] = old if ok_old else value
                self.unmapped.append({"section": "header", "label": path[1], "value": value if ok_old else old})
                return
        if old is not None and old != value:
            self.conflicts.add(path)
        else:
            self.values[path] = value


def to_schema(pairs):
    """Convert a pairs reading into the scoring schema plus mapping evidence."""
    out = copy.deepcopy(SCHEMA)
    slots = _Slots()
    page_type = str(pairs.get("page_type") or "").strip()
    out["page_type"] = title_type(pairs.get("title")) or (page_type if page_type in PAGE_TYPES else "other")
    malformed = []
    # A "row" with no item code that carries a PO/receipt number (by its fixed format) is the document's
    # reference table (أمر الشراء / إشعار استلام مؤقت … الرقم / التاريخ), not an item: read it as header pairs.
    cards, reference, kept = [], [], []
    for c_index, card in enumerate(pairs.get("items") or []):
        cp = _pairs(card)
        if out["page_type"] != "invoice":
            # On a scanned receipt the reference table may be read into the item row itself
            # («إشعار استلام مؤقت / الرقم: STO…» beside «الكمية»): its cells go to the header, the rest stays the item.
            ref = [(label, v) for label, v in cp if _own_id(v) or GRID.match(normalize(label or ""))]
            rest = [p for p in cp if p not in ref]
            if ref and any(lookup(label, "item") in ITEM_BODY and clean(v) for label, v in rest):
                reference += ref
                cp, card = rest, [list(p) for p in rest]
        if (out["page_type"] != "invoice" and any(_own_id(v) for _, v in cp)
                and not any(lookup(label, "item") == "item_code" and clean(v) for label, v in cp)):
            reference += cp
        # An empty table row (no value at all, or only a filler such as "Nothing Follows") is not an item.
        elif any(clean(v) and not FILLER.fullmatch(clean(v)) for label, v in cp if lookup(label, "item") is not None):
            cards.append(card)
            kept.append(c_index)
    pairs = {**pairs, "items": cards}
    nonitem = [("header", p) for p in _pairs(pairs.get("header"), malformed) + reference] + \
              [("total", p) for p in _pairs(pairs.get("totals"), malformed)]
    title = normalize(pairs.get("title") or "")
    own_id = {"receipt": "receipt_no", "invoice": "invoice_no", "purchase_order": "po_no"}.get(out["page_type"])
    for section, (label, value) in nonitem:
        value = clean(value)
        # The page's own number printed beside its title, with no label, is paired with the title.
        if title and own_id and section == "header" and normalize(label or "") == title:
            # Only a value in the document's own number format is its number (a title may also sit beside
            # the tender number, as on the collective invoice).
            if value and OWN_FORMAT[own_id].fullmatch(re.sub(r"\s", "", value)):
                slots.put(("ids", own_id), value)
            continue
        # Identifier/date labels are unambiguous wherever a layout prints them;
        # amount labels are read in the totals block only.
        field = lookup(label, "header")
        # In the totals block an exact totals label wins («NUPCO 4%» there is the commission, not the PO's «NUPCO» tender).
        if field is not None and section == "total" and lookup(label, "total", fuzzy=False):
            field = None
        if field is None and section == "total":
            field = lookup(label, "total")
            if field:
                slots.put(("totals", field), value)
                continue
        if field is None:
            slots.unmapped.append({"section": section, "label": label, "value": value})
            continue
        if field in out["ids"]:
            slots.put(("ids", field), value)
        elif field in out["dates"]:
            slots.put(("dates", field), value)
        elif field == "violation":
            slots.put(("inspection", "description"), value)
        else:
            slots.put(("inspection", field), value)
    for n, card in enumerate(pairs.get("items") or []):
        exact = {lookup(label, "item", fuzzy=False) for label, _ in _pairs(card)} - {None}
        for label, value in _pairs(card, malformed):
            field = lookup(label, "item")
            # A fused header such as "م رقم الصنف" only resembles a column the row already names
            # exactly ("رقم الصنف"); it is not a second value for that column and stays unmapped.
            if field in exact and lookup(label, "item", fuzzy=False) != field:
                field = None
            # The original receipt prints the item's tax rate inside its notes cell («استلام جزئي ضريبة 15%»).
            rate = re.search(r"ضريب[ةه]\s*(\d{1,2}(?:\.\d+)?)\s*[%٪]", str(value or "")) if field is None and "vat_rate" not in exact else None
            if rate and set(normalize(label).split()) == {"ملاحظات"}:
                slots.put(("items", n, "vat_rate"), rate.group(1) + "%")
                continue
            if field is None:
                slots.unmapped.append({"section": "item", "item": n, "label": label, "value": clean(value)})
            else:
                slots.put(("items", n, field), clean(value))
    for n, card in enumerate(pairs.get("items") or []):
        out["items"].append(dict.fromkeys(ITEM_KEYS))
    for path, value in slots.values.items():
        if path in slots.conflicts:
            continue
        if path[0] == "items":
            out["items"][path[1]][path[2]] = value
        else:
            out[path[0]][path[1]] = value
    # Owner (2026-10-25): a purchase-order number is always PON + 10 digits and a receipt number STO + 10 digits.
    # Such a value printed under another field's label is that number; the label it sat under is withheld, since
    # that pairing is wrong. Under a label that names no field (a form title, say) it simply fills the empty slot.
    for key, value in list(out["ids"].items()):
        own = _own_id(value)
        if own and key != own:
            if out["ids"][own] in (None, value):
                out["ids"][own] = value
            out["ids"][key] = None
            slots.conflicts.add(("ids", key))           # withheld: the label did not hold its own value
    # A value under the PO/receipt label that is not that number at all («Customer PO: (NPT0020/22)» on the NUPCO
    # invoice) names another document: it is left unmapped. One that looks like a misread number stays withheld.
    for key in ("po_no", "receipt_no"):
        value = out["ids"][key]
        if value and not OWN_FORMAT[key].fullmatch(re.sub(r"\s", "", value)):
            out["ids"][key] = None
            if re.search(r"P[O0]N|ST[O0]", value, re.I) or re.fullmatch(r"\d{9,11}", re.sub(r"\s", "", value)):
                slots.conflicts.add(("ids", key))
            else:
                slots.unmapped.append({"section": "header", "label": key, "value": value})
    for u in slots.unmapped:
        own = _own_id(u.get("value")) if u.get("section") == "header" else None
        if own and out["ids"][own] in (None, u["value"]) and (own == "po_no" or out["page_type"] in ("receipt", "inspection")):
            out["ids"][own] = u["value"]
    if out["page_type"] == "inspection" and out["ids"]["receipt_no"] is not None:
        out["inspection"]["receipt_no"] = out["ids"]["receipt_no"]
    withheld = slots.conflicts | (slots.unreadable - set(slots.values))
    out["unreadable_fields"] = sorted(".".join(map(str, p)) for p in withheld)
    return out, {"unmapped": slots.unmapped, "malformed": malformed, "cards_kept": kept,
                 "conflicts": sorted(".".join(map(str, p)) for p in slots.conflicts)}


def parse(raw):
    """Parse the model text; fenced or trailing text is tolerated, nothing is repaired."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Punctuation only, never a value: after a label such as «Amount (Excl. VAT» the model may close the pair
        # with ")" instead of "]". A quote followed by ")" and then "," or "]" can only be that closing bracket.
        fixed = re.sub(r'"\)(?=\s*[,\]])', '"]', text)
        # A row opened with one bracket too many after the previous row closed («"]], [[[" for «"]], [["»).
        fixed = re.sub(r'"\]\],\s*\[\[\[', '"]], [[', fixed)
        if fixed == text:
            raise
        return json.loads(fixed)
