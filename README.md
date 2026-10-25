# thinkpad-deals

Eigener Crawler plus Bewertung, um Angebote wie das ThinkPad T580 (i5-8350U, 16 GB, 256 GB,
refurbished, 179 € per Code) **selbst** zu finden, statt auf mydealz-Alarme zu warten.

Grundidee in drei Schritten:

1. **Sammeln.** Listen von Händlern, eBay-Suchen und die mydealz-RSS-Feeds regelmäßig abgrasen.
2. **Normalisieren.** Aus dem Titel Modell, CPU, RAM, SSD, Zoll, Zustand herausparsen. Ohne diesen
   Schritt kann man Angebote nicht vergleichen, denn jeder Shop schreibt anders.
3. **Bewerten.** Leistungspunkte (CPU-Benchmark, RAM, SSD) pro Euro, plus Vergleich mit dem
   Median aller bisher gesehenen Preise derselben Konfiguration. "Sehr gut" heißt: hohe
   Punkte pro Euro **und** deutlich unter dem üblichen Preis.

## Installation

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # plus ".[browser]" und `playwright install chromium` für JS-Shops
pytest                             # alles offline, läuft ohne Netz
```

## Benutzung

```bash
thinkpad-deals scan                           # alle aktiven Quellen aus config/sources.yaml
thinkpad-deals scan --source ebay             # nur eine Quelle
thinkpad-deals top --max-price 250 --min-ram 16
thinkpad-deals top --min-cpu 6000 --days 7
thinkpad-deals parse "Lenovo ThinkPad T580 15.6 Zoll i5 8350u 16GB DDR4 RAM 256GB SSD refurbished" --price 179
thinkpad-deals calibrate https://shop.example/notebooks/lenovo/   # CSS-Selektoren vorschlagen lassen
```

Beispielausgabe von `scan`:

```
   Preis    | Pkt/100€ | Modell / CPU / RAM/SSD                 | Quelle     | Link
  399.00 € |  4.49 | T14 Gen 2        Ryzen 5 PRO 5650U   16GB/256GB   14.0" | shop       | gut https://...
  179.00 € |  4.47 | T580             i5-8350U            16GB/256GB   15.6" | mydealz    | gut -22% vs. Median https://...
  139.00 € |  3.14 | X1 Yoga Gen 2    i5-7300U             8GB/128GB   14.0" | shop       | https://...
