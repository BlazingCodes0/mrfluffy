"""wifivision.py — the wire's wifi apron.

The wire is the whole reachable net, so the wifi networks a box could join are
part of it — and the only way a box with no wifi sight of its own could ever
connect through Mr.Fluffy is to have them shown. This module reads them from the
radio's OWN last scan (NetworkManager caches it; we pass --rescan no and never
start a probe of our own) plus the box's current connection.

Honest by construction: every network is the radio's observed sighting — its
SSID, signal and security exactly as the radio reported them, deduped to the
strongest BSSID — never a scan we launched and never an invented name. It draws
nothing; it touches the net only by reading the cache. Connecting is NOT done
here — that is a separate, gated act in wiregame (uplink guard + confirm).
"""
from __future__ import annotations

import shutil
import subprocess
import time


def _run(args, t=4):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=t)
        return r.stdout or ""
    except Exception:
        return ""


def _split(line: str) -> list:
    """nmcli -t escapes ':' inside a value as '\\:'; split on the real ones."""
    out, cur, i = [], "", 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == ":":
            cur += ":"
            i += 2
            continue
        if ch == ":":
            out.append(cur)
            cur = ""
            i += 1
            continue
        cur += ch
        i += 1
    out.append(cur)
    return out


def available() -> bool:
    return shutil.which("nmcli") is not None


def saved_profiles() -> list:
    if not available():
        return []
    out = _run(["nmcli", "-t", "-f", "NAME,TYPE,ACTIVE", "connection", "show"])
    profs = []
    for ln in out.splitlines():
        f = _split(ln)
        if len(f) >= 2 and f[1] == "802-11-wireless":
            profs.append({"name": f[0], "active": len(f) > 2 and f[2] == "yes"})
    return profs


def build() -> dict:
    """The apron as it stands right now: the box's current wifi connection and
    the networks the radio last saw. Never triggers a scan."""
    now = time.time()
    if not available():
        return {"ok": False, "reason": "no NetworkManager (nmcli) on this host",
                "networks": [], "profiles": [], "on": None, "generated": now}

    on = None
    for ln in _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION",
                    "device", "status"]).splitlines():
        f = _split(ln)
        if len(f) >= 4 and f[1] == "wifi" and f[2] == "connected":
            on = {"iface": f[0], "ssid": f[3]}
            break
    if on:
        ipout = _run(["nmcli", "-t", "-f", "IP4.ADDRESS", "connection",
                      "show", on["ssid"]])
        ipout = ipout.strip()
        on["ip"] = ipout.split(":")[-1].split("/")[0] if ipout else ""

    out = _run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,CHAN,RATE",
                "device", "wifi", "list", "--rescan", "no"])
    nets = []
    for ln in out.splitlines():
        f = _split(ln)
        if len(f) < 6:
            continue
        ssid = f[1]
        if not ssid:
            continue                    # hidden AP: no name to show, so no name
        sec = f[3] or "open"
        nets.append({"ssid": ssid,
                     "signal": int(f[2]) if f[2].isdigit() else 0,
                     "security": sec,
                     "open": sec in ("", "--", "open"),
                     "in_use": f[0].strip() == "*",
                     "channel": f[4], "rate": f[5]})
    by = {}
    for n in nets:                       # a scan lists every BSSID; keep the best
        k = n["ssid"]
        if k not in by or n["in_use"] or n["signal"] > by[k]["signal"]:
            by[k] = n
    nets = sorted(by.values(), key=lambda n: (not n["in_use"], -n["signal"]))

    pnames = {p["name"] for p in saved_profiles()}
    for n in nets:
        n["saved"] = n["ssid"] in pnames
    return {"ok": True, "reason": "", "on": on, "networks": nets,
            "profiles": saved_profiles(), "generated": now}


def connect(ssid: str, password: str = None, timeout: int = 25):
    """The gated REAL act: join a network. Called only from wiregame after its
    own uplink guard and a confirm. Returns (ok, message). It never attacks
    anything and never touches a network other than the one named."""
    if not available():
        return False, "no NetworkManager (nmcli) on this host"
    base = ["nmcli", "--wait", str(timeout), "device", "wifi", "connect", ssid]
    if password:
        base += ["password", password]
    try:
        r = subprocess.run(base, capture_output=True, text=True, timeout=timeout + 5)
        lines = (r.stdout or r.stderr or "").strip().splitlines()
        return r.returncode == 0, (lines[-1] if lines else "")
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    w = build()
    print(f"WIFI APRON — {'ok' if w['ok'] else w['reason']}")
    on = w.get("on")
    print(f"on: {on['ssid']} ({on.get('iface')} {on.get('ip', '')})" if on
          else "on: not connected to wifi")
    for n in w.get("networks", []):
        tag = "ON " if n["in_use"] else ("open" if n["open"] else "sec ")
        sv = " saved" if n.get("saved") else ""
        print(f"  {n['signal']:3d}%  {tag:4s} {n['ssid']}{sv}  ch{n['channel']}")
