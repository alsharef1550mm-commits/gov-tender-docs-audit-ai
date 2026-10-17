"""الأسماء لا تشترط صيغة: ربطة باسم حر تُقبل في فحص الدفعة (بعقد وبلا عقد) والمنافسة، والتقرير يُنتج، وخانتا الدفعة والربطة تبقيان فارغتين."""
import glob, os, shutil, sys, io, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import openpyxl
import job_pipeline as JP, report_template as T
base = os.path.join(T.ROOT, "المنافسات", "منافسة جراحة العظام MED-2026-144")
src = sorted(glob.glob(os.path.join(base, "MED-2026-144-*.pdf")))[3]
contract = os.path.join(base, "العقد", "عقد المنافسة.pdf")
if __name__ == "__main__":
    tmp = tempfile.mkdtemp()
    free = os.path.join(tmp, "ربطة تجربة 1.pdf")
    shutil.copy2(src, free)
    for label, c in (("دفعة بلا عقد", None), ("دفعة بعقد", contract)):
        j = JP.create_job("batch", c, [free], synthetic=True)
        r = JP.run_job(j)
        assert r["state"] in ("awaiting_review", "approved"), (label, r["state"], r.get("error"))
        ws = openpyxl.load_workbook(r["output"])["المطابقة"]
        assert ws.cell(6, 5).value in (None, ""), ws.cell(6, 5).value               # رقم الدفعة فارغ لا مختلق
        print(label, "→", r["state"], "| رقم الدفعة فارغ | الملف:", os.path.basename(r["output"]))
    j = JP.create_job("competition", contract, [free], synthetic=True)
    r = JP.run_job(j)
    assert r["state"] in ("awaiting_review", "approved"), ("منافسة", r["state"], r.get("error"))
    print("منافسة باسم حر →", r["state"])
    print("OK")
