"""قفل قوالب Excel: تقارير الدفعات والمنافسات تلتزم حرفياً بالقالبين المرجعيين، ولا شيء يُضاف أو يُسقَط أو يُعاد تسميته.

القالبان (مصدر الحقيقة؛ لا يُعدَّلان):
  batch        مثال فحص دفعه/تقرير فحص الدفعة MED-2026-318-01-001 - محدث.xlsx      (تقرير السندات، الأصناف، المطابقة)
  competition  مثال فحص منافسة/تقرير فحص المنافسة MED-2026-339.xlsx                (تقرير السندات، تفصيل الأصناف، مطابقة التعاميد، تقرير المنافسة والأصناف)

ما يُقفَل: أسماء الشيتات وترتيبها، وكل كتلة رؤوس في كل شيت (الصف الذي يحمل لون الرأس الداكن) باسمها وترتيبها وعددها،
وعدم وجود أعمدة بيانات خارج رؤوس الجداول. ما لا يُقفَل: القيم (أرقام المنافسة والمبالغ والنصوص الوصفية).
أي بيانات تقنية إضافية (قراءات النماذج، الاتفاق، الثقة...) تُحفظ في المختبر (ocr_audit_v2/out) لا في تقرير دفعة أو منافسة.

الاستعمال:
  python report_template.py snapshot            # يحدّث templates/*.json من القالبين (مع SHA256)
  python report_template.py validate <ملف.xlsx> batch|competition
  python report_template.py audit               # يفحص كل التقارير الموجودة (قراءة فقط ولا يغيّر شيئاً)
في التنفيذ: استدعِ assert_matches_template(path, kind) قبل حفظ أي تقرير نهائي أو تسليمه.
"""
from __future__ import annotations

import glob
import hashlib
import io
import json
import os
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TPL_DIR = os.path.join(HERE, "templates")
HEADER_FILL = "FF17365D"          # لون رأس الجدول في القالبين

TEMPLATE_FILES = {
    "batch": ("مثال فحص دفعه", "تقرير فحص الدفعة MED-2026-318-01-001 - محدث.xlsx"),
    "competition": ("مثال فحص منافسة", "تقرير فحص المنافسة MED-2026-339.xlsx"),
}


def template_path(kind: str) -> str:
    d, f = TEMPLATE_FILES[kind]
    return os.path.join(ROOT, d, f)


def writer_template_path(kind: str) -> str:
    """قالب الكتابة: نسخة مجرَّدة من بيانات المثال (صف 6 فقط للصيغ والتنسيق) إن وُجدت، وإلا القالب المرجعي نفسه."""
    p = os.path.join(TPL_DIR, f"{kind}.xlsx")
    return p if os.path.exists(p) else template_path(kind)


def _fill(cell) -> str | None:
    f = cell.fill
    return f.fgColor.rgb if f is not None and f.fill_type and isinstance(f.fgColor.rgb, str) else None


def extract(path: str) -> dict:
    """بنية القالب: لكل شيت كتل الرؤوس (صف، قيم) وأول أسطر العنوان."""
    import report_style as RS
    wb = openpyxl.load_workbook(path)
    sheets = []
    for ws in wb:
        blocks, titles = [], {}
        hdr_rows = set(RS.header_rows(ws))               # الرأس يُعرَف ببنيته (غامق + تعبئة صلبة + غير مدمج) لا بلون محدد
        for r in range(1, ws.max_row + 1):
            c1 = ws.cell(r, 1)
            vals = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
            if r in hdr_rows:
                while vals and vals[-1] is None:
                    vals.pop()
                blocks.append({"row": r, "headers": vals})
            elif r <= 4 and any(v is not None for v in vals):
                titles[r] = next(v for v in vals if v is not None)
        sheets.append({"name": ws.title, "titles": titles, "header_blocks": blocks, "freeze": ws.freeze_panes})
    return {"sheets": sheets}


