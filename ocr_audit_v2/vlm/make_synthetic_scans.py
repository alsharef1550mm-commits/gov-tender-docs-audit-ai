"""مجموعة قياس «ممسوحة اصطناعياً» بمرجع من **طبقة النص نفسها** (لا من تقارير قديمة).

الفكرة: صفحات ربطات المنافسات النصية معروفة الحقول بدقة (طبقة النص + مستخرجنا المُتحقَّق حسابياً)، فنصوّرها صوراً ثم نُفسدها
(ميل، ضبابية، ضجيج، ضغط JPEG، تباين، ظل) لنقيس قراءة الرؤية/OCR على حقول معروفة الحقيقة بالكامل ونجرّب التحسينات.
القيود الصريحة: هذا ليس ممسوحاً حقيقياً؛ القياس هنا حدّ أدنى لصعوبة الواقع ولا يُدّعى منه تعميم على وثائق حقيقية.
التقسيم على مستوى المنافسة: train = 318/305/144/231، val = 327، test = 339/407 (لا تسرب صفحات متجاورة أو ربطات بين الجانبين).

الاستعمال: python make_synthetic_scans.py [عدد الصفحات لكل نوع لكل منافسة]   -> vlm/bench/{images,manifest.json}
"""
from __future__ import annotations

import glob
import io
import json
import os
import random
import re
import sys

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import extract  # noqa: E402
import report_template as T  # noqa: E402

OUT = os.path.join(HERE, "bench")
SPLIT = {"318": "train", "305": "train", "144": "train", "231": "train", "327": "val", "339": "test", "407": "test"}
SEVERITY = {"mild": dict(rot=0.6, blur=0.4, noise=4, jpeg=80, contrast=0.95, shadow=0.05, scale=1.0),
            "medium": dict(rot=1.4, blur=0.7, noise=8, jpeg=60, contrast=0.85, shadow=0.12, scale=0.85),
            "severe": dict(rot=2.4, blur=1.0, noise=14, jpeg=45, contrast=0.72, shadow=0.22, scale=0.7)}


def degrade(img: Image.Image, sev: dict, rng: random.Random) -> Image.Image:
    img = img.convert("L")
    w, h = img.size
    img = img.resize((int(w * sev["scale"]), int(h * sev["scale"])), Image.BILINEAR)
    img = img.rotate(rng.uniform(-sev["rot"], sev["rot"]), resample=Image.BICUBIC, expand=True, fillcolor=245)
    if sev["blur"] > 0:
        img = img.filter(ImageFilter.GaussianBlur(sev["blur"] * rng.uniform(0.6, 1.2)))
    a = np.asarray(img, dtype=np.float32)
    a = 128 + (a - 128) * sev["contrast"] + (1 - sev["contrast"]) * 70                      # يخفّض التباين ويرفع الخلفية
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    a *= 1 - sev["shadow"] * (xx / a.shape[1]) * rng.uniform(0.5, 1.0)                       # ظل جانبي
    a += np.random.default_rng(rng.randrange(1 << 30)).normal(0, sev["noise"], a.shape)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=sev["jpeg"])
    return Image.open(io.BytesIO(buf.getvalue()))


def _s(x):
    return None if x is None else format(x, "f")


def page_truth(b, n):
    """حقول الصفحة n من مستخرج النص (كلها مطبوعة في الصفحة نفسها)."""
    t = {"page_type": None, "ids": {}, "items": [], "totals": {}}
    ty = b.page_types.get(n)
    t["page_type"] = {"po": "purchase_order", "purchase_order": "purchase_order", "receipt": "receipt", "invoice": "invoice"}.get(ty, "other")
    if t["page_type"] == "receipt":
        for r in b.receipts:
            if n in r.pages:
                t["ids"] = {"receipt_no": r.sto, "po_no": r.pon, "invoice_no": r.invoice_no}
                t["date"] = r.date
                for it in r.items:
                    if it.ev.page == n:
                        t["items"].append({"line_no": it.line_no, "item_code": it.code, "unit": it.unit, "qty": _s(it.qty),
                                           "unit_price": _s(it.unit_price), "line_total": _s(it.line_total)})
                if r.summary_ev is not None and r.summary_ev.page == n:
                    t["totals"] = {k: _s(v) for k, v in r.printed.items() if k in ("net", "nupco", "vat", "total", "penalty", "final")}
    elif t["page_type"] == "invoice":
        for v in b.invoices:
            if n in v.pages:
                t["ids"] = {"invoice_no": v.number}
                t["date"] = v.date
                for it in v.items:
                    if it.ev.page == n:
                        t["items"].append({"line_no": it.line_no, "item_code": it.code, "batch": it.batch, "qty": _s(it.qty),
                                           "unit_price": _s(it.unit_price), "net": _s(it.net), "commission": _s(it.nupco),
                                           "vat": _s(it.vat), "line_total": _s(it.total)})
    elif t["page_type"] == "purchase_order":
        for p in b.pos:
            if n in p.pages:
                t["ids"] = {"po_no": p.number}
                t["date"] = p.release_date
                for it in p.items:
                    if it.ev.page == n:
                        t["items"].append({"line_no": it.line_no, "item_code": it.code, "unit": it.unit, "qty": _s(it.qty_ordered),
                                           "unit_price": _s(it.unit_price), "line_total": _s(it.total), "vat": _s(it.vat), "final": _s(it.final)})
    return t


def one_comp(args):
    comp, per_type, seed = args
    split = SPLIT[comp]
    rng = random.Random(f"{seed}-{comp}")
    manifest = []
    folder = glob.glob(os.path.join(T.ROOT, "المنافسات", f"*MED-2026-{comp}"))[0]
    bundles = sorted(glob.glob(os.path.join(folder, f"MED-2026-{comp}-*.pdf")))
    picks = rng.sample(bundles, min(len(bundles), 6))
    pool = {"receipt": [], "invoice": [], "purchase_order": []}
    for path in picks:
        b = extract.read_bundle(path)
        for n in range(1, b.n_pages + 1):
            t = page_truth(b, n)
            if t["page_type"] in pool and t["items"]:
                pool[t["page_type"]].append((path, n, t))
    for ty, items in pool.items():
        for path, n, t in rng.sample(items, min(per_type, len(items))):
            sev_name = rng.choice(["mild", "medium", "severe"])
            doc = pdfium.PdfDocument(path)
            img = doc[n - 1].render(scale=3.0).to_pil()
            out = degrade(img, SEVERITY[sev_name], rng)
            fn = f"{comp}_{os.path.basename(path)[:-4].split('-')[-1]}_{n:03d}_{sev_name}.jpg"
            out.save(os.path.join(OUT, "images", fn), "JPEG", quality=SEVERITY[sev_name]["jpeg"])
            manifest.append({"image": fn, "competition": comp, "split": split, "bundle": os.path.basename(path), "page": n,
                             "severity": sev_name, "truth": t})
    return manifest


def main(per_type=8, seed=7):
    from multiprocessing import Pool
    os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
    with Pool(7) as pool:
        parts = pool.map(one_comp, [(c, per_type, seed) for c in SPLIT])
    manifest = [m for part in parts for m in part]
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("الإجمالي", len(manifest))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
