from thinkpad_deals.http import Fetcher


class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


class _Session:
    def __init__(self, status, text=""):
        self.r = _Resp(status, text)
        self.headers = {}

    def get(self, url, timeout=None):
        return self.r


def _fetcher(status, text=""):
    f = Fetcher(cache_dir=None)
    f.session = _Session(status, text)
    return f


def test_robots_403_does_not_block():
    assert _fetcher(403).allowed("https://x.de/rss/foo") is True


def test_robots_disallow_blocks_only_matching_paths():
    f = _fetcher(200, "User-agent: *\nDisallow: /sch/\n")
    assert f.allowed("https://x.de/sch/i.html?q=1") is False
    assert f.allowed("https://x.de/itm/123") is True


def test_robots_can_be_switched_off_per_call(monkeypatch):
    f = _fetcher(200, "User-agent: *\nDisallow: /\n")
    monkeypatch.setattr(f, "_plain", lambda url: "<html>ok</html>")
    try:
        f.get("https://x.de/sch/")
        assert False, "sollte blockieren"
    except PermissionError:
        pass
    assert f.get("https://x.de/sch/", check_robots=False) == "<html>ok</html>"
