"""SQLite-Historie. Erst mit Historie wird 'guenstig' messbar: ein Preis ist
gut, wenn er deutlich unter dem liegt, was du fuer dieselbe Konfiguration
sonst beobachtet hast.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .models import Listing
from .scoring import config_key

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    price REAL,
    currency TEXT,
    first_seen TEXT,
    last_seen TEXT,
    model TEXT, cpu TEXT, ram_gb INTEGER, ssd_gb INTEGER, screen_in REAL,
    condition TEXT, grade TEXT, touch INTEGER,
    cpu_score INTEGER, value_score REAL, baseline_price REAL,
    config_key TEXT,
    UNIQUE(source, url)
);
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY,
    source TEXT, url TEXT, price REAL, seen_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_obs_cfg ON observations(config_key);
CREATE INDEX IF NOT EXISTS idx_obs_value ON observations(value_score);
"""


class Store:
    def __init__(self, path: Path | str = "data/deals.db"):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def prices_for_config(self, key: Optional[str]) -> list[float]:
        if not key:
            return []
        rows = self.conn.execute(
            "SELECT price FROM observations WHERE config_key = ? AND price IS NOT NULL", (key,)
        ).fetchall()
        return [r["price"] for r in rows]

    def upsert(self, listing: Listing) -> bool:
        """Speichert das Angebot. Liefert True, wenn es neu war."""
        now = listing.seen_at.isoformat()
        key = config_key(listing.specs)
        row = listing.to_row()
        existing = self.conn.execute(
            "SELECT id, price FROM observations WHERE source=? AND url=?", (listing.source, listing.url)
        ).fetchone()
        s = listing.specs
        if existing:
            self.conn.execute(
                """UPDATE observations SET title=?, price=?, last_seen=?, model=?, cpu=?, ram_gb=?, ssd_gb=?,
                   screen_in=?, condition=?, grade=?, touch=?, cpu_score=?, value_score=?, baseline_price=?,
                   config_key=? WHERE id=?""",
                (listing.title, listing.price, now, s.model, s.cpu, s.ram_gb, s.ssd_gb, s.screen_in,
                 s.condition, s.grade, int(s.touch), listing.cpu_score, listing.value_score,
                 listing.baseline_price, key, existing["id"]),
            )
            if existing["price"] != listing.price:
                self.conn.execute(
                    "INSERT INTO price_history(source,url,price,seen_at) VALUES (?,?,?,?)",
                    (listing.source, listing.url, listing.price, now),
                )
            self.conn.commit()
            return False
        self.conn.execute(
            """INSERT INTO observations(source,url,title,price,currency,first_seen,last_seen,model,cpu,ram_gb,
               ssd_gb,screen_in,condition,grade,touch,cpu_score,value_score,baseline_price,config_key)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (listing.source, listing.url, listing.title, listing.price, listing.currency, now, now,
             s.model, s.cpu, s.ram_gb, s.ssd_gb, s.screen_in, s.condition, s.grade, int(s.touch),
             listing.cpu_score, listing.value_score, listing.baseline_price, key),
        )
        self.conn.execute(
            "INSERT INTO price_history(source,url,price,seen_at) VALUES (?,?,?,?)",
            (listing.source, listing.url, listing.price, now),
        )
        self.conn.commit()
        return True

    def top(self, limit: int = 20, max_price: Optional[float] = None, min_cpu: int = 0,
            min_ram: int = 0, days: Optional[int] = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM observations WHERE value_score IS NOT NULL"
        args: list = []
        if max_price is not None:
            q += " AND price <= ?"
            args.append(max_price)
        if min_cpu:
            q += " AND cpu_score >= ?"
            args.append(min_cpu)
        if min_ram:
            q += " AND ram_gb >= ?"
            args.append(min_ram)
        if days:
            q += " AND last_seen >= datetime('now', ?)"
            args.append(f"-{int(days)} days")
        q += " ORDER BY value_score DESC LIMIT ?"
        args.append(limit)
        return self.conn.execute(q, args).fetchall()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
