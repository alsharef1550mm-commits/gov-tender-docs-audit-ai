"""تصحيح الاتجاه إجباري: صفحة سليمة تُدار 90/180/270 فيعيدها المصحِّح إلى الاتجاه الصحيح (تُقارَن بدرجة القراءة)، والصفحة السليمة لا تُمس."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pypdfium2 as pdfium
import scan_reader as SR, report_template as T

if __name__ == "__main__":
    src = os.path.join(T.ROOT, "المنافسات", "منافسة جراحة العظام MED-2026-144", "MED-2026-144-01-004.pdf")
    doc = pdfium.PdfDocument(src)
    pages = [i for i in (3, 20, 40)]
    ok = total = 0
    for i in pages:
        up = doc[i].render(scale=2).to_pil().convert("L")
        s_up = SR._orientation_score(up)
        for rot in (0, 90, 180, 270):
            bad = up.rotate(rot, expand=True) if rot else up
            fixed, ang = SR.correct_orientation(bad)
            s_fixed = SR._orientation_score(fixed)
            good = s_fixed >= 0.8 * s_up
            total += 1; ok += good
            print(f"صفحة {i+1} دُوِّرت {rot:>3}° → طُبّقت {ang:>3}° | درجة القراءة {s_fixed:.0f} من {s_up:.0f} | {'صحيح' if good else 'خطأ'}")
    print(f"النتيجة: {ok}/{total}")
    assert ok == total
    print("OK")
