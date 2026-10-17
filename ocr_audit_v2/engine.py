"""محرك الحساب والتدقيق: Decimal فقط، والقواعد من نص العقد نفسه.

لا يستخدم نموذجاً لغويّاً. كل فرق يُسجَّل بالقيمة المطبوعة والمحسوبة والدليل.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pdfx
from extract import Bundle, Receipt, Invoice, PO, norm_ar, num, D

TOL = D("0.005")


def r2(x: D) -> D:
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- قواعد العقد
@dataclass
class Rules:
    competition: str
    commission: D = D("0.04")
    vat_rate: D = D("0.15")
    tax_mode: str = "unknown"      # none | full_net | full_net_comm | partial_net | partial_net_comm | unknown
    late_weekly: D = D("0.01")        # 1% من صافي الأصناف المتأخرة عن كل أسبوع «أو جزء منه» (نص عقد 730 ص2)
    late_cap: D = D("0.06")           # سقف تراكمي 6% من إجمالي العقد (لا من الجزء المتأخر)
    contract_total: D | None = None   # إجمالي العقد من نصه؛ بدونه لا يُطبَّق السقف ويُعلَن
    evidence: dict = field(default_factory=dict)
    no_contract: bool = False         # فحص دفعة بلا عقد: لا تُحسب غرامة ولا تُقرأ قاعدة الضريبة من نص؛ تُستنتج الأساس من المطبوع ويُحال الأمر للمراجع


def read_rules(contract_pdf: str | None, competition: str) -> Rules:
    if not contract_pdf:
        # بلا عقد: العمولة 4% (قاعدة العقود المتاحة) والضريبة 15% (نظامية) افتراضان معلنان، وأساس الضريبة يُستنتج من المطبوع لكل سند
        return Rules(competition, tax_mode="inferred", no_contract=True)
    n = pdfx.page_count(contract_pdf)
    pages = pdfx.read_pdf(contract_pdf, [x for x in (1, 2, 3) if x <= n])
    rules = Rules(competition)
    for p in pages:
        for l in p.lines:
            t = norm_ar(l.text)
            if "وعاء" in t and "الضريبه" in t and "=" in t and "المضافه" not in t and "المحتسبه" not in t:
                partial = "المحدده" in t
                comm = ("1.04" in t) or ("نوبكو" in t)
                m = re.match(r"^\s*([\d,]+\.\d{2})", t)
                zero = bool(m and num(m.group(1)) == 0)
                if zero:
                    mode = "none"
                else:
                    mode = ("partial_" if partial else "full_") + ("net_comm" if comm else "net")
                rules.tax_mode = mode
                rules.evidence["tax"] = (p.n, l.text)
            if "وعاء" in t and "المحتسبه" in t:       # الصيغة الصفرية: "0.00 وعاء الضريبة المحتسبة في النموذج"
                m = re.match(r"^\s*([\d,]+\.\d{2})", t)
                if m and num(m.group(1)) == 0:
                    rules.tax_mode = "none"
                    rules.evidence["tax"] = (p.n, l.text)
            if "غرامه" in t and "تاخير" in t and "%" in t:
                rules.evidence["late"] = (p.n, l.text)
            # إجمالي العقد: سطر المعادلة «الإجمالي = الصافي + نوبكو + الضريبة» تسبقه القيمة
            if "=" in t and "جمالي" in t and "الضريبه" in t and "وعاء" not in t and "المضافه" not in t:
                m = re.match(r"^\s*([\d,]+\.\d{2})", t)
                if m and rules.contract_total is None:
                    rules.contract_total = num(m.group(1))
                    rules.evidence["contract_total"] = (p.n, l.text)
    return rules


# بعد حساب غرامة كل سند، نطبق الحد الأقصى التراكمي للغرامة (6% من إجمالي
# العقد).
def apply_cumulative_cap(results: list["Result"], rules: Rules) -> list[Issue]:
    """يطبّق سقف الغرامة التراكمي (6% من إجمالي العقد) ويوزعه بترتيب تاريخ الاستلام ثم رقم السند، كما ينص عقد 730.

    يعدّل penalty/payable في النتائج ويعيد ملاحظات؛ إن لم يُعرف إجمالي العقد يعيد تنبيهاً ولا يخفّض شيئاً.
    """
    notes: list[Issue] = []
    if rules.no_contract:
        return notes                                   # الغرامة في فحص بلا عقد تؤخذ كما طُبعت ولا يُطبَّق عليها سقف
    total_pen = sum((r.penalty for r in results), D(0))
    if total_pen == 0:
        return notes
    if rules.contract_total is None:
        notes.append(Issue("cap_unknown", "إجمالي العقد غير مقروء؛ لم يُطبَّق سقف الغرامة التراكمي"))
        return notes
    # الحد الأقصى يُحسب من إجمالي العقد كله، وليس من الجزء المتأخر.
    cap = r2(rules.contract_total * rules.late_cap)
    left = cap
    # نوزع الحد الأقصى على السندات حسب تاريخ الاستلام ثم رقم السند، ونخفض
    # الغرامة إذا زادت عن المتبقي.
    for r in sorted((x for x in results if x.penalty > 0), key=lambda x: (x.date or "", x.sto)):
        allowed = min(r.penalty, left)
        if allowed != r.penalty:
            notes.append(Issue("cap_applied", f"{r.sto}: الغرامة {r.penalty} خُفّضت إلى {allowed} بسقف {cap}", r.penalty, allowed))
            r.payable += r.penalty - allowed
            r.penalty = allowed
        left -= allowed
    return notes


# ---------------------------------------------------------------- نتيجة السند
@dataclass
class Issue:
    code: str
    text: str
    printed: object = None
    computed: object = None
    page: int | None = None


@dataclass
class Result:
    sto: str
    pon: str | None
    invoice_no: str | None
    date: str | None
    pages: list[int]
    net: D
    commission: D
    vat: D
    total: D
    penalty: D
    payable: D
    late_days: int
    issues: list[Issue]
    items: list[dict]

    @property
    def ok(self) -> bool:
        return not self.issues


def _d(s: str | None) -> date | None:
    try:
        y, m, d = (int(x) for x in s.split("-"))
        return date(y, m, d)
    except Exception:
        return None


def _infer_tax_mode(rows, printed, rules):
    """فحص بلا عقد: أساس الضريبة (الصافي أو الصافي مع العمولة) من أيهما يعيد إنتاج ضريبة السند المطبوعة؛ وإلا الافتراضي «الصافي والعمولة»
    فيظهر الفرق ملاحظةً. خضوع الصنف يؤخذ من نسبة الضريبة المطبوعة في سطره لا من العقد."""
    pv = printed.get("vat")
    if pv is not None:
        for mode in ("partial_net_comm", "partial_net"):
            tot = sum((r2((r["net"] + (r["comm"] if mode.endswith("comm") else D(0))) * rules.vat_rate) for r in rows if r["taxable"]), D(0))
            if abs(tot - pv) <= TOL:
                return mode
    return "partial_net_comm"


# تدقيق سند استلام واحد. المدخلات: السند، وقواعد العقد، والتعاميد،
# والفواتير. المخرج: نتيجة فيها الحسابات والملاحظات.
def check_receipt(r: Receipt, rules: Rules, pos: dict[str, PO], invoices: dict[str, Invoice],
                  inv_by_sto: dict[str, Invoice]) -> Result:
    issues: list[Issue] = []
    po = pos.get(r.pon or "")
    po_items = {i.code: i for i in (po.items if po else [])}
    items_out = []
    net_sum = D(0)
    comm_sum = D(0)
    vat_sum = D(0)
    late_value = D(0)
    due = None
    late_days = 0
    rd = _d(r.date)

    full_net = D(0)
    # نمر على أصناف السند صنفاً صنفاً، نحسب صافي كل صنف ونقارن بياناته
    # بالتعميد.
    for it in r.items:
        pi = po_items.get(it.code)
        price = it.unit_price
        if pi is None:
            issues.append(Issue("item_not_in_po", f"الصنف {it.code} غير موجود في التعميد {r.pon}", it.code, None, it.ev.page))
        else:
            if pi.unit_price != it.unit_price:
                issues.append(Issue("price_vs_po", f"سعر {it.code} في السند يخالف التعميد", it.unit_price, pi.unit_price, it.ev.page))
            price = pi.unit_price
        # صافي الصنف = الكمية × سعر التعميد، وعمولة نوبكو 4% من الصافي، والتقريب
        # إلى هللتين.
        net = r2(it.qty * price)
        comm = r2(net * rules.commission)
        taxable = (it.vat_rate or D(0)) > 0
        if pi is not None and pi.total and (pi.vat > 0) != taxable:
            issues.append(Issue("taxable_vs_po", f"خضوع {it.code} للضريبة يختلف بين السند والتعميد", it.vat_rate, pi.vat, it.ev.page))
        items_out.append({"code": it.code, "qty": it.qty, "price": price, "net": net, "comm": comm, "taxable": taxable, "page": it.ev.page})
        net_sum += net
        comm_sum += comm
        full_net += net
        if pi and pi.due and rd and _d(pi.due) and rd > _d(pi.due):
            late_value += net
            due = _d(pi.due)

    # الضريبة حسب نص العقد
    # أساس الضريبة يأتي من نمط العقد المستخرج من نصه: بلا ضريبة، أو على
    # الصافي، أو على الصافي مع العمولة، أو على الأصناف الخاضعة فقط.
    mode = _infer_tax_mode(items_out, r.printed, rules) if (rules.no_contract and rules.tax_mode == "inferred") else rules.tax_mode
    # ضريبة الصنف 15% من أساسه، ثم إجمالي الصنف.
    for row in items_out:
        base = D(0)
        if mode == "none":
            base = D(0)
        elif mode == "full_net":
            base = row["net"]
        elif mode == "full_net_comm":
            base = row["net"] + row["comm"]
        elif mode == "partial_net":
            base = row["net"] if row["taxable"] else D(0)
        elif mode == "partial_net_comm":
            base = (row["net"] + row["comm"]) if row["taxable"] else D(0)
        row["vat"] = r2(base * rules.vat_rate)
        row["total"] = row["net"] + row["comm"] + row["vat"]
        vat_sum += row["vat"]
    # إجمالي السند = صافي الأصناف + عمولتها + ضريبتها.
    total = net_sum + comm_sum + vat_sum
    if mode == "unknown":
        issues.append(Issue("rule_unknown", "تعذّر استخراج قاعدة الضريبة من العقد"))

    # الغرامة
    # غرامة التأخير: إذا جاء الاستلام بعد موعد التوريد في التعميد نحسب أيام
    # التأخير ونحولها إلى أسابيع (الأسبوع أو جزء منه).
    if due and rd and rd > due:
        late_days = (rd - due).days
        weeks = math.ceil(late_days / 7)          # «أسبوع أو جزء منه»: اليوم الواحد = أسبوع كامل
        penalty = r2(late_value * rules.late_weekly * weeks)   # السقف تراكمي: apply_cumulative_cap
    else:
        penalty = D(0)
    if rules.no_contract:                                  # بلا عقد لا نسبة غرامة ولا سقف: القيمة المطبوعة كما هي وتُذكر في بند المراجعة
        penalty = r.printed.get("penalty", D(0))
        late_days = int(r.printed["late_days"]) if "late_days" in r.printed else late_days
    # المستحق = الإجمالي ناقص الغرامة. هذا مبلغ مستحق، ولا يثبت أن السداد
    # تم.
    payable = total - penalty

    # من هنا نقارن المحسوب بالمطبوع في السند، ونحتفظ بالقيمتين منفصلتين دون
    # أن تحل إحداهما محل الأخرى.
    p = r.printed

    # دالة مساعدة: تقارن القيمة المطبوعة بالمحسوبة، وتسجل ملاحظة إذا اختلفتا
    # أو إذا لم تُقرأ القيمة المطبوعة.
    def cmp(key: str, computed: D, code: str, label: str):
        if key in p and abs(p[key] - computed) > TOL:
            issues.append(Issue(code, f"{label} مطبوع {p[key]} والمحسوب {computed}", p[key], computed,
                                r.summary_ev.page if r.summary_ev else None))
        elif key not in p:
            issues.append(Issue(code + "_missing", f"{label} غير مقروء في السند", None, computed))

    # مقارنة الصافي والعمولة والضريبة والإجمالي المطبوعة في السند بالمحسوبة.
    cmp("net", net_sum, "net", "صافي السند")
    cmp("nupco", comm_sum, "commission", "عمولة نوبكو")
    cmp("vat", vat_sum, "vat", "ضريبة السند")
    cmp("total", total, "total", "إجمالي السند")
    # مقارنة الغرامة وأيام التأخير المطبوعة بما حسبناه من التواريخ.
    if "penalty" in p and abs(p["penalty"] - penalty) > TOL:
        issues.append(Issue("penalty", f"غرامة التأخير مطبوعة {p['penalty']} والمحسوبة {penalty} (تأخر {late_days} يوماً)",
                            p["penalty"], penalty, r.summary_ev.page if r.summary_ev else None))
    if "late_days" in p and int(p["late_days"]) != late_days:
        issues.append(Issue("late_days", f"أيام التأخير مطبوعة {p['late_days']} والمحسوبة {late_days}", p["late_days"], late_days))
    # إجمالي السند بعد الغرامة (النهائي) كما طُبع
    if "final" in p and abs(p["final"] - payable) > TOL and not any(i.code == "penalty" for i in issues):
        issues.append(Issue("final", f"الإجمالي النهائي مطبوع {p['final']} والمحسوب {payable}", p["final"], payable))
    # إجمالي أسطر السند المطبوعة
    # مقارنة إجمالي كل سطر مطبوع بإجمالي الصنف المحسوب.
    for it, row in zip(r.items, items_out):
        if it.line_total is not None and abs(it.line_total - row["total"]) > TOL:
            issues.append(Issue("line_total", f"إجمالي سطر {it.code} مطبوع {it.line_total} والمحسوب {row['total']}",
                                it.line_total, row["total"], it.ev.page))

    # الفاتورة
    # مطابقة السند بفاتورته. لا نعد غياب رقم السند من رأس الفاتورة خطأً،
    # فالربط يتم بالبنود.
    inv = inv_by_sto.get(r.sto)          # غياب رأس السند في الفاتورة ليس خطأً: الربط بالبنود في invoice_match، وغياب الفاتورة نفسها يُحال هناك
    if inv is not None:
        if r.invoice_no and inv.number != r.invoice_no:
            issues.append(Issue("invoice_no", f"رقم الفاتورة في السند {r.invoice_no} والفاتورة التي تحويه {inv.number}",
                                r.invoice_no, inv.number))
        alloc = inv.allocations.get(r.sto)
        if alloc is not None and abs(alloc - payable) > TOL and abs(alloc - total) > TOL:
            issues.append(Issue("invoice_amount", f"مبلغ السند في الفاتورة {alloc} والمحسوب {payable}", alloc, payable))
        # مقارنة كل صنف في السند ببنده في الفاتورة: الكمية والصافي أولاً، ثم
        # العمولة والضريبة.
        ii = [i for i in inv.items if i.sto == r.sto]
        for row in items_out:
            m = [i for i in ii if i.code == row["code"]]
            if not m:
                issues.append(Issue("item_not_in_invoice", f"الصنف {row['code']} غير موجود في بنود الفاتورة"))
                continue
            i0 = m[0]
            if abs(i0.net - row["net"]) > TOL or i0.qty != row["qty"]:
                issues.append(Issue("invoice_item", f"صنف {row['code']} في الفاتورة (كمية {i0.qty}، صافي {i0.net}) يخالف المحسوب ({row['qty']}، {row['net']})",
                                    i0.net, row["net"], i0.ev.page))
            elif abs(i0.vat - row["vat"]) > TOL or abs(i0.nupco - row["comm"]) > TOL:
                issues.append(Issue("invoice_item_tax", f"عمولة/ضريبة {row['code']} في الفاتورة تخالف المحسوب", i0.vat, row["vat"], i0.ev.page))
    # نعيد نتيجة السند كاملة: الأرقام المحسوبة، والملاحظات، وبنود الأصناف.
    return Result(r.sto, r.pon, r.invoice_no, r.date, r.pages, net_sum, comm_sum, vat_sum, total, penalty, payable, late_days, issues, items_out)


def infer_bundle_rules(b: Bundle, rules: Rules) -> Rules:
    """فحص بلا عقد — تقنية «السند المرجع»: أول سند في الربطة يحدد القاعدة ثم تُعمَّم على بقية سندات الدفعة.
      - نسبة العمولة = نوبكو المطبوعة ÷ الصافي المطبوع في أول سند.
      - أساس الضريبة (الصافي أو الصافي مع العمولة) = الذي يعيد إنتاج ضريبة أول سند فيه أصناف خاضعة (نسبة الضريبة المطبوعة في سطر الصنف > 0)؛
        فإن لم يكن في الأول صنف خاضع أُخذ من أول سند لاحق فيه خاضع.
    وأي سند بعد المرجع يخالف القاعدة تظهر مخالفته ملاحظةً فيُحال للمراجع (انظر report_writer). يُسجَّل السندان المرجعان في evidence."""
    ref = next((r for r in b.receipts if r.printed.get("net") and r.printed.get("nupco") is not None and r.printed["net"] > 0), None)
    rate = D(str(round(ref.printed["nupco"] / ref.printed["net"], 4))) if ref else rules.commission
    tax_ref, mode = None, "partial_net_comm"
    for r in b.receipts:
        pv = r.printed.get("vat")
        rows = [(r2(i.qty * i.unit_price), (i.vat_rate or D(0)) > 0) for i in r.items]
        if pv is None or not any(tx for _, tx in rows):
            continue
        tax_ref = r
        for m in ("partial_net_comm", "partial_net"):
            tot = sum((r2((n + (r2(n * rate) if m.endswith("comm") else D(0))) * rules.vat_rate) for n, tx in rows if tx), D(0))
            if abs(tot - pv) <= TOL:
                mode = m
                break
        break
    out = Rules(rules.competition, commission=rate, vat_rate=rules.vat_rate, tax_mode=mode, no_contract=True)
    out.evidence = {"inferred": {"ref_receipt": ref.sto if ref else None, "tax_ref_receipt": tax_ref.sto if tax_ref else None,
                                  "commission": str(rate), "tax_mode": mode}}
    return out


def check_bundle(b: Bundle, rules: Rules) -> list[Result]:
    if rules.no_contract:
        rules = infer_bundle_rules(b, rules)
        b.inferred_rules = rules                         # يقرؤه كاتب التقرير لذكر المستنتج في بند المراجعة
    pos = {p.number: p for p in b.pos}
    invs = {i.number: i for i in b.invoices}
    by_sto: dict[str, Invoice] = {}
    for i in b.invoices:
        stos = {it.sto for it in i.items} | set(i.allocations)
        for s in stos:
            by_sto.setdefault(s, i)
    out = []
    seen = set()
    for r in b.receipts:
        res = check_receipt(r, rules, pos, invs, by_sto)
        if r.sto in seen:
            res.issues.append(Issue("duplicate_sto", f"رقم السند {r.sto} مكرر"))
        seen.add(r.sto)
        out.append(res)
    return out
