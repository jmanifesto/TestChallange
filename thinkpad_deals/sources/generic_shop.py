"""Selektor-gesteuerter Listen-Scraper fuer beliebige Shops.

Du gibst in sources.yaml an, welche Listen-URLs es gibt und mit welchen
CSS-Selektoren Artikel, Titel, Preis und Link zu finden sind. Die Selektoren
findest du mit `thinkpad-deals calibrate URL` oder per Browser-DevTools.
"""
from __future__ import annotations

from typing import Iterable, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..http import Fetcher
from ..models import Listing
from ..parse import is_thinkpad, parse_price, parse_specs


class GenericShop:
    kind = "shop"

    def __init__(
        self,
        name: str,
        urls: list[str],
        item: str,
        title: str,
        price: str,
        link: Optional[str] = None,
        next_page: Optional[str] = None,
        description: Optional[str] = None,
        max_pages: int = 5,
        render: bool = False,
        only_thinkpad: bool = True,
        base_url: Optional[str] = None,
        ignore_robots: bool = False,
    ):
        self.name = name
        self.urls = urls
        self.sel_item = item
        self.sel_title = title
        self.sel_price = price
        self.sel_link = link
        self.sel_next = next_page
        self.sel_desc = description
        self.max_pages = max_pages
        self.render = render
        self.only_thinkpad = only_thinkpad
        self.base_url = base_url
        self.ignore_robots = ignore_robots

    @classmethod
    def from_config(cls, c: dict) -> "GenericShop":
        sel = c["selectors"]
        return cls(
            name=c["name"],
            urls=c["urls"],
            item=sel["item"],
            title=sel["title"],
            price=sel["price"],
            link=sel.get("link"),
            next_page=sel.get("next_page"),
            description=sel.get("description"),
            max_pages=c.get("max_pages", 5),
            render=c.get("render", False),
            only_thinkpad=c.get("only_thinkpad", True),
            base_url=c.get("base_url"),
            ignore_robots=c.get("ignore_robots", False),
        )

    def fetch(self, fetcher: Fetcher) -> Iterable[Listing]:
        for start in self.urls:
            if "{page}" in start:
                # Seitenzaehlung per Platzhalter: .../lenovo?page={page} -> 1..max_pages,
                # Abbruch, sobald eine Seite keine Karten mehr liefert.
                for n in range(1, self.max_pages + 1):
                    url = start.replace("{page}", str(n))
                    html = fetcher.get(url, render=self.render, check_robots=not self.ignore_robots)
                    listings, _ = self.parse(html, page_url=url)
                    if not listings and not self._has_cards(html):
                        break
                    yield from listings
                continue
            url: Optional[str] = start
            pages = 0
            while url and pages < self.max_pages:
                html = fetcher.get(url, render=self.render, check_robots=not self.ignore_robots)
                listings, url = self.parse(html, page_url=url)
                yield from listings
                pages += 1

    def _has_cards(self, html: str) -> bool:
        return bool(BeautifulSoup(html, "lxml").select_one(self.sel_item))

    def parse(self, html: str, page_url: str = "") -> tuple[list[Listing], Optional[str]]:
        soup = BeautifulSoup(html, "lxml")
        base = self.base_url or page_url
        out: list[Listing] = []
        for node in soup.select(self.sel_item):
            t = node.select_one(self.sel_title)
            if not t:
                continue
            title = t.get_text(" ", strip=True)
            if self.only_thinkpad and not is_thinkpad(title):
                continue
            p = node.select_one(self.sel_price)
            price = parse_price(p.get_text(" ", strip=True)) if p else None
            href = None
            link_node = node.select_one(self.sel_link) if self.sel_link else (t if t.name == "a" else node.select_one("a[href]"))
            if link_node is not None:
                href = link_node.get("href")
            url = urljoin(base, href) if href else base
            desc = ""
            if self.sel_desc:
                d = node.select_one(self.sel_desc)
                desc = d.get_text(" ", strip=True) if d else ""
            out.append(Listing(source=self.name, url=url, title=title, price=price, specs=parse_specs(title, desc)))
        nxt = None
        if self.sel_next:
            n = soup.select_one(self.sel_next)
            if n is not None and n.get("href"):
                nxt = urljoin(base, n["href"])
        return out, nxt
