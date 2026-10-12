"""birdguard.py — finch's hand: host-local, reversible containment.

The machine room reads the wire; this is the one place it may *act* — and only
ever on THIS machine. `contain(ip)` adds ONE team-owned rule to a private
iptables chain (`MRFLUFFY-QUAR`, hooked into INPUT), so packets arriving *from*
that source at this NIC are dropped. It never sends a packet, never touches
another host, and is fully reversible with `release(ip)` / `release_all()`.

Nothing here runs until it is called: the module is inert on import. The room
gates the call behind an explicit "arm the birds" confirm, and every attempt
(allowed or refused) is appended to `logs/birdguard.log`; the live set is kept
in `logs/birdguard.json`.

Guardrails (refused, logged, never applied):
  * not a real IPv4 address, or loopback / multicast / unspecified / link-local
    / reserved / broadcast;
  * one of THIS machine's own addresses — never contain yourself;
  * the default gateway — containing it would cut our own lifeline.

Set `MRFLUFFY_BIRDGURD_LIVE=0` to make every *write* a dry run (the plan is
returned, nothing is executed) — used by tests and by anyone who wants the room
read-only even while armed.
"""
import ipaddress
import json
import os
import re
import subprocess
import time
from pathlib import Path

FLUFFY = Path.home() / "mrfluffy"
LOG = FLUFFY / "logs" / "birdguard.log"
LEDGER = FLUFFY / "logs" / "birdguard.json"
CHAIN = "MRFLUFFY-QUAR"
LIVE = os.environ.get("MRFLUFFY_BIRDGURD_LIVE", "1") != "0"


def _run(argv, timeout=6):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def _sudo(*args):
    return _run(["sudo", "-n", *args])


def _ok(r):
    return bool(r and r.returncode == 0)


# ── reading the machine's own addresses (never a write) ─────────────────────
def self_addrs():
    out = set()
    r = _run(["ip", "-4", "-o", "addr", "show"])
    for m in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)", (r.stdout if r else "") or ""):
        out.add(m.group(1))
    return out


def gateway():
    r = _run(["ip", "route", "show", "default"])
    w = (r.stdout if r else "").split()
    return w[w.index("via") + 1] if "via" in w else None


def usable(ip):
    """(ok, why-not). A containment target must be a real, remote-ish IPv4."""
    try:
        a = ipaddress.IPv4Address(str(ip).strip())
    except Exception:
        return False, "not an IPv4 address"
    if (a.is_loopback or a.is_multicast or a.is_unspecified or a.is_link_local
            or a.is_reserved):
        return False, "not a usable source address"
    if str(a) in self_addrs():
        return False, "that is THIS machine — never contain yourself"
    if str(a) == gateway():
        return False, "that is the way out (the gateway) — containing it cuts our lifeline"
    return True, ""


def _log(ip, acted, note):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"{'APPLY' if acted else 'REFUSE/DRY'} {ip} — {note}\n")
    except Exception:
        pass


def _read_ledger():
    try:
        return json.loads(LEDGER.read_text())
    except Exception:
        return {}


def _write_ledger(d):
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(d, indent=1))
    except Exception:
        pass


def contained():
    """ip -> {reason, at} for every source we currently hold in the chain."""
    return dict(_read_ledger())


# ── the chain ───────────────────────────────────────────────────────────────
def _have_chain():
    return _ok(_sudo("iptables", "-n", "-L", CHAIN))


def _ensure_chain():
    if not _have_chain():
        _sudo("iptables", "-N", CHAIN)
    if not _ok(_sudo("iptables", "-C", "INPUT", "-j", CHAIN)):
        _sudo("iptables", "-I", "INPUT", "1", "-j", CHAIN)


def _in_chain(ip):
    r = _sudo("iptables", "-S", CHAIN)
    if not (r and r.returncode == 0):
        return False
    return re.search(r"-s %s(?:/32)? " % re.escape(ip), r.stdout or "") is not None


def contain(ip, reason="", apply=True):
    """Drop packets arriving from `ip` at this host. host-local + reversible."""
    ip = str(ip).strip()
    ok, why = usable(ip)
    if not ok:
        _log(ip, False, "refused: " + why)
        return {"ok": False, "ip": ip, "refused": why}
    if _in_chain(ip):
        return {"ok": True, "ip": ip, "already": True}
    cmd = ["iptables", "-I", CHAIN, "1", "-s", ip, "-j", "DROP"]
    if not LIVE or not apply:
        _log(ip, False, "dry run: " + " ".join(cmd))
        return {"ok": True, "ip": ip, "dry": True, "cmd": " ".join(cmd)}
    _ensure_chain()
    r = _sudo(*cmd)
    if _ok(r):
        led = _read_ledger()
        led[ip] = {"reason": str(reason)[:200], "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        _write_ledger(led)
        _log(ip, True, reason or "contained")
        return {"ok": True, "ip": ip, "cmd": " ".join(cmd)}
    err = (r.stderr.strip() if r else "sudo/iptables failed")
    _log(ip, False, "apply failed: " + err)
    return {"ok": False, "ip": ip, "error": err}


def release(ip):
    """Lift containment of one source (delete only our matching rules)."""
    ip = str(ip).strip()
    if LIVE:
        _sudo("iptables", "-D", CHAIN, "-s", ip, "-j", "DROP")
    led = _read_ledger()
    led.pop(ip, None)
    _write_ledger(led)
    _log(ip, True, "released")
    return {"ok": True, "ip": ip}


def release_all():
    """Flush the whole chain and unhook it — back to a clean firewall."""
    n = len(_read_ledger())
    if LIVE:
        _sudo("iptables", "-F", CHAIN)
        _sudo("iptables", "-D", "INPUT", "-j", CHAIN)
        _sudo("iptables", "-X", CHAIN)
    _write_ledger({})
    _log("*", True, f"released all ({n})")
    return {"ok": True, "released": n}


def status():
    r = _sudo("iptables", "-S", CHAIN)
    rules = []
    if r and r.returncode == 0:
        rules = [l for l in (r.stdout or "").splitlines() if l.startswith("-A")]
    return {"chain": CHAIN, "live": LIVE, "rules": rules, "contained": contained()}
