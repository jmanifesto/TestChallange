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
from .scoring import (baseline_price, config_key, deal_label, load_cpu_scores, load_profiles,
                      profile_misses, value_score)
from .sources import build_sources
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "sources.yaml"
DEFAULT_CONTROL = ROOT / "config" / "control.json"


def load_control(path) -> dict:
    """config/control.json: die von der Steuerseite bearbeiteten Einstellungen. Fehlt sie, gilt sources.yaml."""
    import json
    p = Path(path) if path else DEFAULT_CONTROL
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def apply_control(cfg: dict, control: dict) -> dict:
    """enabled/max_pages/urls pro Quelle aus control.json ueber sources.yaml legen."""
    ctl_sources = control.get("sources") or {}
    for entry in cfg.get("sources", []):
        c = ctl_sources.get(entry["name"])
        if not c:
            continue
        for key in ("enabled", "max_pages", "render"):
            if key in c:
                entry[key] = c[key]
        if c.get("urls"):
            entry["feeds" if entry.get("kind") == "mydealz_rss" else "urls"] = list(c["urls"])
    return cfg


def title_passes(title: str, control: dict) -> bool:
    low = (title or "").lower()
    kws = [k.lower() for k in control.get("keywords") or []]
    if kws and not any(k in low for k in kws):
        return False
    return not any(x.lower() in low for x in control.get("exclude") or [])


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


def get_profile(args, control: dict | None = None) -> dict | None:
    control = control or {}
    name = args.profile or control.get("profile")
    if not name:
        return None
    profiles = load_profiles(args.profiles)
    if name not in profiles:
        raise SystemExit(f"Profil {name!r} nicht in config/profiles.yaml. Vorhanden: {', '.join(profiles)}")
    prof = dict(profiles[name])
    prof.update({k: v for k, v in (control.get("profile_overrides") or {}).items() if v not in (None, "")})
    args.profile = name
    return prof


def cmd_scan(args) -> int:
    control = load_control(args.control)
    cfg = apply_control(load_config(args.config), control)
    cpu_table = load_cpu_scores(args.cpu_scores)
    profile = get_profile(args, control)
    if control.get("notify_min_score") is not None and args.notify_min_score is None:
        args.notify_min_score = float(control["notify_min_score"])
    if args.notify_min_score is None:
        args.notify_min_score = 4.5
    if control.get("limit"):
        args.limit = int(control["limit"])
    store = Store(args.db)
    if control.get("retention_days"):
        removed = store.prune(int(control["retention_days"]))
        if removed:
            print(f"{removed} Angebote aelter als {control['retention_days']} Tage entfernt.")
    fetcher = Fetcher(delay_s=cfg.get("delay_s", 2.0), cache_ttl_s=cfg.get("cache_ttl_s", 1800))
    sources = build_sources(cfg, only=args.source)
    if not sources:
        print("Keine Quelle aktiv. config/sources.yaml pruefen.", file=sys.stderr)
        return 2
    new: list[Listing] = []
    total = 0
    for src in sources:
        n_src = 0
        try:
            for listing in src.fetch(fetcher):
                if not title_passes(listing.title, control):
                    continue
                total += 1
                n_src += 1
                evaluate(listing, store, cpu_table)
                if store.upsert(listing):
                    new.append(listing)
        except Exception as e:  # eine kaputte Quelle soll die anderen nicht stoppen
            print(f"[{src.name}] Fehler: {e}", file=sys.stderr)
        print(f"[{src.name}] {n_src} Angebote" + ("  <- nichts gefunden, Selektoren pruefen" if n_src == 0 else ""))
    new.sort(key=lambda l: (l.value_score is None, -(l.value_score or 0)))
    print(f"{total} Angebote gesehen, {len(new)} neu, {store.count()} in der Historie.\n")
    print("   Preis    | Pkt/100€ | Modell / CPU / RAM/SSD                 | Quelle     | Link")
    for l in new[: args.limit]:
        print(fmt_row(l))
    if profile:
        matches = [l for l in new if not profile_misses(l, profile)]
        print(f"\nProfil '{args.profile}': {len(matches)} neue Treffer")
        for l in matches:
            print(fmt_row(l))
    if args.notify_file:
        if profile:
            hits = [l for l in new if not profile_misses(l, profile)]
        else:
            hits = [l for l in new if (l.value_score or 0) >= args.notify_min_score]
        Path(args.notify_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.notify_file).write_text(
            "".join(f"{l.price:.0f} € | {l.specs.model} {l.specs.cpu} {l.specs.ram_gb}GB/{l.specs.ssd_gb}GB "
                    f"| {l.value_score} Pkt | {deal_label(l)} | {l.url}\n" for l in hits),
            encoding="utf-8")
        crit = f"zum Profil '{args.profile}'" if profile else f"ueber {args.notify_min_score} Punkten"
        print(f"\n{len(hits)} neue Angebote {crit} -> {args.notify_file}")
    if args.report:
        write_report(store, Path(args.report), new, profile=profile, profile_name=args.profile)
    return 0


def markdown_table(rows) -> str:
    out = ["| Preis | Pkt/100€ | Modell | CPU | RAM/SSD | Zoll | Quelle | Link |", "|---:|---:|---|---|---|---|---|---|"]
    for r in rows:
        if isinstance(r, Listing):
            s = r.specs
            model, cpu, ram, ssd, scr, src, url, price, vs = s.model, s.cpu, s.ram_gb, s.ssd_gb, s.screen_in, r.source, r.url, r.price, r.value_score
        else:
            model, cpu, ram, ssd, scr, src, url, price, vs = r["model"], r["cpu"], r["ram_gb"], r["ssd_gb"], r["screen_in"], r["source"], r["url"], r["price"], r["value_score"]
        out.append(f"| {price:.0f} € | {vs if vs is not None else '-'} | {model or '?'} | {cpu or '?'} | "
                   f"{ram or '?'}/{ssd or '?'} GB | {scr or ''} | {src} | [Link]({url}) |")
    return "\n".join(out)


