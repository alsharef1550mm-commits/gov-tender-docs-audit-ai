"""انحدار كاتب تقرير المنافسة: يعيد توليد تقرير 339 من الربطات الأصلية ويقارنه بالقالب خلية بخلية (اتساق لا دليل)."""
import glob
import io
import os
import sys
import tempfile
import time

import report_template as T
import competition_writer as W
import report_writer as RW

R = T.ROOT


def main(workers=6):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    folder = glob.glob(os.path.join(R, "المنافسات", "*MED-2026-339"))[0]
    bundles = sorted(glob.glob(os.path.join(folder, "MED-2026-339-*.pdf")))
    contract = os.path.join(folder, "العقد", "عقد المنافسة.pdf")
    out = os.path.join(tempfile.mkdtemp(), "تقرير فحص المنافسة MED-2026-339.xlsx")
    t0 = time.time()
    path, unresolved = W.write_competition_report(bundles, contract, out, workers=workers,
                                                  progress=lambda i, n, f: print(f"  {i}/{n} {f}", flush=True) if i % 10 == 0 else None)
    print("الملف:", path, "| زمن", round(time.time() - t0), "ث | غير محسوم:", len(unresolved))
    print("مطابقة القالب:", T.validate(path, "competition") or "مطابق حرفياً")
    diffs = RW.compare_workbooks(path, T.template_path("competition"), 10 ** 6)
    print("فروق مقابل القالب:", len(diffs))
    import collections
    by = collections.Counter((d[0], "".join(ch for ch in d[1] if ch.isalpha())) for d in diffs)
    for k, v in by.most_common(40):
        print("  ", v, k, next(d for d in diffs if (d[0], "".join(ch for ch in d[1] if ch.isalpha())) == k))
    for u in unresolved[:10]:
        print("  غير محسوم:", u)


if __name__ == "__main__":
    main()
