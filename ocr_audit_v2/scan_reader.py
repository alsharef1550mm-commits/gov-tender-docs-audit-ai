"""قراءة الصفحات الممسوحة (بلا طبقة نص): تصوير ← تحديد الاتجاه ← Tesseract بإحداثيات ← كلمات pdfx بوحدة نقاط PDF.

المخرجات تمرّ على المحلّلات نفسها (extract.py) ثم محرك الحساب؛ كل قيمة هنا «مقروءة آلياً» لا موثّقة: يتحقق منها التحقق الحسابي
وتُحال للمراجعة عند أي تعارض، ولا يُحكم منها بسلامة نهائية بلا اعتماد بشري.
"""
from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import tempfile
from multiprocessing import Pool

import pypdfium2 as pdfium
from PIL import Image

import pdfx

TESS = os.environ.get("TESSERACT_CMD") or (r"C:\Program Files\Tesseract-OCR\tesseract.exe" if os.name == "nt" else "tesseract")
LANG = os.environ.get("OCR_LANG", "eng+ara")
SCALE = 3.0                                   # 216 dpi


_BIDI = "".join(chr(c) for c in (0x200e, 0x200f, 0x202a, 0x202b, 0x202c, 0x202d, 0x202e, 0x2066, 0x2067, 0x2068, 0x2069, 0xfeff))


def _clean(t: str) -> str:
    return t.translate({ord(c): None for c in _BIDI}).strip()


