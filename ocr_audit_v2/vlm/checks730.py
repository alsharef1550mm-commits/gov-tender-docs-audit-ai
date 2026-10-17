"""الفحوص المتبقية على قراءات 730 المتفق عليها: ضريبة الصنف، الغرامة من موعد التعميد الممسوح، وربط الفاتورة وإدراج السند.

كل فحص يعمل على قيم مقروءة بإجماع قارئين، ويُنتج «علامة» وليس حكماً؛ الحكم للمراجع. المطبوع منفصل عن المحسوب.
  ITEM   صفّ البند: الصافي = كمية×سعر، العمولة = 4%، الضريبة = (نسبة 0 ⇒ 0، وإلا 15% من الصافي+العمولة)، الإجمالي = الثلاثة؛
         وفي السند: مجموع صفوف الصافي = الصافي المطبوع، ومجموع الضرائب = ضريبة السند.
  PEN    الغرامة = 1% × الصافي × ceil(أيام التأخير/7) من تاريخ الاستلام وموعد التعميد، مقابل «الغرامة المسجلة» المطبوعة.
  INVNO  رقم الفاتورة المطبوع في السند ∈ أرقام فواتير الربطة (من صفحات الفواتير المصنَّفة).
  LIST   السند مُدرج في جدول السندات بالفاتورة الجماعية (حيث وُجد جدول)، وصافيه فيه = صافي السند.
  XDOC   بنود السند مقابل بنود صفحة فاتورة التوريد بالتعميد نفسه (كمية/سعر).
الموعد: تعميد ممسوح (OCR) + نص العقد؛ يُقبل عند تطابق المصدرين.
"""
import glob
import io
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import consensus as C  # noqa: E402
import scan_parse  # noqa: E402
import verify as V  # noqa: E402
from datetime import date  # noqa: E402

D = Decimal
TOL = D("0.01")


def d_(x):
    try:
        return D(str(x).replace(",", ""))
    except Exception:  # noqa: BLE001
        return None


def r2(x):
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def iso(s):
    try:
        y, m, d = (int(x) for x in re.split(r"[-/]", s))
        return date(y, m, d)
    except Exception:  # noqa: BLE001
        return None


def po_due_dates():
    """موعد التوريد من كل تعميد ممسوح (OCR). المفتاح رقم التعميد من اسم الملف (تُذكر هذه الحدود)."""
    out = {}
    for f in glob.glob(os.path.join(ROOT, "out", "scan", "PON00000730??", "p1.json")):
        js = json.load(open(f, encoding="utf-8"))
        text = "\n".join(scan_parse.page_lines(js))
        m = re.search(r"موعد للتوريد:?\s*(\d{4}/\d{2}/\d{2})", text)
        out[os.path.basename(os.path.dirname(f))] = iso(m.group(1)) if m else None
    return out


def contract_facts():
    js = json.load(open(os.path.join(ROOT, "out", "scan", "عقد المنافسة", "p2.json"), encoding="utf-8"))
    text = "\n".join(scan_parse.page_lines(js))
    m = re.search(r"آخر موعد لتوريد كل تعميد هو (\d{4}/\d{2}/\d{2})", text)
    js1 = json.load(open(os.path.join(ROOT, "out", "scan", "عقد المنافسة", "p1.json"), encoding="utf-8"))
    t1 = "\n".join(scan_parse.page_lines(js1))
    m2 = re.search(r"شامل نوبكو والضريبة\s*([\d,]+\.\d{2})", t1)
    return {"due": iso(m.group(1)) if m else None, "total": d_(m2.group(1)) if m2 else None}


def pick(readings, key):
    """أول قيمة لها قارئان متفقان (بالصيغة المطبَّعة)، وإلا None."""
    votes = Counter(str(r.get(key)) for r in readings.values() if r and r.get(key))
    for v, n in votes.most_common(1):
        if n >= 2:
            return v
    return None


def rows_of(readings, reader):
    r = readings.get(reader) or {}
    return r.get("items_full") or []


def agreed_rows(readings):
    """صفوف Paddle (فيها النسبة والضريبة) التي يؤيد Qwen كودها وكميتها وسعرها."""
    q = {(i.get("item_code"), C.norm_field("qty", i.get("qty")), C.norm_field("unit_price", i.get("unit_price"))) for i in rows_of(readings, "qwen")}
    out = []
    for i in rows_of(readings, "paddle"):
        key = (i.get("item_code"), C.norm_field("qty", i.get("qty")), C.norm_field("unit_price", i.get("unit_price")))
        out.append((i, key in q))
    return out


