"""الإلغاء القوي: الفحص يعمل في عملية مستقلة، والإلغاء يقتلها بالكامل فتختفي ولا تكمل الكتابة."""
import os, sys, io, time, tempfile, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pypdfium2 as pdfium
import app as A, job_pipeline as JP, report_template as T

if __name__ == "__main__":
    src = os.path.join(T.ROOT, "المنافسات", "منافسة جراحة العظام MED-2026-144", "MED-2026-144-01-004.pdf")
    pdf = pdfium.PdfDocument(src)
    imgs = [pdf[i].render(scale=2).to_pil().convert("L") for i in range(12)]
    scan = os.path.join(tempfile.mkdtemp(), "مسح إلغاء.pdf")
    imgs[0].save(scan, save_all=True, append_images=imgs[1:], resolution=150)
    os.environ.pop("VLM_URL", None)
    j = JP.create_job("batch", None, [scan], synthetic=True)
    JP.check_files(j)
    p = A._spawn(j.id)
    time.sleep(8)
    m = JP.Job(j.id).load()
    print("قبل الإلغاء:", m["state"], m.get("progress", {}).get("done"), "/", m.get("progress", {}).get("total"), "| pid", m.get("pid"))
    A._kill_tree(int(m["pid"]))
    JP.Job(j.id).set_state("failed", error="أُلغي الفحص بطلب المستخدم (أُوقفت العملية بالكامل)", cancelled=True)
    time.sleep(2)
    alive = p.poll() is None
    m2 = JP.Job(j.id).load()
    time.sleep(6)
    m3 = JP.Job(j.id).load()
    print("العملية حيّة بعد الإلغاء؟", alive, "| الحالة:", m3["state"], "| لم تتغير بعده:", m2["state"] == m3["state"] and m2.get("progress") == m3.get("progress"))
    assert not alive and m3["state"] == "failed" and m2.get("progress") == m3.get("progress")
    print("OK")