```

## Einen neuen Shop anbinden

1. Listen-URL des Shops im Browser öffnen (Kategorie "Lenovo Notebooks", nach Preis sortiert).
2. `thinkpad-deals calibrate <URL>` ausführen. Das Tool sucht alle Preis-Knoten, klettert zum
   gemeinsamen wiederholten Vorfahren (der Artikelkarte) und schlägt `item`, `title`, `price`,
   `link` als CSS-Selektoren vor. Lädt der Shop die Liste per JavaScript nach, `--render` anhängen.
3. Vorschlag in `config/sources.yaml` als neue Quelle mit `kind: shop` eintragen, `next_page`
   ergänzen (Selektor des "Weiter"-Links), `enabled: true` setzen.
4. `thinkpad-deals scan --source <name>` und Ausgabe prüfen. Stimmen Modell/CPU/RAM nicht,
   `thinkpad-deals parse "<Titel>"` zeigt, was der Parser erkennt. Regexe stehen in
   `thinkpad_deals/parse.py`.

Der Händler aus dem Deal (hardware-online-shop.de) ist in `sources.yaml` bereits als Vorlage
angelegt, aber deaktiviert: die Selektoren sind Platzhalter, weil der Shop aus der
Entwicklungsumgebung nicht erreichbar war. Einmal `calibrate` laufen lassen, eintragen, fertig.

## Wie die Bewertung funktioniert

`thinkpad_deals/scoring.py`, bewusst klein gehalten:

```
Punkte  = CPU-PassMark/1000 + RAM_GB * 0.35 + SSD_GB/256 * 0.8 (+ Touch, + 14"-Bonus)
Wert    = Punkte / (Preis + 100 €) * 100
```

Der Grundbetrag von 100 € verhindert, dass Uralt-Geräte für 99 € automatisch jedes bessere
Gerät schlagen. CPU-Werte stehen in `config/cpu_scores.yaml` (die ersten fünf stammen aus der
Vergleichstabelle im Deal, der Rest sind Richtwerte, einfach pflegen).

Der zweite Hebel ist die **Historie** in `data/deals.db` (SQLite). Jeder Scan speichert alle
Angebote samt Preisverlauf. Sobald für eine Konfiguration (Modell + CPU + RAM + SSD) mindestens
drei Preise bekannt sind, wird der Median als Referenz genutzt. Liegt ein Angebot 20 % oder mehr
darunter, bekommt es das Etikett `-xx% vs. Median`. Das ist genau der Effekt, den der Gutschein im
T580-Deal hatte: 229 € Listenpreis, 179 € mit Code.

## Ohne eigenen Rechner laufen lassen

`.github/workflows/scan.yml` macht das Repo selbst zum Server: GitHub Actions startet alle drei
Stunden einen Scan, committet `data/deals.db` (Historie) und `data/report.md` (lesbarer Report mit
Top-Listen) zurück ins Repo und zeigt die Ausgabe unter Actions als Zusammenfassung. Kosten: null
bei öffentlichem Repo, bei privatem gut innerhalb der 2000 Freiminuten pro Monat.

Einrichten:

1. Repo auf GitHub, Branch mit diesem Code. Unter Settings > Actions > General
   "Read and write permissions" für `GITHUB_TOKEN` erlauben.
2. Unter Actions den Workflow `scan-deals` einmal per "Run workflow" starten.
3. **Push aufs Handy** (optional, 2 Minuten): App [ntfy](https://ntfy.sh) installieren, ein
   Topic mit zufälligem Namen abonnieren (z.B. `tp-deals-k3x9q2`), diesen Namen als
   Repository-Variable `NTFY_TOPIC` unter Settings > Secrets and variables > Actions > Variables
   anlegen. Ab dann meldet sich das Handy, sobald ein neues Angebot über 4,5 Punkten auftaucht.
   Schwelle über die Variable `NOTIFY_MIN_SCORE` ändern.

Alternativ kann eine Claude-Cloud-Session dasselbe als geplante Aufgabe ausführen und dir die
Treffer kommentieren. Dafür muss die Umgebung die Shop-Domains im Netzwerk erlauben und das Repo
erreichen können. Für reines Sammeln ist Actions die robustere und billigere Variante.

## Quellen, die sich lohnen

- **mydealz RSS** (`/rss/gruppe/lenovo-thinkpad`, `/rss/suche?q=...`): strukturiert, offiziell,
  keine Last. Der Deal-Autor postet dort wöchentlich, die Temperatur steht in der Beschreibung.
- **Refurbisher-Shops**: hardware-online-shop.de, AfB, Luxnote, ESM Computer, lapstore, GreenPanda,
  Harlander. Jeweils die Lenovo-Kategorie als `kind: shop` anbinden. Gutschein-Codes stehen oft
  nur im Warenkorb oder in Newslettern; die Historie fängt den Normalpreis trotzdem ein.
- **eBay-Suche**: als Quelle vorkonfiguriert, aber deaktiviert. eBay beantwortet Anfragen von
  GitHub-Actions-Runnern mit 403 und sperrt `/sch/` per robots.txt. Lokal kann es laufen
  (`enabled: true`), sauber ist nur die eBay Browse API mit eigenem Key.
- **Geizhals/Idealo** listen Gebrauchtware, verbieten Scraping aber in den AGB. Besser deren
  Preisalarme nutzen oder weglassen.

## Spielregeln

Der Fetcher liest `robots.txt`, wartet standardmäßig 2 s zwischen Requests pro Host, cached
Seiten 30 min lokal und meldet sich mit erkennbarem User-Agent. Bitte so lassen: ein paar Dutzend
Seitenaufrufe pro Tag fallen keinem Shop auf, ein aggressiver Crawler schon. Keine Logins
umgehen, keine Captchas brechen, keine Daten weiterverkaufen.

## Struktur

```
thinkpad_deals/
  parse.py       Titel -> Specs, Preis-Parser (deutsches Format)
  scoring.py     Punkte, Wert, Median-Vergleich, Etiketten
  store.py       SQLite-Historie (observations, price_history)
  http.py        höflicher Fetcher, Cache, robots, optional Playwright
  calibrate.py   CSS-Selektoren automatisch vorschlagen
  sources/       mydealz_rss.py, generic_shop.py
  cli.py         scan / top / calibrate / parse
config/sources.yaml   Quellen und Selektoren
config/cpu_scores.yaml
tests/                offline, mit Fixtures
```