def profile_rows(store: Store, profile: dict, limit: int = 25):
    """Historie nach Profil filtern (Preis, RAM, SSD, CPU, Alter)."""
    rows = store.top(limit=500, max_price=profile.get("max_price"), min_ram=profile.get("min_ram_gb", 0),
                     min_ssd=profile.get("min_ssd_gb", 0), published_days=profile.get("max_age_days"))
    min_cpu = profile.get("min_cpu_score", 0)
    return [r for r in rows if (r["cpu_score"] or 0) >= min_cpu][:limit]


def row_dict(r) -> dict:
    """Listing oder DB-Row -> flaches Dict fuer report.json."""
    if isinstance(r, Listing):
        s = r.specs
        return {"price": r.price, "value_score": r.value_score, "model": s.model, "cpu": s.cpu, "ram_gb": s.ram_gb,
                "ssd_gb": s.ssd_gb, "screen_in": s.screen_in, "grade": s.grade, "source": r.source, "url": r.url,
                "title": r.title, "published": r.seen_at.isoformat(), "cpu_score": r.cpu_score, "label": deal_label(r)}
    keys = ("price", "value_score", "model", "cpu", "ram_gb", "ssd_gb", "screen_in", "grade", "source", "url", "title",
            "published", "cpu_score", "baseline_price", "first_seen", "last_seen")
    d = {k: (r[k] if k in r.keys() else None) for k in keys}
    d["label"] = ""
    return d


def write_report(store: Store, path: Path, new: list[Listing] | None = None, limit: int = 25,
                 profile: dict | None = None, profile_name: str | None = None) -> None:
    """Schreibt report.md (lesbar) und daneben report.json (fuer die Steuerseite)."""
    import json
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    parts = [f"# ThinkPad-Deals Report\n\nStand: {now:%Y-%m-%d %H:%M} UTC, {store.count()} Angebote in der Historie.\n"]
    data = {"generated_at": now.isoformat(), "history_count": store.count(), "profile": profile_name,
            "profile_description": (profile or {}).get("description", "").strip(), "sections": []}
    if profile:
        rows = profile_rows(store, profile, limit)
        parts.append(f"## Profil '{profile_name}' ({len(rows)} aktuelle Treffer)\n\n"
                     f"{profile.get('description', '').strip()}\n\n" + markdown_table(rows) + "\n")
        data["sections"].append({"key": "profile", "title": f"Profil '{profile_name}'", "rows": [row_dict(r) for r in rows]})
    if new:
        parts.append(f"## Neu in diesem Lauf ({len(new)})\n\n" + markdown_table(new[:limit]) + "\n")
        data["sections"].append({"key": "new", "title": "Neu in diesem Lauf", "rows": [row_dict(r) for r in new[:limit]]})
    top = store.top(limit=limit, days=14)
    parts.append("## Beste Preis-Leistung (letzte 14 Tage)\n\n" + markdown_table(top) + "\n")
    data["sections"].append({"key": "top", "title": "Beste Preis-Leistung (14 Tage)", "rows": [row_dict(r) for r in top]})
    cheap = store.top(limit=limit, max_price=250, min_ram=16, days=14)
    parts.append("## Bis 250 € mit 16 GB\n\n" + markdown_table(cheap) + "\n")
    data["sections"].append({"key": "cheap", "title": "Bis 250 € mit 16 GB", "rows": [row_dict(r) for r in cheap]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_top(args) -> int:
    store = Store(args.db)
    profile = get_profile(args, load_control(args.control))
    if profile:
        rows = profile_rows(store, profile, args.limit)
    else:
        rows = store.top(limit=args.limit, max_price=args.max_price, min_cpu=args.min_cpu,
                         min_ram=args.min_ram, days=args.days)
    if args.markdown:
        print(markdown_table(rows))
        return 0
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
    p.add_argument("--control", type=Path, default=None, help="Steuerdatei, Standard config/control.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    prof = argparse.ArgumentParser(add_help=False)
    prof.add_argument("--profiles", type=Path, default=None, help="Pfad zu profiles.yaml")
    prof.add_argument("--profile", help="Suchprofil aus config/profiles.yaml, z.B. dev")

    s = sub.add_parser("scan", help="Quellen abfragen und bewerten", parents=[prof])
    s.add_argument("--source", help="nur diese Quelle (Name aus sources.yaml)")
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--notify-file", help="neue Angebote ab --notify-min-score hier hineinschreiben (fuer Push-Benachrichtigung)")
    s.add_argument("--notify-min-score", type=float, default=None)
    s.add_argument("--report", help="Markdown-Report in diese Datei schreiben, z.B. data/report.md")
    s.set_defaults(fn=cmd_scan)

    t = sub.add_parser("top", help="beste Angebote aus der Historie", parents=[prof])
    t.add_argument("--limit", type=int, default=20)
    t.add_argument("--max-price", type=float)
    t.add_argument("--min-cpu", type=int, default=0, help="min. PassMark, z.B. 6000")
    t.add_argument("--min-ram", type=int, default=0)
    t.add_argument("--days", type=int, help="nur in den letzten N Tagen gesehen")
    t.add_argument("--markdown", action="store_true")
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
