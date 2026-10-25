from thinkpad_deals.models import Listing
from thinkpad_deals.parse import parse_specs
from thinkpad_deals.scoring import baseline_price, config_key, deal_label, load_cpu_scores, value_score
from thinkpad_deals.store import Store


def mk(title, price, source="t", url=None):
    return Listing(source=source, url=url or f"https://x/{abs(hash(title))}", title=title, price=price, specs=parse_specs(title))


def test_cpu_table_loads():
    t = load_cpu_scores()
    assert t["i5-8350U"] == 6076
    assert t["Ryzen 7 PRO 3700U"] == 7173


def test_value_ranking_matches_intuition():
    t = load_cpu_scores()
    t580 = mk("Lenovo ThinkPad T580 15.6\" i5-8350U 16GB RAM 256GB SSD refurbished", 179)
    yoga = mk("Lenovo ThinkPad X1 Yoga 2nd 14\" i5-7300U 8GB RAM 128GB SSD", 139)
    l15 = mk("Lenovo ThinkPad L15 G3 15.6\" i5-1235U 16GB RAM 512GB SSD", 389)
    l13 = mk("Lenovo ThinkPad L13 13,3\" i5-10210U 8GB 256GB SSD", 1099)
    for l in (t580, yoga, l15, l13):
        l.value_score = value_score(l, t)
    assert t580.cpu_score == 6076
    # 6.076 + 16*0.35 + 0.8 = 12.48 Punkte -> /(179+100)*100 = 4.47
    assert abs(t580.value_score - 4.47) < 0.05
    assert t580.value_score > l15.value_score > yoga.value_score > l13.value_score
    assert "gut" in deal_label(t580)
    assert deal_label(l13) == ""


def test_unknown_cpu_or_price_gives_no_score():
    t = load_cpu_scores()
    assert value_score(mk("ThinkPad T580 i5-9999U 16GB 256GB", 100), t) is None
    assert value_score(mk("ThinkPad T580 i5-8350U 16GB 256GB", None), t) is None


def test_baseline_needs_three_prices():
    assert baseline_price([199]) is None
    assert baseline_price([199, 229, 249]) == 229.0


def test_store_upsert_and_baseline():
    s = Store(":memory:")
    t = load_cpu_scores()
    titles = "ThinkPad T580 15.6\" i5-8350U 16GB RAM 256GB SSD"
    for i, p in enumerate((229, 249, 219)):
        l = mk(titles, p, url=f"https://shop/{i}")
        l.value_score = value_score(l, t)
        assert s.upsert(l) is True
    key = config_key(parse_specs(titles))
    assert sorted(s.prices_for_config(key)) == [219, 229, 249]
    deal = mk(titles, 179, url="https://shop/deal")
    deal.value_score = value_score(deal, t)
    deal.baseline_price = baseline_price(s.prices_for_config(key))
    assert deal.baseline_price == 229.0
    assert "-22% vs. Median" in deal_label(deal)
    assert s.upsert(deal) is True
    # zweites Sehen desselben Angebots ist kein neuer Eintrag, Preisaenderung landet in der Historie
    deal.price = 169
    assert s.upsert(deal) is False
    hist = s.conn.execute("SELECT price FROM price_history WHERE url='https://shop/deal' ORDER BY id").fetchall()
    assert [h[0] for h in hist] == [179, 169]
    assert s.top(limit=1)[0]["url"] == "https://shop/deal"
    assert s.top(max_price=170)[0]["price"] == 169
