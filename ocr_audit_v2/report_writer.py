"""كاتب تقارير Excel: يملأ **قالب الدفعة المعتمد حرفياً** (لا عمود ولا شيت ولا مصطلح جديد).

يحمّل القالب المرجعي نفسه بتنسيقه، وينسخ تنسيق صف البيانات الأول، ويعيد توليد صيغه (مع تحديث النطاقات)، ويملأ القيم من:
extract.py (الاستخراج) + engine.py (المحرك) + invoice_match.py (الفاتورة كمبرر مؤيد). ثم يمر على
report_template.assert_matches_template قبل الحفظ. لا يلمس أي تقرير قديم، ويكتب في المسار الذي يُعطاه فقط.

الناتج: (مسار الملف، قائمة غير المحسوم). إن كانت القائمة غير فارغة فالتقرير مسودة تقنية لا يُسلَّم (انظر jobs/pipeline).
"""
from __future__ import annotations

import copy
import datetime as dt
import os
import re
from collections import defaultdict
from decimal import Decimal

import openpyxl

import engine
import extract
import invoice_match as IM
import pdfx
import report_style as RS
import report_template as T
from document_order import batch_receipt_ids

D = Decimal
SEP = "، "


# ------------------------------------------------------------------ أدوات
def _d(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return None


def _f(x):
    return float(x) if x is not None else None


def _qty(q: Decimal):
    return int(q) if q == q.to_integral() else float(q)


def _runs(pages):
    pages = sorted(set(pages))
    out, cur = [], []
    for p in pages:
        if cur and p != cur[-1] + 1:
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def _pick_after(groups, ref_page):
    """المجموعة (نسخة) التي تلي صفحة السند مباشرة؛ وإلا آخر ما قبله."""
    after = [g for g in groups if min(g) > ref_page]
    if after:
        return min(after, key=lambda g: min(g))
    return groups[-1] if groups else []


def _pick_before(groups, ref_page):
    """المجموعة التي تسبق صفحة السند مباشرة (التعميد يسبق سنداته)؛ وإلا الأولى."""
    before = [g for g in groups if max(g) < ref_page]
    if before:
        return max(before, key=lambda g: max(g))
    return groups[0] if groups else []


def _same_row(inv, inv_row, copy_id):
    """صف الفاتورة المقابل لصف الإسناد في نسخة الفاتورة copy_id. نسخ الفاتورة مطبوعات متطابقة، فإن تكرر (الصنف، الكمية، السعر)
    في الفاتورة نفسها يُختار الصف بترتيب ظهوره داخل نسخته لا أول صف مطابق؛ فتكون الصفحة هي صفحة السطر المنسوب فعلاً."""
    tol = D("0.005")
    sig = lambda x: x.code == inv_row["code"] and x.qty == inv_row["qty"] and abs(x.unit_price - inv_row["price"]) <= tol
    src = [x for x in inv.items if x.copy == inv_row.get("copy", copy_id) and sig(x)]
    dst = [x for x in inv.items if x.copy == copy_id and sig(x)]
    if not dst:
        return None
    idx = next((k for k, x in enumerate(src) if x.ev.page == inv_row.get("page")), 0)
    return dst[idx] if idx < len(dst) else dst[0]


def review_item(num, rv, mode="batch", n_bundles=None):
    """بند مراجعة من مطابقة الفاتورة بمفاتيح الدليل التي تقرؤها واجهة المراجعة (file/page).
    قاعدة المالك (16 أكتوبر 2026):
      - فحص الدفعة: الفاتورة **مبرر** يكفي أن ترد فيه بنود سندات الدفعة؛ بنودها الأخرى (لسندات في ربطات أخرى) لا تهمّ
        فلا يُسجَّل لها بند مراجعة ولا تُنسب لسندات الدفعة ولا يدخل مبلغها فيها (يرجع None).
      - فحص المنافسة: يجب أن تُطابَق الفاتورة بسند أو عدة سندات كاملة؛ «بلا سند» لا يُسجَّل إلا بعد البحث في كل الربطات المرفوعة."""
    it = {"invoice": num, **rv}
    it.setdefault("file", rv.get("invoice_file"))
    it.setdefault("page", rv.get("invoice_page"))
    if rv.get("invoice_code"):
        it["page"] = rv.get("receipt_page") or it.get("page")
        it["why"] = (f"رمز الصنف في السند {rv.get('code')} (ص{rv.get('receipt_page')}) وفي الفاتورة {num} {rv['invoice_code']} "
                     f"(ص{rv.get('invoice_page')})؛ "
                     + (f"الكمية {rv.get('qty')} موزعة في الفاتورة على {len(rv['invoice_split'])} أسطر ({' + '.join(rv['invoice_split'])}) بالسعر {rv.get('price')}. "
                        if rv.get("invoice_split") else f"الكمية {rv.get('qty')} والسعر {rv.get('price')} متطابقان. ") +
                     "لا يُربط الرمزان آلياً: «سليم» إن كانا للصنف نفسه.")
    if rv.get("reason") != "بند في الفاتورة بلا سند يذكرها":
        return it
    if mode != "competition":
        return None
    cands = rv.get("candidate_stos_not_citing_invoice") or []
    line = f"صف الفاتورة {num} (ص{it.get('page')}) للصنف {rv.get('code')} بكمية {rv.get('qty')}"
    it["why"] = (line + f": بُحث في جميع الربطات المرفوعة{f' ({n_bundles})' if n_bundles else ''} ولم يُعثر على سند مطابق يذكر هذه الفاتورة."
                 + (f" سندات مرشحة لا تذكرها: {'، '.join(cands)}." if cands else ""))
    return it


def related_pages(b, sto=None, invoice=None, page=None):
    """صفحات المعاملة الكاملة لبند مراجعة. قاعدة المالك: لا يُستعرض مستند وحده إن كان له مقابل؛ ملاحظة على السند تُعرض مع فاتورته وتعميده،
    وملاحظة على الفاتورة تُعرض مع سندات الاستلام المرتبطة بها، ولا يُعرض أحدهما وحده إلا إن كان غياب المقابل هو المشكلة."""
    out = []
    rec = next((r for r in b.receipts if r.sto == sto), None) if sto else None
    inv_no = invoice or (rec.invoice_no if rec else None)
    inv = next((v for v in b.invoices if v.number == inv_no), None) if inv_no else None
    if rec:
        out.append({"label": "سند الاستلام", "file": b.file, "pages": sorted(rec.pages)})
    if inv and not rec:
        # بند في الفاتورة: تُعرض معه سندات الاستلام المرتبطة بها (التي تذكر رقمها)؛ تُعرض الفاتورة وحدها فقط إن لم يوجد سند مرتبط (وهو المشكلة نفسها)
        for r in b.receipts:
            if r.invoice_no == inv_no:
                out.append({"label": f"سند الاستلام {r.sto}", "file": b.file, "pages": sorted(r.pages)})
    if inv:
        groups = [sorted(v) for v in inv.copy_pages.values()]
        grp = None
        if rec and rec.pages:
            grp = _pick_after(groups, min(rec.pages))
        elif page:
            grp = next((g for g in groups if int(page) in g), None)
        out.append({"label": "الفاتورة", "file": b.file, "pages": grp or sorted(inv.pages)})
    po = next((x for x in b.pos if rec and x.number == rec.pon), None)
    if po:
        runs = _runs(po.pages)
        out.append({"label": "التعميد", "file": b.file, "pages": runs[0] if runs else sorted(po.pages)})
    return out


def _adapt(formula: str, row: int, last_items: int, last_main: int) -> str:
    """صيغة صف القالب الأول -> صيغة الصف row: المراجع النسبية للصف 6 تتبع الصف، والنطاقات المطلقة تمتد لآخر صف."""
    f = re.sub(r"(?<![$A-Z])([A-Z]{1,2})6(?!\d)", lambda m: f"{m.group(1)}{row}", formula)
    f = re.sub(r"\$(\d+)\b", lambda m: f"${last_items}" if int(m.group(1)) > 6 else m.group(0), f)
    return f


def _clone_row_style(ws, tpl_row: int, row: int, ncols: int, height):
    for c in range(1, ncols + 1):
        src, dst = ws.cell(tpl_row, c), ws.cell(row, c)
        dst._style = copy.copy(src._style)
    if height:
        ws.row_dimensions[row].height = height


def _reason_text(res: engine.Result) -> str:
    return "؛ ".join(i.text for i in res.issues) if res.issues else None


READ_CONFLICT = {"ocr": "قراءة OCR: تعارض بين المطبوع والمحسوب (قد يكون خطأ قراءة) يلزم مراجعة الصفحة",
                 "vlm": "قراءة آلية: تعارض بين المطبوع والمحسوب أو بند لم يُقرأ كاملاً؛ يلزم مراجعة الصفحة"}


def _ocr_review(b, res_by, unresolved):
    """ربطة ممسوحة (OCR): كل سند فيه تعارض حسابي يُحال ولا يُحكم عليه «غير سليم» (سبب التعارض لا يثبت بالحساب وحده)،
    وبند واحد للربطة يطلب الاعتماد البشري. يعيد {sto: مفتاح البند}."""
    from job_pipeline import item_key
    out = {}
    src = getattr(b, "source", "text")
    if src not in ("ocr", "vlm"):
        return out
    skipped = getattr(b, "reread_skipped", 0)
    unresolved.append({"reason": ("الربطة ممسوحة وقُرئت بنموذج رؤية" if src == "vlm" else "الربطة ممسوحة وقُرئت بـOCR") +
                       ": القيم غير موثّقة بشرياً (التحقق الحسابي وحده لا يكفي قبل نتائج القبول)"
                       + (f"؛ واشتُبه في {skipped} صفحة فلم تُكرَّر قراءتها (بلغت الصفحات حد إعادة القراءة الآلية)" if skipped else ""), "file": b.file, "page": 1})
    for n, iss in sorted(getattr(b, "agree_issues", {}).items()):                  # صفحات لم يتفق عليها قارئان مستقلان
        u = {"reason": "قراءة آلية غير محسومة: يلزم التحقق من القيم وعناوينها في الصفحة", "file": b.file, "page": n, "why": iss["why"]}
        unresolved.append(u)
        pty = b.page_types.get(n)
        held = ([r.sto for r in b.receipts if n in r.pages] if pty == "receipt" else
                [r.sto for r in b.receipts if any(n in x.pages and x.number == r.pon for x in b.pos)] if pty == "po" else
                [r.sto for r in b.receipts if any(n in x.pages and x.number == r.invoice_no for x in b.invoices)] if pty == "invoice" else [])
        for sto in held:
            out.setdefault(sto, item_key(u))
    for v in b.invoices:
        for fl in getattr(v, "flags", []):
            u = {"reason": "إجمالي بند في الفاتورة %s لا يساوي الصافي+العمولة+الضريبة (مقروء %s، المتوقع %s)؛ قراءة آلية غير موثقة؛ المطبوع محفوظ منفصلاً عن المحسوب" % (v.number, fl["seen"], fl["expected"]),
                 "invoice": v.number, "code": fl["code"], "file": b.file, "page": fl["page"]}
            unresolved.append(u)
            for r in b.receipts:
                if r.invoice_no == v.number:
                    out.setdefault(r.sto, item_key(u))
    for r in b.receipts:
        res = res_by.get(r.sto)
        for fl in getattr(r, "flags", []):
            u = {"reason": "إجمالي سطر غير مقروء كاملاً: ظهر جزء الريال فقط (%s) وغاب جزء الهللة في القراءة الآلية؛ لا خطأ حسابي منسوب للسند" % fl["seen"],
                 "sto": r.sto, "code": fl["code"], "file": b.file, "page": fl["page"]}
            unresolved.append(u)
            out.setdefault(r.sto, item_key(u))
        if res is not None and res.issues:
            u = {"reason": READ_CONFLICT[src], "sto": r.sto,
                 "file": b.file, "page": r.pages[0] if r.pages else None, "why": "تعارض يحتاج فحص المطبوع؛ لا يُرجّح خطأ القراءة أو المستند من الحساب وحده: " + "؛ ".join(i.text for i in res.issues if i.code != "no_invoice")[:300]}
            unresolved.append(u)
            out[r.sto] = item_key(u)
    return out


# ------------------------------------------------------------------ تجميع بيانات الدفعة
def _read_cached(bundle_path: str, cache_dir: str | None):
    """قراءة الربطة مرة واحدة لكل مهمة: إعادة بناء التقرير بعد المراجعة تستعمل القراءة المحفوظة ولا تعيد OCR/النموذج."""
    if not cache_dir:
        return extract.read_bundle(bundle_path)
    import hashlib, pickle
    base = hashlib.sha256(open(bundle_path, "rb").read()).hexdigest()[:20]
    h = base + ("-vlm" if os.environ.get("VLM_URL") else "")
    p = os.path.join(cache_dir, f"bundle-{h}-evidence-v1.pkl")
    # A rebuild after review keeps the model's saved reading even when the model is off now: falling back to OCR
    # would re-read the bundle differently and replace the reviewed items.
    for q in (p,) if os.environ.get("VLM_URL") else (os.path.join(cache_dir, f"bundle-{base}-vlm-evidence-v1.pkl"), p):
        if os.path.exists(q):
            try:
                with open(q, "rb") as f:
                    return pickle.load(f)
            except Exception:  # noqa: BLE001
                pass
    b = extract.read_bundle(bundle_path)
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(p, "wb") as f:
            pickle.dump(b, f)
    except Exception:  # noqa: BLE001
        pass
    return b


def _tender_key(t):
    r"""Tender numbers come in many forms (MED-2026-339, NPT2323\23 …). They are compared without spaces and with
    / \ - _ as one separator, because a file name cannot hold / or \ (NPT2323\23 is saved as NPT2323-23)."""
    return re.sub(r"\s+", "", re.sub(r"[\\/\-_]+", "/", str(t))).upper()


# A tender number inside a printed value: «NUPCO : (NPT0020/22)», «REF : NUPCO : MED-2026-327».
TENDER_TOKEN = re.compile(r"[A-Z]{2,}[A-Z0-9]*(?:[-/\\][A-Z0-9]+)+", re.I)


def clean_tender(value):
    """The tender number inside a printed value («NUPCO : (NPT0020/22)» → «NPT0020/22»); the value itself otherwise."""
    m = TENDER_TOKEN.search(re.sub(r"\s*([-/\\])\s*", r"\1", str(value or "")))
    return m.group(0).upper() if m else (str(value).strip() or None)


def bundle_tenders(b, bundle_path=None):
    """[(page, printed tender)] of every document that prints one. A scanned bundle has them from the model reading;
    a text bundle from its purchase-order pages (extract.parse_po_pages)."""
    pages = list(getattr(b, "tender_pages", []) or [])
    if not pages:
        pages = [x for po in b.pos for x in po.__dict__.get("tender_pages", [])]
    return sorted(set(pages))


def first_po_tender(b, pages):
    """Owner's rule (2026-10-26): the competition of a bundle is the tender printed on its first purchase order,
    never the file name. None when no purchase order prints one."""
    po_pages = [(n, v) for n, v in pages if b.page_types.get(n) == "po"]
    return clean_tender(po_pages[0][1]) if po_pages else None


def tender_issues(b, comp_no=None, pages=None):
    """Every document whose printed tender number differs from the bundle's competition (the tender of its first
    purchase order; without one, the number most documents print) is held for review with its page."""
    from collections import Counter
    pages = pages if pages is not None else getattr(b, "tender_pages", [])
    if not pages:
        return []
    counts = Counter(_tender_key(v) for _, v in pages)
    if comp_no:
        ref, shown = _tender_key(comp_no), comp_no
    else:
        ref, n = counts.most_common(1)[0]
        shown = next(v for _, v in pages if _tender_key(v) == ref)
        if n * 2 <= len(pages):
            ref = None                                               # no clear majority: every page is checked by a person
    out = []
    for n, v in pages:
        # Equal, or printed whole inside a longer value such as «NUPCO : MED-2026-327».
        if ref is not None and (_tender_key(v) == ref or re.search(r"(?<![A-Z0-9])" + re.escape(ref) + r"(?![A-Z0-9])", _tender_key(v))):
            continue
        pty = b.page_types.get(n)
        holds = ([r.sto for r in b.receipts if n in r.pages] if pty == "receipt" else
                 [r.sto for r in b.receipts if any(n in x.pages and x.number == r.pon for x in b.pos)] if pty == "po" else
                 [r.sto for r in b.receipts if any(n in x.pages and x.number == r.invoice_no for x in b.invoices)] if pty == "invoice" else [])
        why = f"رقم المنافسة المطبوع «{v}» يخالف رقم المنافسة «{shown}»" if ref is not None else f"رقم المنافسة المطبوع «{v}» غير محسوم بين مستندات الربطة"
        out.append({"reason": "تعارض هوية المنافسة: " + why, "file": b.file, "page": n, "why": why, "_holds": holds})
    return out


def collect_batch(bundle_path: str, contract_path: str, code_map=None, context_paths=None, cache_dir=None):
    """context_paths: ربطات مجاورة من المنافسة نفسها تُقرأ لمطابقة الفواتير المشتركة فقط (سنداتها لا تدخل صفوف التقرير)."""
    code_map = code_map or {}
    m = re.match(r"(.+)-(\d{2})-\d{3}\.pdf$", os.path.basename(bundle_path))     # رقم المنافسة-رقم الدفعة-رقم الربطة.pdf
    b = _read_cached(bundle_path, cache_dir)
    # The competition is the tender printed on the first purchase order (owner, 2026-10-26); the file name is only a
    # fallback when no order prints one (its batch/bundle numbers still fill those two columns).
    tpages = bundle_tenders(b, bundle_path)
    comp_no = first_po_tender(b, tpages) or (m.group(1) if m else os.path.splitext(os.path.basename(bundle_path))[0])
    rules = engine.read_rules(contract_path, comp_no)           # contract_path=None: فحص دفعة بلا عقد (انظر Rules.no_contract)
    results = engine.check_bundle(b, rules)
    rules = getattr(b, "inferred_rules", rules)                 # بلا عقد: القاعدة المستنتجة من الربطة (عمولة وأساس ضريبة)
    engine.apply_cumulative_cap(results, rules)
    # نسخة مكررة لسند داخل الربطة: تُحال صراحةً بالصفحتين، ويبقى صف التقرير للنسخة الأولى (الثانية لا تُحسب مرتين)
    dup_items = []
    first_seen = {}
    for r in b.receipts:
        if r.sto in first_seen:
            dup_items.append({"reason": "سند استلام مكرر داخل الربطة: يحتمل ازدواج السداد ويلزم مراجعته", "sto": r.sto, "file": b.file,
                              "page": first_seen[r.sto].pages[0] if first_seen[r.sto].pages else None, "dup_file": b.file,
                              "dup_page": r.pages[0] if r.pages else None,
                              "why": f"السند {r.sto} ورد في الصفحات {first_seen[r.sto].pages} ثم في الصفحات {r.pages} من الملف نفسه"})
        else:
            first_seen[r.sto] = r
    res_by, rec_by = {}, {}
    for r in results:
        res_by.setdefault(r.sto, r)
    for r in b.receipts:
        rec_by.setdefault(r.sto, r)
    pos = {p.number: p for p in b.pos}
    invs = {}
    for v in b.invoices:
        invs[v.number] = v
    # مطابقة الفاتورة: كل السندات التي تذكر الرقم داخل هذه الدفعة ببنود الفاتورة (نسخها بالترقيم المطبوع)
    unresolved = list(dup_items)
    attribution = {}
    ctx_receipts = []                                       # سندات الربطات المجاورة: تُسند لها بنود الفاتورة المشتركة ولا تُكتب في التقرير
    for cp in (context_paths or []):
        cb = extract.read_bundle(cp)
        ctx_receipts += [(r, cb.file) for r in cb.receipts]
    ctx_stos = {r.sto for r, _ in ctx_receipts}
    for num, inv in invs.items():
        cit = [r for r in b.receipts if r.invoice_no == num and first_seen.get(r.sto) is r]     # النسخة المكررة لا تدخل المطابقة
        cit_ctx = [(r, f) for r, f in ctx_receipts if r.invoice_no == num and r.sto not in {x.sto for x in cit}]
        if getattr(inv, "collective", False) and not inv.items:
            for r in cit:                                         # فاتورة جماعية: السند منسوب لها بسطره (صافيه) إن ورد فيها
                a = inv.allocations.get(r.sto)
                attribution[r.sto] = ({"clear": True, "amount": str(a), "why": None, "pairs": []} if a is not None else
                                      {"clear": False, "amount": None, "pairs": [],
                                       "why": "السند غير مذكور في الفاتورة الجماعية %s رغم أنه يذكر رقمها" % num})
            continue
        by_copy = defaultdict(list)
        for it in inv.items:
            by_copy[it.copy].append({"code": it.code, "qty": it.qty, "price": it.unit_price, "amount": it.total,
                                     "net": it.net, "nupco": it.nupco, "vat": it.vat, "page": it.ev.page, "copy": it.copy,
                                     "file": b.file, "sto": it.sto or None})        # رقم السند المطبوع على صف الفاتورة إن وُجد
        out = IM.match_invoice(
            [{"sto": r.sto, "invoice_no": num, "lines": [{"code": i.code, "qty": i.qty, "price": i.unit_price, "page": i.ev.page, "file": b.file}
                                                          for i in r.items]} for r in cit]
            + [{"sto": r.sto, "invoice_no": num, "lines": [{"code": i.code, "qty": i.qty, "price": i.unit_price, "page": i.ev.page, "file": f}
                                                            for i in r.items]} for r, f in cit_ctx],
            {"number": num, "copies": list(by_copy.values())}, code_map=code_map)
        for sto, v in out["receipts"].items():
            attribution[sto] = v
        for rv in out["review"]:
            item = review_item(num, rv)
            if item is not None:                                   # بنود فاتورة سندات الربطات الأخرى لا تُذكر في فحص الدفعة
                unresolved.append(item)
    missing_inv = []                                                 # سندات بلا فاتورة في الربطة: محجوزة للمراجعة، لا «سليم»
    for r in b.receipts:
        if first_seen.get(r.sto) is not r:
            continue                                                 # النسخة المكررة محالة ببندها الخاص
        if r.invoice_no not in invs:
            listed = [n for n, v in invs.items() if getattr(v, "collective", False)]
            holder = [n for n in listed if r.sto in invs[n].allocations]
            why = (("السند مدرج في الفاتورة الجماعية %s لكنه يذكر رقماً آخر للفاتورة" % "، ".join(holder)) if holder else
                   ("لا يرد السند كذلك في الفاتورة الجماعية للدفعة %s" % "، ".join(listed)) if listed else None)
            u = {"reason": "السند يذكر فاتورة غير موجودة في الربطة", "sto": r.sto, "invoice": r.invoice_no,
                 "file": b.file, "page": r.pages[0] if r.pages else None, "why": why}
            unresolved.append(u)
            missing_inv.append(u)
        elif not attribution.get(r.sto, {}).get("clear") and not any(u.get("sto") == r.sto and u.get("code") for u in unresolved)                 and not r.__dict__.get("incomplete_rows"):           # an unread row is referred once, as such (engine: items_unread)
            # (a receipt line already referred by the invoice matching with its own reason is not referred twice)
            unresolved.append({"reason": "بنود السند لم تُنسب للفاتورة بوضوح", "sto": r.sto, "invoice": r.invoice_no,
                               "file": b.file, "page": r.pages[0] if r.pages else None,
                               "why": attribution.get(r.sto, {}).get("why")})
    review_stos = _ocr_review(b, res_by, unresolved)
    if missing_inv:
        from job_pipeline import item_key
        for u in missing_inv:
            if not res_by.get(u["sto"]) or res_by[u["sto"]].ok:          # سند غير سليم بسبب مستقل يبقى حكمه، والبند يوضح الفاتورة
                review_stos.setdefault(u["sto"], item_key(u))
    for u in tender_issues(b, first_po_tender(b, tpages), tpages):  # هوية المنافسة في كل مستند مقابل أول أمر شراء
        from job_pipeline import item_key
        unresolved.append(u)
        for sto in u.pop("_holds"):
            review_stos.setdefault(sto, item_key(u))
    absent = {}                                                      # سندات تعاميدها غير موجودة في الربطة
    for r in b.receipts:
        res = res_by.get(r.sto)
        if res is not None and res.po_absent and first_seen.get(r.sto) is r:
            absent.setdefault(r.pon or "(بلا رقم تعميد)", []).append(r)
    if absent:
        from job_pipeline import item_key
        u = {"reason": "التعميد غير موجود في الربطة (%s): لم تُطابق أصناف السندات وأسعارها وموعد التوريد بالتعميد؛ أرفق التعاميد أو راجعها يدوياً"
                       % "، ".join(sorted(absent)), "file": b.file, "page": min((r.pages[0] for rs in absent.values() for r in rs if r.pages), default=1)}
        unresolved.append(u)
        for rs in absent.values():
            for r in rs:
                review_stos.setdefault(r.sto, item_key(u))
    if dup_items:
        from job_pipeline import item_key
        for u in dup_items:                                          # حكم السند المكرر محجوز حتى يحسمه المراجع
            review_stos.setdefault(u["sto"], item_key(u))
    no_contract_note = None
    if not contract_path:
        ev = rules.evidence.get("inferred", {})
        mode_ar = {"partial_net_comm": "الصافي والعمولة", "partial_net": "الصافي فقط"}.get(rules.tax_mode, rules.tax_mode)
        if ev.get("ref_receipt"):
            tax_ref = ev.get("tax_ref_receipt")
            no_contract_note = ("فحص بدون عقد: السند الأول %s مرجع لنسبة العمولة (%s%%) ولأساس الضريبة (%s%% على %s)%s، وتُعمَّم قاعدته على بقية سندات الدفعة؛ وأي سند يخالفها يُحال للمراجعة. "
                                "لا تُتحقق قواعد العقد ولا الغرامة ولا مبلغ السداد المستحق." % (
                                    ev["ref_receipt"], (rules.commission * 100).normalize(), int(rules.vat_rate * 100), mode_ar,
                                    (" (أُخذ الأساس من السند %s لأنه أول سند فيه أصناف خاضعة)" % tax_ref) if tax_ref and tax_ref != ev["ref_receipt"] else ""))
        else:
            other = sum(1 for t in b.page_types.values() if t == "other")
            why = (f"لم يُستخرج أي سند: صفحات الربطة ممسوحة ونموذج الرؤية غير متصل، وقارئ OCR الاحتياطي يعرف قالب مستندات واحداً فقط "
                   f"ولم يتعرّف على {other} من {b.n_pages} صفحات. شغّل نموذج الرؤية ثم أعد الفحص؛ غياب العقد ليس السبب"
                   if b.source == "ocr" and not os.environ.get("VLM_URL") and other == b.n_pages
                   else "لم يُستخرج أي سند من الربطة: لا يمكن اعتماد سند مرجع ولا فحص أي سند (فحص بدون عقد)")
            unresolved.append({"reason": why, "file": b.file, "page": 1})
        from job_pipeline import item_key
        for sto, res in sorted(res_by.items()):                              # بلا عقد لا يُحكم على سند «غير سليم»: كل مخالفة تُحال
            iss = [i for i in res.issues if i.code != "no_invoice"]
            held = next((x for x in unresolved if x.get("sto") == sto and x.get("reason") in READ_CONFLICT.values()), None)
            if iss and held is not None:
                # A scanned receipt already referred for the same findings: one decision, not two.
                held["why"] = held.get("why", "") + "؛ وبلا عقد يُحال بدل الحكم عليه"
            elif iss:
                u = {"reason": "سند يخالف قاعدة السند المرجع (الأول في الدفعة) أو فحوصه الداخلية: يُحال للمراجعة بدل الحكم عليه بلا عقد",
                     "sto": sto, "file": b.file, "page": res.pages[0] if res.pages else None, "why": "؛ ".join(i.text for i in iss)[:400]}
                unresolved.append(u)
                review_stos[sto] = item_key(u)
    items_page = None
    for p in (pdfx.read_pdf(contract_path) if contract_path else []):                      # صفحة قائمة البنود (الملحق ب) لذكرها في ملاحظة المطابقة
        if "قائمة" in p.text and "البنود" in p.text:
            items_page = p.n
            break
    return {"rules": rules, "bundle": b, "results": res_by, "receipts": rec_by, "pos": pos, "invoices": invs,
            "attribution": attribution, "unresolved": unresolved, "review_stos": review_stos, "comp_no": comp_no, "bundle_file": b.file,
            "contract_pages": pdfx.page_count(contract_path) if contract_path else 0, "items_page": items_page,
            "no_contract_note": no_contract_note}


def reviewer_sound(data, resolved_keys):
    """Receipts whose machine findings were all put to the reviewer (a scanned page's reading conflict, or a batch
    without contract) and that the reviewer confirmed «سليم»: the findings were the reading, not the document.
    A «فيه مشكلة» decision never reaches here (that receipt is excluded from the report)."""
    from job_pipeline import item_key
    routed = {}
    for u in data.get("unresolved", []):
        if u.get("sto") and (u.get("reason") in READ_CONFLICT.values() or u.get("reason", "").startswith("سند يخالف قاعدة السند المرجع")):
            routed[u["sto"]] = item_key(u)
    return {sto for sto, k in routed.items() if k in (resolved_keys or set())}


# ------------------------------------------------------------------ كتابة تقرير الدفعة
LAST_DATA = None


def write_batch_report(bundle_path: str, contract_path: str, out_path: str, code_map=None, overrides=None, resolved_keys=None, context_paths=None, cache_dir=None, exclude_stos=None):
    """overrides={'invoice_amount': {sto: Decimal}}: قيمة أدخلها المراجع لمبلغ السند في الفاتورة (تُسجَّل بملاحظته في job.json)."""
    global LAST_DATA
    data = collect_batch(bundle_path, contract_path, code_map, context_paths, cache_dir)
    LAST_DATA = data                       # يقرأه تقييم المهمة مقابل النسخة النصية المرجعية (job_pipeline.evaluate_against_truth)
    for sto, v in ((overrides or {}).get('invoice_amount') or {}).items():
        data['attribution'].setdefault(sto, {})['amount'] = str(v)
    rules, b = data["rules"], data["bundle"]
    # الترتيب ثابت: بترتيب ظهور السند في الملف (أول صفحة له) ثم رقمه؛ لا يتغير بالمراجعة ولا بأخطاء قراءة الأرقام
    excluded = sorted(set(exclude_stos or ()) & set(data["results"]))
    stos = batch_receipt_ids(data, excluded)  # ترتيب الورق، وليس ترتيب أرقام السندات.
    wb = openpyxl.load_workbook(T.writer_template_path("batch"))
    ws1, ws2, ws3 = wb["تقرير السندات"], wb["الأصناف"], wb["المطابقة"]
    # صيغ الصف الأول وتنسيقه من القالب نفسه
    tpl = {}
    for ws in (ws1, ws2, ws3):
        tpl[ws.title] = {"formulas": {c.column: c.value for c in ws[6] if isinstance(c.value, str) and c.value.startswith("=")},
                         "ncols": ws.max_column, "height": ws.row_dimensions[6].height, "last": ws.max_row}
    n_items = sum(len(data["results"][s].items) for s in stos)
    last_items, last_main = 5 + n_items, 5 + len(stos)
    for ws, last_new in ((ws1, last_main), (ws2, last_items), (ws3, last_main)):
        old_last = tpl[ws.title]["last"]
        for r in range(6, max(old_last, last_new) + 1):                 # نظّف بيانات القالب مع إبقاء التنسيق
            for c in range(1, tpl[ws.title]["ncols"] + 1):
                ws.cell(r, c).value = None
        for r in range(6, last_new + 1):
            _clone_row_style(ws, 6, r, tpl[ws.title]["ncols"], tpl[ws.title]["height"])
        if old_last > last_new:
            ws.delete_rows(last_new + 1, old_last - last_new)

    def formulas(ws, r):
        for col, f in tpl[ws.title]["formulas"].items():
            ws.cell(r, col).value = _adapt(f, r, last_items, last_main)

    comp = data["comp_no"]
    _bm = re.search(r"-(\d{2})-\d{3}", data["bundle_file"])
    batch_no = int(_bm.group(1)) if _bm else None                         # اسم بلا رقم دفعة: تبقى الخلية فارغة ولا يُختلق رقم
    # ---------------- عناوين الشيتات (نفس صياغة القالب)
    ws1["A1"] = f"تقرير فحص الدفعة - المنافسة {comp}"
    ex_txt = (f" استُبعد {len(excluded)} سنداً أكّد المراجع أن فيها مشكلة: {'، '.join(excluded)}." if excluded else "")
    ws1["A2"] = (f"المصادر: {data['bundle_file']} ({b.n_pages} صفحة)، وعقد المنافسة.pdf ({data['contract_pages']} صفحات). جميع القيم بالريال السعودي.{ex_txt}" if contract_path
                 else f"المصدر: {data['bundle_file']} ({b.n_pages} صفحة) دون عقد المنافسة (فحص بلا عقد: قواعد العقد غير متحقق منها). جميع القيم بالريال السعودي.{ex_txt}")
    ws1["B3"] = _f(rules.commission)
    ws1["D3"] = f"=SUM(S6:S{last_main})"
    ws1["F3"] = len(stos)
    ws1["H3"] = comp
    ws2["A2"] = f"المصدر: {data['bundle_file']}. صف واحد لكل صنف في السند؛ الفاتورة المشتركة محتسبة مرة واحدة."
    rep = [(n, len(v.copy_pages)) for n, v in data["invoices"].items() if len(v.copy_pages) > 1]
    times = {2: "مرتين", 3: "ثلاث مرات", 4: "أربع مرات", 5: "خمس مرات", 6: "ست مرات", 7: "سبع مرات", 8: "ثماني مرات", 9: "تسع مرات", 10: "عشر مرات"}
    ws3["A2"] = (f"فاتورة {rep[0][0]} مرفقة {times.get(rep[0][1], str(rep[0][1]) + ' مرات')} في الملف؛ احتسبت بنودها وتوزيعها مرة واحدة، "
                 "مع ذكر صفحات النسخة المرتبطة بكل سند." if rep else None)
    ordinal = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة", 7: "السابعة", 8: "الثامنة", 9: "التاسعة", 10: "العاشرة"}
    batch_txt = f" الدفعة {ordinal.get(batch_no, batch_no)}." if batch_no is not None else ""
    tax_txt = {"none": "دون ضريبة قيمة مضافة في هذا المثال", "unknown": "قاعدة الضريبة غير مقروءة"}.get(rules.tax_mode)
    refs = sorted({rules.evidence.get("tax", (None,))[0], data.get("items_page")} - {None})
    pg = ("ص " + " و".join(str(p) for p in refs)) if refs else ""
    ws3["A3"] = ((f"شروط العقد{('، ' + pg) if pg else ''}: عمولة نوبكو {int(rules.commission * 100)}% من الصافي"
                  + (f"، {tax_txt}" if tax_txt else "، وضريبة القيمة المضافة 15% وفق قاعدة العقد")
                  + f".{batch_txt}") if contract_path
                 else f"{data.get('no_contract_note') or 'فحص بدون عقد: لا تُتحقق قواعد العقد.'}{batch_txt}")

    # ---------------- كتابة الصفوف
    r2 = 6
    for i, sto in enumerate(stos):
        r = 6 + i
        res, rec = data["results"][sto], data["receipts"][sto]
        att = data["attribution"].get(sto, {})
        pairs = att.get("pairs") or []
        inv = data["invoices"].get(rec.invoice_no)
        inv_page_groups = [sorted(v) for v in inv.copy_pages.values()] if inv else []
        grp = _pick_after(inv_page_groups, min(rec.pages)) if inv else []
        copy_id = next((k for k, v in inv.copy_pages.items() if sorted(v) == grp), 0) if inv else 0
        po = data["pos"].get(rec.pon)
        po_runs = _runs(po.pages) if po else []
        po_grp = po_runs[0] if po_runs else []       # القالب يعتمد أول ظهور للتعميد (التكرار داخل الربطات لا يُحتسب مرة أخرى)
        taxable = [it["taxable"] for it in res.items]
        # ---- الشيت 1
        ws1.cell(r, 1, sto)
        ws1.cell(r, 2, _d(rec.date))
        ws1.cell(r, 3, rec.invoice_no)
        ws1.cell(r, 4, _d(inv.date) if inv and inv.date else None)
        ws1.cell(r, 5, "\n".join(it["code"] for it in res.items))
        ws1.cell(r, 6, "\n".join(str(_qty(it["qty"])) for it in res.items))
        ws1.cell(r, 7, "\n".join(f"{it['price']:.2f}" for it in res.items))
        ws1.cell(r, 10, "نعم" if res.vat > 0 else "لا")
        ws1.cell(r, 11, None if res.vat == 0 and not any(taxable) else ("كامل السند" if all(taxable) else "جزئي"))
        ws1.cell(r, 12, "نعم" if res.penalty > 0 else "لا")
        ws1.cell(r, 13, _f(res.penalty))
        ws1.cell(r, 14, "لا")
        ws1.cell(r, 15, 0)
        held = sto in data["review_stos"] and data["review_stos"][sto] not in (resolved_keys or set())
        sound = res.ok or sto in reviewer_sound(data, resolved_keys)
        ws1.cell(r, 20, None if held else ("سليم" if sound else "غير سليم محاسبياً"))
        ws1.cell(r, 21, None if held or sound else _reason_text(res))
        ws1.cell(r, 22, comp)
        formulas(ws1, r)
        # ---- الشيت 2: صف لكل صنف
        for k, it in enumerate(res.items):
            rr = r2
            r2 += 1
            ritem = rec.items[k]
            pair = next((p for p in pairs if p[0]["code"] == it["code"] and p[0]["qty"] == it["qty"]), None)
            inv_row = pair[1] if pair else None
            # القالب: «صفحة الفاتورة» في شيت الأصناف = صفحة الصف في **النسخة الأولى**، بينما «صفحات الفاتورة» في المطابقة =
            # النسخة المجاورة للسند. (تباين داخل القالب نفسه يُقلَّد كما هو)
            # صفحة صف الفاتورة = صفحة الصف نفسه في النسخة المسجلة في «المطابقة» (الدليل الواحد لهذا السند)، وإلا صفحة النسخة الأولى
            inv_page = inv_row.get("page") if inv_row else None
            if inv_row and inv:
                same = _same_row(inv, inv_row, copy_id)
                if same is not None:
                    inv_page = same.ev.page
            po_item = next((x for x in (po.items if po else []) if x.code == it["code"] and x.ev.page in po_grp), None) \
                or next((x for x in (po.items if po else []) if x.code == it["code"]), None)
            ws2.cell(rr, 1, sto)
            ws2.cell(rr, 2, it["code"])
            ws2.cell(rr, 3, _qty(it["qty"]))
            ws2.cell(rr, 4, _f(it["price"]))
            ws2.cell(rr, 6, _f(ritem.line_total))
            ws2.cell(rr, 7, _f(inv_row["net"]) if inv_row else None)
            ws2.cell(rr, 8, _f(inv_row["nupco"]) if inv_row else None)
            ws2.cell(rr, 9, _f(inv_row["vat"]) if inv_row else None)
            ws2.cell(rr, 10, rec.pon)
            ws2.cell(rr, 11, _f(po_item.unit_price) if po_item else None)
            ws2.cell(rr, 12, ritem.ev.page)
            ws2.cell(rr, 13, inv_page)
            ws2.cell(rr, 14, po_item.ev.page if po_item else (po_grp[0] if po_grp else None))      # صفحة سطر الصنف نفسه في التعميد (لا صفحة بداية التعميد)
            line_ok = (inv_row is not None and ritem.line_total is not None and abs(ritem.line_total - inv_row["amount"]) <= D("0.005")
                       and po_item is not None and po_item.unit_price == ritem.unit_price)
            ws2.cell(rr, 15, ("مطابق" if line_ok else "غير مطابق") if inv_row is not None else None)
            formulas(ws2, rr)
        # ---- الشيت 3
        printed = rec.printed
        amount = att.get("amount")
        ws3.cell(r, 1, sto)
        ws3.cell(r, 2, rec.pon)
        ws3.cell(r, 3, rec.invoice_no)
        ws3.cell(r, 4, comp)
        ws3.cell(r, 5, batch_no)
        ws3.cell(r, 6, SEP.join(str(p) for p in sorted(rec.pages)))
        ws3.cell(r, 7, SEP.join(str(p) for p in grp) if grp else None)
        ws3.cell(r, 8, SEP.join(str(p) for p in po_grp) if po_grp else None)
        ws3.cell(r, 9, _f(printed.get("net")))
        ws3.cell(r, 11, _f(printed.get("nupco")))
        ws3.cell(r, 13, _f(printed.get("vat")))
        ws3.cell(r, 14, _f(printed.get("total")))
        ws3.cell(r, 15, _f(D(amount)) if amount is not None else None)
        pay_ok = amount is not None and abs(D(amount) - res.payable - res.penalty) <= D("0.005")
        ws3.cell(r, 17, None if amount is None else ("مطابق" if (res.ok and pay_ok) else "غير مطابق"))
        formulas(ws3, r)
    n_f, f_err = RS.finalize(wb, out_path)                 # تنسيق المراجعة + حفظ + نتائج الصيغ المخزّنة
    T.assert_matches_template(out_path, "batch")
    return out_path, data["unresolved"]


def _save(wb, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    wb.save(out_path)
    return out_path


# ------------------------------------------------------------------ مقارنة خلية بخلية (اختبار انحدار)
def compare_workbooks(a_path: str, b_path: str, max_report: int = 40):
    """يقارن كل خلايا الشيتات (قيم وصيغ) بين ملفين؛ يعيد قائمة الفروق."""
    a, b = openpyxl.load_workbook(a_path), openpyxl.load_workbook(b_path)
    diffs = []
    if a.sheetnames != b.sheetnames:
        diffs.append(("sheets", a.sheetnames, b.sheetnames))
    for name in a.sheetnames:
        if name not in b.sheetnames:
            continue
        wa, wb_ = a[name], b[name]
        if (wa.max_row, wa.max_column) != (wb_.max_row, wb_.max_column):
            diffs.append((name, "dims", wa.dimensions, wb_.dimensions))
        for r in range(1, max(wa.max_row, wb_.max_row) + 1):
            for c in range(1, max(wa.max_column, wb_.max_column) + 1):
                va, vb = wa.cell(r, c).value, wb_.cell(r, c).value
                if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool) and abs(va - vb) < 1e-6:
                    continue
                if va != vb:
                    diffs.append((name, wa.cell(r, c).coordinate, va, vb))
    return diffs