def main():
    cons = V.run("730")
    facts = contract_facts()
    dues = po_due_dates()
    img = json.load(open(os.path.join(ROOT, "gold", "730_printed_verified.json"), encoding="utf-8"))["receipts"]
    # صفحات الفواتير وصفحات السندات لكل ملف
    inv_by_file = defaultdict(list)
    for pid, v in cons.items():
        if v["accepted"].get("type") == "invoice":
            inv_by_file[v["file"]].append(v)
    flags = defaultdict(list)
    receipts = {}
    for pid, v in cons.items():
        if v["accepted"].get("type") != "receipt":
            continue
        rd, acc = v["readings"], v["accepted"]
        sto = acc.get("receipt_no")
        if not sto:
            continue
        receipts[sto] = v
        net, vat = d_(acc.get("net")), d_(acc.get("vat"))
        # --- REL: علاقات العمولة/الإجمالي من طبقة التحقق (المطبوع مقابل المحسوب)
        for fld, code in (("commission", "REL_COMM"), ("total", "REL_TOTAL")):
            for w in v["fields"][fld]["why"]:
                if w.startswith("تعارض مطبوع"):
                    flags[sto].append((code, w))
        # --- ITEM
        rows = agreed_rows(rd)
        good = [i for i, ok in rows if ok]
        if len(good) != len(rows) or not rows:
            flags[sto].append(("ITEM_UNAGREED", f"{len(rows) - len(good)} من {len(rows)} صفوف بلا تأييد من قارئ ثانٍ"))
        s_net = s_vat = D(0)
        for i in good:
            q, p = d_(i.get("qty")), d_(i.get("unit_price"))
            n, c, vt = d_(i.get("net")), d_(i.get("commission")), d_(i.get("vat"))
            rate = d_(i.get("rate"))
            code = i.get("item_code")
            if None in (q, p, n):
                continue
            s_net += n
            if abs(q * p - n) > TOL:
                flags[sto].append(("ITEM_NET", f"{code}: كمية {q} × سعر {p} = {q * p} والصافي المطبوع {n}"))
            if c is not None and abs(c - r2(n * D("0.04"))) > TOL:
                flags[sto].append(("ITEM_COMM", f"{code}: عمولة {c} والمحسوبة {r2(n * D('0.04'))}"))
            if vt is not None and rate is not None and c is not None:
                s_vat += vt
                exp = D(0) if rate == 0 else r2((rate / 100) * (n + c))
                if abs(vt - exp) > TOL:
                    flags[sto].append(("ITEM_TAX", f"{code}: نسبة {rate}% والضريبة المطبوعة {vt} والمحسوبة {exp}"))
        if good and net is not None and abs(s_net - net) > TOL:
            flags[sto].append(("SUM_NET", f"مجموع صفوف الصافي {s_net} والصافي المطبوع {net}"))
        if good and vat is not None and abs(s_vat - vat) > TOL:
            flags[sto].append(("SUM_VAT", f"مجموع ضرائب الصفوف {s_vat} وضريبة السند المطبوعة {vat}"))
        # --- PEN
        rdate, pon = iso(acc.get("date") or ""), acc.get("po_no")
        due = dues.get(pon)
        if due and facts["due"] and due != facts["due"]:
            due = None      # مصدران متعارضان: لا فحص
        pen_printed = d_(acc.get("penalty"))
        if rdate and due and net is not None and pen_printed is not None:
            late = max(0, (rdate - due).days)
            exp = r2(net * D("0.01") * math.ceil(late / 7)) if late else D(0)
            if abs(exp - pen_printed) > TOL:
                flags[sto].append(("PEN", f"تأخر {late} يوماً: الغرامة المحسوبة {exp} والمسجلة {pen_printed}"))
        elif not (rdate and due and pen_printed is not None):
            flags[sto].append(("PEN_UNCHECKED", f"تعذّر: تاريخ {rdate}، موعد {due}، غرامة مسجلة {pen_printed}"))
        # --- INVNO / LIST / XDOC
        invs = inv_by_file.get(v["file"], [])
        nums = {i["accepted"].get("invoice_no") for i in invs if i["accepted"].get("invoice_no")}
        printed_inv = acc.get("invoice_no")
        if nums and printed_inv and printed_inv not in nums:
            flags[sto].append(("INVNO", f"رقم الفاتورة {printed_inv} ليس بين فواتير الربطة {sorted(nums)}"))
        listed = None
        for i in invs:
            lst = [x for r in i["readings"].values() if r for x in (r.get("listing") or []) if x.get("net") is not None]
            if lst:
                listed = (listed or []) + lst
        if listed is not None:
            hit = [x for x in listed if x["sto"] == sto]
            if not hit:
                flags[sto].append(("LIST", "السند غير مدرج في جدول السندات بالفاتورة الجماعية"))
            elif net is not None and abs(d_(hit[0]["net"]) - net) > TOL:
                flags[sto].append(("LIST_NET", f"صافي السند في الفاتورة {hit[0]['net']} ومطبوع {net}"))
        def sig(rs):
            return sorted((r.get("item_code"), C.norm_field("qty", r.get("qty")), C.norm_field("unit_price", r.get("unit_price"))) for r in rs)

        # صفحات فواتير التوريد بالتعميد نفسه: يكفي أن يقرأ أي قارئ رقم التعميد، وصفوفها يؤيدها قارئان (Paddle+Qwen)
        # فاتورة التوريد تطبع رقم السند صراحة (تحققت من صور 04 ص5 و06 ص5)، فيُفضَّل القرن به؛ والتعميد احتياط
        def pages_for(match):
            out = []
            for i in invs:
                if any(r and match(r) for r in i["readings"].values()):
                    g = [r for r, ok in agreed_rows(i["readings"]) if ok]
                    if g:
                        out.append(sig(g))
            return out
        cands = pages_for(lambda r: r.get("receipt_no") == sto) or pages_for(lambda r: r.get("po_no") == pon)
        if cands and good:
            mine = sig(good)
            if all(c != mine for c in cands):
                near = min(cands, key=lambda c: sum(a != b for a, b in zip(c, mine)))
                diffs = [(a, b) for a, b in zip(mine, near) if a != b]
                flags[sto].append(("XDOC", f"بنود السند تخالف فاتورة التوريد: السند {diffs[0][0]} والفاتورة {diffs[0][1]}" if diffs else "اختلاف في عدد الصفوف"))
    bad9 = set(img)
    # ----------------------------------------------------------------- النتائج
    gold_ok = {s for s in receipts if s not in bad9}
    CODES = ("REL_COMM", "REL_TOTAL", "ITEM_NET", "ITEM_COMM", "ITEM_TAX", "SUM_NET", "SUM_VAT", "PEN", "INVNO", "LIST", "LIST_NET", "XDOC")
    hard = {s: [f for f in fl if f[0] in CODES] for s, fl in flags.items()}
    flagged = {s for s, fl in hard.items() if fl}
    print(f"== فحوص 730 على {len(receipts)} سنداً | موعد التعميد: {', '.join(f'{k[-4:]}={v}' for k, v in sorted(dues.items()))} | العقد: {facts['due']} | إجمالي العقد {facts['total']}")
    print(f"سندات بعلامة: {len(flagged)} | من التسعة المعروفة: {len(flagged & bad9)}/9 | علامات على سندات 'سليمة' في التقرير: {len(flagged - bad9)}")
    print("\nالتسعة:")
    for s in sorted(bad9):
        print(f"  {s}  {'✔' if hard.get(s) else '✘'}  {[f[0] for f in hard.get(s, [])]}  |  {img[s]['printed_inconsistency'][:60]}")
    print("\nعلامات على غير التسعة (للمراجعة؛ ليست كلها أخطاء):")
    for s in sorted(flagged - bad9):
        for f in hard[s]:
            print(f"  {s} {f[0]}: {f[1]}")
    unc = Counter(f[0] for fl in flags.values() for f in fl if f[0] in ("PEN_UNCHECKED", "ITEM_UNAGREED"))
    print("\nتعذّر الفحص:", dict(unc))
    print("حالات PEN لم تُفحص: ", sorted(s for s, fl in flags.items() if any(f[0] == "PEN_UNCHECKED" for f in fl))[:10])
    return flags


if __name__ == "__main__":
    main()
