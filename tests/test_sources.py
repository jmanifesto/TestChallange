from pathlib import Path

from thinkpad_deals.calibrate import suggest_selectors
from thinkpad_deals.sources.generic_shop import GenericShop
from thinkpad_deals.sources.mydealz_rss import MydealzRss

FIX = Path(__file__).parent / "fixtures"


def test_mydealz_rss_parse():
    src = MydealzRss("mydealz", feeds=[])
    items = list(src.parse((FIX / "mydealz.rss").read_text(encoding="utf-8")))
    titles = [i.title for i in items]
    assert len(items) == 3  # HP OMEN rausgefiltert
    t580 = items[0]
    assert t580.price == 179.0  # aus der Beschreibung, nicht aus dem Titel
    assert t580.specs.model == "T580" and t580.specs.cpu == "i5-8350U"
    assert "utm_" not in t580.url
    assert t580.extra["temperature"] == 639
    assert t580.seen_at.year == 2026
    assert items[2].price == 389.0  # "ab 389€" im Titel


def test_generic_shop_parse_and_pagination():
    src = GenericShop("shop", urls=[], item="div.product-box", title="a.product-name", price="span.product-price",
                      link="a.product-name", next_page="a.pagination-next", base_url="https://www.example-shop.de/")
    html = (FIX / "shop_listing.html").read_text(encoding="utf-8")
    listings, nxt = src.parse(html, page_url="https://www.example-shop.de/notebooks/lenovo/")
    assert nxt == "https://www.example-shop.de/notebooks/lenovo/?p=2"
    assert len(listings) == 5  # HP EliteBook rausgefiltert
    by_model = {l.specs.model: l for l in listings}
    assert by_model["T580"].price == 229.0
    assert by_model["T580"].url == "https://www.example-shop.de/p/lenovo-t580-713003"
    assert by_model["T580"].specs.grade == "B"
    assert by_model["X1 Yoga Gen 2"].price == 139.0
    assert by_model["L13"].price == 1099.0


def test_calibrate_finds_product_cards():
    html = (FIX / "shop_listing.html").read_text(encoding="utf-8")
    sugg = suggest_selectors(html)
    assert sugg, "keine Vorschlaege"
    best = sugg[0]
    assert best.item == "div.product-box"
    assert best.count == 6
    assert best.title == "a.product-name"
    assert best.price == "span.product-price"
    # Vorschlag muss tatsaechlich funktionieren:
    src = GenericShop("x", urls=[], item=best.item, title=best.title, price=best.price, link=best.link, only_thinkpad=False)
    listings, _ = src.parse(html, page_url="https://s.de/")
    assert len(listings) == 6 and all(l.price for l in listings)
