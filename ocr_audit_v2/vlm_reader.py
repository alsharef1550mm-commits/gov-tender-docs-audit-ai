"""قراءة الربطات الممسوحة بنموذج رؤية (خادم متوافق مع OpenAI، مثل vLLM) ثم بناء الكائنات نفسها التي يبنيها مسار النص المباشر.

التفعيل: متغير البيئة VLM_URL (مثل http://127.0.0.1:8000/v1) و VLM_MODEL (افتراضي Qwen/Qwen3.5-9B).
كل قيمة هنا مقروءة آلياً لا موثّقة: يتحقق منها محرك الحساب (كمية×سعر، العمولة، الإجماليات، الربط بين المستندات)
وبوابة vlm/gate.py، وما يتعارض يُحال للمراجعة (extract.Bundle.source == "vlm").
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation

import pypdfium2 as pdfium
from PIL import Image

import extract
import pdfx
import scan_reader
from number_reading import decimal_reading, amount_reading, quantity_reading, page_separator
from reading_policy import reading_signals, reconcile_readings, POLICY_VERSION, MAX_REREADS

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(HERE, "vlm", "space_gpu", "prompt_typed.txt")
if not os.path.exists(PROMPT_PATH):
    PROMPT_PATH = os.path.join(HERE, "prompt_typed.txt")
SKELETON = json.dumps({
    "page_type": "purchase_order | receipt | invoice | other",
    "ids": {"receipt_no": None, "po_no": None, "invoice_no": None, "customer_po_no": None, "tender_no": None},
    "dates": {"document_date": None, "po_date": None, "due_date": None},
    "items": [{"line_no": None, "item_code": None, "description": None, "unit": None, "qty": None, "unit_price": None,
               "unit_price_halala": None, "line_total": None, "line_total_halala": None, "commission": None, "vat": None, "batch": None}],
    "totals": {"net_excl_vat": None, "commission": None, "discount": None, "vat": None, "total_incl": None, "total": None,
               "shipping": None, "penalty": None},
    "unreadable_fields": []}, indent=1)
CRITICAL_IDS = {"receipt_no", "po_no", "invoice_no"}
RELEVANT_IDS = {"receipt": {"receipt_no", "invoice_no", "po_no"}, "invoice": {"invoice_no"}, "purchase_order": {"po_no"}}   # ما يهمّ كل نوع صفحة
PRIMARY_ID = {"receipt": "receipt_no", "invoice": "invoice_no", "purchase_order": "po_no"}
RECEIPT_FACTORS = (Decimal("1.04"), Decimal("1.19"), Decimal("1.196"))
RE_STO, RE_PON, RE_INV = extract.RE_STO, extract.RE_PON, re.compile(r"^(?:TF)?\d{10}$")


_SEP = None   # decimal separator the page being built proves by itself (number_reading.page_separator)


def _d(x):
    return decimal_reading(x, _SEP)


def _with_halala(v, h):
    return amount_reading(v, h, _SEP)


NON_CRITICAL = {"description", "unit", "batch", "line_no"}     # item cells no audit figure uses (as pairs_reader)


def _code(x):
    """An item code with a neighbouring label read into its cell («5110157700000 E.D.Date :»): the trailing words carry
    no digit, so they are not part of the code. Anything else is returned as read."""
    if x is None:
        return None
    s = str(x).strip()
    m = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9./-]*\d[A-Za-z0-9./-]*)\s+([^\d]+)", s)
    # or a long numeric code followed by another cell's «label : value» («5119190501600 E.D.Date : 09-10-2026»)
    m = m or re.fullmatch(r"(\d{8,})\s+[A-Za-z؀-ۿ][^:\d]*:.*", s)
    return m.group(1) if m else s


def _qty(x):
    return quantity_reading(x, _SEP)    # shared with reading_policy (number_reading.quantity_reading)


def _rate(x):
    """A printed tax rate such as "15%" or "٪١٥" as a fraction; anything else is None (never inferred)."""
    if x is None:
        return None
    s = str(x).strip()
    if not re.fullmatch(r"[%٪]?\s*[\d٠-٩.٫]+\s*[%٪]?", s) or not re.search(r"[%٪]", s):
        return None
    v = _d(re.sub(r"[%٪\s]", "", s))
    return v / 100 if v is not None and 0 <= v <= 100 else None


def _clean_id(x, rx):
    if x is None:
        return None
    s = re.sub(r"\s", "", str(x))
    # Owner's rule (2026-10-25): a receipt number is always "STO" + 10 digits, so a scan reading of the
    # letter O as zero ("ST0" + 10 digits) can only be that number. The raw reading stays in raw_readings.
    if rx is RE_STO and re.fullmatch(r"ST0\d{10}", s):
        s = "STO" + s[3:]
    return s if rx.fullmatch(s) else None


def pairs_mode():
    """VLM_FORMAT=pairs selects the label/value reader (pairs_reader); default keeps the schema reader."""
    return os.environ.get("VLM_FORMAT") == "pairs"


def call_vlm(img, base_url=None, model=None, prompt_path=None):
    if pairs_mode():
        import pairs_reader
        return pairs_reader.read_page(img, base_url, model)
    base_url = base_url or os.environ["VLM_URL"]
    model = model or os.environ.get("VLM_MODEL", "Qwen/Qwen3.5-9B")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    prompt = open(prompt_path or PROMPT_PATH, encoding="utf-8").read()
    body = {"model": model, "temperature": 0, "max_tokens": 3000,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
                {"type": "text", "text": prompt + "\nReturn exactly this JSON shape (one item object per table row; null where not visible):\n" + SKELETON}]}],
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        txt = json.loads(r.read())["choices"][0]["message"]["content"]
    try:
        return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip()))
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", txt, re.S)
        try:
            return json.loads(m.group(0)) if m else None
        except Exception:  # noqa: BLE001
            return None


def _prep_up(img):
    from PIL import ImageFilter, ImageOps
    img = img.convert("L").resize((int(img.width * 1.5), int(img.height * 1.5)), Image.LANCZOS)
    return ImageOps.autocontrast(img.filter(ImageFilter.UnsharpMask(2, 100, 3)), cutoff=1)


def wait_ready(base_url=None, timeout=1500):
    """ينتظر جاهزية خادم النموذج (قد يكون يحمّل بعد استيقاظ الـSpace)."""
    import time
    base_url = base_url or os.environ["VLM_URL"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=5)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(10)
    raise RuntimeError("خادم نموذج الرؤية لم يجهز")


def _num(x):
    return None if x in (None, "") else _d(x)


def _row_key(it):
    """مفتاح صف للمقارنة بين قارئين: الرمز والكمية والسعر (مع الهللة) والإجمالي (مع الهللة) والعمولة والضريبة."""
    return (str(it.get("item_code") or "").strip(), _num(it.get("qty")), _with_halala(it.get("unit_price"), it.get("unit_price_halala")),
            _with_halala(it.get("line_total"), it.get("line_total_halala")), _num(it.get("commission")), _num(it.get("vat")))


def merge_preds(p1, p2):
    """مقارنة قراءتين؛ اتفاقهما ليس تحققاً بشرياً أو إثباتاً لصحة المطبوع.
    - نوع الصفحة مختلف أو قراءة فاشلة: الصفحة بلا محتوى ويُسجَّل التعارض (_type_conflict).
    - معرّف مختلف: يُصفَّر (_id_conflicts). صف بلا نظير مطابق في القراءة الأخرى: يُسقَط (_dropped). إجمالي مختلف: يُصفَّر.
    تحفظ القراءتان للمراجعة؛ اختلاف الموجّه وحده لا يثبت استقلال الأخطاء."""
    if not isinstance(p1, dict) or not isinstance(p2, dict) or p1.get("page_type") != p2.get("page_type"):
        return {"page_type": "other", "ids": {}, "dates": {}, "items": [], "totals": {}, "_type_conflict": True,
                "_failed": not (isinstance(p1, dict) and isinstance(p2, dict)),
                "_readings": [p1, p2], "_agreement_is_source_verification": False}
    out = {"page_type": p1.get("page_type"), "ids": {}, "dates": dict(p1.get("dates") or {}), "items": [], "totals": {}, "_id_conflicts": [], "_dropped": [], "_value_conflicts": []}
    i1, i2 = p1.get("ids") or {}, p2.get("ids") or {}
    rel = RELEVANT_IDS.get(p1.get("page_type"), CRITICAL_IDS) | {"tender_no", "quarter"}
    for k in set(i1) | set(i2):
        if k not in rel:
            out["ids"][k] = i1.get(k) if i1.get(k) == i2.get(k) else None      # حقل غير معتمد لهذا النوع: لا يُحال عند الاختلاف
            continue
        a, b = i1.get(k), i2.get(k)
        s = lambda x: None if x is None else re.sub(r"\s", "", str(x))
        if s(a) == s(b):
            out["ids"][k] = a
        elif a is not None or b is not None:
            out["ids"][k] = None
            out["_id_conflicts"].append(k)
    keys2 = [_row_key(i) for i in (p2.get("items") or [])]
    for it in (p1.get("items") or []):
        k = _row_key(it)
        if k in keys2:
            keys2.remove(k)                                  # كل صف في القراءة الثانية يُستهلك مرة واحدة (التكرار المشروع)
            out["items"].append(it)
        else:
            out["_dropped"].append(str(it.get("item_code")))
    out["_dropped"] += ["+" + str(k[0]) for k in keys2]       # صفوف في القراءة الثانية بلا نظير: تعارض كذلك
    t1, t2 = p1.get("totals") or {}, p2.get("totals") or {}
    for k in set(t1) | set(t2):
        out["totals"][k] = t1.get(k) if (_num(t1.get(k)) == _num(t2.get(k))) else None
    for k in set(t1) | set(t2):
        if _num(t1.get(k)) != _num(t2.get(k)):
            out['_value_conflicts'].append('totals.' + k)
    for k in set(p1.get('dates') or {}) | set(p2.get('dates') or {}):
        if (p1.get('dates') or {}).get(k) != (p2.get('dates') or {}).get(k):
            out['_value_conflicts'].append('dates.' + k)
            out['dates'][k] = None
    out['_readings'] = [p1, p2]
    out['_agreement_is_source_verification'] = False
    return out


def _reader2():
    """القارئ الثاني المستقل من البيئة (VLM2_URL، VLM2_MODEL، VLM2_PROMPT)؛ None إن لم يُضبط."""
    if not os.environ.get("VLM2_URL"):
        return None
    return {"url": os.environ["VLM2_URL"], "model": os.environ.get("VLM2_MODEL", os.environ.get("VLM_MODEL", "Qwen/Qwen3.5-9B")),
            "prompt": os.environ.get("VLM2_PROMPT") or None}


def _cached_call(img, url, model, prompt):
    """قراءة صفحة بقارئ معيّن مع ذاكرة اختيارية (VLM_CACHE_DIR) تُسرّع إعادة القياس نفسه؛ مفتاحها الصورة والنموذج والموجّه."""
    import hashlib
    cdir = os.environ.get("VLM_CACHE_DIR")
    key = None
    if cdir:
        os.makedirs(cdir, exist_ok=True)
        pp = prompt or (os.path.join(HERE, "vlm", "prompt_pairs.txt") if pairs_mode() else PROMPT_PATH)
        key = hashlib.sha1(img.tobytes() + (model or os.environ.get("VLM_MODEL", "")).encode() + open(pp, "rb").read()
                           + (b"pairs" if pairs_mode() else b"")).hexdigest()
        fp = os.path.join(cdir, key + ".json")
        if os.path.exists(fp):
            return json.load(open(fp, encoding="utf-8"))
    try:
        p = call_vlm(img, url, model, prompt)
    except Exception:  # noqa: BLE001
        return None
    if key and p is not None:
        json.dump(p, open(os.path.join(cdir, key + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    return p


def _tess_digits10(img):
    """الأرقام ذات العشرة خانات في نص Tesseract للصفحة (قارئ مستقل ثالث للتحكيم بين قارئين مختلفين على معرّف).
    تُحفظ في الذاكرة الاختيارية بمفتاح الصورة. يعيد مجموعة سلاسل أرقام (تُقارَن بالأرقام العشرة لكل معرّف)."""
    import hashlib
    import subprocess
    import tempfile
    cdir = os.environ.get("VLM_CACHE_DIR")
    fp = None
    if cdir:
        os.makedirs(cdir, exist_ok=True)
        fp = os.path.join(cdir, "tess_" + hashlib.sha1(img.tobytes()).hexdigest() + ".json")
        if os.path.exists(fp):
            return set(json.load(open(fp, encoding="utf-8")))
    tess = os.environ.get("TESSERACT_CMD") or (r"C:\Program Files\Tesseract-OCR\tesseract.exe" if os.name == "nt" else "tesseract")
    found = set()
    with tempfile.TemporaryDirectory() as d:
        pth = os.path.join(d, "x.png")
        img.convert("L").save(pth)
        for psm in ("6", "11"):
            try:
                txt = subprocess.run([tess, pth, "stdout", "-l", "eng", "--psm", psm], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout
            except Exception:  # noqa: BLE001
                continue
            found |= set(re.findall(r"(?<!\d)\d{10}(?!\d)", re.sub(r"(?<=\d)[\s,](?=\d)", "", txt)))
            found |= set(re.findall(r"(?<!\d)\d{10}(?!\d)", txt))
    if fp:
        json.dump(sorted(found), open(fp, "w", encoding="utf-8"))
    return found


def _arbitrate_ids(merged, p1, p2, img):
    # A number appearing elsewhere on the page does not prove its field role.
    # Keep conflicting identities unresolved until their labelled source is checked.
    return merged


def read_preds(path, workers=4, progress=None):
    wait_ready()
    r2 = _reader2()
    if r2:
        wait_ready(r2["url"])
    n = pdfx.page_count(path)
    imgs = []                                     # التصيير تسلسلي: pdfium غير آمن مع الخيوط (انهيار/فشل تحميل متقطع)؛ الخيوط لاستدعاءات النموذج فقط
    doc = pdfium.PdfDocument(path)
    scale = 3.0 if pairs_mode() else 2.0                                 # الأزواج: قرب دقة صفحات التدريب (~2100×2700)
    raw = [doc[i].render(scale=scale).to_pil() for i in range(n)]       # تصيير تسلسلي (pdfium)
    doc.close()

    key = os.path.abspath(path)

    def prep(i):
        img = raw[i]                                              # الاتجاه يُصحَّح قبل الرفع بالأداة المستقلة (خارج الفحص)
        if pairs_mode():
            return img                            # قارئ الأزواج دُرّب على صفحات ملونة بدقة كاملة؛ لا تكبير ولا شحذ
        img.thumbnail((1600, 1600))
        return _prep_up(img)                     # أفضل إعداد قيس: تكبير 1.5× وشحذ وتباين (vlm/space_gpu: typed:up)
    with ThreadPoolExecutor(workers) as ex:      # كشف الاتجاه يستدعي Tesseract كعملية مستقلة فيتوازى بأمان
        for k, im in enumerate(ex.map(prep, range(n)), 1):
            imgs.append(im)
            _report(progress, k, n, "prep")
    del raw

    def one(i):
        img = imgs[i]
        p1 = _cached_call(img, None, None, None)
        if isinstance(p1, dict):
            import copy, hashlib
            p1 = copy.deepcopy(p1)
            p1['_page_evidence'] = {'file': os.path.basename(path), 'page': i+1,
                'image_sha256': hashlib.sha256(img.tobytes()).hexdigest(), 'size': list(img.size),
                'model': os.environ.get('VLM_MODEL','Qwen/Qwen3.5-9B'), 'field_boxes_verified': False}
        if not r2:
            return p1
        p2 = _cached_call(img, r2["url"], r2["model"], r2["prompt"])
        merged = merge_preds(p1, p2)
        merged["_readings"] = [p1, p2]
        merged["_agreement_is_source_verification"] = False
        return merged
    out = []
    with ThreadPoolExecutor(workers) as ex:
        for k, p in enumerate(ex.map(one, range(n)), 1):
            out.append(p)
            _report(progress, k, n, "read")
    return out


def _report(progress, k, n, stage):
    """يبلغ بالتقدم مع اسم المرحلة (تجهيز/قراءة) إن قبل المستدعي ثلاث معاملات، وإلا (k, n) فقط."""
    if not progress:
        return
    try:
        progress(k, n, stage)
    except TypeError:
        progress(k, n)


def bundle_from_preds(fname: str, preds: list) -> extract.Bundle:
    """يبني Bundle (source='vlm') من قراءات صفحة بصفحة. ما لا يطابق صيغة المعرّفات يُترك None فتُحيله بقية الطبقات."""
    Ev, Rec, RItem = extract.Ev, extract.Receipt, extract.RItem
    box = (0.0, 0.0, 0.0, 0.0)
    pos: dict[str, extract.PO] = {}
    recs: dict[str, extract.Receipt] = {}
    invs: dict[str, extract.Invoice] = {}
    r_order, types = [], {}
    last_rec = last_inv = last_po = None
    issues = {}                                       # صفحات لم يتفق عليها القارئان: {رقم الصفحة: وصف}
    tenders = []
    for n, p in enumerate(preds, 1):
        if not isinstance(p, dict):
            types[n] = "other"
            issues[n] = {"kind": "failed", "why": "تعذرت قراءة الصفحة آلياً"}
            continue
        global _SEP
        _SEP = page_separator(p)                         # «1,320» is read by the convention this page itself proves
        p = {**p, "items": [{**it, "item_code": _code(it.get("item_code"))} if isinstance(it, dict) else it
                            for it in p.get("items") or []]}
        prim = PRIMARY_ID.get(p.get("page_type"))
        if p.get("_type_conflict") or (prim and prim in (p.get("_id_conflicts") or [])):
            types[n] = "other"                            # لا تُنسب لمستند سابق صامتاً: هوية الصفحة لم تثبت
            issues[n] = {"kind": "identity", "why": ("القارئان لم يتفقا على نوع الصفحة" if p.get("_type_conflict")
                                                      else "القارئان لم يتفقا على: " + "، ".join(p["_id_conflicts"]))}
            continue
        if p.get("_id_conflicts"):
            issues[n] = {"kind": "link", "why": "القارئان لم يتفقا على رقم مرتبط: " + "، ".join(p["_id_conflicts"]) + " (تُصفَّر القيمة ويُحال الربط)"}
        ty = p.get("page_type")
        if p.get("_dropped") and ty in ("receipt", "purchase_order", "invoice"):
            issues[n] = {"kind": "rows", "why": "أُسقطت من التدقيق أصناف لم يتفق عليها القارئان: " + "، ".join(p["_dropped"][:8])}
        ty = p.get("page_type")
        ids, items, tot = p.get("ids") or {}, p.get("items") or [], p.get("totals") or {}
        dates = p.get("dates") or {}
        types[n] = {"purchase_order": "po", "receipt": "receipt", "invoice": "invoice"}.get(ty, "other")
        if ty in ("receipt", "invoice", "purchase_order") and ids.get("tender_no"):
            tenders.append((n, str(ids["tender_no"]).strip()))     # the tender number exactly as printed, any format
        own = {"receipt": ("receipt_no", RE_STO), "invoice": ("invoice_no", RE_INV), "purchase_order": ("po_no", RE_PON)}.get(ty)
        if own and not _clean_id(ids.get(own[0]), own[1]):
            # Its own number was not read: it may be a separate document, so the page is shown for review
            # (and holds the document it is attached to) instead of being merged or dropped silently.
            issues.setdefault(n, {'kind': 'reading', 'why': 'صفحة مستند لم يُقرأ رقمه: قد تكون مستنداً مستقلاً؛ يلزم التحقق من الصفحة'})
        if ty == "receipt":
            sto = _clean_id(ids.get("receipt_no"), RE_STO) or last_rec
            if not sto:
                continue
            r = recs.get(sto)
            if r is None:
                r = recs[sto] = Rec(sto)
                r_order.append(sto)
            last_rec = sto
            r.pon = r.pon or _clean_id(ids.get("po_no"), RE_PON)
            r.invoice_no = r.invoice_no or _clean_id(ids.get("invoice_no"), RE_INV)
            r.date = r.date or dates.get("document_date")
            r.due = r.due or dates.get("due_date")
            r.pages.append(n)
            for k, it in enumerate(items, 1):
                q, up = _qty(it.get("qty")), _with_halala(it.get("unit_price"), it.get("unit_price_halala"))
                lt = _with_halala(it.get("line_total"), it.get("line_total_halala"))
                if not it.get("item_code") or q is None or up is None:
                    # صف ناقص: لا يُخمَّن، ويُحال السند ببند واضح (engine: items_unread). The line total is a check
                    # figure only (the net is quantity × the order's price): a row without it is still computed.
                    gone = [ar for key, ar, v in (("item_code", "رمز الصنف", it.get("item_code")), ("qty", "الكمية", q),
                                                   ("unit_price", "سعر الوحدة", up)) if not v and v != 0]
                    r.__dict__.setdefault("incomplete_rows", []).append(f"ص{n} سطر {it.get('line_no') or k}: {'، '.join(gone)} غير مقروء")
                    continue
                try:
                    ln = int(str(it.get("line_no")))
                except Exception:  # noqa: BLE001
                    ln = k
                rate = _rate(it.get("vat_rate"))  # the printed rate only; tax status is never inferred from arithmetic
                r.items.append(RItem(ln, it["item_code"], it.get("unit") or "", q, up, lt, rate, Ev(fname, n, box)))
            mp = {"net_excl_vat": "net", "commission": "nupco", "vat": "vat", "total_incl": "total", "total": "final",
                  "discount": "discount", "shipping": "shipping", "penalty": "penalty"}
            for k_src, k_dst in mp.items():
                v = _d(tot.get(k_src))
                if v is not None and k_dst not in r.printed:
                    r.printed[k_dst] = v
                    r.summary_ev = Ev(fname, n, box)
        elif ty == "invoice":
            num = _clean_id(ids.get("invoice_no"), RE_INV) or last_inv
            if not num:
                continue
            v = invs.get(num)
            if v is None:
                v = invs[num] = extract.Invoice(num)
            if last_inv == num and v.pages and n != v.pages[-1] + 1 and False:
                v.cur_copy += 1
            last_inv = num
            v.date = v.date or dates.get("document_date")
            v.pages.append(n)
            v.copy_pages.setdefault(v.cur_copy, []).append(n)
            for k, it in enumerate(items, 1):
                q, up, tt = _qty(it.get("qty")), _d(it.get("unit_price")), _d(it.get("line_total"))
                comm, vat = _d(it.get("commission")), _d(it.get("vat"))
                line_sto = _clean_id(it.get("_receipt_no"), RE_STO)
                if not it.get("item_code") and line_sto and _d(it.get("line_net")) is not None:
                    # A collective invoice lists each receipt's net without item lines: an allocation, not an item.
                    v.allocations[line_sto] = _d(it.get("line_net"))
                    if _clean_id(it.get("_po_no"), RE_PON):
                        v.allocation_pon[line_sto] = it["_po_no"]
                    continue
                if not it.get("item_code") or None in (q, up, tt, comm, vat):
                    continue
                net = q * up
                if abs(net + comm + vat - tt) > Decimal("0.02"):
                    # تعارض حسابي لا يحدد هل السبب قراءة أم مستند؛ تحفظ القيم وتُحال.
                    v.__dict__.setdefault("flags", []).append({"code": it["item_code"], "seen": str(tt), "expected": str(net + comm + vat), "page": n})
                    # Preserve the printed total and row; the contradiction is evidence.
                line_sto = _clean_id(it.get("_receipt_no"), RE_STO)        # رقم السند المطبوع في سطر الفاتورة نفسه (قارئ الأزواج)
                v.items.append(extract.IItem(line_sto or _clean_id(ids.get("receipt_no"), RE_STO) or "", k, it["item_code"], it.get("batch") or "",
                                             up, q, net, comm, Decimal(0), net + comm, Decimal(0), vat, tt, Ev(fname, n, box),
                                             copy=v.cur_copy))
        elif ty == "purchase_order":
            num = _clean_id(ids.get("po_no"), RE_PON) or last_po
            if not num:
                continue
            po = pos.get(num)
            if po is None:
                po = pos[num] = extract.PO(num, dates.get("po_date"), None)
            last_po = num
            po.pages.append(n)
            for k, it in enumerate(items, 1):
                q, up, lt, vat = _qty(it.get("qty")), _d(it.get("unit_price")), _d(it.get("line_total")), _d(it.get("vat")) or Decimal(0)
                if not it.get("item_code") or None in (q, up, lt):
                    continue
                try:
                    ln = int(str(it.get("line_no")))
                except Exception:  # noqa: BLE001
                    ln = k
                po.items.append(extract.POItem(ln, it["item_code"], it.get("unit") or "", q, up, lt, vat, lt + vat,
                                               dates.get("due_date"), Ev(fname, n, box)))
    for v in invs.values():
        if v.allocations and not v.items:
            v.__dict__["collective"] = True           # as extract.parse_invoices marks a collective invoice
    b = extract.Bundle(fname, len(preds), types, list(pos.values()), [recs[s] for s in r_order], list(invs.values()), "vlm")
    for n, p in enumerate(preds, 1):
        critical = ([u for u in (p.get('unreadable_fields') or []) if not (u.startswith('items.') and u.split('.')[-1] in NON_CRITICAL)]
                    if isinstance(p, dict) else [])
        if isinstance(p, dict) and (p.get('_reading_review') or critical or p.get('_value_conflicts')):
            issues.setdefault(n, {'kind': 'reading', 'why': 'قراءة غير محسومة؛ القيم الأصلية محفوظة ويلزم فحص موضعها في الصفحة'})
    b.__dict__["raw_readings"] = preds
    b.__dict__["tender_pages"] = tenders
    b.__dict__["reading_policy"] = POLICY_VERSION
    b.__dict__["agree_issues"] = issues
    return b


def _norm_price(x):
    return x.quantize(Decimal("0.01")) if x is not None else None


def suspect_pages(b):
    """Only reading evidence triggers retries; arithmetic and invoice absence do not."""
    return {n: '؛ '.join(signals) for n, p in enumerate(getattr(b, 'raw_readings', []), 1)
            if (signals := reading_signals(p))}


_ANGLES: dict = {}                               # (مسار الملف، رقم الصفحة) -> زاوية التصحيح المطبّقة في القراءة الأولى
REREAD_MAX_SHARE = 0.4  # Resource bound only; exceeding it does not diagnose the design.
RETRY_SETTINGS = ((3.0, 2200),)  # One enhanced read: render scale, maximum side.


def _reread_pages(path, pages, attempt, progress=None):
    """يعيد قراءة صفحات محددة بإعداد صورة مغاير للقراءة الأولى؛ يعيد {صفحة: قراءة أو None}.
    زاوية الاتجاه تُؤخذ من القراءة الأولى (محفوظة)، ولا يُعاد كشفها إلا إن لم تُحفظ."""
    scale, side = RETRY_SETTINGS[min(attempt, len(RETRY_SETTINGS)) - 1]
    key = os.path.abspath(path)
    doc = pdfium.PdfDocument(path)
    out = {}
    for pg in pages:                                   # تصيير تسلسلي (pdfium غير آمن مع الخيوط)
        img = doc[pg - 1].render(scale=scale).to_pil()
        img.thumbnail((side, side))
        out[pg] = _prep_up(img)
    doc.close()
    res = {}
    with ThreadPoolExecutor(4) as ex:
        for k, (pg, r) in enumerate(zip(pages, ex.map(lambda pg: _cached_call(out[pg], None, None, None), pages)), 1):
            res[pg] = r
            _report(progress, k, len(pages), "reread")
    return res


def read_bundle_vlm(path: str, workers: int = 4, progress=None, max_retries: int = 1) -> extract.Bundle:
    """At most one enhanced reread. Changed values require source review.

    Without validated field boxes, enhancement is page-level and is recorded as
    such; we do not claim a crop or a verified source from model agreement.
    """
    fname = os.path.basename(path)
    preds = read_preds(path, workers, progress)
    retried = {}
    skipped = 0
    initial = bundle_from_preds(fname, preds)
    suspects = suspect_pages(initial)
    if _reader2() or pairs_mode():
        max_retries = 0  # Two reads already exist, or the pairs reader did its own zoomed re-read.
    if len(preds) >= 10 and len(suspects) > REREAD_MAX_SHARE * len(preds):
        skipped = len(suspects)
        max_retries = 0
    if min(MAX_REREADS, max(0, max_retries)) and suspects:
        new = _reread_pages(path, sorted(suspects), 1, progress)
        for pg, reason in suspects.items():
            preds[pg-1] = reconcile_readings(preds[pg-1], new.get(pg))
            retried[pg] = [reason]
    b = bundle_from_preds(fname, preds)
    for pg in suspects:
        b.agree_issues.setdefault(pg, {'kind': 'reading', 'why': 'سبب شك في القراءة؛ اتفاق القراءات لا يثبت المطبوع ويلزم مراجعة الدليل'})
    b.__dict__['retried_pages'] = retried
    b.__dict__['reread_skipped'] = skipped
    b.__dict__['reread_scope'] = 'enhanced_page_without_verified_field_boxes'
    return b
