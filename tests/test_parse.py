from thinkpad_deals.parse import is_thinkpad, parse_all_prices, parse_price, parse_specs

DEAL_TITLE = ("Lenovo ThinkPad T580, 15.6 Zoll Laptop mit Windows 11 - Intel i5 8350u, "
              "16GB DDR4 RAM, 256GB SSD, 2x USB-C, HDMI - refurbished Notebook")


def test_prices_german_formats():
    assert parse_price("179,00 €") == 179.0
    assert parse_price("1.557,99€") == 1557.99
    assert parse_price("ab 389€ - Intel") == 389.0
    assert parse_price("EUR 249") == 249.0
    assert parse_price("1.099,00 €") == 1099.0
    assert parse_price("kein Preis") is None
    assert parse_all_prices("statt 229,00 € jetzt 179,00 €") == [229.0, 179.0]


def test_deal_title_specs():
    s = parse_specs(DEAL_TITLE)
    assert s.model == "T580"
    assert s.cpu == "i5-8350U"
    assert s.ram_gb == 16
    assert s.ssd_gb == 256
    assert s.screen_in == 15.6
    assert s.condition == "refurbished"
    assert s.touch is False


def test_other_titles():
    s = parse_specs('Lenovo ThinkPad T490s 14" FHD Touch, i5-8365U, 8GB DDR4, 256GB SSD - refurbished')
    assert (s.model, s.cpu, s.ram_gb, s.ssd_gb, s.screen_in, s.touch) == ("T490s", "i5-8365U", 8, 256, 14.0, True)

    s = parse_specs("Lenovo ThinkPad X1 Yoga 2nd, 14\", i5-7300U, 8 RAM, 128 SSD, Zustand: B+")
    assert s.model == "X1 Yoga Gen 2"
    assert s.cpu == "i5-7300U"
    assert s.grade == "B+"

    s = parse_specs("Lenovo ThinkPad T14 Gen 2 14\" Ryzen 5 PRO 5650U 16GB 256GB SSD Zustand: A")
    assert s.model == "T14 Gen 2"
    assert s.cpu == "Ryzen 5 PRO 5650U"
    assert (s.ram_gb, s.ssd_gb, s.grade) == (16, 256, "A")

    s = parse_specs("Lenovo ThinkPad L15 G3, 15.6\" Laptop - Intel i5 1235U, 16GB RAM, 1 TB SSD")
    assert s.model == "L15 Gen 3"
    assert s.cpu == "i5-1235U"
    assert s.ssd_gb == 1000

    s = parse_specs("ThinkPad X1 Carbon Gen 6 i7-8650U 16GB/512GB gebraucht")
    assert s.model == "X1 Carbon Gen 6"
    assert (s.ram_gb, s.ssd_gb, s.condition) == (16, 512, "gebraucht")


def test_is_thinkpad():
    assert is_thinkpad("Lenovo ThinkPad T580")
    assert is_thinkpad("Lenovo T480s 14 Zoll")
    assert not is_thinkpad("HP HyperX OMEN 16")
    assert not is_thinkpad("Lenovo IdeaPad 5")
