"""Hoeflicher Fetcher: robots.txt, Wartezeit zwischen Requests, Cache auf Platte,
sauberer User-Agent. Optional Rendering per Playwright fuer JS-lastige Shops.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36 thinkpad-deals/0.1 (privater Preisvergleich)"
)


class Fetcher:
    def __init__(
        self,
        delay_s: float = 2.0,
        cache_dir: Optional[Path] = Path(".http_cache"),
        cache_ttl_s: int = 1800,
        user_agent: str = DEFAULT_UA,
        respect_robots: bool = True,
        timeout_s: int = 25,
    ):
        self.delay_s = delay_s
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_ttl_s = cache_ttl_s
        self.ua = user_agent
        self.respect_robots = respect_robots
        self.timeout_s = timeout_s
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.ua, "Accept-Language": "de-DE,de;q=0.9"})
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- robots -------------------------------------------------------------
    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        host = urlparse(url).netloc
        rp = self._robots.get(host)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{urlparse(url).scheme}://{host}/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None  # robots nicht lesbar -> nicht blockieren
            self._robots[host] = rp
        return True if rp is None else rp.can_fetch(self.ua, url)

    # -- cache --------------------------------------------------------------
    def _cache_path(self, url: str) -> Optional[Path]:
        if not self.cache_dir:
            return None
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")

    def _from_cache(self, url: str) -> Optional[str]:
        p = self._cache_path(url)
        if not p or not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
        if time.time() - d.get("t", 0) > self.cache_ttl_s:
            return None
        return d.get("body")

    def _to_cache(self, url: str, body: str) -> None:
        p = self._cache_path(url)
        if p:
            p.write_text(json.dumps({"t": time.time(), "url": url, "body": body}), encoding="utf-8")

    # -- throttle -----------------------------------------------------------
    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_hit.get(host)
        if last is not None:
            rest = self.delay_s - (time.time() - last)
            if rest > 0:
                time.sleep(rest)
        self._last_hit[host] = time.time()

    # -- public -------------------------------------------------------------
    def get(self, url: str, render: bool = False) -> str:
        cached = self._from_cache(url)
        if cached is not None:
            return cached
        if not self.allowed(url):
            raise PermissionError(f"robots.txt verbietet {url}")
        self._wait(url)
        body = self._render(url) if render else self._plain(url)
        self._to_cache(url, body)
        return body

    def _plain(self, url: str) -> str:
        r = self.session.get(url, timeout=self.timeout_s)
        r.raise_for_status()
        return r.text

    def _render(self, url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("pip install playwright && playwright install chromium") from e
        with sync_playwright() as p:  # pragma: no cover - braucht Browser
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=self.ua, locale="de-DE")
            page.goto(url, wait_until="networkidle", timeout=self.timeout_s * 1000)
            html = page.content()
            browser.close()
            return html
