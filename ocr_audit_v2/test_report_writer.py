"""اختبار انحدار كاتب التقارير: يعيد توليد تقرير دفعة قالبي من مصادره ويقارنه بالقالب خلية بخلية.

القالب المرجعي: «مثال فحص دفعه/تقرير فحص الدفعة MED-2026-318-01-001 - محدث.xlsx» (مصدره MED-2026-318-01-001.pdf وعقد 318).
هذا انحدار/اتساق مع تقرير سابق لا دليل مستقل: أي فرق يُحقَّق منه في الأصل قبل الحكم لأيٍّ منهما.
الاستعمال: python test_report_writer.py [مجلد_الخرج]
"""
import io
import os
import sys
import tempfile

import report_template as T
import report_writer as W

R = T.ROOT


def main(out_dir=None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    out_dir = out_dir or tempfile.mkdtemp()
    bundle = os.path.join(R, "مثال فحص دفعه", "MED-2026-318-01-001.pdf")
    contract = os.path.join(R, "مثال فحص دفعه", "عقد 318.pdf")
    out = os.path.join(out_dir, "تقرير فحص الدفعة MED-2026-318-01-001.xlsx")
    path, unresolved = W.write_batch_report(bundle, contract, out)
    print("الملف:", path, "| غير محسوم:", len(unresolved))
    print("مطابقة القالب:", T.validate(path, "batch") or "مطابق حرفياً")
    diffs = W.compare_workbooks(path, T.template_path("batch"))
    print("فروق مقابل القالب:", len(diffs))
    for d in diffs[:40]:
        print("  ", d)
    return len(diffs)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
