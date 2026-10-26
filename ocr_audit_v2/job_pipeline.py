"""مسار المهمة: رفع ← فحص الملفات ← استخراج ← مطابقة ← بانتظار المراجعة ← معتمد ← مُصدَّر.

- الحالة والتقدم والقرارات في job.json داخل مجلد المهمة (تستأنف المهمة بعد انقطاع: نتائج كل ربطة محفوظة بصمة SHA-256).
- لا يُصدَّر تقرير نهائي (حالة «exported») وفي المهمة بنود غير محسومة؛ المسودة تُنزَّل بخلية الإقفال «يتطلب مراجعة».
- قرارات المراجع: set_value (يدخل قيمة مبلغ سند الفاتورة بملاحظة)، confirm_blank (تحقق أن المصدر لا يطبع قيمة)، cannot_decide.
  الأخيران لا يُنشئان قيمة؛ cannot_decide يبقي البند غير محسوم فيبقى الإقفال «يتطلب مراجعة».
- ما لا يُقرأ بالنص المباشر (صفحات ممسوحة بلا طبقة نصية) يُحال للمراجعة، ولا يُخمَّن.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
import pickle
import re
import shutil
import threading
import time
import traceback
import uuid
from decimal import Decimal as D

import pdfx

STATES = ["uploaded", "files_checked", "extracting", "matching", "awaiting_review", "approved", "exported", "failed"]
STATE_AR = {"uploaded": "تم الرفع", "files_checked": "تم فحص الملفات", "extracting": "جارٍ الاستخراج", "matching": "جارٍ المطابقة وكتابة التقرير",
            "awaiting_review": "بانتظار المراجعة", "approved": "معتمد", "exported": "مُصدَّر", "failed": "فشل"}
BUNDLE_RE = re.compile(r"^(MED-[A-Z0-9]+(?:-\d+)?)-(\d{2})-(\d{3})\.pdf$")
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "200"))
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "14"))
ROOT = os.environ.get("AUDIT_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs")
_LOCK = threading.Lock()


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_reporter(job, st):
    """مُبلِّغ تقدّم القراءة: يحوّل (صفحات منتهية/كل الصفحات) إلى نسبة حقيقية في شريط المتابعة (من 5% إلى 80%)؛ وبعدها يبدأ التدقيق.
    st = {"i": ربطات منتهية، "n": عدد الربطات} لحساب موضع الربطة الحالية. يرمي Cancelled إن طُلب الإلغاء."""
    import progress_hook as PH
    last = {"t": 0.0, "pct": 5.0, "t0": time.time()}

    def rep(stage, done, total, note=""):
        if job.load().get("cancel"):
            raise PH.Cancelled()
        now = time.time()
        if done < total and now - last["t"] < 0.7:
            return
        if stage == "reread":                                           # إعادة قراءة المشتبه فيها: 80% → 92%
            pct = round(80 + 12 * done / max(total, 1), 1)
            frac = 1.0
            if job.load().get("state") != "extracting":
                job.update(state="extracting", state_ar=STATE_AR["extracting"])
        else:
            lo_, hi_ = {"prep": (0.0, 0.3), "read": (0.3, 1.0)}.get(stage, (0.0, 1.0))    # تجهيز الصفحات 30% من القراءة ثم النموذج 70%
            fr = lo_ + (hi_ - lo_) * done / max(total, 1)
            frac = (st.get("i", 0) + fr) / max(st.get("n", 1), 1)
            pct = round(5 + 75 * frac, 1)
        eta = round((now - last["t0"]) * (1 - frac) / frac) if frac > 0.02 else None
        job.update(progress={"done": done, "total": total, "unit": "صفحة", "note": note, "pct": pct, "from_pct": last["pct"],
                             "eta_s": eta, "ts": now, "bundle": f'{st.get("i", 0) + 1}/{st.get("n", 1)}'})
        last.update(t=now, pct=pct)
        if done >= total and stage != "prep" and st.get("n", 1) == 1:   # انتهت قراءة كل الصفحات: تبدأ مرحلة التدقيق والمطابقة (80% فما فوق)
            job.set_state("matching", progress={"done": done, "total": total, "unit": "صفحة", "note": "", "pct": max(80.0, pct), "from_pct": pct, "ts": time.time()})
    return rep


def item_key(it: dict) -> str:
    keep = {k: str(it.get(k)) for k in ("reason", "sto", "invoice", "code", "qty", "price", "file", "page", "receipt_page", "receipt_file", "invoice_page")}
    return hashlib.sha1(json.dumps(keep, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


class Job:
    def __init__(self, job_id, root=None):
        self.id = job_id
        self.dir = os.path.join(root or ROOT, job_id)
        self.meta_path = os.path.join(self.dir, "job.json")

    # ---- الحالة
    def load(self):
        with open(self.meta_path, encoding="utf-8") as f:
            return json.load(f)

    def save(self, meta):
        with _LOCK:
            tmp = self.meta_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=1, default=str)
            for attempt in range(10):                       # مزامنة OneDrive قد تقفل الملف لحظياً (PermissionError): نعيد المحاولة قليلاً
                try:
                    os.replace(tmp, self.meta_path)
                    break
                except PermissionError:
                    if attempt == 9:
                        raise
                    time.sleep(0.3)

    def update(self, **kw):
        m = self.load()
        m.update(kw)
        self.save(m)
        return m

    def log(self, msg):
        m = self.load()
        m.setdefault("log", []).append(f"{_now()} {msg}")
        m["log"] = m["log"][-200:]
        self.save(m)

    def set_state(self, state, **kw):
        self.update(state=state, state_ar=STATE_AR[state], **kw)
        self.log(f"الحالة: {STATE_AR[state]}")


MAX_ZIP_MB = int(os.environ.get("MAX_ZIP_MB", "3000"))      # مجموع حجم الملفات بعد فك الضغط
MAX_ZIP_FILES = int(os.environ.get("MAX_ZIP_FILES", "600"))


def expand_uploads(paths, workdir):
    """يقبل ملفات PDF وملفات ZIP تحوي ربطات PDF؛ يعيد (قائمة مسارات PDF، ملاحظات للمستخدم).
    الأمان: أسماء الملفات المفكوكة تُسطَّح إلى الاسم الأخير فقط (لا مسارات ../ ولا مجلدات)، وغير PDF يُتجاهل مع ملاحظة،
    وحدّ لعدد الملفات ولمجموع الحجم بعد الفك (ضد القنابل الضاغطة). المكرر بالاسم يُرفض ملاحظةً ولا يُكتب فوق غيره."""
    import zipfile
    os.makedirs(workdir, exist_ok=True)
    out, notes, seen = [], [], set()
    for p in paths or []:
        if not str(p).lower().endswith(".zip"):
            out.append(p)
            seen.add(os.path.basename(p))
            continue
        try:
            zf = zipfile.ZipFile(p)
        except zipfile.BadZipFile:
            notes.append(f"الملف المضغوط {os.path.basename(p)} غير صالح")
            continue
        with zf:
            members = [i for i in zf.infolist() if not i.is_dir()]
            members = [i for i in members if "__MACOSX" not in i.filename and not os.path.basename(i.filename).startswith(".")]
            pdfs = [i for i in members if i.filename.lower().endswith(".pdf")]
            skipped = [os.path.basename(i.filename) for i in members if i not in pdfs]
            if len(pdfs) > MAX_ZIP_FILES or sum(i.file_size for i in pdfs) > MAX_ZIP_MB * 1024 * 1024:
                notes.append(f"الملف المضغوط {os.path.basename(p)} يتجاوز الحد المسموح ({MAX_ZIP_FILES} ملفاً أو {MAX_ZIP_MB}MB بعد الفك) ولم يُفك")
                continue
            n = 0
            for i in pdfs:
                name = os.path.basename(i.filename.replace("\\", "/"))
                if not name or name in seen:
                    notes.append(f"ملف مكرر الاسم تُجوهل نسخته: {name}")
                    continue
                dst = os.path.join(workdir, name)
                with zf.open(i) as src, open(dst, "wb") as f:
                    shutil.copyfileobj(src, f)
                out.append(dst)
                seen.add(name)
                n += 1
            notes.append(f"من {os.path.basename(p)}: فُكّ {n} ملف PDF" + (f"، وتُجوهل {len(skipped)} ملف غير PDF" if skipped else ""))
    return out, notes


def ensure_review_style(path):
    """ملف مخرجات مهمة أُنتج قبل اعتماد نمط المراجعة: يُنسَّق في مكانه (تنسيق ونتائج صيغ فقط؛ لا قيمة ولا صيغة تتغير). لا يمسّ التقارير القديمة ولا القوالب."""
    import openpyxl
    import report_style as RS
    if not path or not os.path.exists(path):
        return False
    wb = openpyxl.load_workbook(path)
    ok = True
    for ws in wb:
        hdr = RS.header_rows(ws)
        if hdr and not (ws.cell(hdr[0], 1).fill.fill_type == "solid" and ws.cell(hdr[0], 1).fill.fgColor.rgb == RS.HEADER_FILL):
            ok = False
    if ok:
        return False
    RS.finalize(wb, path)
    return True


def create_job(mode: str, contract_path: str, bundle_paths: list[str], root=None, owner="", synthetic: bool = False, truth_path: str | None = None, context_paths: list | None = None) -> Job:
    assert mode in ("batch", "competition")
    job_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    job = Job(job_id, root)
    os.makedirs(os.path.join(job.dir, "input"), exist_ok=True)
    os.makedirs(os.path.join(job.dir, "cache"), exist_ok=True)
    os.makedirs(os.path.join(job.dir, "out"), exist_ok=True)
    files = []
    for kind, p in ([("contract", contract_path)] if contract_path else []) + [("bundle", b) for b in bundle_paths] + [("context", c) for c in (context_paths or [])] + ([("truth", truth_path)] if truth_path else []):
        name = os.path.basename(p)
        dst = os.path.join(job.dir, "input", name if kind == "bundle" else ({"contract": "عقد_", "context": "سياق_"}.get(kind, "مرجع_نصي_") + name))
        shutil.copy2(p, dst)
        files.append({"kind": kind, "name": os.path.basename(dst), "orig": name, "size": os.path.getsize(dst), "sha256": sha256(dst)})
    job.save({"id": job_id, "mode": mode, "owner": owner, "synthetic": bool(synthetic), "created": _now(), "state": "uploaded", "state_ar": STATE_AR["uploaded"],
              "files": files, "progress": {"done": 0, "total": 0, "note": ""}, "review": {}, "pending": [], "decisions": {}, "log": [],
              "output": None, "check": None})
    job.log(f"رُفعت {len(bundle_paths)} ربطة وعقد ({mode})")
    return job


def check_files(job: Job) -> dict:
    """فحص الملفات: الصيغة، الأسماء، الحجم، طبقة النص (الممسوح يُحال)، اتساق رقم المنافسة."""
    m = job.load()
    problems, scanned, info = [], [], []
    comps = set()
    unnamed = []                                            # ربطات أسماؤها لا تتبع الصيغة المعتادة: لا خطأ، تُستخدم أسماؤها كما هي
    contract = next((f for f in m["files"] if f["kind"] == "contract"), None)     # اختياري في الدفعة والمنافسة
    # العقد اختياري في الدفعة والمنافسة: بدونه يُستنتج النمط من السندات ويُحال كل ما يخالفه (انظر engine.consistency_issues)
    bundles = [f for f in m["files"] if f["kind"] == "bundle"]
    if m["mode"] == "batch" and len(bundles) != 1:
        problems.append({"level": "error", "msg": f"فحص الدفعة يتطلب ربطة واحدة، وصل {len(bundles)}"})
    if m["mode"] == "competition" and len(bundles) < 1:
        problems.append({"level": "error", "msg": "لا توجد ربطات"})
    for f in ([contract] if contract else []) + bundles:
        path = os.path.join(job.dir, "input", f["name"])
        if f["size"] > MAX_FILE_MB * 1024 * 1024:
            problems.append({"level": "error", "file": f["name"], "msg": f"الحجم يتجاوز {MAX_FILE_MB}MB"})
            continue
        try:
            n = pdfx.page_count(path)
        except Exception as e:  # noqa: BLE001
            problems.append({"level": "error", "file": f["name"], "msg": f"ملف PDF غير صالح: {type(e).__name__}"})
            continue
        f["pages"] = n
        if f["kind"] == "bundle":
            mm = BUNDLE_RE.match(f["name"])
            if mm:                                           # الاسم المعتاد يعطي رقم المنافسة؛ وأي اسم آخر مقبول ولا يؤثر في المضمون
                comps.add(mm.group(1))
            else:
                unnamed.append(f["name"])
        # طبقة النص: عينة من أول صفحتين وآخر صفحة
        sample = sorted({1, min(2, n), n})
        empty = [p.n for p in pdfx.read_pdf(path, sample) if len(p.text.split()) < 15]
        if empty:
            scanned.append({"file": f["name"], "pages_sampled_without_text": empty})
    for f in [x for x in m["files"] if x["kind"] == "context"]:                      # ربطات مجاورة لمطابقة الفاتورة المشتركة (فحص الدفعة)
        path = os.path.join(job.dir, "input", f["name"])
        try:
            pdfx.page_count(path)
        except Exception as e:  # noqa: BLE001
            problems.append({"level": "error", "file": f["name"], "msg": f"ربطة السياق ليست PDF صالحاً: {type(e).__name__}"})
            continue
        mm = BUNDLE_RE.match(f["name"][len("سياق_"):])
        if mm and comps and mm.group(1) not in comps:
            problems.append({"level": "error", "file": f["name"], "msg": f"ربطة السياق من منافسة مختلفة ({mm.group(1)})"})
    if m["mode"] == "competition":
        nums = sorted(int(BUNDLE_RE.match(f["name"]).group(3)) for f in bundles if BUNDLE_RE.match(f["name"]))
        gaps = [k for k in range(nums[0], nums[-1] + 1) if k not in nums] if nums else []
        if gaps:
            problems.append({"level": "review", "msg": "ترقيم الربطات المرفوعة غير متصل (تنقص: " + "، ".join(f"{g:03d}" for g in gaps[:12]) +
                             "): قد تخص بنود فاتورة مشتركة سندات في الربطات الناقصة، ولا يُسجَّل «بند بلا سند» قبل اكتمال ربطات المنافسة"})
    if m["mode"] == "batch" and contract is None:
        problems.append({"level": "info", "msg": "فحص دفعة بدون عقد: يُعتمد السند الأول مرجعاً لنسبة العمولة وأساس الضريبة وتُعمَّم قاعدته على بقية السندات، وأي سند يخالفها يُحال للمراجعة. لا تُتحقق قواعد العقد ولا الغرامة ولا مبلغ السداد."})
    if unnamed:
        problems.append({"level": "info", "msg": "أسماء بعض الملفات لا تتبع صيغة رقم المنافسة-رقم الدفعة-رقم الربطة؛ لا يؤثر ذلك في الفحص (المضمون هو المعتمد). "
                         "تبقى خانتا رقم الدفعة والربطة فارغتين في التقرير حين لا يحملهما الاسم، ولا يُختلق لهما رقم.", "files": unnamed})
    if len(comps) > 1:
        problems.append({"level": "error", "msg": "الربطات من أكثر من منافسة: " + "، ".join(sorted(comps))})
    if scanned:
        problems.append({"level": "review", "msg": "صفحات بلا طبقة نصية (ممسوحة): الاستخراج بالنص المباشر غير كافٍ ويلزم مسار الرؤية/OCR",
                         "files": scanned})
    info.append({"bundles": len(bundles), "pages": sum(f.get("pages", 0) for f in bundles), "competition": sorted(comps)})
    chk = {"ok": not any(p["level"] == "error" for p in problems), "problems": problems, "info": info, "scanned": bool(scanned)}
    m["files"] = m["files"]
    job.save({**m, "check": chk})
    job.set_state("files_checked")
    return chk


def _decided(m, key):
    d = m["decisions"].get(key)
    return d and d["action"] in RESOLVED


_RUN_LOCKS: dict = {}
_RUN_LOCKS_GUARD = threading.Lock()


def reap(job: Job) -> dict:
    """A scan whose process is gone (the app was restarted or the computer slept) is marked failed with the reason,
    instead of showing «جارٍ الاستخراج» forever."""
    m = job.load()
    if m.get("state") in ("extracting", "matching") and m.get("pid"):
        try:
            import psutil
            alive = psutil.pid_exists(int(m["pid"])) and psutil.Process(int(m["pid"])).status() != psutil.STATUS_ZOMBIE
        except Exception:  # noqa: BLE001
            alive = True                                  # unknown: never fail a scan on a guess
        if not alive:
            job.set_state("failed", error="توقفت عملية الفحص قبل اكتمالها (أُعيد تشغيل التطبيق أو توقف الجهاز). أعد بدء الفحص.")
            return job.load()
    return m


def run_job(job: Job, workers: int | None = None, code_map=None) -> dict:
    """يمنع تشغيلين متزامنين لمهمة واحدة (كالضغط على «إعادة البناء» أثناء الفحص): يتسلسلان بدل أن يكتب أحدهما التقرير والآخر يقرؤه (BadZipFile)."""
    with _RUN_LOCKS_GUARD:
        lock = _RUN_LOCKS.setdefault(job.id, threading.Lock())
    with lock:
        return _run_job_locked(job, workers, code_map)


def _run_job_locked(job: Job, workers: int | None = None, code_map=None) -> dict:
    """تنفيذ المهمة كاملة بنقاط حفظ. آمن للاستدعاء مرة أخرى (يستأنف من النتائج المحفوظة)."""
    import competition_writer as CW
    import report_writer as RW
    try:
        m = job.load()
        if not m.get("check"):
            check_files(job)
            m = job.load()
        if not m["check"]["ok"]:
            job.set_state("failed", error="فشل فحص الملفات: " + "؛ ".join(p["msg"] for p in m["check"]["problems"] if p["level"] == "error"))
            return job.load()
        workers = workers or max(1, min(4, (os.cpu_count() or 2)))
        inp = os.path.join(job.dir, "input")
        cname = next((f["name"] for f in m["files"] if f["kind"] == "contract"), None)
        contract = os.path.join(inp, cname) if cname else None             # None: فحص دفعة بلا عقد
        bundles = [os.path.join(inp, f["name"]) for f in m["files"] if f["kind"] == "bundle"]
        by_key = {p["key"]: p for p in m.get("pending", [])}
        overrides = {"invoice_amount": {by_key[k]["sto"]: D(d["value"]) for k, d in m["decisions"].items()
                                        if d["action"] == "set_value" and k in by_key and by_key[k].get("sto") and d.get("value")}}
        t_start = time.time()
        job.set_state("extracting", progress={"done": 0, "total": len(bundles), "note": ""})

        st = {"i": 0, "n": len(bundles)}
        last_pct = {"v": 5.0}

        def prog(i, n, name):
            st.update(i=i, n=n)
            pct = round(5 + 75 * i / max(n, 1), 1)
            job.update(progress={"done": i, "total": n, "unit": "ربطة", "note": name, "pct": pct, "from_pct": last_pct["v"], "ts": time.time()})
            last_pct["v"] = pct

        out_name = ("تقرير فحص الدفعة " if m["mode"] == "batch" else "تقرير فحص المنافسة ") + \
                   (os.path.basename(bundles[0])[:-4] if m["mode"] == "batch" else
                    (lambda mm_: mm_.group(1) if mm_ else os.path.basename(bundles[0])[:-4])(BUNDLE_RE.match(os.path.basename(bundles[0])))) + ".xlsx"
        out_path = os.path.join(job.dir, "out", out_name)
        decided_keys = {k for k, d in m["decisions"].items() if d["action"] in RESOLVED}
        # «فيه مشكلة»: السند الذي أكّد المراجع أن فيه مشكلة لا يدخل التقرير
        exclude = {by_key[k]["sto"] for k, d in m["decisions"].items() if d["action"] == "reject" and k in by_key and by_key[k].get("sto")}
        import progress_hook as PH
        if m["mode"] == "batch":
            scanned = bool(m["check"].get("scanned"))
            # الربطة الممسوحة تُقرأ (OCR) داخل هذه المرحلة؛ والتقدّم الحقيقي يأتي من المُبلِّغ (صفحة بعد صفحة)
            job.set_state("extracting" if scanned else "matching", progress={"done": 0, "total": max(1, sum(f.get("pages", 0) for f in m["files"] if f["kind"] == "bundle")), "unit": "صفحة",
                                                                                       "note": "تجهيز الصفحات" if scanned else "", "pct": 5.0, "from_pct": 5.0, "ts": time.time()})
            ctx = [os.path.join(inp, f["name"]) for f in m["files"] if f["kind"] == "context"]
            PH.set_reporter(_make_reporter(job, {"i": 0, "n": 1}))
            try:
                path, unresolved = RW.write_batch_report(bundles[0], contract, out_path, code_map=code_map, overrides=overrides, resolved_keys=decided_keys, context_paths=ctx,
                                                         cache_dir=os.path.join(job.dir, "cache"), exclude_stos=exclude)
            finally:
                PH.set_reporter(None)
            if not contract and (RW.LAST_DATA or {}).get("no_contract_note"):
                job.update(note_ar=RW.LAST_DATA["no_contract_note"])             # تظهر في بطاقة المتابعة، وليست بند مراجعة حاجباً
        else:
            PH.set_reporter(_make_reporter(job, st))                       # يعمل حين تُقرأ الربطات في هذه العملية (ربطة واحدة أو workers=1)
            try:
                data = CW.collect_competition(bundles, contract, code_map, workers=(1 if len(bundles) == 1 else workers), progress=prog, cache_dir=os.path.join(job.dir, "cache"))
            finally:
                PH.set_reporter(None)
            job.set_state("matching")
            if data.get("no_contract_note"):
                job.update(note_ar=data["no_contract_note"])
            path, unresolved = CW.write_competition_report(bundles, contract, out_path, code_map=code_map, data=data, resolved_keys=decided_keys,
                                                         exclude_stos=exclude)
        def related_for(u):
            try:
                if m["mode"] == "batch":
                    b = RW.LAST_DATA["bundle"]
                else:
                    fname = u.get("file") or data["bundle_of"].get(u.get("sto"))
                    b = next(x for x in data["bundles"] if x.file == fname)
                rel = RW.related_pages(b, u.get("sto"), u.get("invoice"), u.get("page") or u.get("invoice_page"))
                if u.get("dup_file") and u.get("dup_page"):                       # الظهور الثاني للسند المكرر يُعرض مع الأول
                    rel.append({"label": "الظهور المكرر للسند", "file": u["dup_file"], "pages": [int(u["dup_page"])]})
                return rel
            except Exception:  # noqa: BLE001
                return []
        pending = []
        for u in unresolved:
            k = item_key(u)
            pending.append({"key": k, **u, "related": related_for(u), "decision": m["decisions"].get(k)})
        unresolved_open = [p for p in pending if not (p["decision"] and p["decision"]["action"] in RESOLVED)]
        job.update(output=path, pending=pending, open_count=len(unresolved_open))
        tr = next((f for f in m["files"] if f["kind"] == "truth"), None)
        if tr and m["mode"] == "batch":
            try:
                ev = evaluate_against_truth(job, contract, os.path.join(inp, tr["name"]), decided_keys)
                job.update(eval=ev, seconds=round(time.time() - t_start, 1))
                job.log("تقييم مقابل المرجع النصي: " + json.dumps(ev, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                job.log(f"تعذّر التقييم: {type(e).__name__}: {e}")
        if unresolved_open:
            job.set_state("awaiting_review")
        else:
            job.set_state("approved")
        return job.load()
    except Exception as e:  # noqa: BLE001
        import progress_hook as PH
        if isinstance(e, PH.Cancelled):
            job.set_state("failed", error="أُلغي الفحص بطلب المستخدم", cancelled=True)
        else:
            job.set_state("failed", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
        return job.load()


RESOLVED = ("set_value", "confirm_blank", "verified_ok", "reject")      # قرارات تحسم البند؛ reject = «فيه مشكلة» فيُستبعد سنده من التقرير


def review(job: Job, key: str, action: str, value: str | None = None, note: str = "", reviewer: str = "") -> dict:
    assert action in ("set_value", "confirm_blank", "cannot_decide", "verified_ok", "reject")
    if action == "set_value":
        D(value)                                    # يرفع استثناءً إن لم يكن رقماً
    m = job.load()
    m["decisions"][key] = {"action": action, "value": value, "note": note, "reviewer": reviewer, "time": _now()}
    # A decision on an audit finding is not a verified page-level training label.
    # Keep a separate review candidate, never append it to a training dataset.
    item = next((x for x in m.get('pending',[]) if x.get('key')==key), {})
    m.setdefault('label_review_candidates', {})[key] = {
        'decision': dict(m['decisions'][key]), 'source_finding': dict(item),
        'training_eligible': False, 'status': 'pending_field_label_review',
        'requires': ['source_image', 'field_locations', 'verified_target', 'split_check', 'explicit_label_approval']}
    job.save(m)
    job.log(f"قرار مراجعة {key}: {action}")
    return m


def approve_and_export(job: Job) -> str:
    """يعيد توليد التقرير بقرارات المراجعة، ويُصدِّر نهائياً فقط إن لم يبق بند غير محسوم."""
    m = run_job(job)
    if m["state"] == "approved":
        job.set_state("exported")
    return m["output"]


def evaluate_against_truth(job: Job, contract: str, truth_path: str, resolved: set) -> dict:
    """قياس لمهمة دفعة على ربطة اصطناعية: النسخة النصية المرجعية (نفس الصفحات بطبقة نص) مقابل ما قُرئ آلياً.
    لكل سند: مقبول/محال × صحيح/خاطئ. «المقبول الخاطئ» = خطأ مرّ دون إحالة. لا يدخل هذا في التقرير نفسه."""
    import report_writer as RW
    read = RW.LAST_DATA
    truth = RW.collect_batch(truth_path, contract)
    held = {s for s, k in read["review_stos"].items() if k not in resolved}
    held |= {u["sto"] for u in read.get("unresolved", []) if u.get("sto") and item_key(u) not in resolved}   # إحالة ربط/مبلغ الفاتورة باسم السند تُعدّ إحالة له
    sig = lambda d, s: (d["results"][s].net, d["results"][s].commission, d["results"][s].vat, d["results"][s].total, d["results"][s].payable,
                        d["receipts"][s].pon, d["receipts"][s].invoice_no,
                        [(i.code, i.qty, i.unit_price) for i in d["receipts"][s].items],
                        (d["attribution"].get(s) or {}).get("amount"))
    c = {"سندات المرجع": len(truth["results"]), "غير مقروءة": 0, "مقبولة صحيحة": 0, "مقبولة خاطئة (مرّت دون إحالة)": 0,
         "محالة وصحيحة (إحالة زائدة)": 0, "محالة وخاطئة (أُحيلت فعلاً)": 0, "سندات زائدة غير موجودة في المرجع": 0}
    wrong = []
    for s in truth["results"]:
        if s not in read["results"]:
            c["غير مقروءة"] += 1
            continue
        ok = sig(truth, s) == sig(read, s)
        key = ("محالة " if s in held else "مقبولة ") + ("صحيحة" if ok else "خاطئة")
        key = {"محالة صحيحة": "محالة وصحيحة (إحالة زائدة)", "محالة خاطئة": "محالة وخاطئة (أُحيلت فعلاً)", "مقبولة صحيحة": "مقبولة صحيحة",
               "مقبولة خاطئة": "مقبولة خاطئة (مرّت دون إحالة)"}[key]
        c[key] += 1
        if key.startswith("مقبولة خاطئة"):
            wrong.append(s)
    c["سندات زائدة غير موجودة في المرجع"] = sum(1 for s in read["results"] if s not in truth["results"])
    c["مقبولة خاطئة: السندات"] = wrong
    return c


def cleanup(root=None, days=None):
    root = root or ROOT
    days = days if days is not None else RETENTION_DAYS
    cutoff = time.time() - days * 86400
    n = 0
    for d in glob.glob(os.path.join(root, "*")):
        if os.path.isdir(d) and os.path.getmtime(d) < cutoff:
            shutil.rmtree(d, ignore_errors=True)
            n += 1
    return n


def list_jobs(root=None):
    out = []
    for p in sorted(glob.glob(os.path.join(root or ROOT, "*", "job.json")), reverse=True):
        try:
            with open(p, encoding="utf-8") as f:
                m = json.load(f)
            out.append(m)
        except Exception:  # noqa: BLE001
            pass
    return out
