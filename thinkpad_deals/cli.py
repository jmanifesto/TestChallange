"""Kommandozeile.

  thinkpad-deals scan                  alle Quellen abfragen, bewerten, speichern
  thinkpad-deals scan --source ebay    nur eine Quelle
  thinkpad-deals top --max-price 250   beste Angebote aus der Historie
  thinkpad-deals calibrate URL         CSS-Selektoren fuer einen neuen Shop vorschlagen
  thinkpad-deals parse "Titel ..."     Titel-Erkennung testen
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .http import Fetcher
from .models import Listing
from .scoring import baseline_price, config_key, deal_label, load_cpu_scores, value_score
from .sources import build_sources
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "sources.yaml"


def load_config(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def evaluate(listing: Listing, store: Store, cpu_table: dict) -> Listing:
    listing.value_score = value_score(listing, cpu_table)
    listing.baseline_price = baseline_price(store.prices_for_config(config_key(listing.specs)))
    return listing


def fmt_row(l) -> str:
    """Einheitliche Zeile fuer Listing-Objekte und DB-Rows."""
    get = (lambda k: getattr(l, k, None)) if isinstance(l, Listing) else (lambda k: l[k])
    if isinstance(l, Listing):
        s = l.specs
        model, cpu, ram, ssd, scr = s.model, s.cpu, s.ram_gb, s.ssd_gb, s.screen_in
    else:
        model, cpu, ram, ssd, scr = l["model"], l["cpu"], l["ram_gb"], l["ssd_gb"], l["screen_in"]
    price = get("price")
    vs = get("value_score")
    label = deal_label(l) if isinstance(l, Listing) else ""
    return (
        f"{(f'{price:7.2f} €' if price else '    ?   €'):>10} | "
        f"{(f'{vs:5.2f}' if vs is not None else '  -  '):>5} | "
        f"{(model or '?'):<16} {(cpu or '?'):<18} {(f'{ram}GB' if ram else '?'):>5}/{(f'{ssd}GB' if ssd else '?'):<7} "
        f"{(f'{scr}\"' if scr else ''):>5} | {get('source'):<10} | {label} {get('url')}"
    )


def cmd_scan(args) -> int:
    cfg = load_config(args.config)
    cpu_table = load_cpu_scores(args.cpu_scores)
    store = Store(args.db)
    fetcher = Fetcher(delay_s=cfg.get("delay_s", 2.0), cache_ttl_s=cfg.get("cache_ttl_s", 1800))
    sources = build_sources(cfg, only=args.source)
    if not sources:
        print("Keine Quelle aktiv. config/sources.yaml pruefen.", file=sys.stderr)
        return 2
    new: list[Listing] = []
    total = 0
    for src in sources:
        try:
            for listing in src.fetch(fetcher):
                total += 1
                evaluate(listing, store, cpu_table)
                if store.upsert(listing):
                    new.append(listing)
        except Exception as e:  # eine kaputte Quelle soll die anderen nicht stoppen
            print(f"[{src.name}] Fehler: {e}", file=sys.stderr)
    new.sort(key=lambda l: (l.value_score is None, -(l.value_score or 0)))
    print(f"{total} Angebote gesehen, {len(new)} neu, {store.count()} in der Historie.\n")
    print("   Preis    | Pkt/100€ | Modell / CPU / RAM/SSD                 | Quelle     | Link")
    for l in new[: args.limit]:
        print(fmt_row(l))
    return 0


def cmd_top(args) -> int:
    store = Store(args.db)
    rows = store.top(limit=args.limit, max_price=args.max_price, min_cpu=args.min_cpu,
                     min_ram=args.min_ram, days=args.days)
    print("   Preis    | Pkt/100€ | Modell / CPU / RAM/SSD                 | Quelle     | Link")
    for r in rows:
        print(fmt_row(r))
    return 0


def cmd_calibrate(args) -> int:
    from .calibrate import suggest_selectors

    if Path(args.url).exists():
        html = Path(args.url).read_text(encoding="utf-8", errors="replace")
    else:
        html = Fetcher(cache_ttl_s=0).get(args.url, render=args.render)
    sugg = suggest_selectors(html)
    if not sugg:
        print("Keine wiederholten Preis-Bloecke gefunden. Seite evtl. per JS gerendert: --render probieren.")
        return 1
    for i, s in enumerate(sugg[:5], 1):
        print(f"--- Vorschlag {i} ({s.count} Karten) ---")
        print(f"  selectors:\n    item: \"{s.item}\"\n    title: \"{s.title}\"\n    price: \"{s.price}\"\n    link: \"{s.link}\"")
        print(f"  Beispiel: {s.sample_title!r} -> {s.sample_price!r}\n")
    return 0


def cmd_parse(args) -> int:
    from .parse import parse_price, parse_specs

    cpu_table = load_cpu_scores(args.cpu_scores)
    title = " ".join(args.text)
    l = Listing(source="cli", url="-", title=title, price=args.price or parse_price(title), specs=parse_specs(title))
    l.value_score = value_score(l, cpu_table)
    for k, v in vars(l.specs).items():
        print(f"{k:>10}: {v}")
    print(f"{'price':>10}: {l.price}")
    print(f"{'cpu_score':>10}: {l.cpu_score}")
    print(f"{'Pkt/100€':>10}: {l.value_score}  {deal_label(l)}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="thinkpad-deals", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--db", default="data/deals.db")
    p.add_argument("--cpu-scores", type=Path, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Quellen abfragen und bewerten")
    s.add_argument("--source", help="nur diese Quelle (Name aus sources.yaml)")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(fn=cmd_scan)

    t = sub.add_parser("top", help="beste Angebote aus der Historie")
    t.add_argument("--limit", type=int, default=20)
    t.add_argument("--max-price", type=float)
    t.add_argument("--min-cpu", type=int, default=0, help="min. PassMark, z.B. 6000")
    t.add_argument("--min-ram", type=int, default=0)
    t.add_argument("--days", type=int, help="nur in den letzten N Tagen gesehen")
    t.set_defaults(fn=cmd_top)

    c = sub.add_parser("calibrate", help="Selektoren fuer eine Shop-Liste vorschlagen")
    c.add_argument("url", help="URL oder lokale HTML-Datei")
    c.add_argument("--render", action="store_true", help="per Playwright rendern")
    c.set_defaults(fn=cmd_calibrate)

    q = sub.add_parser("parse", help="Titel-Erkennung testen")
    q.add_argument("text", nargs="+")
    q.add_argument("--price", type=float)
    q.set_defaults(fn=cmd_parse)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
