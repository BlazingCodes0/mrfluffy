"""wirenet.py — the net beyond the edge: real requests, no browser.

Wire Vision is a MEMORY — it replays what dye and the crows already observed and
touches nothing. This module is the opposite side of that wall. Past the edge
there is a gate that really goes out, and wirenet is the hand that dials it:

  * it does REAL DNS lookups      (socket.getaddrinfo)
  * and REAL HTTP(S) requests     (ssl + urllib, certificate-checked as usual)

with the standard library ONLY — never a browser, never a headless render,
never an invented number. Every field it returns (IP, status, milliseconds, the
Server header, the bytes) is what the network actually answered; when it cannot
answer, the error it hands back is the real error, unedited.

It is built for a slow machine: everything runs on ONE daemon worker thread, so
the world never stutters while a request is in flight. You submit a job, you get
an id, and you poll that id — the answer appears when it lands, or not at all.

Security stance: only http / https are allowed, every request has a wall-clock
timeout and a byte ceiling, private / loopback addresses are refused unless you
opt in (MRFLUFFY_NET_ALLOW_PRIVATE=1), and nothing is ever sent to an address you
did not name yourself.

CLI:  python3 wirenet.py --selftest            # dial a few real hosts and print
      python3 wirenet.py --resolve HOST
      python3 wirenet.py --get URL
"""
from __future__ import annotations
import ipaddress
import gzip
import html
import json
import os
import queue
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import zlib
from urllib.parse import urlsplit, urlencode, unquote, parse_qs

UA = "mrfluffy-wirenet/0.1 (+the gate beyond the edge)"
DEFAULT_TIMEOUT = 8.0
MAX_BYTES = 1 << 18          # 256 KiB is plenty for a peek at a page
MAX_REDIRECTS = 5
ALLOW_PRIVATE = os.environ.get("MRFLUFFY_NET_ALLOW_PRIVATE", "0") not in ("", "0", "false", "no")


class NetError(Exception):
    """A real failure, carried back unchanged."""


# ---- the guards -------------------------------------------------------------

