"""بوابة التحقق الحتمية لقراءة صفحة (من نموذج رؤية أو OCR): تقبل الصفحة آلياً فقط إن اجتازت كل الفحوص، وإلا تُحال.

الفحوص (لا تستعمل المرجع):
  - صيغ المعرّفات: STO\\d{10}، PON\\d{10}، رقم فاتورة 10 أرقام (أو TF + 10).
  - حساب الأسطر: فاتورة: net = qty × unit_price، commission = 4% من net (قاعدة العقود المتاحة)، line_total = net + commission + vat.
  - اتساق نوع الصفحة مع الحقول (سند: بنود بلا net/commission؛ فاتورة: بها).
  - تعارض الحقول: رقم السند لا يساوي رقم الفاتورة أو التعميد؛ لا حقل مالي بلا قيمة (null) ضمن صف مقبول.
قياس الجدوى على مجموعة القياس: bench_gate.py (نسبة القبول، وأخطاء مقبولة خطأً = الأخطاء الفائتة).
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# صيغ أرقام السند والتعميد والفاتورة. أي رقم يخالفها لا يُقبل آلياً.
RE_STO = re.compile(r"^STO\d{10}$")
RE_PON = re.compile(r"^PON\d{10}$")
RE_INV = re.compile(r"^(?:TF)?\d{10}$")
TOL = Decimal("0.02")
# إجمالي سطر السند = صافي×معامل: 1.04 (عمولة فقط)، 1.19 (ضريبة على الصافي)، 1.196 (ضريبة على الصافي+العمولة)
# معاملات إجمالي سطر السند في العقود المعروفة: عمولة فقط، أو عمولة مع
# ضريبة على الصافي، أو مع ضريبة على الصافي والعمولة.
RECEIPT_FACTORS = (Decimal("1.04"), Decimal("1.19"), Decimal("1.196"))


# تحويل النص إلى رقم عشري دقيق (Decimal)، وإرجاع قيمة فارغة إذا فشل
# التحويل.
def d(x):
    if x is None:
        return None
    try:
        return Decimal(re.sub(r"[,\s]", "", str(x)))
    except InvalidOperation:
        return None


# بوابة التحقق الحتمية: تفحص قراءة النموذج لصفحة واحدة، وتعيد قرار
# القبول مع أسباب الرفض.
def check_page(pred: dict, commission_rate=Decimal("0.04")):
    """يعيد (قبول: bool، أسباب الرفض: list[str])."""
    reasons = []
    if not pred or not isinstance(pred, dict):
        return False, ["لا قراءة"]
    ty = pred.get("page_type")
    ids = pred.get("ids") or {}
    items = pred.get("items") or []
    if ty not in ("receipt", "invoice", "purchase_order"):
        return False, ["نوع صفحة غير معتمد"]
    # فحص أرقام صفحة السند: رقم السند والتعميد والفاتورة.
    if ty == "receipt":
        if not (ids.get("receipt_no") and RE_STO.match(str(ids["receipt_no"]).replace(" ", ""))):
            reasons.append("رقم السند غير مطابق للصيغة")
        if ids.get("po_no") and not RE_PON.match(str(ids["po_no"])):
            reasons.append("رقم التعميد غير مطابق للصيغة")
        if ids.get("invoice_no") and not RE_INV.match(str(ids["invoice_no"])):
            reasons.append("رقم الفاتورة غير مطابق للصيغة")
    elif ty == "invoice":
        if not (ids.get("invoice_no") and RE_INV.match(str(ids["invoice_no"]))):
            reasons.append("رقم الفاتورة غير مطابق للصيغة")
    else:
        if not (ids.get("po_no") and RE_PON.match(str(ids["po_no"]))):
            reasons.append("رقم التعميد غير مطابق للصيغة")
    if not items:
        reasons.append("لا بنود")
    # فحص كل بند: هل الرمز والكمية والسعر موجودة؟ وندمج الريال والهللة إذا
    # كانا في عمودين.
    for k, it in enumerate(items, 1):
        q, p = d(it.get("qty")), d(it.get("unit_price"))
        if it.get("unit_price_halala") not in (None, ""):
            h = d(it.get("unit_price_halala"))
            if p is not None and h is not None and p == p.to_integral_value():
                p = p + h / 100
        if not it.get("item_code") or q is None or p is None:
            reasons.append(f"بند {k}: رمز/كمية/سعر ناقص")
            continue
        # فحوص بنود الفاتورة: الكمية × السعر = الصافي، والعمولة 4%، والإجمالي =
        # الصافي + العمولة + الضريبة.
        if ty == "invoice":
            net = d(it.get("net"))
            if net is None:
                net = q * p                       # مخطط النموذج بلا حقل «الصافي»: يُشتق من الكمية×السعر ثم تُفحص العمولة والإجمالي عليه
            comm, vat, tot = d(it.get("commission")), d(it.get("vat")), d(it.get("line_total"))
            if None in (comm, vat, tot):
                reasons.append(f"بند {k}: حقل مالي ناقص")
                continue
            if abs(q * p - net) > TOL:
                reasons.append(f"بند {k}: كمية×سعر ≠ الصافي")
            if abs(net * commission_rate - comm) > TOL:
                reasons.append(f"بند {k}: العمولة ≠ 4%")
            if abs(net + comm + vat - tot) > TOL:
                reasons.append(f"بند {k}: الإجمالي ≠ الصافي+العمولة+الضريبة")
        # إجمالي سطر السند يجب أن يساوي الكمية × السعر × أحد معاملات العقود.
        elif ty == "receipt":
            tot = d(it.get("line_total"))
            if it.get("line_total_halala") not in (None, ""):
                h = d(it.get("line_total_halala"))
                if tot is not None and h is not None and tot == tot.to_integral_value():
                    tot = tot + h / 100
            if tot is None:
                reasons.append(f"بند {k}: إجمالي السطر ناقص")
            elif not any(abs(tot - q * p * f) <= TOL for f in RECEIPT_FACTORS):
                reasons.append(f"بند {k}: إجمالي السطر لا يطابق كمية×سعر بأي من معاملات العقود (عمولة/ضريبة)")
        else:
            net = d(it.get("line_total"))
            if net is None or abs(q * p - net) > TOL:
                reasons.append(f"بند {k}: كمية×سعر ≠ الإجمالي")
    # الفحص الأخير: مجموع أسطر الصفحة يساوي الإجمالي المطبوع. إذا لم
    # يتساويا، فإما أن الصفحة تكمل في التالية أو أن القراءة خاطئة.
    tot_block = (pred.get("totals") or {})
    if ty == "receipt" and d(tot_block.get("total")) is not None and not reasons:
        s = Decimal(0)
        for it in items:
            t = d(it.get("line_total"))
            if t is not None and it.get("line_total_halala") not in (None, "") and d(it.get("line_total_halala")) is not None and t == t.to_integral_value():
                t = t + d(it.get("line_total_halala")) / 100
            s += t or Decimal(0)
        if abs(s - d(tot_block["total"])) > Decimal("0.05"):
            reasons.append("مجموع أسطر الصفحة لا يساوي الإجمالي المطبوع (قد تمتد الصفحة أو قراءة خاطئة)")
    # نقبل الصفحة آلياً فقط إذا خلت قائمة أسباب الرفض، وإلا نحيلها إلى
    # المراجع مع الأسباب.
    return (not reasons), reasons
