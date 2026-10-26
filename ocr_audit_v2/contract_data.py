"""قراءة بيانات العقد النصي: أصناف الملحق (ب)، مجاميع العقد، مبالغ الدفعات (الملحق أ). Decimal فقط.

كل ما لا يُقرأ بوضوح يبقى None (غير محسوم) ولا يُخمَّن.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal as D

import pdfx
from extract import num

_ITEM = re.compile(r"^\s*([\d,]+\.\d{2}) ([\d,]+\.\d{2}) (?:(\d+)% )?([\d,]+\.\d{2}) ([\d,]+\.\d{2}) ([\d,]+\.\d{2}) (\d+) (\S+) (.+?) ([A-Z]{2,}-[A-Z]?\d+) (\d+)\s*$")
_TOTAL = re.compile(r"^\s*([\d,]+\.\d{2}) ([\d,]+\.\d{2}) ([\d,]+\.\d{2}) ([\d,]+\.\d{2}) (?:\S+\s+)?(?:اجمالي|الإجمالي|الاجمالي|إجمالي)\s*$")
_BATCH = re.compile(r"^\s*([\d,]+\.\d{2}) ([\d,]+\.\d{2}) ([\d,]+\.\d{2}) ([\d,]+\.\d{2}) (\d+) \S+ (\d+)\s*$")


@dataclass
class ContractItem:
    code: str
    description: str
    unit: str
    qty: D
    price: D
    net: D
    nupco: D
    vat_rate: D
    vat: D
    total: D
    page: int


@dataclass
class ContractData:
    items: list[ContractItem] = field(default_factory=list)
    totals: dict = field(default_factory=dict)          # net, nupco, vat, total (من صف الإجمالي في الملحق ب)
    batches: dict = field(default_factory=dict)         # رقم الدفعة -> {net,nupco,vat,total}
    supplier: str | None = None
    items_page: int | None = None
    batches_page: int | None = None
    notes: list[str] = field(default_factory=list)


def _logical(tokens: str) -> str:
    """نص عربي مقروء بترتيب بصري يسار-يمين -> ترتيب كلمات منطقي."""
    return " ".join(reversed(tokens.split()))


def read_contract(path: str) -> ContractData:
    cd = ContractData()
    for p in pdfx.read_pdf(path):
        for l in p.lines:
            t = l.text
            m = _ITEM.match(t)
            if m:
                tot, vat, rate, nup, net, price, qty, unit, desc, code, _ = m.groups()
                cd.items.append(ContractItem(code, _logical(desc), unit, num(qty), num(price), num(net), num(nup),
                                             (D(rate) / 100 if rate else (D("0.15") if num(vat) > 0 else D(0))), num(vat), num(tot), p.n))
                cd.items_page = cd.items_page or p.n
                continue
            m = _TOTAL.match(t)
            if m and not cd.totals and cd.items:
                tot, vat, nup, net = (num(x) for x in m.groups())
                cd.totals = {"net": net, "nupco": nup, "vat": vat, "total": tot, "page": p.n}
                continue
            m = _BATCH.match(t)
            if m and "الربع" in t:
                tot, vat, nup, net, _per, b = m.groups()
                cd.batches[int(b)] = {"net": num(net), "nupco": num(nup), "vat": num(vat), "total": num(tot)}
                cd.batches_page = cd.batches_page or p.n
            if "|" in t and "شركة" in t and cd.supplier is None:
                for seg in t.split("|"):
                    if "شركة" in seg:
                        cd.supplier = _logical(seg.strip())
    if not cd.items:
        cd.notes.append("بنود الملحق (ب) لم تُقرأ من العقد")
    if not cd.totals:
        cd.notes.append("صف إجمالي الملحق (ب) لم يُقرأ")
    if not cd.batches:
        cd.notes.append("جدول مبالغ الدفعات في العقد غير موجود أو لم يُقرأ؛ تبقى أعمدة العقد للدفعة غير محسومة")
    return cd
