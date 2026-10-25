from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Specs:
    """Aus dem Angebotstitel extrahierte Hardware-Daten."""

    model: Optional[str] = None        # z.B. "T580", "X1 Carbon Gen 6"
    cpu: Optional[str] = None          # z.B. "i5-8350U"
    ram_gb: Optional[int] = None
    ssd_gb: Optional[int] = None
    screen_in: Optional[float] = None  # 14.0, 15.6
    condition: Optional[str] = None    # "refurbished", "gebraucht", "neu"
    grade: Optional[str] = None        # "A", "A-", "B+", ...
    touch: bool = False


@dataclass
class Listing:
    """Ein beobachtetes Angebot aus einer Quelle."""

    source: str
    url: str
    title: str
    price: Optional[float]
    currency: str = "EUR"
    seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    specs: Specs = field(default_factory=Specs)
    cpu_score: Optional[int] = None
    value_score: Optional[float] = None   # Leistungspunkte pro Euro, hoeher = besser
    baseline_price: Optional[float] = None  # Median bisher gesehener Preise fuer gleiche Konfig
    extra: dict = field(default_factory=dict)

    def to_row(self) -> dict:
        d = asdict(self)
        d.pop("specs")
        d.pop("extra")
        d["seen_at"] = self.seen_at.isoformat()
        for k, v in asdict(self.specs).items():
            d[k] = int(v) if isinstance(v, bool) else v
        return d
