# Steuerseite (GitHub Pages)

`index.html` ist die Steuerseite des Scanners. Sie enthaelt keine Geheimnisse: nur den
SHA-256-Hash der PIN. Das GitHub-Token gibt man im Browser ein, es bleibt dort (localStorage)
und geht nur an api.github.com.

Veroeffentlichen: Settings > Pages > Source "Deploy from a branch", Branch `main`, Ordner `/docs`.
Bei einem privaten Repository ist Pages nur in den Bezahlplaenen verfuegbar; dann die Datei
stattdessen in ein oeffentliches Repo legen (sie verraet nichts ueber den Scanner).