def snapshot(kind: str) -> str:
    src = template_path(kind)
    data = extract(src)
    data["source"] = os.path.relpath(src, ROOT)
    data["sha256"] = hashlib.sha256(open(src, "rb").read()).hexdigest()
    os.makedirs(TPL_DIR, exist_ok=True)
    dst = os.path.join(TPL_DIR, f"{kind}.json")
    json.dump(data, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return dst


def load_snapshot(kind: str) -> dict:
    p = os.path.join(TPL_DIR, f"{kind}.json")
    if not os.path.exists(p):
        snapshot(kind)
    return json.load(open(p, encoding="utf-8"))


def template_is_current(kind: str) -> bool:
    """القالب المرجعي لم يتغير منذ اللقطة؟ (وإلا يجب تحديث اللقطة بقرار صاحب المشروع)"""
    snap = load_snapshot(kind)
    return hashlib.sha256(open(template_path(kind), "rb").read()).hexdigest() == snap["sha256"]


def validate(path: str, kind: str, style: bool = False) -> list[str]:
    """قائمة مخالفات القالب؛ فارغة = مطابق. style=True للتقارير الجديدة: يضيف فحص نمط المراجعة (report_style) والصيغ المخزّنة."""
    tpl = load_snapshot(kind)["sheets"]
    got = extract(path)["sheets"]
    errs: list[str] = []
    names_t, names_g = [s["name"] for s in tpl], [s["name"] for s in got]
    if names_g != names_t:
        extra = [n for n in names_g if n not in names_t]
        missing = [n for n in names_t if n not in names_g]
        if extra:
            errs.append(f"شيتات زائدة: {extra}")
        if missing:
            errs.append(f"شيتات ناقصة: {missing}")
        if not extra and not missing:
            errs.append(f"ترتيب الشيتات يخالف القالب: {names_g} بدل {names_t}")
    by_g = {s["name"]: s for s in got}
    wb = None
    for t in tpl:
        g = by_g.get(t["name"])
        if g is None:
            continue
        tb, gb = t["header_blocks"], g["header_blocks"]
        if len(gb) != len(tb):
            errs.append(f"[{t['name']}] عدد كتل الرؤوس {len(gb)} بدل {len(tb)}")
        for i, (a, b) in enumerate(zip(tb, gb), 1):
            if a["headers"] != b["headers"]:
                ex = [h for h in b["headers"] if h not in a["headers"]]
                mi = [h for h in a["headers"] if h not in b["headers"]]
                if ex:
                    errs.append(f"[{t['name']}] كتلة {i}: أعمدة/رؤوس زائدة {ex}")
                if mi:
                    errs.append(f"[{t['name']}] كتلة {i}: أعمدة ناقصة {mi}")
                if not ex and not mi:
                    errs.append(f"[{t['name']}] كتلة {i}: ترتيب الأعمدة يخالف القالب")
        # أعمدة بيانات بلا رأس (خارج رؤوس الجدول) في الشيتات ذات الجدول الواحد
        if len(tb) == 1 and len(gb) >= 1:
            if wb is None:
                wb = openpyxl.load_workbook(path, read_only=True)
            ws = wb[t["name"]]
            width = len(tb[0]["headers"])
            if ws.max_column and ws.max_column > width:
                errs.append(f"[{t['name']}] أعمدة بيانات خارج رؤوس القالب (الأعمدة {width + 1} إلى {ws.max_column})")
    if style:
        import report_style as RS
        errs.extend(RS.validate_style(path))
    return errs


def assert_matches_template(path: str, kind: str, style: bool = True) -> None:
    """التقارير الجديدة تُفحص بنمط المراجعة أيضاً؛ التقارير القديمة تُفحص بـvalidate(style=False) ولا تُعدَّل."""
    errs = validate(path, kind, style=style)
    if errs:
        raise ValueError("التقرير يخالف القالب المعتمد ولا يُسلَّم:\n  " + "\n  ".join(errs))


def audit() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    for kind in TEMPLATE_FILES:
        print(f"قالب {kind}: لقطة {'حديثة' if template_is_current(kind) else 'قديمة (تغيّر القالب المرجعي!)'}")
    groups = {
        "batch": glob.glob(os.path.join(ROOT, "مثال فحص دفعه", "تقرير فحص الدفعة*.xlsx")),
        "competition": glob.glob(os.path.join(ROOT, "المنافسات", "*", "تقرير فحص المنافسة*.xlsx"))
        + glob.glob(os.path.join(ROOT, "مثال فحص منافسة", "تقرير فحص المنافسة*.xlsx")),
    }
    for kind, files in groups.items():
        print(f"\n== تقارير {kind} الموجودة ({len(files)}) مقابل القالب (قراءة فقط)")
        for f in sorted(files):
            errs = validate(f, kind)
            print(f"  {'مطابق ' if not errs else 'يخالف '} {os.path.basename(f)}")
            for e in errs:
                print("      -", e)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "snapshot":
        for k in TEMPLATE_FILES:
            print(snapshot(k))
    elif cmd == "validate":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        e = validate(sys.argv[2], sys.argv[3])
        print("مطابق للقالب" if not e else "\n".join(e))
        sys.exit(1 if e else 0)
    else:
        audit()
