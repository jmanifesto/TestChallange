"""Bewertung: wie viel Rechner bekomme ich pro Euro, und ist der Preis fuer
diese Konfiguration historisch guenstig?

Die Formel ist bewusst simpel und in einer Datei, damit du sie nach deinem
Geschmack verbiegen kannst.
"""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Iterable, Optional

import yaml

from .models import Listing, Specs

_DEFAULT_CPU_FILE = Path(__file__).resolve().parent.parent / "config" / "cpu_scores.yaml"

# Gewichte: ein "Leistungspunkt" entspricht grob 1000 PassMark-Punkten.
W_CPU = 1.0        # pro 1000 PassMark
W_RAM = 0.35       # pro GB -> 16 GB = 5.6 Punkte
W_SSD = 0.8        # pro 256 GB
W_TOUCH = 0.5
SCREEN_BONUS = {14.0: 0.5, 13.3: 0.3, 12.5: 0.0, 15.6: 0.0}

# Jedes Geraet kostet dich Zeit, Versand und Risiko. Dieser Grundbetrag wird
# zum Preis addiert, damit 139-Euro-Schrott nicht automatisch vor einem
# 389-Euro-Geraet mit vierfacher Leistung landet.
PRICE_OFFSET = 100.0

# Ohne Preis oder ohne CPU ist kein Vergleich moeglich.
MIN_PRICE = 30.0

LABEL_GOOD = 4.0
LABEL_TOP = 5.0


def load_cpu_scores(path: Optional[Path] = None) -> dict[str, int]:
    p = Path(path) if path else _DEFAULT_CPU_FILE
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {str(k).strip(): int(v) for k, v in data.items()}


def cpu_score_for(cpu: Optional[str], table: dict[str, int]) -> Optional[int]:
    if not cpu:
        return None
    if cpu in table:
        return table[cpu]
    # Tolerant: "i5-8350U" vs "I5-8350u"
    low = {k.lower(): v for k, v in table.items()}
    return low.get(cpu.lower())


def hardware_points(specs: Specs, cpu_score: Optional[int]) -> Optional[float]:
    if cpu_score is None:
        return None
    pts = cpu_score / 1000.0 * W_CPU
    if specs.ram_gb:
        pts += specs.ram_gb * W_RAM
    if specs.ssd_gb:
        pts += specs.ssd_gb / 256.0 * W_SSD
    if specs.touch:
        pts += W_TOUCH
    if specs.screen_in in SCREEN_BONUS:
        pts += SCREEN_BONUS[specs.screen_in]
    return pts


def value_score(listing: Listing, cpu_table: dict[str, int]) -> Optional[float]:
    """Leistungspunkte pro 100 Euro (Preis + Grundbetrag). Hoeher = mehr Rechner fuers Geld."""
    if listing.price is None or listing.price < MIN_PRICE:
        return None
    score = cpu_score_for(listing.specs.cpu, cpu_table)
    listing.cpu_score = score
    pts = hardware_points(listing.specs, score)
    if pts is None:
        return None
    return round(pts / (listing.price + PRICE_OFFSET) * 100.0, 2)


def config_key(specs: Specs) -> Optional[str]:
    """Schluessel fuer 'gleiche Konfiguration' beim historischen Vergleich."""
    if not specs.model or not specs.cpu:
        return None
    return f"{specs.model}|{specs.cpu}|{specs.ram_gb or '?'}|{specs.ssd_gb or '?'}"


def baseline_price(prices: Iterable[float]) -> Optional[float]:
    prices = [p for p in prices if p and p >= MIN_PRICE]
    if len(prices) < 3:
        return None
    return round(statistics.median(prices), 2)


def deal_label(listing: Listing) -> str:
    """Kurze Einordnung fuer die Ausgabe."""
    tags = []
    if listing.value_score is not None:
        if listing.value_score >= LABEL_TOP:
            tags.append("TOP")
        elif listing.value_score >= LABEL_GOOD:
            tags.append("gut")
    if listing.baseline_price and listing.price:
        ratio = listing.price / listing.baseline_price
        if ratio <= 0.8:
            tags.append(f"-{round((1 - ratio) * 100)}% vs. Median")
        elif ratio >= 1.2:
            tags.append("teurer als ueblich")
    return ", ".join(tags)
