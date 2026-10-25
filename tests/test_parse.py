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


def test_plausibility_filters_formfactor_and_bogus_ram():
    s = parse_specs("Lenovo ThinkPad T14 Gen 1 i5-10310U 16GB RAM 512GB M.2 SSD",
                    "Formfaktor M.2 2280 SSD, 512 GB Speicher, Arbeitsspeicher 16 GB DDR4")
    assert (s.ram_gb, s.ssd_gb) == (16, 512)
    s = parse_specs("Lenovo ThinkPad X13 Gen 2 i5-1145G7 8GB RAM 256GB M.2 2280 SSD")
    assert (s.ram_gb, s.ssd_gb) == (8, 256)


def test_thinkpad_without_space_and_yoga_370():
    s = parse_specs('Lenovo ThinkPadX1 Yoga 4th | 14" | i5-8365U | 16 GB RAM | 256 GB SSD')
    assert s.model == "X1 Yoga Gen 4"
    assert parse_specs("Lenovo ThinkPad T14Gen2 i5-1145G7 16GB 256GB").model == "T14 Gen 2"


def test_real_mydealz_descriptions():
    # Echte Feed-Texte vom 2026-10-25, die vorher 512 GB RAM bzw. 32 GB ergaben
    t = 'Lenovo Thinkpad T14 Gen 1: 14" FHD, Intel Core i5-10310U, 16GB RAM, 512GB M.2 SSD, TB3, Wi-Fi 6, Win11 Pro - Refurbished für 177€ (eBay)'
    d = ("177€ - eBay ... Intel Core i5-10310U Prozessor, 4 Kerne / 8 Threads 16 GB DDR4 Arbeitsspeicher "
         "512 GB M.2 NVMe SSD Intel UHD Graphics WLAN 6 (802.11ax)")
    s = parse_specs(t, d)
    assert (s.model, s.cpu, s.ram_gb, s.ssd_gb, s.screen_in) == ("T14 Gen 1", "i5-10310U", 16, 512, 14.0)

    t = 'Lenovo ThinkPad L14 G2, 14" Laptop, ab 312€ - Intel i7 1165g7, 16-32GB RAM, LTE, 500GB M.2 SSD, 2x USB-C 1x TB4, LAN - refurbished, AfB-Shop'
    d = ("343,20€ - AfB ... Falls ihr mehr RAM benötigt, dann könnt ihr zu der 32GB-Version greifen: 14,0 Zoll - "
         "Intel Core i7 1165G7 @ 2,8 GHz - 32 GB DDR4 - 500 GB SSD ... RAM: 1x 16GB DDR4 2x SO-DIMM Slots")
    s = parse_specs(t, d)
    assert (s.model, s.cpu, s.ram_gb, s.ssd_gb) == ("L14 Gen 2", "i7-1165G7", 16, 500)
