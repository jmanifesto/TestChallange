"""mydealz stellt RSS-Feeds bereit. Das ist der sauberste Weg: strukturierte
Daten, kein HTML-Raten, keine Last auf der Seite.

Beispiele:
  https://www.mydealz.de/rss/gruppe/lenovo-thinkpad
  https://www.mydealz.de/rss/suche?q=thinkpad+refurbished
  https://www.mydealz.de/rss/neu
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable

import feedparser
from bs4 import BeautifulSoup

from ..http import Fetcher
from ..models import Listing
from ..parse import is_thinkpad, parse_price, parse_specs


class MydealzRss:
    kind = "mydealz_rss"

    def __init__(self, name: str, feeds: list[str], only_thinkpad: bool = True):
        self.name = name
        self.feeds = feeds
        self.only_thinkpad = only_thinkpad

    @classmethod
    def from_config(cls, c: dict) -> "MydealzRss":
        return cls(c["name"], c["feeds"], c.get("only_thinkpad", True))

    def fetch(self, fetcher: Fetcher) -> Iterable[Listing]:
        for url in self.feeds:
            # Feeds sind ausdruecklich fuer Maschinen gedacht, robots.txt greift hier nicht.
            xml = fetcher.get(url, check_robots=False)
            yield from self.parse(xml)

    def parse(self, xml: str) -> Iterable[Listing]:
        feed = feedparser.parse(xml)
        for e in feed.entries:
            title = (e.get("title") or "").strip()
            if self.only_thinkpad and not is_thinkpad(title):
                continue
            desc_html = e.get("summary") or e.get("description") or ""
            desc = BeautifulSoup(desc_html, "lxml").get_text(" ", strip=True)
            price = None
            # mydealz schreibt den Preis in manche Feeds als eigenes Feld, sonst steht er im Text.
            for key in ("pepper_merchant", "price"):
                v = e.get(key)
                if isinstance(v, dict):
                    v = v.get("price")
                if v:
                    price = parse_price(str(v))
                    break
            if price is None:
                price = parse_price(title) or parse_price(desc)
            seen = datetime.now(timezone.utc)
            if e.get("published"):
                try:
                    seen = parsedate_to_datetime(e["published"])
                except Exception:
                    pass
            link = e.get("link") or ""
            link = re.sub(r"[?&]utm_[^&]+", "", link).rstrip("?&")
            yield Listing(
                source=self.name,
                url=link,
                title=title,
                price=price,
                seen_at=seen,
                specs=parse_specs(title, desc),
                extra={"temperature": _temperature(desc_html)},
            )


def _temperature(html: str):
    m = re.search(r"(-?\d+)\s*°", html or "")
    return int(m.group(1)) if m else None
