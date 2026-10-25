from datetime import datetime, timedelta, timezone

from thinkpad_deals.cli import main
from thinkpad_deals.models import Listing
from thinkpad_deals.parse import parse_specs
from thinkpad_deals.scoring import load_cpu_scores, load_profiles, profile_misses, value_score

T = load_cpu_scores()
P = load_profiles()


def mk(title, price, days_old=0):
    l = Listing(source="t", url=f"https://x/{title}", title=title, price=price, specs=parse_specs(title),
                seen_at=datetime.now(timezone.utc) - timedelta(days=days_old))
    l.value_score = value_score(l, T)
    return l


def test_dev_profile_matches_workstation_only():
    dev = P["dev"]
    assert profile_misses(mk("ThinkPad T14 Gen 3 i7-1260P 32GB RAM 1TB SSD", 699), dev) == []
    assert profile_misses(mk("ThinkPad P14s Gen 4 Ryzen 7 PRO 7840U 32GB 512GB SSD", 899), dev) == []
    # der T580-Deal: 16 GB, alte CPU
    miss = profile_misses(mk("ThinkPad T580 i5-8350U 16GB DDR4 RAM 256GB SSD", 179), dev)
    assert any("RAM" in m for m in miss) and any("CPU" in m for m in miss)
    # i7, aber alt und zu wenig RAM
    miss = profile_misses(mk("ThinkPad X1 Carbon Gen 6 i7-8650U 16GB 512GB SSD", 299), dev)
    assert any("CPU i7-8650U" in m for m in miss)
    # zu teuer
    assert any("Preis" in m for m in profile_misses(mk("ThinkPad P1 Gen 5 i7-12700H 32GB 1TB SSD", 1400), dev))
    # zu alt
    assert any("Tage" in m for m in profile_misses(mk("ThinkPad T14 Gen 3 i7-1260P 32GB 1TB SSD", 699, days_old=30), dev))
    # unbekannte CPU, aber i7-Klasse: zaehlt
    assert profile_misses(mk("ThinkPad T14 Gen 5 i7-9999X 32GB 1TB SSD", 800), dev) == []


def test_office_profile_accepts_t580():
    assert profile_misses(mk("ThinkPad T580 i5-8350U 16GB DDR4 RAM 256GB SSD refurbished", 179), P["office"]) == []


def test_top_with_profile(tmp_path, capsys):
    from thinkpad_deals.store import Store
    db = tmp_path / "d.db"
    s = Store(db)
    for l in (mk("ThinkPad T14 Gen 3 i7-1260P 32GB RAM 1TB SSD", 699),
              mk("ThinkPad T580 i5-8350U 16GB DDR4 RAM 256GB SSD", 179)):
        s.upsert(l)
    s.close()
    assert main(["--db", str(db), "--profile", "dev", "top", "--markdown"]) == 0
    out = capsys.readouterr().out
    assert "T14 Gen 3" in out and "T580" not in out
