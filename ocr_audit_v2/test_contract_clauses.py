"""Prose-clause contract rules: tax base, commission, penalty, total, and refusal on conflict."""
from decimal import Decimal as D
from unittest import mock

import engine
from extract import norm_ar


def rules_from(*sentences):
    r = engine.Rules("TEST")
    with mock.patch.object(engine, "_sentences", return_value=[(1, norm_ar(s)) for s in sentences]):
        engine._clause_rules("unused.pdf", r)
    return r


def test_partial_net_without_nupco():
    r = rules_from("تحتسب ضريبة 15% على صافي الأصناف الخاضعة فقط دون رسوم نوبكو، ولا ضريبة على بقية الأصناف")
    assert r.tax_mode == "partial_net", r.tax_mode


def test_full_net_plus_commission():
    r = rules_from("تحتسب ضريبة القيمة المضافة بنسبة 15% على صافي الأصناف مضافاً إليه عمولة نوبكو لكامل السند")
    assert r.tax_mode == "full_net_comm", r.tax_mode


def test_full_net_only():
    r = rules_from("تحتسب ضريبة 15% على صافي الأصناف فقط دون رسوم نوبكو")
    assert r.tax_mode == "full_net", r.tax_mode


def test_no_vat():
    r = rules_from("لا تحتسب ضريبة قيمة مضافة على الأصناف ولا على رسوم نوبكو")
    assert r.tax_mode == "none", r.tax_mode


def test_value_sentence_is_not_a_tax_rule():
    r = rules_from("صافي قيمة الأصناف 750,000.00 ريال، وتضاف رسوم نوبكو بنسبة 4% من الصافي، وضريبة القيمة المضافة 63,000.00 ريال، فيكون الإجمالي 843,000.00 ريال",
                   "تحتسب ضريبة 15% على صافي الأصناف الخاضعة فقط دون رسوم نوبكو")
    assert r.tax_mode == "partial_net" and r.commission == D("0.04") and r.contract_total == D("843000.00"), (r.tax_mode, r.commission, r.contract_total)


def test_conflicting_tax_sentences_stay_unknown():
    r = rules_from("تحتسب ضريبة 15% على صافي الأصناف فقط", "تحتسب ضريبة 15% على صافي الأصناف مضافاً إليه عمولة نوبكو")
    assert r.tax_mode == "unknown", r.tax_mode


def test_late_penalty_rate_and_cap():
    r = rules_from("تحتسب غرامة تأخير بنسبة 2% عن كل أسبوع تأخير على قيمة الجزء المتأخر، وبحد أعلى 8% من قيمة العقد")
    assert (r.late_weekly, r.late_cap) == (D("0.02"), D("0.08")), (r.late_weekly, r.late_cap)


def test_table_percent_is_not_commission_without_nupco():
    r = rules_from("م الرمز الصنف الكمية سعر الوحدة الصافي نسبة الضريبة 15% الإجمالي")
    assert r.commission == D("0.04") and r.tax_mode == "unknown"


class _FakeTextPage:
    """Two runs of one right-to-left visual line, returned left part first (as pdfium does for a wrapped clause)."""

    def __init__(self, runs):
        self.text, self.boxes = "", []
        for y, x0, s in runs:
            for k, ch in enumerate(s):
                self.text += ch
                self.boxes.append((x0 + k, y - 5, x0 + k + 1, y + 5))
            self.text += "\r\n"
            self.boxes += [(0, 0, 0, 0), (0, 0, 0, 0)]

    def count_chars(self):
        return len(self.text)

    def get_text_range(self, start, count):
        return self.text[start:start + count]

    def get_charbox(self, i):
        return self.boxes[i]


def test_rtl_runs_on_one_line_are_read_right_to_left():
    page = _FakeTextPage([(686, 10, "إليه عمولة نوبكو لكامل السند."), (686, 300, "الضريبة: تحتسب ضريبة القيمة المضافة بنسبة %15 على صافي الأصناف مضافًا")])
    assert engine._page_lines(page) == ["الضريبة: تحتسب ضريبة القيمة المضافة بنسبة %15 على صافي الأصناف مضافًا إليه عمولة نوبكو لكامل السند."]


def test_reversed_lam_alef_ligature_is_repaired():
    s = norm_ar("صافي قيمة األصناف 2,400,000.00 لاير، واإلجمالي 2,870,400.00 لاير")
    for pattern, repl in engine.LIGATURE:
        s = pattern.sub(repl, s)
    assert "الاصناف" in s and "والاجمالي" in s and s.count("ريال") == 2, s


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
