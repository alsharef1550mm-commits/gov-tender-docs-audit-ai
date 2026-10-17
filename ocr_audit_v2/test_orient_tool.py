"""أداة تصحيح الاتجاه: صفحات مُدارة عمداً تُعاد مستقيمة (يُتحقق بإعادة كشف الاتجاه على الناتج = 0 لكل صفحة)."""
import os, sys, io, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pypdfium2 as pdfium
import orient_tool as OT, scan_reader as SR, report_template as T

if __name__ == "__main__":
    src = os.path.join(T.ROOT, "المنافسات", "منافسة جراحة العظام MED-2026-144", "MED-2026-144-01-004.pdf")
    pdf = pdfium.PdfDocument(src)
    rots = [0, 90, 180, 270, 90, 0]
    imgs = [pdf[i].render(scale=2).to_pil().convert("L").rotate(r, expand=True) for i, r in zip(range(3, 9), rots)]
    tmp = tempfile.mkdtemp()
    bad = os.path.join(tmp, "مقلوب.pdf")
    imgs[0].save(bad, save_all=True, append_images=imgs[1:], resolution=150)
    out, ch, secs = OT.fix_pdf(bad)
    print("صُحّح:", ch, "| الزمن:", secs, "ث")
    d = pdfium.PdfDocument(out)
    left = [SR.correct_orientation(d[i].render(scale=1.4).to_pil())[1] for i in range(len(d))]
    print("زوايا الكشف على الناتج:", left)
    assert all(a == 0 for a in left) and len(ch) == 4
    print("OK")
