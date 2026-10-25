"""Selektoren automatisch vorschlagen.

Idee: Auf einer Listenseite stehen viele Preise. Fuer jeden Preis-Knoten
klettern wir nach oben, bis wir einen Vorfahren finden, von dem es auf der
Seite viele gleichartige Geschwister gibt. Dieser Vorfahre ist die
Artikelkarte. Innerhalb der Karte suchen wir den laengsten Linktext
(= Titel) und den Preis-Knoten. Das Ergebnis sind CSS-Selektoren, die du in
sources.yaml eintragen kannst.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, Tag

from .parse import _PRICE_RE

_MIN_ITEMS = 4


@dataclass
class Suggestion:
    item: str
    title: str
    price: str
    link: Optional[str]
    count: int
    sample_title: str
    sample_price: str


def _class_selector(tag: Tag) -> Optional[str]:
    classes = [c for c in (tag.get("class") or []) if re.match(r"^[A-Za-z][\w-]*$", c)]
    if not classes:
        return None
    # Kuerzeste, nicht-generische Klasse bevorzugen.
    classes = sorted(classes, key=len)
    for c in classes:
        if c.lower() not in {"row", "col", "item", "card", "box", "active", "clearfix"}:
            return f"{tag.name}.{c}"
    return f"{tag.name}.{classes[0]}"


def _rel_selector(root: Tag, node: Tag) -> str:
    """Selektor relativ zur Karte. Erst Klasse, sonst Pfad aus Tag-Namen."""
    cur: Optional[Tag] = node
    while cur is not None and cur is not root:
        s = _class_selector(cur)
        if s and len(root.select(s)) >= 1:
            return s
        cur = cur.parent
    parts = []
    cur = node
    while cur is not None and cur is not root:
        parts.append(cur.name)
        cur = cur.parent
    return " > ".join(reversed(parts)) or node.name


def _price_leaves(soup: BeautifulSoup) -> list[Tag]:
    leaves = []
    for s in soup.find_all(string=_PRICE_RE):
        parent = s.parent
        if parent and parent.name not in ("script", "style", "option", "title"):
            leaves.append(parent)
    return leaves


def suggest_selectors(html: str, min_items: int = _MIN_ITEMS) -> list[Suggestion]:
    soup = BeautifulSoup(html, "lxml")
    leaves = _price_leaves(soup)
    if not leaves:
        return []

    # Kandidaten fuer die Artikelkarte: Vorfahren der Preis-Knoten, gezaehlt nach Selektor.
    cand: Counter[str] = Counter()
    rep: dict[str, Tag] = {}
    for leaf in leaves:
        cur = leaf.parent
        depth = 0
        while isinstance(cur, Tag) and cur.name not in ("body", "html") and depth < 8:
            sel = _class_selector(cur)
            if sel:
                cand[sel] += 1
                rep.setdefault(sel, cur)
            cur = cur.parent
            depth += 1

    suggestions: list[Suggestion] = []
    for sel, n in cand.most_common(12):
        if n < min_items:
            continue
        cards = soup.select(sel)
        if len(cards) < min_items:
            continue
        # Karte muss klein genug sein, dass sie genau einen Preis enthaelt (sonst ist es der Container).
        per_card = [len(c.find_all(string=_PRICE_RE)) for c in cards]
        if sum(1 for x in per_card if x >= 1) < min_items or max(per_card) > 3:
            continue
        card = next(c for c in cards if c.find_all(string=_PRICE_RE))
        price_node = card.find(string=_PRICE_RE).parent
        links = [a for a in card.find_all("a") if a.get_text(strip=True)]
        if links:
            title_node = max(links, key=lambda a: len(a.get_text(strip=True)))
        else:
            heads = card.find_all(re.compile(r"^h[1-6]$"))
            title_node = heads[0] if heads else None
        if title_node is None:
            continue
        suggestions.append(
            Suggestion(
                item=sel,
                title=_rel_selector(card, title_node),
                price=_rel_selector(card, price_node),
                link=_rel_selector(card, title_node) if title_node.name == "a" else "a[href]",
                count=len(cards),
                sample_title=title_node.get_text(" ", strip=True)[:80],
                sample_price=price_node.get_text(" ", strip=True)[:30],
            )
        )
    # Meiste Karten zuerst; bei Gleichstand die aeusserste Huelle, die noch
    # genau ein Produkt umfasst (dort liegen Titel, Link und Preis sicher drin).
    suggestions.sort(key=lambda s: (-s.count, -len(str(rep[s.item]))))
    return suggestions