def _tsv(img: Image.Image, psm: int, lang: str):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.png")
        img.save(p)
        out = subprocess.run([TESS, p, "stdout", "-l", lang, "--psm", str(psm), "tsv"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout
    rows = []
    for r in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE):
        t = _clean(r.get("text") or "")
        if r.get("level") == "5" and t:
            try:
                rows.append((t, float(r["conf"]), int(r["left"]), int(r["top"]), int(r["width"]), int(r["height"])))
            except Exception:  # noqa: BLE001
                pass
    return rows


def _orientation_score(img: Image.Image) -> float:
    small = img.convert("L")
    small = small.resize((max(1, small.width // 2), max(1, small.height // 2)))
    rows = _tsv(small, 6, "eng")
    return sum(c for (t, c, *_r) in rows if len(t) >= 3 and c > 60)


_STO_BAD = re.compile(r"^[S$5§]T[O0Q](\d{10})$")
_INDN = re.compile(r"^(?:IN|DN)(\d{10})$")


def _normalize_ids(words):
    """«$TO…» أو «5TO…» → STO… فقط حين تؤيّده أرقام IN/DN المطبوعة في الصفحة نفسها (تأييد لا تخمين)."""
    corro = {m.group(1) for w in words if (m := _INDN.match(w.text))}
    for w in words:
        m = _STO_BAD.match(w.text)
        if m and m.group(1) in corro:
            w.text = "STO" + m.group(1)


def _prep(img: Image.Image, mode: str) -> Image.Image:
    from PIL import ImageFilter, ImageOps
    if mode == "up15":
        img = img.resize((int(img.width * 1.5), int(img.height * 1.5)), Image.LANCZOS)
        return ImageOps.autocontrast(img.filter(ImageFilter.UnsharpMask(2, 100, 3)), cutoff=1)
    if mode == "ac":
        return ImageOps.autocontrast(img, cutoff=1)
    return img


def _osd(img: Image.Image):
    """كشف الاتجاه بـTesseract OSD على نسخة مصغّرة: (زاوية PIL المقابلة لـ«Rotate»، الثقة) أو None إن تعذّر."""
    import tempfile
    small = img.convert("L")
    k = 2200 / max(small.size)                                # الدقة مهمة: دون نحو 1500 بكسل تضعف ثقة OSD وتخطئ
    if k < 1:
        small = small.resize((int(small.width * k), int(small.height * k)))
    fd, p = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        small.save(p)
        out = subprocess.run([TESS, p, "stdout", "--psm", "0", "-l", "osd"], capture_output=True, text=True, timeout=60,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        rot = re.search(r"Rotate:\s*(\d+)", out)
        conf = re.search(r"Orientation confidence:\s*([\d.]+)", out)
        return (int(rot.group(1)), float(conf.group(1))) if rot and conf else None
    except Exception:  # noqa: BLE001
        return None
    finally:
        try:
            os.remove(p)
        except OSError:
            pass


def _read_score(img: Image.Image) -> float:
    """درجة قراءة فعلية بدقة كافية (الضلع الأطول نحو 1600 بكسل، بلا تصغير إضافي): مجموع ثقة الكلمات اللاتينية المقروءة."""
    g = img.convert("L")
    k = 1600 / max(g.size)
    if k < 1:
        g = g.resize((int(g.width * k), int(g.height * k)))
    return sum(cf for (tx, cf, *_r) in _tsv(g, 6, "eng") if len(tx) >= 3 and cf > 60)


def correct_orientation(img: Image.Image):
    """كشف اتجاه الصفحة وتصحيحه. يعيد (الصورة المصححة، زاوية PIL المطبّقة عكس عقارب الساعة).
    1) Tesseract OSD بدقة كافية: إن كانت ثقته ≥ 1.5 تُعتمد زاويته مباشرة (Rotate=r ⇒ يُدار الصورة بـ 360−r). سريع (~2 ث).
    2) وإلا تُقرأ الصفحة بالزوايا الأربع ويُختار أعلاها درجة قراءة (أبطأ، للصفحات الملتبسة فقط)."""
    img = img.convert("L")
    osd = _osd(img)
    if osd and osd[1] >= 1.5:
        a = (360 - osd[0]) % 360
        return (img.rotate(a, expand=True) if a else img), a
    scores = {a: _read_score(img.rotate(a, expand=True) if a else img) for a in (0, 90, 180, 270)}
    best = max(scores, key=lambda x: scores[x])
    return (img.rotate(best, expand=True) if best else img), best


def words_from_image(img: Image.Image, wpt: float, hpt: float, try_rotations: bool = True, pre: str = "none", psm: int = 6):
    """صورة (تدرج رمادي) ← كلمات pdfx بنقاط PDF مع اتجاه صحيح. يعيد (words, زاوية_الدوران, wpt, hpt)."""
    img = img.convert("L")
    best_a = 0
    if try_rotations:                                        # تصحيح الاتجاه إجباري (الافتراضي)
        img, best_a = correct_orientation(img)
    if best_a in (90, 270):
        wpt, hpt = hpt, wpt
    sx, sy = wpt / img.width, hpt / img.height
    # مرحلتان: اللاتينية وحدها تقرأ المعرّفات والأرقام بدقة أعلى (خلط ara+eng يفسدها)، والعربية من المرحلة الثنائية
    img = _prep(img, pre)
    sx, sy = wpt / img.width, hpt / img.height
    arabic = [r for r in _tsv(img, psm, LANG) if pdfx.ARABIC.search(r[0])]
    latin = [r for r in _tsv(img, psm, "eng") if not pdfx.ARABIC.search(r[0])]
    words = [pdfx.Word(t, t, x * sx, (x + w) * sx, y * sy, (y + h) * sy) for (t, c, x, y, w, h) in latin + arabic]
    _normalize_ids(words)
    return words, best_a, wpt, hpt


def _ocr_page(args):
    path, i = args
    doc = pdfium.PdfDocument(path)
    page = doc[i]
    wpt, hpt = page.get_size()
    words, _a, wpt, hpt = words_from_image(page.render(scale=SCALE).to_pil(), wpt, hpt, try_rotations=False)   # الاتجاه يُصحَّح بالأداة المستقلة قبل الرفع
    return pdfx.Page(i + 1, float(wpt), float(hpt), words, pdfx.build_lines(words))


def ocr_pages(path: str, workers: int | None = None, progress=None):
    n = pdfx.page_count(path)
    workers = workers or max(1, min(4, os.cpu_count() or 2))
    args = [(path, i) for i in range(n)]
    if workers == 1:
        out = []
        for k, a in enumerate(args, 1):
            out.append(_ocr_page(a))
            if progress:
                progress(k, n)
        return out
    with Pool(workers) as pool:
        out = []
        for k, p in enumerate(pool.imap(_ocr_page, args), 1):
            out.append(p)
            if progress:
                progress(k, n)
    return out
