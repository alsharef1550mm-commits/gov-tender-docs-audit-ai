"""يتحقق حاسب الصيغ مقابل نتائج مخزّنة حسبها Excel/LibreOffice في ملفات مرجعية (قراءة فقط)."""
import glob, os, sys, io
import openpyxl
import report_template as T
import xl_calc

DL = os.path.expanduser(r"~\Downloads")


def check(formula_file, cached_file, label):
    got = xl_calc.compute(formula_file)
    ref = openpyxl.load_workbook(cached_file, data_only=True)
    n = bad = 0
    shown = 0
    for sh, d in got.items():
        for coord, v in d.items():
            exp = ref[sh][coord].value
            n += 1
            if exp is None and v in ("", None):
                continue
            if isinstance(exp, (int, float)) and isinstance(v, (int, float)) and abs(exp - v) < 1e-6:
                continue
            if exp == v:
                continue
            bad += 1
            if shown < 6:
                shown += 1
                print("   فرق", label, sh, coord, "المخزّن:", repr(exp), "المحسوب:", repr(v))
    print(f"{label}: {n} صيغة، فروق {bad}")
    return n, bad


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    total_bad = 0
    ref305 = os.path.join(DL, "تقرير فحص الدفعة MED-2026-305-01-001 - منسق للمراجعة.xlsx")
    org305 = os.path.join(DL, "تقرير فحص الدفعة MED-2026-305-01-001.xlsx")
    if os.path.exists(ref305) and os.path.exists(org305):
        total_bad += check(org305, ref305, "305 (الأصل مقابل المرجع المنسّق)")[1]
    for kind in T.TEMPLATE_FILES:
        p = T.template_path(kind)
        total_bad += check(p, p, f"قالب {kind} (مخزّن في الملف نفسه)")[1]
    for p in sorted(glob.glob(os.path.join(T.ROOT, "المنافسات", "*", "تقرير فحص المنافسة*.xlsx")))[:8]:
        total_bad += check(p, p, os.path.basename(p))[1]
    print("OK" if total_bad == 0 else f"FAIL {total_bad}")
    sys.exit(1 if total_bad else 0)
