"""السند 3084 في الربطة المصغرة: قراءة آلية تُسقط الهللة من «مجموع القيمة» (20/15/50/500). المطلوب: لا خطأ حسابي منسوب للسند،
إحالة بنود إجمالي السطر غير المقروءة، وربط الفاتورة 5002601670 ببنود السند بالصنف/العدد/السعر رغم صف يخص سنداً آخر."""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlm"))
import engine, extract, report_template as T, report_writer as RW, vlm_reader
from make_synthetic_scans import page_truth
from test_vlm_reader import to_pred


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    src = os.path.join(os.environ["TEMP"], "MED-2026-318-01-077.pdf")
    b = extract.read_bundle(src)
    preds = []
    for n in range(1, b.n_pages + 1):
        t = page_truth(b, n)
        p = to_pred(t) if t["page_type"] != "other" else {"page_type": "other", "ids": {}, "items": []}
        if p["page_type"] == "receipt":
            for it in p["items"]:
                lt = str(it["line_total"]).split(".")[0]            # ريال بلا هللات
                it["line_total"], it["line_total_halala"] = lt, None
        preds.append(p)
    vb = vlm_reader.bundle_from_preds("MED-2026-318-01-077.pdf", preds)
    rules = engine.read_rules(os.path.join(T.ROOT, "مثال فحص دفعه", "عقد 318.pdf"), "MED-2026-318")
    res = {r.sto: r for r in engine.check_bundle(vb, rules)}["STO0000003084"]
    print("مشاكل حسابية:", [i.text for i in res.issues], "| net/comm/total:", res.net, res.commission, res.total)
    assert not res.issues and str(res.total) == "608.40"
    flags = [f for r in vb.receipts for f in getattr(r, "flags", [])]
    print("إجماليات غير مقروءة كاملة:", [(f["code"], f["seen"]) for f in flags])
    assert len(flags) == 2   # 20.80 و15.60 فقط؛ 52 و520 صحيحة بلا هللة
    print("OK")


if __name__ == "__main__":
    main()
