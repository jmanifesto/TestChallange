from pathlib import Path

from thinkpad_deals.cli import main

FIX = Path(__file__).parent / "fixtures"


def test_parse_command(capsys):
    rc = main(["parse", "Lenovo ThinkPad T580 15.6 Zoll i5 8350u 16GB DDR4 RAM 256GB SSD refurbished", "--price", "179"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "T580" in out and "i5-8350U" in out and "6076" in out


def test_calibrate_command_on_file(capsys):
    rc = main(["calibrate", str(FIX / "shop_listing.html")])
    out = capsys.readouterr().out
    assert rc == 0
    assert 'item: "div.product-box"' in out


def test_scan_with_local_sources(tmp_path, capsys, monkeypatch):
    """Scan komplett offline: Fetcher wird auf die Fixtures umgebogen."""
    import thinkpad_deals.cli as cli

    files = {"rss": (FIX / "mydealz.rss").read_text(encoding="utf-8"),
             "shop": (FIX / "shop_listing.html").read_text(encoding="utf-8")}

    class FakeFetcher:
        def __init__(self, *a, **k): ...
        def get(self, url, render=False, check_robots=True):
            return files["rss"] if "rss" in url else files["shop"]

    monkeypatch.setattr(cli, "Fetcher", FakeFetcher)
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("""
sources:
  - name: mydealz
    kind: mydealz_rss
    feeds: ["https://x/rss"]
  - name: shop
    kind: shop
    urls: ["https://shop.example/list"]
    max_pages: 1
    selectors: {item: "div.product-box", title: "a.product-name", price: "span.product-price", link: "a.product-name"}
""", encoding="utf-8")
    db = tmp_path / "deals.db"
    notify = tmp_path / "notify.txt"
    report = tmp_path / "report.md"
    rc = main(["--config", str(cfg), "--db", str(db), "scan", "--notify-file", str(notify),
               "--notify-min-score", "4.4", "--report", str(report)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "8 Angebote gesehen, 8 neu" in out
    # Preis-Leistung sortiert: T14 Gen 2 (399) und T580 (179) ganz oben, L13 fuer 1099 ganz unten
    lines = out.splitlines()[3:]
    assert "T14 Gen 2" in lines[0] and "179.00" in lines[1] and "T580" in lines[1]
    assert "1099.00" in lines[-3]
    hits = notify.read_text(encoding="utf-8").splitlines()
    assert len(hits) == 2 and "T580" in hits[1] and "mydealz.de" in hits[1]
    md = report.read_text(encoding="utf-8")
    assert "## Neu in diesem Lauf (8)" in md and "| 179 € |" in md and "## Bis 250 € mit 16 GB" in md

    rc = main(["--config", str(cfg), "--db", str(db), "top", "--max-price", "200"])
    out = capsys.readouterr().out
    assert rc == 0 and "T580" in out and "399.00" not in out
    rc = main(["--config", str(cfg), "--db", str(db), "top", "--markdown", "--limit", "2"])
    out = capsys.readouterr().out
    assert rc == 0 and out.startswith("| Preis |") and out.count("[Link](") == 2
