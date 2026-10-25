"""Selektoren und Parser gegen Karten aus den echten Shop-Seiten (probe-page, 2026-10-25)."""
from pathlib import Path

import yaml

from thinkpad_deals.parse import parse_specs
from thinkpad_deals.sources.generic_shop import GenericShop

FIX = Path(__file__).parent / "fixtures"
CFG = yaml.safe_load((Path(__file__).parent.parent / "config" / "sources.yaml").read_text(encoding="utf-8"))
SRC = {s["name"]: s for s in CFG["sources"]}


def shop(name, **kw):
    c = dict(SRC[name]); c.update(kw)
    return GenericShop.from_config(c)


def test_hardware_online_shop_cards():
    listings, _ = shop("hardware-online-shop").parse((FIX / "hos_listing.html").read_text(encoding="utf-8"),
                                                     page_url="https://www.hardware-online-shop.de/refurbished-laptops/lenovo")
    assert len(listings) == 3  # IdeaPad rausgefiltert
    prices = sorted(l.price for l in listings)
    assert prices == [174.9, 299.0, 379.0]
    assert all(l.url.startswith("https://www.hardware-online-shop.de/p/") for l in listings)
    assert all(l.specs.model and l.specs.cpu and l.specs.ram_gb for l in listings), [l.specs for l in listings]


def test_refurbed_cards_with_spec_line():
    listings, _ = shop("refurbed").parse((FIX / "refurbed_listing.html").read_text(encoding="utf-8"),
                                         page_url="https://www.refurbed.de/c/lenovo-laptops/")
    by = {l.specs.model: l for l in listings}
    assert set(by) == {"X1 Yoga Gen 6", "T490"}  # MacBook rausgefiltert
    x1 = by["X1 Yoga Gen 6"]
    assert (x1.price, x1.specs.cpu, x1.specs.ram_gb, x1.specs.ssd_gb, x1.specs.screen_in) == (559.0, "i7-1185G7", 16, 256, 14.0)
    assert x1.url == "https://www.refurbed.de/p/lenovo-tp-x1-yoga-g6-i7-1185g7/"
    assert by["T490"].price == 290.49


def test_rebuy_cards():
    listings, _ = shop("rebuy").parse((FIX / "rebuy_listing.html").read_text(encoding="utf-8"),
                                      page_url="https://www.rebuy.de/kaufen/notebooks/lenovo")
    assert len(listings) == 1  # das iPad faellt raus
    l = listings[0]
    assert l.price == 843.99
    assert (l.specs.model, l.specs.cpu, l.specs.ram_gb, l.specs.ssd_gb) == ("T14 Gen 3", "i7-1260P", 32, 1000)
    assert l.url.startswith("https://www.rebuy.de/i,")


def test_label_specs_parse():
    s = parse_specs("Lenovo ThinkPad T14 G2 | i5-1145G7 | 14\"", "Arbeitsspeicher Größe 16.0 GB +1 | Speicherplatz 1 TB +3")
    assert (s.model, s.cpu, s.ram_gb, s.ssd_gb) == ("T14 Gen 2", "i5-1145G7", 16, 1000)


def test_page_placeholder_stops_on_empty_page():
    html = (FIX / "hos_listing.html").read_text(encoding="utf-8")
    calls = []

    class F:
        def get(self, url, render=False, check_robots=True):
            calls.append(url)
            return html if url.endswith("page=1") else "<html><body>leer</body></html>"

    out = list(shop("hardware-online-shop", max_pages=4).fetch(F()))
    assert len(out) == 3 and calls == ["https://www.hardware-online-shop.de/refurbished-laptops/lenovo?page=1",
                                       "https://www.hardware-online-shop.de/refurbished-laptops/lenovo?page=2"]


def test_afb_cards_take_smallest_variant():
    listings, _ = shop("afb").parse((FIX / "afb_listing.html").read_text(encoding="utf-8"),
                                    page_url="https://www.afbshop.de/gebrauchte-notebooks/lenovo-thinkpads/")
    assert len(listings) == 2
    t14s = next(l for l in listings if "T14s" in l.title)
    assert t14s.price == 469.0
    assert (t14s.specs.model, t14s.specs.cpu, t14s.specs.ram_gb, t14s.specs.ssd_gb) == ("T14s Gen 2", "i5-1135G7", 8, 250)
    assert t14s.url == "https://www.afbshop.de/lenovo-thinkpad-t14s-gen-2-intel/de-35.209-b/"
