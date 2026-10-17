"""استخراج النص المباشر من صفحات PDF مع مواضع الكلمات.

العربية في هذه الملفات مخزنة بأشكال العرض وبترتيب بصري معكوس، لذلك:
- كل كلمة تُطبَّع بـ NFKC ثم تُعكس حروفها لتصبح بترتيب منطقي.
- السطر يُرتَّب حسب x؛ ويحتفظ الكائن بالإحداثيات لتكون دليلاً للمراجع.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import pdfplumber

_LIGATURE = re.compile("[ﻵ-ﻼ]")
ARABIC = re.compile(r"[؀-ۿﭐ-﻿]")


def fix_word(t: str) -> str:
    """كلمة عربية مخزنة بالمقلوب -> منطقية. الكلمات اللاتينية/الرقمية تبقى كما هي."""
    if ARABIC.search(t):
        t = _LIGATURE.sub(lambda m: unicodedata.normalize("NFKC", m.group(0))[::-1], t)   # حرف «لا» المركّب يُفكّ معكوساً قبل عكس الكلمة
        return unicodedata.normalize("NFKC", t)[::-1]
    return t


@dataclass
class Word:
    text: str          # بعد التصحيح
    raw: str           # كما ظهر في PDF
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass
class Line:
    top: float
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in sorted(self.words, key=lambda w: w.x0))

    def has(self, s: str) -> bool:
        return s in self.text


@dataclass
class Page:
    n: int                      # رقم الصفحة (يبدأ من 1)
    width: float
    height: float
    words: list[Word]
    lines: list[Line]

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)


def build_lines(words: list[Word], tol: float = 3.0) -> list[Line]:
    lines: list[Line] = []
    for w in sorted(words, key=lambda w: (w.top, w.x0)):
        if lines and abs(lines[-1].top - w.top) <= tol:
            lines[-1].words.append(w)
        else:
            lines.append(Line(top=w.top, words=[w]))
    return lines


def read_pdf(path: str, pages: list[int] | None = None) -> list[Page]:
    out: list[Page] = []
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        rng = pages or list(range(1, total + 1))
        for n in rng:
            pg = pdf.pages[n - 1]
            ws = [
                Word(fix_word(w["text"]), w["text"], w["x0"], w["x1"], w["top"], w["bottom"])
                for w in pg.extract_words(keep_blank_chars=False, use_text_flow=False)
            ]
            out.append(Page(n, float(pg.width), float(pg.height), ws, build_lines(ws)))
    return out


def page_count(path: str) -> int:
    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)
