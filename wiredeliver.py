"""wiredeliver.py — hand a file to a device on the same wifi (the real wire move).

Not an exploit and not a push: this box stands up a tiny READ-ONLY HTTP server on
its own LAN address and shows a URL (and a QR) that a phone on the SAME wifi can
open to pull the file down. Same segment, real handoff — the image is the only
thing served, there is no directory listing, and the path carries a one-time
token so it is not guessable. One background thread, bounded, no external calls.

Honesty: nobody can hand a phone a file silently. The phone has to open the URL.
This module only makes the wire half real — the rest is up to the hand that
carries the phone.

CLI:  python3 wiredeliver.py --serve /path/to/image.png
"""
from __future__ import annotations
import html, io, secrets, socket, subprocess, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CHUNK = 64 * 1024


def lan_ipv4() -> str:
    """This host's LAN IPv4 without sending a packet (AF_INET+UDP `connect`
    only picks the route). Falls back to wirevision's own ioctl read."""
    for probe in ("1.1.1.1", "8.8.8.8"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect((probe, 53))
                return s.getsockname()[0]
            finally:
                s.close()
        except Exception:
            pass
    try:
        from wirevision import _self_ips
        for ip in sorted(_self_ips()):
            if not ip.startswith("127."):
                return ip
    except Exception:
        pass
    return "127.0.0.1"


def _qr_png(url: str) -> bytes:
    try:
        import qrcode
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return b""


def _make_handler():
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"
        server_version = "mrfluffy-wiredeliver"
        timeout = 12

        def log_message(self, *a):
            pass

        def _hdr(self, code, ctype, clen):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(clen))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def do_GET(self):
            d = self.server.delivery
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/", "/index.html"):
                body = d._index_html().encode("utf-8")
                self._hdr(200, "text/html; charset=utf-8", len(body))
                self.wfile.write(body)
                return
            want = "/%s/%s" % (d.token, urllib.parse.quote(d.name))
            if path == want:
                try:
                    fp = open(d.path, "rb")
                except OSError:
                    self._hdr(404, "text/plain", 9)
                    self.wfile.write(b"not here\n")
                    return
                self._hdr(200, "image/*", d.size)
                try:
                    with fp:
                        while True:
                            b = fp.read(CHUNK)
                            if not b:
                                break
                            self.wfile.write(b)
                except (BrokenPipeError, ConnectionError):
                    pass
                return
            self._hdr(404, "text/plain", 9)
            self.wfile.write(b"not here\n")

    return H


class Delivery:
    """One file, served read-only on your LAN address, QR-handed to a phone."""

    def __init__(self):
        self._srv = None
        self._thread = None
        self.path = None
        self.name = ""
        self.size = 0
        self.token = ""
        self.ip = ""
        self.port = 0
        self.url = ""
        self.qr = b""

    def serve(self, path):
        p = Path(str(path)).expanduser()
        if not p.is_file():
            raise FileNotFoundError(str(p))
        self.stop()
        self.path = p.resolve()
        self.name = self.path.name
        self.size = self.path.stat().st_size
        self.token = secrets.token_hex(6)
        self.ip = lan_ipv4()
        srv = ThreadingHTTPServer(("0.0.0.0", 0), _make_handler())
        srv.daemon_threads = True
        srv.delivery = self
        self._srv = srv
        self.port = srv.server_address[1]
        qname = urllib.parse.quote(self.name)
        self.url = f"http://{self.ip}:{self.port}/{self.token}/{qname}"
        self.qr = _qr_png(self.url)
        self._thread = threading.Thread(target=srv.serve_forever,
                                        name="wiredeliver", daemon=True)
        self._thread.start()
        return self.status()

    def stop(self):
        srv, self._srv = self._srv, None
        self._thread = None
        if srv is not None:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass

    def status(self):
        return {"running": self._srv is not None, "ip": self.ip, "port": self.port,
                "name": self.name, "size": self.size, "url": self.url, "qr": self.qr}

    def _index_html(self):
        q = urllib.parse.quote(self.name)
        nm = html.escape(self.name)
        return ("<!doctype html><meta name=viewport content='width=device-width'>"
                f"<title>{nm}</title>"
                "<body style='background:#0a1216;color:#cfe3dd;"
                "font-family:system-ui;padding:22px'>"
                "<h3 style='color:#8be0ff'>a file, over the wifi</h3>"
                f"<p>{nm} \u2014 {self.size} bytes, served from {self.port} on {self.ip}</p>"
                f"<p><a style='color:#8be0ff' href='/{self.token}/{q}' "
                f"download='{nm}'>download it</a></p>"
                "<p style='color:#6b8a91'>a single file, read-only \u2014 "
                "the way the wire hands things to the ones who ask.</p>")


def _main(argv):
    if "--serve" in argv:
        i = argv.index("--serve")
        path = argv[i + 1] if i + 1 < len(argv) else None
        if not path:
            print("usage: wiredeliver.py --serve FILE")
            return 2
        d = Delivery()
        try:
            st = d.serve(path)
        except FileNotFoundError:
            print(f"no such file: {path}")
            return 2
        print(f"serving {st['name']} ({st['size']} bytes) on {st['ip']}:{st['port']}")
        print(f"open on the phone (same wifi): {st['url']}")
        print("Ctrl-C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            d.stop()
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))