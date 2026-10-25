from __future__ import annotations

from typing import Iterable, Protocol

from ..http import Fetcher
from ..models import Listing


class Source(Protocol):
    name: str

    def fetch(self, fetcher: Fetcher) -> Iterable[Listing]: ...


def build_sources(config: dict, only: str | None = None) -> list[Source]:
    """Baut aus config/sources.yaml die Quell-Objekte."""
    from .mydealz_rss import MydealzRss
    from .generic_shop import GenericShop

    kinds = {"mydealz_rss": MydealzRss, "shop": GenericShop}
    out: list[Source] = []
    for entry in config.get("sources", []):
        if not entry.get("enabled", True):
            continue
        if only and entry["name"] != only:
            continue
        cls = kinds[entry["kind"]]
        out.append(cls.from_config(entry))
    return out
