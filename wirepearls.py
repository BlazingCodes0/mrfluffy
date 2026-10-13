"""wirepearls.py — the pearl ring: kept sites behind gates in the Exchange.

A "pearl" is a website you keep on the ring of the Exchange, out past the edge
of the world. Fly to it, step in, and the page is fetched for real (wirenet,
standard library only) and served as text — no browser, no JavaScript, no
invented word, exactly like the DuckDuckGo gate.

The ring carries a STOCK pearl that is always present and can never be deleted:
IslamQA (islamqa.info), the questions answered with evidence. It is a fact of
the world, not a preference — it is merged in from this module, so no edit to
the file can remove it and no stray save can drop it. Users may cast their own
pearls and uncast them; only the stock ones are held fast.

State lives in config/wire_pearls.json (user pearls only). Reads are tolerant
(a missing or broken file is simply an empty ring); writes are atomic (tmp +
replace). Nothing here touches the network — this is only the ring of names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

PATH = Path.home() / "mrfluffy" / "config" / "wire_pearls.json"

# The stock pearls: always on the ring, never removable. This is the world's
# fixed furniture — edit with care. (IslamQA's own search is a client-side React
# app the standard library cannot run, so searching within it is done as a real
# web search restricted to its domain — see wiregame._site_search.)
STOCK = (
    {"id": "islamqa", "name": "IslamQA", "url": "https://islamqa.info/en",
     "blurb": "the questions, answered with evidence"},
)


def _host(url: str) -> str:
    try:
        return urlsplit(url).hostname or ""
    except Exception:
        return ""


def normalize_url(url: str) -> str:
    """A URL we will actually dial: http / https only, with a host. Anything
    else is refused with a plain reason — the same wall wirenet stands behind."""
    u = (url or "").strip()
    if not u:
        raise ValueError("no address given")
    if "://" not in u:
        u = "https://" + u
    p = urlsplit(u)
    scheme = (p.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"{scheme!r} is not allowed — only http / https")
    if not p.hostname:
        raise ValueError("that address has no host")
    path = p.path or "/"
    if p.query:
        path += "?" + p.query
    return f"{scheme}://{p.netloc}{path}"


def _slug(name: str, url: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    if not base:
        base = re.sub(r"[^a-z0-9]+", "-", _host(url).lower()).strip("-") or "pearl"
    pid, n = base, 1
    while pid in taken:
        n += 1
        pid = f"{base}-{n}"
    return pid


def load() -> list:
    """The user's own pearls, read tolerantly from disk."""
    try:
        d = json.loads(PATH.read_text())
    except Exception:
        return []
    raw = d.get("pearls") if isinstance(d, dict) else d
    if not isinstance(raw, list):
        return []
    stock_ids = {s["id"] for s in STOCK}
    out, taken = [], set(stock_ids)
    for p in raw:
        if not isinstance(p, dict):
            continue
        try:
            url = normalize_url(p.get("url", ""))
        except ValueError:
            continue
        name = (p.get("name") or _host(url) or "pearl").strip()
        pid = str(p.get("id") or "").strip() or _slug(name, url, taken)
        if pid in taken:
            pid = _slug(name, url, taken)
        taken.add(pid)
        out.append({"id": pid, "name": name, "url": url, "host": _host(url),
                    "kind": "site", "stock": False,
                    "search": str(p.get("search") or "").strip(),
                    "blurb": (p.get("blurb") or "").strip()})
    return out


def _save(pearls: list) -> None:
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"version": 1, "pearls": pearls}, indent=2))
        tmp.replace(PATH)
    except Exception:
        pass


def all_pearls() -> list:
    """The whole ring, stock first — what the world lays out on the floor."""
    stock = [{**s, "host": _host(s["url"]), "kind": "site", "stock": True,
              "search": s.get("search", "")} for s in STOCK]
    return stock + load()


def is_stock(pid: str) -> bool:
    return any(s["id"] == pid for s in STOCK)


def add(name: str, url: str) -> dict:
    """Cast a new pearl. Raises ValueError with a plain reason if it cannot."""
    url = normalize_url(url)
    name = (name or "").strip() or _host(url) or "pearl"
    user = load()
    taken = {s["id"] for s in STOCK} | {p["id"] for p in user}
    pearl = {"id": _slug(name, url, taken), "name": name, "url": url,
             "host": _host(url), "kind": "site", "stock": False, "blurb": ""}
    user.append(pearl)
    _save(user)
    return pearl


def remove(pid: str) -> bool:
    """Uncast one of your own pearls. A stock pearl is held fast — refused."""
    if is_stock(pid):
        return False
    user = load()
    keep = [p for p in user if p["id"] != pid]
    if len(keep) == len(user):
        return False
    _save(keep)
    return True


if __name__ == "__main__":
    print("the pearl ring:")
    for p in all_pearls():
        tag = "stock (held fast)" if p["stock"] else "yours"
        print(f"  \u25cb {p['name']:18} {p['url']:34} [{tag}]")
    print(f"file: {PATH}")
