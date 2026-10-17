"""طبقة التحقق فوق الإجماع: «اقتراح» (قارئان فأكثر) ثم «مُتحقَّق» فقط عند استيفاء شروط الحقل الحرج، وإلا «إحالة».

شروط التحقق (كلها لازمة):
  نوع المستند: اتفق عليه قارئان فأكثر.
  رقم السند/التعميد/الفاتورة: صيغة صحيحة + وُضع في خانته الصحيحة عند قارئ منظَّم واحد على الأقل (أو شريط الهوية المقصوص)
      + ربط: التعميد بصفحة تعميد في الملف نفسه، والفاتورة بصفحة فاتورة تحمل الرقم نفسه (أو الصفحة نفسها من النوع المناسب).
  الصافي/العمولة/الإجمالي: علاقتها الحسابية سليمة (عمولة = 4% من الصافي؛ إجمالي = صافي + عمولة + ضريبة).
القيمة المطبوعة (printed) تبقى منفصلة عن المحسوبة (computed)، وتعارضهما يُسجَّل «تعارض مطبوع» ولا يُصحَّح.
"""
import io
import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import consensus as C  # noqa: E402

CRITICAL = ("receipt_no", "po_no", "invoice_no", "net", "commission", "total")
TOL = Decimal("0.01")
# الحقول التي تنطبق على كل نوع صفحة؛ غيرها «لا ينطبق» لا «إحالة». (التعميد: رقمه وإجمالياته فقط)
APPLIES = {
    "receipt": {"receipt_no", "po_no", "invoice_no", "net", "commission", "total"},
    "invoice": {"invoice_no", "net", "commission", "total"},
    "purchase_order": {"po_no", "net", "total"},
}
STATUSES = ("verified", "proposed", "referred", "absent", "na")
# verified: تحقق الشروط | proposed: قارئان اتفقا لكن شرط ناقص | referred: قرّاء قرؤوا قيماً دون اتفاق أو قارئ واحد
# absent: لا قارئ وجد قيمة (قد تكون غير موجودة في الصفحة، كإجماليات تعميد متعدد الصفحات) | na: الحقل لا ينطبق على هذا النوع


def D(x):
    return None if x is None else Decimal(x)


def q2(x):
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def run(set_name):
    cons = C.run(set_name)
    # فهارس الربط داخل كل ملف: ما اقتُرح على صفحات التعميد/الفواتير
    po_pages, inv_pages = {}, {}
    for pid, v in cons.items():
        a = v["accepted"]
        if a.get("type") == "purchase_order" and a.get("po_no"):
            po_pages.setdefault(v["file"], set()).add(a["po_no"])
        if a.get("type") == "invoice" and a.get("invoice_no"):
            inv_pages.setdefault(v["file"], set()).add(a["invoice_no"])
    for pid, v in cons.items():
        a, rd = v["accepted"], v["readings"]
        ptype = a.get("type")
        out = {}
        for f in CRITICAL:
            val = a.get(f)
            cands = {k: (r or {}).get(f) for k, r in rd.items()}
            st = {"printed": val, "computed": None, "status": "referred", "why": [], "candidates": cands}
            if ptype and f not in APPLIES.get(ptype, set()):
                st["status"], st["why"] = "na", [f"لا ينطبق على صفحة من نوع {ptype}"]
                out[f] = st
                continue
            if val is None:
                if any(cands.values()):
                    st["why"].append("لا اتفاق بين قارئين")           # قُرئ ولم يُتفق: إحالة
                else:
                    st["status"], st["why"] = "absent", ["لم يقرأه أي قارئ"]
                    if not ptype:
                        st["why"].append("ونوع الصفحة غير متفق عليه")
                out[f] = st
                continue
            st["status"] = "proposed"
            why = []
            if not ptype:
                why.append("نوع المستند غير متفق عليه")
            if f in ("receipt_no", "po_no", "invoice_no"):
                slot_ok = any(f in ((r or {}).get("slots") or {}).get(f, set()) for k, r in rd.items()
                              if r and (r.get(f) == val))
                if not slot_ok:
                    why.append("لا قارئ وضعه تحت عنوانه الصحيح")
                if f == "receipt_no" and ptype != "receipt":
                    why.append("ليست صفحة سند")
                if f == "po_no" and not (ptype == "purchase_order" or val in po_pages.get(v["file"], set())):
                    why.append("لا صفحة تعميد بالرقم نفسه في الملف")
                if f == "invoice_no" and not (ptype == "invoice" or val in inv_pages.get(v["file"], set())):
                    why.append("لا صفحة فاتورة بالرقم نفسه في الملف")
            else:
                n, c, t, vat = D(a.get("net")), D(a.get("commission")), D(a.get("total")), D(a.get("vat"))
                if f in ("net", "commission"):
                    if n is None or c is None:
                        why.append("الزوج صافي/عمولة غير مكتمل")
                    else:
                        exp = q2(n * Decimal("0.04"))
                        st["computed"] = str(exp) if f == "commission" else None
                        if abs(c - exp) > TOL:
                            why.append(f"تعارض مطبوع: العمولة {c} والمحسوبة {exp}")
                else:  # total
                    vat_val = vat if vat is not None else (Decimal(0) if (rd.get("qwen") or {}).get("vat") == "0" else None)
                    if n is None or c is None or vat_val is None:
                        why.append("الصافي أو العمولة أو الضريبة غير مقبولة بإجماع")
                    else:
                        exp = n + c + vat_val
                        st["computed"] = str(exp)
                        if abs(t - exp) > TOL:
                            why.append(f"تعارض مطبوع: الإجمالي {t} والمحسوب {exp}")
            st["why"] = why
            st["status"] = "verified" if not why else "proposed"
            out[f] = st
        v["fields"] = out
    return cons


def summary(cons, only=None):
    rows = {}
    for f in CRITICAL:
        c = {k: 0 for k in STATUSES}
        for v in cons.values():
            if only and not only(v):
                continue
            c[v["fields"][f]["status"]] += 1
        rows[f] = c
    return rows


def rates(rows):
    """نسب على الحقول المنطبقة فقط (بلا «لا ينطبق»). المقام = مُتحقَّق + مقترح + مُحال + غائب."""
    tot = {k: sum(r[k] for r in rows.values()) for k in STATUSES}
    den = sum(tot[k] for k in ("verified", "proposed", "referred", "absent"))
    return tot, den


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    s = sys.argv[1] if len(sys.argv) > 1 else "real"
    cons = run(s)
    dst = os.path.join(os.path.dirname(HERE), "out", f"verified_{s}.json")
    json.dump(cons, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    for f, c in summary(cons).items():
        print(f"{f:11s} {c}")
