"""يتحقق من نمط المراجعة: (1) على الأصل المنسَّق بالنسخة المرجعية للمالك، (2) أن التقارير القديمة لم تتغير نتيجة فحصها."""
import io, os, shutil, sys, tempfile
import openpyxl
import report_style as RS
import report_template as T
import xl_calc

DL = os.path.expanduser(r"~\Downloads")


def cmp_style(a_path, b_path):
    """يقارن نمط ملفين خلية بخلية (تعبئة، خط، حدود، محاذاة) + الدمج + ارتفاعات الصفوف المعتمدة."""
    a, b = openpyxl.load_workbook(a_path), openpyxl.load_workbook(b_path)
    diffs = []
    for ws in a:
        wb_ = b[ws.title]
        if sorted(map(str, ws.merged_cells.ranges)) != sorted(map(str, wb_.merged_cells.ranges)):
            diffs.append((ws.title, "merged", sorted(map(str, ws.merged_cells.ranges)), sorted(map(str, wb_.merged_cells.ranges))))
        for row in ws.iter_rows():
            for c in row:
                d = wb_[c.coordinate]
                sa = (c.fill.fill_type, c.fill.fgColor.rgb if c.fill.fgColor.type == "rgb" else None, c.font.b, c.font.sz, c.font.name,
                      c.font.color.rgb if c.font.color is not None and c.font.color.type == "rgb" else None,
                      tuple(getattr(c.border, s).style for s in ("left", "right", "top", "bottom")), c.alignment.horizontal, c.alignment.vertical, bool(c.alignment.wrap_text))
                sb = (d.fill.fill_type, d.fill.fgColor.rgb if d.fill.fgColor.type == "rgb" else None, d.font.b, d.font.sz, d.font.name,
                      d.font.color.rgb if d.font.color is not None and d.font.color.type == "rgb" else None,
                      tuple(getattr(d.border, s).style for s in ("left", "right", "top", "bottom")), d.alignment.horizontal, d.alignment.vertical, bool(d.alignment.wrap_text))
                if sa != sb and not (c.value is None and d.value is None and sa[0] is None and sb[0] is None and "thin" not in sa[6] and "thin" not in sb[6]):
                    diffs.append((ws.title, c.coordinate, sa, sb))
        for r in (1, 2, 3, 4, 5):
            if (ws.row_dimensions[r].height or 0) != (wb_.row_dimensions[r].height or 0):
                diffs.append((ws.title, f"row{r}height", ws.row_dimensions[r].height, wb_.row_dimensions[r].height))
    return diffs


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    org = os.path.join(DL, "تقرير فحص الدفعة MED-2026-305-01-001.xlsx")
    ref = os.path.join(DL, "تقرير فحص الدفعة MED-2026-305-01-001 - منسق للمراجعة.xlsx")
    tmp = os.path.join(tempfile.mkdtemp(), "out305.xlsx")
    wb = openpyxl.load_workbook(org)
    n, errs = RS.finalize(wb, tmp)
    print("صيغ محفوظة:", n, "أخطاء صيغ:", errs)
    d = cmp_style(tmp, ref)
    print("فروق النمط مقابل المرجع المنسّق:", len(d))
    for x in d[:12]:
        print("  ", x)
    print("فحص القالب (نمط جديد):", T.validate(tmp, "batch", style=True) or "مطابق")
    # القيم والصيغ لم تتغير
    a, b = openpyxl.load_workbook(org), openpyxl.load_workbook(tmp)
    vd = sum(1 for ws in a for row in ws.iter_rows() for c in row if b[ws.title][c.coordinate].value != c.value)
    print("فروق قيم/صيغ مقابل الأصل:", vd)
    # الأصل لم يُمَس والتقرير المنسّق القديم يخالف النمط (لأنه بالنمط الداكن) لكنه يطابق القالب
    print("الأصل القديم يُفحص بلا نمط:", T.validate(org, "batch", style=False) or "مطابق", "| والمرجع المنسّق:", T.validate(ref, "batch", style=True) or "مطابق النمط والقالب")
    ok = not d and vd == 0 and not errs and not T.validate(tmp, "batch", style=True)
    print("OK" if ok else "FAIL")
    sys.exit(0 if ok else 1)
