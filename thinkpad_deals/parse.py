"""Titel- und Preis-Normalisierung.

Alles hier ist reine Textverarbeitung ohne Netz, damit es offline testbar ist.
"""
from __future__ import annotations

import re
from typing import Optional

from .models import Specs

# --- Preis -----------------------------------------------------------------

_NUM = r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\d+(?:\.\d{1,2})?)"
# "179,00 €" / "1.557,99€" / "389 Euro"  oder  "EUR 249" / "€ 179,00"
_PRICE_RE = re.compile(
    r"(?<![\d,.])" + _NUM + r"\s*(?:€|EUR|Euro)(?![\w])|(?:€|EUR)\s*" + _NUM + r"(?![\d,.])",
    re.IGNORECASE,
)


def parse_price(text: str) -> Optional[float]:
    """Erster Euro-Betrag im Text. Deutsches Format (1.557,99 €) und 179.00 EUR."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    if "," in raw:
        raw = raw.replace(".", "").replace(" ", "").replace(",", ".")
    elif raw.count(".") == 1 and len(raw.split(".")[1]) == 3:
        # "1.557" ohne Cent: Tausenderpunkt
        raw = raw.replace(".", "")
    else:
        raw = raw.replace(" ", "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_all_prices(text: str) -> list[float]:
    out = []
    for m in _PRICE_RE.finditer(text or ""):
        p = parse_price(m.group(0))
        if p is not None:
            out.append(p)
    return out


# --- Specs -----------------------------------------------------------------

_MODEL_PATTERNS = [
    # X1 Carbon Gen 6 / X1 Carbon 6th / X1 Yoga 2nd / X1 Nano
    (re.compile(r"\bX1\s*(Carbon|Yoga|Nano|Extreme|Titanium)\s*(?:Gen(?:eration)?\.?\s*(\d+)|G(\d+)\b|(\d+)(?:st|nd|rd|th)?\b(?:\s*Gen)?)?", re.I),
     lambda m: f"X1 {m.group(1).title()}" + (f" Gen {m.group(2) or m.group(3) or m.group(4)}" if (m.group(2) or m.group(3) or m.group(4)) else "")),
    # T480s, T14 Gen 2, L15 G3, P52s, E14 Gen 4, X390, L13 Yoga
    (re.compile(r"\b([TXLPEAW])(\d{2,3})(s|p|i)?\s*(?:Yoga)?\s*(?:Gen(?:eration)?\.?\s*(\d+)|G(\d+))?\b", re.I),
     lambda m: f"{m.group(1).upper()}{m.group(2)}{(m.group(3) or '').lower()}"
               + (f" Gen {m.group(4) or m.group(5)}" if (m.group(4) or m.group(5)) else "")),
]

_CPU_RE = re.compile(
    r"\b(?:Intel\s*)?(?:Core\s*)?(i[3579])[\s-]*(\d{4,5}[A-Z]{0,2}\d?)\b"
    r"|\b(?:AMD\s*)?Ryzen\s*([3579])\s*(PRO\s*)?(\d{4}[A-Z]{1,2})\b"
    r"|\bCore\s*Ultra\s*([579])\s*(\d{3}[A-Z]?)\b",
    re.I,
)
_RAM_RE = re.compile(r"\b(\d{1,3})\s*GB\s*(?:(?:LP)?DDR\d?\w*|RAM|Arbeitsspeicher|Memory)", re.I)
_RAM_BARE_RE = re.compile(r"\b(\d{1,3})\s*RAM\b", re.I)          # "8 RAM, 128 SSD"
# refurbed/rebuy-Schreibweise: "Arbeitsspeicher Größe 16.0 GB", "Speicherplatz 512 GB" / "1 TB"
_RAM_LABEL_RE = re.compile(r"Arbeitsspeicher(?:\s*Gr[öo]ß?e)?\s*:?\s*(\d{1,3})(?:[.,]0)?\s*GB", re.I)
_SSD_LABEL_RE = re.compile(r"(?:Speicherplatz|Festplatte|Speicher)\s*(?:Größe)?\s*:?\s*(?:(\d{3,4})\s*GB|(\d)(?:[.,]0)?\s*TB)", re.I)
_SSD_BARE_RE = re.compile(r"\b(\d{3,4})\s*SSD\b", re.I)
# "16GB 256GB SSD": typische RAM-Groesse ohne Einheitenwort, nicht gefolgt von SSD/NVMe
_RAM_GUESS_RE = re.compile(r"\b(4|8|12|16|20|24|32|40|48|64)\s*GB\b(?!\s*(?:SSD|NVMe|HDD|eMMC|M\.?2))", re.I)
_RAM_SLASH_RE = re.compile(r"\b(\d{1,3})\s*GB\s*/\s*(\d{3,4})\s*GB\b", re.I)  # "16GB/256GB"
_SSD_RE = re.compile(r"\b(\d{3,4})\s*GB\s*(?:M\.?2\s*|NVMe\s*|PCIe\s*)?(?:SSD|NVMe|Speicher|Festplatte)\b|\b([12])\s*TB\b", re.I)
_SCREEN_RE = re.compile(r"\b(1[0-7])[.,]?(\d)?\s*(?:\"|''|Zoll|inch|in\b|”)", re.I)
_GRADE_RE = re.compile(r"\b(?:Zustand|Grade|Klasse|Note)?\s*:?\s*\b([ABC])\s?([+-])?(?:\s*-?\s*Ware|\s*Zustand)?\b")
_TOUCH_RE = re.compile(r"\btouch", re.I)


# Plausible Groessen. 2230/2242/2280 sind M.2-Bauformen, keine Kapazitaeten.
_RAM_OK = {2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 96, 128}
_SSD_BAD = {2230, 2242, 2280, 1920, 1080, 1200, 1600}


def _ram_ok(v) -> bool:
    return v in _RAM_OK


def _ssd_ok(v) -> bool:
    return v is not None and 64 <= v <= 8192 and v not in _SSD_BAD


def _normalize_title(title: str) -> str:
    # "ThinkPadX1 Yoga" -> "ThinkPad X1 Yoga", "T14Gen2" -> "T14 Gen2"
    title = re.sub(r"(?i)thinkpad(?=[A-Z0-9])", "ThinkPad ", title)
    return re.sub(r"(?i)(\d)(gen)\b", r"\1 \2", title)


def parse_specs(title: str, description: str = "") -> Specs:
    title = _normalize_title(title or "")
    text = f"{title} {description or ''}"
    s = Specs()

    for pat, fmt in _MODEL_PATTERNS:
        m = pat.search(title)
        if m:
            s.model = fmt(m)
            break

    m = _CPU_RE.search(text)
    if m:
        if m.group(1):
            s.cpu = f"{m.group(1).lower()}-{m.group(2).upper()}"
        elif m.group(3):
            pro = "PRO " if m.group(4) else ""
            s.cpu = f"Ryzen {m.group(3)} {pro}{m.group(5).upper()}"
        elif m.group(6):
            s.cpu = f"Core Ultra {m.group(6)} {m.group(7).upper()}"

    # RAM: Kandidaten in Prioritaet, erster plausibler Wert gewinnt
    ram_cands = []
    for pat in (_RAM_LABEL_RE, _RAM_RE, _RAM_BARE_RE):
        ram_cands += [int(m.group(1)) for m in pat.finditer(text)]
    m = _RAM_SLASH_RE.search(text)
    if m:
        ram_cands.append(int(m.group(1)))
    ram_cands += [int(m.group(1)) for m in _RAM_GUESS_RE.finditer(text)]
    s.ram_gb = next((v for v in ram_cands if _ram_ok(v)), None)

    # SSD: ebenso
    ssd_cands = []
    for m in _SSD_LABEL_RE.finditer(text):
        ssd_cands.append(int(m.group(1)) if m.group(1) else int(m.group(2)) * 1000)
    for m in _SSD_RE.finditer(text):
        ssd_cands.append(int(m.group(1)) if m.group(1) else int(m.group(2)) * 1000)
    m = _RAM_SLASH_RE.search(text)
    if m:
        ssd_cands.append(int(m.group(2)))
    ssd_cands += [int(m.group(1)) for m in _SSD_BARE_RE.finditer(text)]
    if s.ram_gb is not None:
        ssd_cands += [int(m.group(1)) for m in re.finditer(r"\b(\d{3,4})\s*GB\b", text, re.I)]
    s.ssd_gb = next((v for v in ssd_cands if _ssd_ok(v)), None)

    m = _SCREEN_RE.search(text)
    if m:
        s.screen_in = float(f"{m.group(1)}.{m.group(2) or 0}")

    low = text.lower()
    if re.search(r"refurb|generalüberholt|generalueberholt|wiederaufbereitet|aufbereitet", low):
        s.condition = "refurbished"
    elif re.search(r"\bgebraucht|\bused\b|second ?hand|vorführ", low):
        s.condition = "gebraucht"
    elif re.search(r"\bneu\b|\bnew\b|neuware|ovp", low):
        s.condition = "neu"

    m = re.search(r"(?:Zustand|Grade|Klasse)\s*:?\s*([ABC])\s?([+-])?", text, re.I)
    if m:
        s.grade = m.group(1).upper() + (m.group(2) or "")

    s.touch = bool(_TOUCH_RE.search(text))
    return s


def is_thinkpad(title: str) -> bool:
    return bool(re.search(r"thinkpad|\b[TXLPE]\d{2,3}[sp]?\b|\bX1\s*(Carbon|Yoga|Nano)", title or "", re.I))
