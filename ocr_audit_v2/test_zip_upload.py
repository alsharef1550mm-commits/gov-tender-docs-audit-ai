"""رفع ZIP لملفات المنافسة: فك آمن لـPDF فقط بأسماء مسطّحة، تجاهل غير PDF، رفض المكرر والمتلف، حد العدد."""
import io, os, sys, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import job_pipeline as JP


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    d = tempfile.mkdtemp()
    z = os.path.join(d, "bundles.zip")
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("MED-2026-305-01-001.pdf", b"%PDF-1.4 a")
        f.writestr("sub/dir/MED-2026-305-01-002.pdf", b"%PDF-1.4 b")                 # مجلد داخلي: يُسطَّح
        f.writestr("../../evil/MED-2026-305-01-003.pdf", b"%PDF-1.4 c")              # محاولة الخروج من المجلد: يُسطَّح
        f.writestr("C:\\windows\\MED-2026-305-01-004.pdf", b"%PDF-1.4 d")        # مسار ويندوز
        f.writestr("notes.txt", b"x")                                                # غير PDF: يُتجاهل
        f.writestr("__MACOSX/._MED-2026-305-01-001.pdf", b"x")                       # ضجيج ماك: يُتجاهل
        f.writestr("other/MED-2026-305-01-001.pdf", b"%PDF-1.4 dup")                 # مكرر الاسم: يُرفض
    plain = os.path.join(d, "MED-2026-305-01-009.pdf")
    open(plain, "wb").write(b"%PDF-1.4 p")
    bad = os.path.join(d, "broken.zip")
    open(bad, "wb").write(b"not a zip")
    work = os.path.join(d, "work")
    out, notes = JP.expand_uploads([plain, z, bad], work)
    names = sorted(os.path.basename(p) for p in out)
    print(names)
    for n in notes:
        print(" -", n)
    assert names == ["MED-2026-305-01-001.pdf", "MED-2026-305-01-002.pdf", "MED-2026-305-01-003.pdf", "MED-2026-305-01-004.pdf", "MED-2026-305-01-009.pdf"], names
    assert all(os.path.dirname(p) in (work, d) for p in out), out                       # لا شيء خارج مجلد العمل
    assert not os.path.exists(os.path.join(d, "evil")) and not os.path.exists(os.path.join(os.path.dirname(d), "evil"))
    assert any("مكرر" in n for n in notes) and any("غير صالح" in n for n in notes) and any("غير PDF" in n for n in notes)
    JP.MAX_ZIP_FILES = 2
    out2, notes2 = JP.expand_uploads([z], os.path.join(d, "work2"))
    assert out2 == [] and any("يتجاوز" in n for n in notes2), notes2
    print("OK")


if __name__ == "__main__":
    main()
