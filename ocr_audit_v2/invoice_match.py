"""مطابقة الفاتورة كـ«مبرر مؤيد» لا كمقابل واحد لواحد (قاعدة صاحب المشروع).

المبدأ:
- الفاتورة قد تشمل عدة سندات، بل سندات من تعاميد مختلفة في المنافسة نفسها، ولا يُشترط أن تطبع رقم السند.
- نبدأ برقم الفاتورة المذكور في السند، ثم نطابق **بنود** السند ببنود الفاتورة: الصنف (بخريطة رموز معتمدة إن اختلف الترميز)،
  عدد الوحدات، وسعر الوحدة بحسب دقة العرض في المستند (لا مقارنة إجمالي الفاتورة بإجمالي سند واحد).
- كل سند يُحتسب مرة واحدة، والفاتورة المشتركة (ولو تكررت نسخها) مرة واحدة.
- بند في الفاتورة بلا سند، أو كمية سند تزيد على الفاتورة، أو صنف بلا رمز معتمد، أو بند يقع بين سندين بلا التباس: إحالة للمراجع مع السبب،
  ولا نخمّن ولا ننسب كامل الفاتورة لسند.
- «مبلغ السند في الفاتورة»: مجموع مبالغ البنود **المطبوعة** المنسوبة إلى السند بتطابق واضح في الصنف والعدد والسعر؛ وإلا غير محسوم مع السبب.
  لا يُترك فارغاً تلقائياً لمجرد أن الفاتورة لا تكتب رقم السند.

الواجهة (قيم بسيطة، لا تعتمد على شكل PDF):
  receipt = {"sto", "invoice_no", "lines": [{"code","qty","price"}...]}            (الأسعار/الكميات Decimal)
  invoice = {"number", "copies": [[{"code","qty","price","amount"}...] ...]}        (النسخ المتكررة تُوحَّد)
  match_invoice(receipts_citing, invoice, code_map, other_receipts) -> dict
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

PRICE_TOL = Decimal("0.005")     # نصف أدنى منزلة تعرضها الوثائق (سعر 129.08 مقابل 129.0750)


def _key_matches(a, b):
    return a["code"] == b["code"] and abs(a["price"] - b["price"]) <= PRICE_TOL


def canonical_lines(copies):
    """نسخ الفاتورة المتكررة تُحتسب مرة واحدة؛ إن اختلفت النسخ فالمرجع الأولى ويُسجَّل الاختلاف."""
    if not copies:
        return [], False
    sig = lambda ls: sorted((l["code"], str(l["qty"]), str(l["price"]), str(l.get("amount"))) for l in ls)
    first = copies[0]
    return first, any(sig(c) != sig(first) for c in copies[1:])


def match_invoice(receipts, invoice, code_map=None, other_receipts=None):
    code_map = code_map or {}
    other_receipts = other_receipts or []
    m = lambda c: code_map.get(c, c)

    inv_lines, copies_differ = canonical_lines(invoice["copies"])
    inv_lines = [{**l, "code": m(l["code"]), "used": False, "owner": None} for l in inv_lines]
    review: list[dict] = []
    if copies_differ:
        review.append({"reason": "نسخ الفاتورة المكررة تختلف في البنود", "invoice": invoice["number"]})

    attribution = {}          # sto -> {"matched": bool, "amount": Decimal|None, "reasons": [...]}
    # مطابقة بند لبند (الصنف+السعر ضمن دقة العرض+العدد). تطابق متعدد البدائل المتساوية لا يغيّر المبالغ.
    for r in receipts:
        rr = {"matched_lines": 0, "lines": len(r["lines"]), "amount": Decimal(0), "printed_ok": True, "reasons": [], "pairs": []}
        for rl in r["lines"]:
            rl = {**rl, "code": m(rl["code"])}
            cand = next((il for il in inv_lines if not il["used"] and _key_matches(rl, il) and il["qty"] == rl["qty"]), None)
            if cand is None:
                rr["reasons"].append(("unmatched_line", rl["code"], str(rl["qty"]), str(rl["price"]), rl.get("page"), rl.get("file")))
                continue
            cand["used"], cand["owner"] = True, r["sto"]
            rr["matched_lines"] += 1
            rr["pairs"].append((rl, cand))                 # بند السند ↔ صف الفاتورة المطابق (للتقرير: صافي/عمولة/ضريبة الفاتورة وصفحتها)
            if cand.get("amount") is None:
                rr["printed_ok"] = False
            else:
                rr["amount"] += cand["amount"]
        attribution[r["sto"]] = rr

    # بنود لم يطابقها سند يذكر الفاتورة: هل تنقسم بين سندين؟ هل تعود لسند آخر في المنافسة لا يذكر الفاتورة؟
    leftovers = [il for il in inv_lines if not il["used"]]
    unmatched_receipt_lines = defaultdict(list)
    for sto, rr in attribution.items():
        for reason in rr["reasons"]:
            unmatched_receipt_lines[(reason[1])].append((sto, Decimal(reason[2]), Decimal(reason[3])))
    for il in leftovers:
        # انقسام: كمية بند الفاتورة = مجموع كميات بنود غير مطابقة لسندات تذكر الفاتورة
        pool = [x for x in unmatched_receipt_lines.get(il["code"], []) if abs(x[2] - il["price"]) <= PRICE_TOL]
        if pool and sum(x[1] for x in pool) == il["qty"] and len(pool) > 1:
            review.append({"reason": "بند الفاتورة يقع بين سندين (انقسام) فلا تُنسب مبالغه لسند بعينه",
                           "code": il["code"], "qty": str(il["qty"]), "stos": [x[0] for x in pool]})
            continue
        # سند آخر في المنافسة بالبنود نفسها لكنه لا يذكر هذه الفاتورة: مرشح للمراجع، لا يُربط تلقائياً
        cands = [o["sto"] for o in other_receipts
                 if any(_key_matches({"code": m(ol["code"]), "price": ol["price"]}, il) and ol["qty"] == il["qty"] for ol in o["lines"])]
        review.append({"reason": "بند في الفاتورة بلا سند يذكرها", "code": il["code"], "qty": str(il["qty"]), "price": str(il["price"]),
                       "invoice_page": il.get("page"), "invoice_file": il.get("file"),
                       "candidate_stos_not_citing_invoice": cands[:5]})
    for sto, rr in attribution.items():
        for reason in rr["reasons"]:
            pool_used = any(il["code"] == reason[1] for il in inv_lines)
            review.append({"reason": "بند في السند لا يقابله بند مطابق في الفاتورة (صنف/عدد/سعر)" if pool_used
                           else "صنف السند غير موجود في الفاتورة (أو يحتاج خريطة رموز معتمدة)",
                           "sto": sto, "code": reason[1], "qty": reason[2], "price": reason[3],
                           "receipt_page": reason[4] if len(reason) > 4 else None, "receipt_file": reason[5] if len(reason) > 5 else None})

    # بنود متنازع عليها: صفوف فاتورة بلا سند، أو بنود سند بلا صف مطابق. أي سند تتقاطع بنوده (صنف+سعر) معها يُحال:
    # التطابق الظاهر لديه قد يكون مصادفة (صف يعود لسند آخر) فلا نسجّل له مبلغاً ولا نخمّن.
    def _interchangeable(il):
        """صف فائض مطابق تماماً (صنف/عدد/سعر/مبلغ) لصف مُسنَد: التبديل بينهما لا يغيّر مبلغ أي سند، فليس التباساً."""
        return any(ul["used"] and _key_matches(il, ul) and ul["qty"] == il["qty"] and ul.get("amount") == il.get("amount")
                   for ul in inv_lines if ul is not il)
    contested = [{"code": il["code"], "price": il["price"]} for il in leftovers if not _interchangeable(il)]
    for sto, rr in attribution.items():
        for reason in rr["reasons"]:
            contested.append({"code": reason[1], "price": Decimal(reason[3])})
    receipts_by_sto = {r["sto"]: r for r in receipts}
    out = {}
    for sto, rr in attribution.items():
        matched_all = rr["matched_lines"] == rr["lines"] and rr["lines"] > 0
        touched = any(_key_matches({"code": m(l["code"]), "price": l["price"]}, c)
                      for l in receipts_by_sto[sto]["lines"] for c in contested)
        clear = matched_all and not touched
        if clear and rr["printed_ok"]:
            why = None
        elif clear:
            why = "مبالغ البنود غير مطبوعة"
        elif matched_all:
            why = "بنود السند تتقاطع مع بنود متنازع عليها في الفاتورة (فائضة أو غير مطابقة): التباس في التوزيع"
        else:
            why = "بنود السند لم تُنسب كلها بتطابق واضح"
        out[sto] = {"clear": clear, "amount": str(rr["amount"]) if clear and rr["printed_ok"] else None, "why": why,
                    "pairs": rr["pairs"] if clear else []}          # الأزواج لا تُعرض إلا للنسبة الواضحة
    group_ok = not review and all(v["clear"] for v in out.values())
    return {"invoice": invoice["number"], "receipts": out, "group_consistent": group_ok, "review": review,
            "lines": len(inv_lines), "matched_lines": sum(1 for l in inv_lines if l["used"])}
