"""Lossless reading of printed decimal numbers, independent of accounting.

The caller retains the raw value. Ambiguous punctuation is not repaired by a
quantity-times-price calculation. Decimal comma is allowed only when unambiguous
or when the source's decimal convention is explicitly supplied.
"""
from decimal import Decimal, InvalidOperation
import re
import unicodedata


def decimal_reading(value, decimal_separator=None):
    if value is None or isinstance(value,bool):return None
    if isinstance(value,Decimal):return value if value.is_finite() else None
    s=unicodedata.normalize('NFKC',str(value)).strip()
    s=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in s)
    s=s.replace('\u200e','').replace('\u200f','').replace('\u061c','')
    if s.startswith('(') and s.endswith(')'):s='-'+s[1:-1]
    # Currency labels are accepted only at the edges, never inside digits.
    s=re.sub(r'^(?:SAR|ر\.س|ريال)\s*|\s*(?:SAR|ر\.س|ريال)$','',s,flags=re.I).strip()
    if '٫' in s:
        if '.' in s or ',' in s:return None
        s=s.replace('٫','.')
    if '٬' in s:
        if not re.fullmatch(r'[+-]?\d{1,3}(?:٬\d{3})+(?:\.\d+)?',s):return None
        s=s.replace('٬','')
    if re.search(r'\s',s):
        if not re.fullmatch(r'[+-]?\d{1,3}(?:\s\d{3})+(?:[.,]\d+)?',s):return None
        s=re.sub(r'\s','',s)
    if ',' in s:
        if decimal_separator==',':
            if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+),\d+',s):return None
            s=s.replace('.','').replace(',','.')
        elif '.' in s or s.count(',')>1 or decimal_separator=='.':
            if not re.fullmatch(r'[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?',s):return None
            s=s.replace(',','')
        elif re.fullmatch(r'[+-]?\d+,\d{1,2}',s):s=s.replace(',','.')
        else:return None  # 107,500 could mean 107.500 or 107500.
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',s):return None
    try:v=Decimal(s);return v if v.is_finite() else None
    except InvalidOperation:return None


def amount_reading(value,halala=None,decimal_separator=None):
    if halala in (None,''):return decimal_reading(value,decimal_separator)
    # With the halala in its own column the riyal part is a whole number, so "1,860" can only be grouped thousands.
    s=str(value or '').strip()
    if re.fullmatch(r'\d{1,3}(?:,\d{3})+',s):s=s.replace(',','')
    v=decimal_reading(s,decimal_separator)
    h=decimal_reading(halala)
    if v is None or h is None:return None
    # Some forms print the whole amount in the riyal column and repeat its fraction in the halala column
    # («33808.32 | 0.32» or «… | 32»): accepted only when the two printed values agree.
    if v!=v.to_integral_value():
        frac=abs(v)-int(abs(v))
        return v if h in (frac,frac*100) else None
    if h!=h.to_integral_value() or not 0<=h<100:return None
    return v-h/100 if v<0 else v+h/100


def quantity_reading(value, decimal_separator=None):
    """A quantity, also when its unit is printed in the same cell ("14 EA", "5 علبة"); nothing else is accepted."""
    if value is None:
        return None
    m = re.fullmatch(r"\s*([\d٠-٩.,٫٬]+)\s*[A-Za-z؀-ۿ]{1,8}\s*", str(value))
    return decimal_reading(m.group(1) if m else value, decimal_separator)


def page_separator(pred):
    """The decimal separator a page proves by itself: a value such as "22,486.46" (comma groups, dot decimal) shows
    that "1,320" on the same page is one thousand three hundred and twenty. None when the page proves nothing."""
    values = [v for sec in ("totals",) for v in ((pred or {}).get(sec) or {}).values()]
    values += [v for it in (pred or {}).get("items") or [] if isinstance(it, dict) for v in it.values()]
    texts = [str(v) for v in values if isinstance(v, str)]
    if any(re.fullmatch(r"\s*\d{1,3}(?:,\d{3})+\.\d+\s*", t) for t in texts):
        return "."
    if any(re.fullmatch(r"\s*\d{1,3}(?:\.\d{3})+,\d+\s*", t) for t in texts):
        return ","
    return None