def _norm(url: str) -> tuple[str, str, int, str]:
    """(scheme, host, port, path) for a URL we will actually dial, or raise."""
    u = url.strip()
    if "://" not in u:
        u = "https://" + u
    p = urlsplit(u)
    scheme = (p.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise NetError(f"refused scheme {scheme!r} — only http / https go out")
    host = p.hostname
    if not host:
        raise NetError("no host in that address")
    port = p.port or (443 if scheme == "https" else 80)
    path = p.path or "/"
    if p.query:
        path += "?" + p.query
    return scheme, host, port, path


def _refuse_if_private(ips: list[str]) -> None:
    if ALLOW_PRIVATE:
        return
    for ip in ips:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved:
            raise NetError(f"{ip} is a private / local address — set "
                           "MRFLUFFY_NET_ALLOW_PRIVATE=1 to dial it on purpose")


# ---- the real operations ----------------------------------------------------

def resolve(host: str, port: int | None = None) -> dict:
    """A real DNS lookup. Returns the addresses the resolver actually gave."""
    t0 = time.time()
    infos = socket.getaddrinfo(host, port or 0, proto=socket.IPPROTO_TCP)
    ips = sorted({i[4][0] for i in infos})
    return {"host": host, "ips": ips, "ms": round((time.time() - t0) * 1000.0, 1)}


def _read_capped(r, max_bytes: int) -> bytes:
    return r.read(max_bytes) if max_bytes else r.read(MAX_BYTES)


def fetch(url: str, max_bytes: int = MAX_BYTES, timeout: float = DEFAULT_TIMEOUT,
          method: str = "GET", data: dict | None = None) -> dict:
    """A real HTTP(S) request. Returns what actually came back over the wire.
    Pass data (a dict) to send a form-encoded POST body."""
    t0 = time.time()
    dns = {"ips": [], "ms": 0.0}
    target = url
    try:
        scheme, host, port, path = _norm(url)
        dns = resolve(host, port)
        _refuse_if_private(dns["ips"])
        target = f"{scheme}://{host}:{port}{path}"
        body = None
        headers = {"User-Agent": UA, "Accept": "*/*",
                   "Accept-Encoding": "identity", "Connection": "close"}
        if data is not None:
            body = urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            method = "POST"
        req = urllib.request.Request(target, method=method, data=body, headers=headers)
        ctx = ssl.create_default_context() if scheme == "https" else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = _read_capped(r, max_bytes)
            enc = (r.headers.get("Content-Encoding") or "").lower()
            try:
                if "gzip" in enc:
                    raw = gzip.decompress(raw)
                elif "deflate" in enc:
                    raw = zlib.decompress(raw)
            except Exception:
                pass
            ctype = r.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in ctype.lower():
                charset = ctype.lower().split("charset=", 1)[1].split(";")[0].strip()
            try:
                text = raw.decode(charset, "replace")
            except LookupError:
                text = raw.decode("utf-8", "replace")
            return {"ok": True, "url": target, "scheme": scheme,
                    "host": host, "ip": dns["ips"][0] if dns["ips"] else None,
                    "dns_ms": dns["ms"], "status": r.status, "reason": r.reason,
                    "ms": round((time.time() - t0) * 1000.0, 1),
                    "bytes": len(raw), "content_type": ctype,
                    "server": r.headers.get("Server", ""),
                    "text": text[:max_bytes]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "url": target, "host": getattr(e, "url", target),
                "ip": dns["ips"][0] if dns["ips"] else None, "dns_ms": dns["ms"],
                "status": e.code, "reason": e.reason,
                "ms": round((time.time() - t0) * 1000.0, 1),
                "error": f"HTTP {e.code} {e.reason}"}
    except Exception as e:
        return {"ok": False, "url": target, "host": target,
                "ip": dns["ips"][0] if dns["ips"] else None, "dns_ms": dns["ms"],
                "ms": round((time.time() - t0) * 1000.0, 1),
                "error": f"{type(e).__name__}: {e}"}


def _dechunk(b: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(b):
        j = b.find(b"\r\n", i)
        if j < 0:
            break
        try:
            size = int(b[i:j].split(b";")[0], 16)
        except ValueError:
            break
        if size == 0:
            break
        start = j + 2
        out += b[start:start + size]
        i = start + size + 2
    return bytes(out)


def trace(url: str, data: dict | None = None, max_bytes: int = MAX_BYTES,
          timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Do the request one REAL phase at a time over a plain socket — DNS, TCP
    connect, TLS handshake, the request, the response — timing each and counting
    the bytes. This is the true sequence the packet theatre animates; every field
    is measured, never invented."""
    t_start = time.perf_counter()
    phases: list = []
    sock = None
    try:
        scheme, host, port, path = _norm(url)
        def mark(name, ms, **kw):
            phases.append({"phase": name, "ms": round(ms, 2), **kw})
        # --- DNS ---
        t = time.perf_counter()
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ip = infos[0][4][0]
        mark("dns", (time.perf_counter() - t) * 1000.0, host=host, ip=ip, answers=len(infos))
        _refuse_if_private([i[4][0] for i in infos])
        # --- TCP connect ---
        t = time.perf_counter()
        sock = socket.create_connection((ip, port), timeout=timeout)
        mark("tcp", (time.perf_counter() - t) * 1000.0, ip=ip, port=port)
        # --- TLS handshake ---
        if scheme == "https":
            t = time.perf_counter()
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)
            mark("tls", (time.perf_counter() - t) * 1000.0,
                 version=sock.version(), cipher=(sock.cipher() or ["?"])[0])
        # --- request ---
        body = urlencode(data).encode() if data else b""
        method = "POST" if data is not None else "GET"
        head = (f"{method} {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {UA}\r\n"
                f"Accept: */*\r\nAccept-Encoding: identity\r\nConnection: close\r\n")
        if data is not None:
            head += ("Content-Type: application/x-www-form-urlencoded\r\n"
                     f"Content-Length: {len(body)}\r\n")
        head += "\r\n"
        t = time.perf_counter()
        sock.sendall(head.encode() + body)
        mark("request", (time.perf_counter() - t) * 1000.0,
             method=method, path=path, bytes=len(head) + len(body))
        # --- response ---
        t = time.perf_counter()
        chunks, got = [], 0
        while got <= max_bytes:
            b = sock.recv(65536)
            if not b:
                break
            chunks.append(b)
            got += len(b)
        raw = b"".join(chunks)
        head_bytes, _, rest = raw.partition(b"\r\n\r\n")
        status = 0
        lines = head_bytes.split(b"\r\n")
        headers: dict = {}
        if lines and lines[0].startswith(b"HTTP/"):
            try:
                status = int(lines[0].split(b" ")[1])
            except (IndexError, ValueError):
                pass
        for ln in lines[1:]:
            if b":" in ln:
                k, v = ln.split(b":", 1)
                headers[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
        payload = rest
        if "chunked" in headers.get("transfer-encoding", "").lower():
            payload = _dechunk(payload)
        enc = headers.get("content-encoding", "").lower()
        try:
            if "gzip" in enc:
                payload = gzip.decompress(payload)
            elif "deflate" in enc:
                payload = zlib.decompress(payload)
        except Exception:
            pass
        mark("response", (time.perf_counter() - t) * 1000.0, status=status, bytes=len(raw))
        ctype = headers.get("content-type", "")
        charset = "utf-8"
        if "charset=" in ctype.lower():
            charset = ctype.lower().split("charset=", 1)[1].split(";")[0].strip()
        try:
            text = payload.decode(charset, "replace")
        except LookupError:
            text = payload.decode("utf-8", "replace")
        return {"ok": True, "url": f"{scheme}://{host}:{port}{path}", "scheme": scheme,
                "host": host, "ip": ip, "port": port, "status": status,
                "ms": round((time.perf_counter() - t_start) * 1000.0, 1),
                "bytes": len(raw), "content_type": ctype,
                "server": headers.get("server", ""), "text": text[:max_bytes],
                "phases": phases, "headers": headers}
    except Exception as e:
        return {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}",
                "phases": phases}
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def whoami() -> dict:
    """Our real public address, asked of Cloudflare's trace endpoint — nothing
    inferred, nothing invented. Only ever called when someone asks."""
    r = fetch("https://1.1.1.1/cdn-cgi/trace", max_bytes=4096)
    if not r.get("ok"):
        return r
    fields = {}
    for line in r.get("text", "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k.strip()] = v.strip()
    return {"ok": True, "url": r["url"], "ip": fields.get("ip"), "ipv6": fields.get("ip6"),
            "colo": fields.get("colo"), "loc": fields.get("loc"),
            "warp": fields.get("warp"), "ts": fields.get("ts"), "ms": r["ms"]}


# ---- DuckDuckGo, the first real service behind a gate -----------------------

_DDG_TITLE = re.compile(r'href="([^"]+)"[^>]*class=.result-link.>(.*?)</a>', re.S)
_DDG_SNIP = re.compile(r"class=.result-snippet.>(.*?)</td>", re.S)


def _clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _real_url(href: str) -> str:
    if href.startswith("http"):
        return href
    qs = parse_qs(urlsplit(href).query)
    if "uddg" in qs:
        return unquote(qs["uddg"][0])
    return "https://duckduckgo.com" + href


def _parse_ddg(text: str) -> list:
    titles = _DDG_TITLE.findall(text)
    snips = _DDG_SNIP.findall(text)
    out = []
    for i, (href, title) in enumerate(titles):
        title = _clean(title)
        if not title:
            continue
        out.append({"title": title, "url": _real_url(href),
                    "snippet": _clean(snips[i]) if i < len(snips) else ""})
    return out[:20]


def _parse_next(text: str):
    i = text.find("next_form")
    if i < 0:
        return None
    i = text.rfind("<form", 0, i)
    j = text.find("</form>", i)
    if i < 0 or j < 0:
        return None
    form = text[i:j]
    if "Next Page" not in form:
        return None
    fields = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', form))
    return fields or None


def duckduckgo(query: str, data: dict | None = None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """A real DuckDuckGo search via the lite endpoint (POST, no JS, no browser).
    Pass the returned 'next' fields back as data to page on; returns the results
    as they came — real titles, URLs and snippets. DDG now and then answers with
    an empty challenge page; we simply ask again once."""
    if data is None:
        q = (query or "").strip()
        if not q:
            return {"ok": False, "error": "empty query", "results": [], "next": None}
        data = {"q": q, "kl": "us-en"}
    q = data.get("q", query or "")
    last = {"ok": False, "error": "no answer", "results": [], "next": None}
    for attempt in range(2):
        r = trace("https://lite.duckduckgo.com/lite/", data=data,
                  max_bytes=262144, timeout=timeout)
        if not r.get("ok"):
            last = {**r, "results": [], "next": None}
        else:
            text = r.get("text", "")
            results = _parse_ddg(text)
            last = {"ok": True, "engine": "duckduckgo", "query": q, "url": r["url"],
                    "ip": r.get("ip"), "ms": r.get("ms"), "status": r.get("status"),
                    "bytes": r.get("bytes"), "phases": r.get("phases", []),
                    "results": results, "next": _parse_next(text)}
            if results:
                return last
        if attempt == 0:
            time.sleep(1.5)
    return last


# ---- the one worker thread --------------------------------------------------

class Net:
    """One daemon thread, a queue of real jobs, and a poll-able answer board.

    ask(kind, target[, **kw]) -> job id
    poll(job_id)             -> None while it is still out, else the answer dict
    latest()                 -> the most recent finished answer, or None
    """

    def __init__(self):
        self._q: queue.Queue = queue.Queue()
        self._answers: dict = {}
        self._order: list = []
        self._seq = 0
        self._lock = threading.Lock()
        self._t = threading.Thread(target=self._run, daemon=True, name="wirenet")
        self._t.start()

    def ask(self, kind: str, target: str = "", **kw) -> int:
        with self._lock:
            self._seq += 1
            jid = self._seq
            self._answers[jid] = {"state": "out", "kind": kind, "target": target}
            self._order.append(jid)
            if len(self._order) > 64:                 # keep the board small
                for old in self._order[:-32]:
                    self._answers.pop(old, None)
                self._order = self._order[-32:]
        self._q.put((jid, kind, target, kw))
        return jid

    def poll(self, jid: int):
        with self._lock:
            a = self._answers.get(jid)
            if not a or a.get("state") == "out":
                return None
            return dict(a)

    def latest(self):
        with self._lock:
            for jid in reversed(self._order):
                a = self._answers.get(jid)
                if a and a.get("state") != "out":
                    return dict(a)
        return None

    def _run(self):
        while True:
            jid, kind, target, kw = self._q.get()
            try:
                if kind == "resolve":
                    res = {"ok": True, **resolve(target, kw.get("port"))}
                elif kind == "fetch":
                    res = fetch(target, **{k: v for k, v in kw.items()
                                           if k in ("max_bytes", "timeout", "method", "data")})
                elif kind == "search":
                    res = duckduckgo(target, **{k: v for k, v in kw.items()
                                                if k in ("timeout", "data")})
                elif kind == "read":
                    res = trace(target, **{k: v for k, v in kw.items()
                                           if k in ("max_bytes", "timeout", "data")})
                elif kind == "whoami":
                    res = whoami()
                else:
                    res = {"ok": False, "error": f"unknown job {kind!r}"}
            except Exception as e:                     # real error, carried back
                res = {"ok": False, "target": target,
                       "error": f"{type(e).__name__}: {e}"}
            res["job"] = jid
            res["kind"] = kind
            res["state"] = "done" if res.get("ok") else "error"
            res["at"] = time.time()
            with self._lock:
                self._answers[jid] = res


# ---- CLI --------------------------------------------------------------------

def _selftest() -> int:
    print("wirenet selftest — dialing the real net, no browser")
    print("=" * 56)
    for host in ("example.com", "1.1.1.1"):
        try:
            d = resolve(host)
            print(f"DNS  {host:16} {d['ms']:6.1f}ms  {', '.join(d['ips'][:3])}")
        except Exception as e:
            print(f"DNS  {host:16} FAIL  {type(e).__name__}: {e}")
    for url in ("https://example.com", "https://1.1.1.1/cdn-cgi/trace"):
        r = fetch(url, max_bytes=512)
        if r.get("ok"):
            print(f"GET  {url:34} {r['status']} {r['ms']:6.0f}ms "
                  f"{r['bytes']}b ip={r['ip']}")
        else:
            print(f"GET  {url:34} FAIL {r.get('error')}")
    w = whoami()
    if w.get("ok"):
        print(f"YOU  public ip {w['ip']}  colo {w.get('colo')}  loc {w.get('loc')}")
    r = duckduckgo("open source search engine")
    if r.get("ok"):
        print(f"SEARCH duckduckgo '{r['query']}' -> {len(r['results'])} results "
              f"in {r['ms']:.0f}ms")
        for hit in r["results"][:3]:
            print(f"     · {hit['title'][:60]}")
            print(f"       {hit['url'][:72]}")
    else:
        print(f"SEARCH duckduckgo FAIL {r.get('error')}")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv or argv[0] == "--selftest":
        raise SystemExit(_selftest())
    if argv[0] == "--resolve" and len(argv) > 1:
        print(json.dumps(resolve(argv[1]), indent=2))
    elif argv[0] == "--get" and len(argv) > 1:
        print(json.dumps(fetch(argv[1]), indent=2)[:4000])
    elif argv[0] == "--search" and len(argv) > 1:
        r = duckduckgo(" ".join(argv[1:]))
        for hit in r.get("results", []):
            print(f"{hit['title']}\n  {hit['url']}\n  {hit['snippet'][:120]}\n")
    else:
        print(__doc__)
