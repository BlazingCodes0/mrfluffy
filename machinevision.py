"""machinevision.py — THIS machine, rebuilt as a place you can walk.

The wire channel looks OUTWARD: who is on the LAN, what each device talks to.
This looks INWARD: the machine Mr.Fluffy is standing on, as a low-poly world.
It is the same idea wirevision.py uses, pointed at the box under your feet.

    the shell      this host — its name, its users, its interfaces
    the doors      every listening socket = a way in (the services you expose)
    the roads      every live connection = a path already drawn on the wire
    the inhabitants  the processes themselves, each standing at its doors
    the dark figures INTRUDERS — only ever from local defensive evidence

Ground truth only, and LOCAL only: every process, port, connection, user and
file is read from THIS host (/proc, /etc, /sys) and from raven's own local
defensive logs. No network is touched, no packet is sent, no tool is run, no
model is called. If it is not in /proc or a local log, it is not in the world.

Honesty about the dark figures, kept explicit:
  * OBSERVED — a source IP/MAC, the door (service/port) it touched, and when.
  * INFERRED — that it is hostile at all, who it is, or what it wanted.
A quiet machine means no figures at all, and that is a complete, honest answer.
Reading the machine's own tables is not an attack; it never leaves this host.

CLI:  python3 machinevision.py            # the world model as JSON
      python3 machinevision.py --summary  # a one-screen human read of the world
"""
from __future__ import annotations
import glob, ipaddress, json, os, re, socket, time
from pathlib import Path

FLUFFY = Path.home() / "mrfluffy"
RAVEN = Path.home() / "raven"
DYE = RAVEN / "dye"
CROW = RAVEN / "crow"
IDS = RAVEN / "ids" / "eve.json"
HEART = Path("/tmp/ravenheart/state.json")
EVENTS = Path("/tmp/ravenheart/events.log")
FINCH = RAVEN / "finch"
SHIELD = RAVEN / "shield"
SELF_MAC_FILE = "/sys/class/net/*/address"

MAX_DOORS = 32          # listening sockets shown (the ways in)
MAX_ROADS = 48          # live connections shown (paths already drawn)
MAX_PROCS = 40          # inhabitants shown
MAX_USERS = 16
MAX_FIGURES = 16        # dark figures shown
MAX_EVENTS = 400        # tail of the lifeline log we scan for strikes

# a small, honest service dictionary — only used to NAME a port, never invented
SERVICE_NAMES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "domain", 80: "http",
    110: "pop3", 139: "netbios", 143: "imap", 443: "https", 445: "smb",
    587: "smtp", 631: "ipp", 993: "imaps", 995: "pop3s", 1433: "mssql",
    1521: "oracle", 2049: "nfs", 3306: "mysql", 3389: "rdp", 5432: "postgres",
    5900: "vnc", 6379: "redis", 8080: "http-alt", 8443: "https-alt",
    17833: "wiregate relay", 11434: "ollama",
}

_TCP_ST = {"01": "ESTABLISHED", "02": "SYN_SENT", "03": "SYN_RECV",
           "04": "FIN_WAIT1", "05": "FIN_WAIT2", "06": "TIME_WAIT",
           "07": "CLOSE", "08": "CLOSE_WAIT", "09": "LAST_ACK",
           "0A": "LISTEN", "0B": "CLOSING", "0C": "NEW_SYN_RECV"}

_RE_TS = re.compile(r"\[(\d\d:\d\d:\d\d)\]\s+([A-Z][A-Z0-9_]*):\s*(.*)")
_RE_IPV4 = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
_RE_MAC = re.compile(r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")

# event kinds that are evidence of an attempt to reach INTO this machine.
# NOTE: CRIT is deliberately NOT here — in raven's log CRIT marks a lifeline
# health blip ("no default route"), not an attacker. Only kinds that name an
# attempt on the machine, and only when the line carries a source, are figures.
HOSTILE = {"STRIKE", "GUARD", "BLOCK", "BLOCKED", "DENY", "DENIED", "DROP",
           "DROPPED", "ATTACK", "ARP", "SPOOF", "MITM", "QUARANTINE", "BAN",
           "BANNED", "EVIL", "INTRUSION", "ALERT", "SCAN"}
HIGH = {"STRIKE", "BLOCK", "BLOCKED", "DENY", "DENIED", "DROP", "DROPPED",
        "ATTACK", "ARP", "SPOOF", "MITM", "BAN", "BANNED", "EVIL", "INTRUSION"}


def _read(p) -> str:
    try:
        return Path(p).read_text(errors="ignore")
    except Exception:
        return ""


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _ago(sec) -> str:
    if sec is None:
        return "unknown"
    sec = int(sec)
    if sec < 90:
        return f"{max(sec, 0)}s ago"
    if sec < 5400:
        return f"{sec // 60}m ago"
    if sec < 172800:
        return f"{sec // 3600}h ago"
    return f"{sec // 86400}d ago"


def _users() -> dict:
    """uid -> login name, from /etc/passwd (names only, no secrets)."""
    out = {}
    for line in _read("/etc/passwd").splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[2].isdigit():
            out[int(parts[2])] = parts[0]
    return out


def _self_ips() -> list:
    """This host's own IPv4s (kernel ioctl; no packets sent)."""
    import fcntl, struct
    ips = []
    try:
        names = [n for _, n in socket.if_nameindex()]
    except Exception:
        names = []
    for name in names:
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            packed = struct.pack("256s", name.encode()[:15])
            res = fcntl.ioctl(s.fileno(), 0x8915, packed)   # SIOCGIFADDR
            ips.append(socket.inet_ntoa(res[20:24]))
        except Exception:
            pass
        finally:
            if s is not None:
                s.close()
    return ips


def _interfaces() -> list:
    out = []
    for iface in sorted(os.listdir("/sys/class/net")):
        base = Path("/sys/class/net") / iface
        mac = _read(base / "address").strip().lower()
        oper = _read(base / "operstate").strip()
        try:
            ip_addrs = []
            for a in (base / "address").parent.glob(".*"):
                pass
        except Exception:
            pass
        out.append({"iface": iface, "up": oper == "up",
                    "mac": mac if mac and mac != "00:00:00:00:00:00" else ""})
    # attach our IPv4s to the interface that reports them (best effort)
    ip_to_if = {}
    try:
        for iface in os.listdir("/sys/class/net"):
            d = Path("/sys/class/net") / iface
            for fam in ("ipv4",):
                pass
    except Exception:
        pass
    ips = _self_ips()
    if out:
        out[0].setdefault("ips", [])
    for row in out:
        row.setdefault("ips", [])
    # the first non-loopback interface carries the host's addresses (approximate —
    # the kernel does not hand us the mapping here without netlink, so we say so)
    main = next((r for r in out if r["iface"] != "lo"), out[0] if out else None)
    if main is not None:
        main["ips"] = ips
    return out


# ---- sockets: doors and roads ---------------------------------------------

def _hex_ip4(h: str) -> str:
    try:
        b = bytes.fromhex(h)
        return ".".join(str(x) for x in reversed(b))
    except Exception:
        return "0.0.0.0"


def _hex_ip6(h: str) -> str:
    try:
        raw = bytes.fromhex(h)
        words = b"".join(raw[i:i + 4][::-1] for i in range(0, 16, 4))
        return str(ipaddress.IPv6Address(words))
    except Exception:
        return "::"


def _inode_pid_map() -> dict:
    """socket inode -> pid, from /proc/<pid>/fd (same-user; unreadable pids skipped)."""
    m = {}
    for p in glob.glob("/proc/[0-9]*/fd/*"):
        if "socket:" not in _safe_link(p):
            continue
        try:
            inode = _safe_link(p).split("socket:[", 1)[1].rstrip("]")
        except Exception:
            continue
        try:
            pid = int(p.split("/")[2])
        except Exception:
            continue
        m.setdefault(inode, pid)
    return m


def _safe_link(p: str) -> str:
    try:
        return os.readlink(p)
    except Exception:
        return ""


def _proc_info(pid: int, users: dict) -> dict:
    comm = _read(f"/proc/{pid}/comm").strip() or "?"
    cmd = _read(f"/proc/{pid}/cmdline").replace("\x00", " ").strip()
    uid = None
    for line in _read(f"/proc/{pid}/status").splitlines():
        if line.startswith("Uid:"):
            parts = line.split()
            if len(parts) > 1 and parts[1].isdigit():
                uid = int(parts[1])
            break
    exe = _safe_link(f"/proc/{pid}/exe")
    return {"pid": pid, "name": comm, "user": users.get(uid, str(uid) if uid is not None else "?"),
            "cmd": cmd[:200], "exe": exe}


def _parse_net(path: str, proto: str, ipv6: bool):
    rows = []
    text = _read(path)
    for line in text.splitlines()[1:]:
        f = line.split()
        if len(f) < 10:
            continue
        lip, lport = _split_addr(f[1], ipv6)
        rip, rport = _split_addr(f[2], ipv6)
        st = _TCP_ST.get(f[3].upper(), f[3])
        inode = f[9]
        rows.append({"proto": proto, "laddr": lip, "lport": lport,
                     "raddr": rip, "rport": rport, "state": st, "inode": inode})
    return rows


def _split_addr(a: str, ipv6: bool):
    if ":" not in a:
        return ("", 0)
    host, port = a.rsplit(":", 1)
    try:
        p = int(port, 16)
    except Exception:
        p = 0
    addr = _hex_ip6(host) if ipv6 else _hex_ip4(host)
    return (addr, p)


def _is_external(ip: str) -> bool:
    if not ip:
        return False
    try:
        a = ipaddress.ip_address(ip)
    except Exception:
        return False
    return not (a.is_private or a.is_loopback or a.is_link_local
                or a.is_unspecified or a.is_multicast)


def _sockets(users: dict):
    """Return (doors, roads): listening sockets, and live connections."""
    inodes = _inode_pid_map()
    doors, roads = [], []
    for path, proto, ipv6 in (("/proc/net/tcp", "tcp", False),
                              ("/proc/net/tcp6", "tcp", True),
                              ("/proc/net/udp", "udp", False),
                              ("/proc/net/udp6", "udp", True)):
        for r in _parse_net(path, proto, ipv6):
            pid = inodes.get(r["inode"])
            info = _proc_info(pid, users) if pid else None
            rec = dict(r)
            rec["pid"] = pid
            rec["proc"] = info["name"] if info else ""
            rec["user"] = info["user"] if info else ""
            if proto == "tcp" and r["state"] == "LISTEN":
                doors.append(rec)
            elif proto == "udp" and r["lport"] and r["rport"] == 0:
                doors.append(rec)
            elif r["state"] == "ESTABLISHED" or (proto == "udp" and r["rport"]):
                roads.append(rec)
    door_ports = {(d["proto"], d["lport"]) for d in doors}
    for r in roads:
        r["inbound"] = (r["proto"], r["lport"]) in door_ports and bool(r["raddr"])
        r["external"] = _is_external(r["raddr"])
        r["peer_external"] = _is_external(r["laddr"])
    doors.sort(key=lambda d: (d["lport"] if d["lport"] else 0, d["proto"]))
    roads.sort(key=lambda r: (not r["external"], r["lport"]))
    return doors[:MAX_DOORS], roads[:MAX_ROADS]


# ---- the dark figures: intruders, from local defensive evidence ------------

def _lifeline() -> dict:
    st = _load(HEART, {})
    guard = st.get("guard") or {}
    return {"up": st.get("up"), "iface": st.get("iface"), "gw": st.get("gw"),
            "strikes": st.get("strikes", 0), "rtt": st.get("rtt"),
            "guard_mode": guard.get("mode"), "guard_acts": guard.get("acts", 0),
            "guard_last": guard.get("last") or "", "ts": st.get("ts")}


def _events() -> list:
    lines = [l for l in _read(EVENTS).splitlines() if l.strip()]
    return [l for l in lines if _RE_TS.match(l)][-MAX_EVENTS:]


def _ids_alerts() -> list:
    out = []
    for line in _read(IDS).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        a = r.get("alert") or {}
        out.append({"sig": a.get("signature"), "sev": a.get("severity"),
                    "src": r.get("src_ip"), "dst": r.get("dest_ip"),
                    "sport": r.get("src_port"), "dport": r.get("dest_port"),
                    "ts": str(r.get("timestamp") or "")})
    return out


def _figures(doors: list, roads: list) -> list:
    """Dark figures = INTRUDERS. Only from local defensive evidence, never guessed.
    Each carries the door (service) it touched, when, and how sure we are."""
    door_by_port = {}
    for d in doors:
        door_by_port.setdefault(d["lport"], d)
    figs = []

    # 1) the lifeline guard's own record of strikes
    life = _lifeline()
    if life.get("strikes") or life.get("guard_acts"):
        figs.append({
            "kind": "lifeline", "src": life.get("guard_last") or "unknown",
            "src_mac": "", "touched": "the lifeline (ravenheart)",
            "severity": 3 if life.get("strikes") else 2,
            "last_seen": "", "age_s": None,
            "confidence": "observed",
            "evidence": [f"strikes={life.get('strikes')} "
                         f"guard={life.get('guard_mode')} acts={life.get('guard_acts')}"],
        })

    # 2) hostile lines in the lifeline event log
    seen = {}
    for line in _events():
        m = _RE_TS.match(line)
        if not m:
            continue
        kind, msg = m.group(2), m.group(3)
        if kind not in HOSTILE:
            continue
        ips = _RE_IPV4.findall(msg)
        macs = _RE_MAC.findall(msg)
        src = ips[0] if ips else (macs[0] if macs else "")
        if not src:
            continue            # a strike with no source is a lifeline note, not a figure
        key = (kind, src)
        if key not in seen:
            seen[key] = {"kind": kind.lower(), "src": src,
                         "src_mac": (macs[0] if macs else ""),
                         "touched": _door_from_msg(msg, door_by_port),
                         "severity": 3 if kind in HIGH else 2,
                         "last_seen": m.group(1), "age_s": None,
                         "confidence": "observed",
                         "evidence": [f"[{m.group(1)}] {kind}: {msg[:120]}"]}
        else:
            seen[key]["evidence"].append(f"[{m.group(1)}] {kind}: {msg[:120]}")
    figs.extend(seen.values())

    # 3) Suricata alerts
    for a in _ids_alerts()[-MAX_FIGURES:]:
        touched = door_by_port.get(a.get("dport"))
        figs.append({
            "kind": "ids", "src": a.get("src") or "unknown", "src_mac": "",
            "touched": (f"{touched['proc']} :{touched['lport']}"
                        if touched else f"port {a.get('dport')}"),
            "severity": int(a.get("sev") or 2) if str(a.get("sev") or "").isdigit() else 2,
            "last_seen": (a.get("ts") or "")[11:19], "age_s": None,
            "confidence": "observed",
            "evidence": [f"{a.get('sig')} {a.get('src')} -> {a.get('dst')}:{a.get('dport')}"],
        })

    # 4) a live inbound road from a public address into one of our doors — a
    #    figure made from the connection table itself. This is the weakest sort:
    #    it is only INFERRED, so it says so, and it never cries wolf alone.
    for r in roads:
        if not (r.get("inbound") and r.get("external")):
            continue
        door = door_by_port.get(r["lport"])
        figs.append({
            "kind": "inbound", "src": r["raddr"], "src_mac": "",
            "touched": (f"{door['proc']} :{door['lport']}" if door
                        else f"port {r['lport']}"),
            "severity": 2, "last_seen": "live", "age_s": 0,
            "confidence": "inferred",
            "evidence": [f"live {r['proto']} {r['raddr']}:{r['rport']} -> "
                         f"{r['laddr']}:{r['lport']} from {r.get('proc') or '?'}"],
        })

    figs.sort(key=lambda f: (-f["severity"], f["kind"]))
    return figs[:MAX_FIGURES]


def _door_from_msg(msg: str, door_by_port: dict) -> str:
    """If the log line names a port we have open, name the door it touched."""
    for m in re.finditer(r"\b(\d{1,5})\b", msg):
        p = int(m.group(1))
        if p in door_by_port:
            d = door_by_port[p]
            return f"{d.get('proc') or '?'} :{d['lport']}"
    return "the wire"


# ---- sources: how to look again -------------------------------------------

def _sources() -> list:
    feeds = [
        ("this machine · live tables", "/proc/net/tcp", "it is always live"),
        ("lifeline · heart state", str(HEART), "ravenheart.py is always beating"),
        ("lifeline · events", str(EVENTS), "ravenheart.py logs strikes here"),
        ("ids · suricata alerts", str(IDS), "run raven/ids/run_suricata.sh"),
        ("dye · who is on the wire", str(DYE / "contacts.json"), "run dye"),
        ("finch · baseline", str(FINCH / "baseline.json"), "run finch"),
        ("shield · baseline", str(SHIELD / "baseline.json"), "run shield"),
    ]
    out = []
    now = time.time()
    for name, path, hint in feeds:
        p = Path(path)
        try:
            age = now - p.stat().st_mtime
            exists = True
        except Exception:
            age, exists = None, False
        out.append({"name": name, "path": path, "exists": exists,
                    "age": _ago(age), "age_s": None if age is None else int(age),
                    "stale": (not exists) or (age is not None and age > 3600),
                    "hint": hint})
    return out


def _truth(ties: int, figures: list) -> dict:
    notes = [
        "every door (listening port), road (connection) and inhabitant (process) "
        "is read LIVE from /proc on THIS host — not a memory.",
        "the dark figures are INTRUDERS drawn only from local defensive evidence "
        "(the lifeline log, the IDS, and the connection table).",
        "an inbound figure from the connection table is INFERRED — a public "
        "address did connect to one of our doors; that is a fact, but 'hostile' "
        "is not.",
    ]
    if not figures:
        notes.append("no figure is on the floor: nothing in the local logs is "
                     "striking at this machine. A quiet machine is a complete answer.")
    return {
        "observed": ["a listening socket and the program that owns it",
                     "a live connection: local/remote address, port and state",
                     "the process, its user, and its command line",
                     "an intruder's source address and the door it touched, when"],
        "inferred": ["what a program is FOR, or whether it is safe",
                     "that a connecting address is hostile at all",
                     "why any figure is here"],
        "notes": notes,
    }


def build() -> dict:
    users = _users()
    doors, roads = _sockets(users)
    life = _lifeline()
    figures = _figures(doors, roads)

    # inhabitants: processes that own a door or a road (the ones worth standing at)
    procs = {}
    for d in doors:
        if d.get("pid"):
            p = procs.setdefault(d["pid"], _proc_info(d["pid"], users))
            p.setdefault("doors", []).append(d["lport"])
    for r in roads:
        if r.get("pid"):
            p = procs.setdefault(r["pid"], _proc_info(r["pid"], users))
            p.setdefault("roads", []).append(f"{r['laddr']}:{r['lport']}")

    inhabitants = []
    for pid, p in procs.items():
        p = dict(p)
        p["doors"] = sorted(set(p.get("doors", [])))
        p["roads"] = len(set(p.get("roads", [])))
        p["weight"] = len(p["doors"]) * 2 + p["roads"]
        inhabitants.append(p)
    inhabitants.sort(key=lambda p: (-p["weight"], p["pid"]))
    inhabitants = inhabitants[:MAX_PROCS]

    hn = ""
    try:
        hn = socket.gethostname()
    except Exception:
        hn = _read("/etc/hostname").strip() or "?"
    up_s = None
    try:
        up_s = int(float(_read("/proc/uptime").split()[0]))
    except Exception:
        pass
    kernel = _read("/proc/sys/kernel/osrelease").strip()

    return {
        "generated": time.time(),
        "host": {"name": hn, "kernel": kernel, "uptime_s": up_s,
                 "uptime": _ago(up_s),
                 "users": [u for u in sorted(set(users.values()))[:MAX_USERS]]},
        "interfaces": _interfaces(),
        "lifeline": life,
        "doors": doors,
        "roads": roads,
        "inhabitants": inhabitants,
        "figures": figures,
        "counts": {"doors": len(doors), "roads": len(roads),
                   "inhabitants": len(inhabitants), "figures": len(figures),
                   "users": len(set(users.values()))},
        "truth": _truth(len(inhabitants), figures),
        "memory": {
            "note": "This world is THIS MACHINE, live. Every door, road and "
                    "inhabitant is read from /proc right now; the lifeline and "
                    "the dark figures from raven's own local logs. It touches no "
                    "network, sends no packet, runs no tool, and never attacks. "
                    "Past the last process there is nothing — this machine has a "
                    "bottom, unlike the open sea.",
        },
        "sources": _sources(),
        "codex": {
            "shell": {"friendly": "the machine", "real": "this host"},
            "door": {"friendly": "a door", "real": "a listening socket / open port"},
            "road": {"friendly": "a road", "real": "a live connection"},
            "inhabitant": {"friendly": "an inhabitant",
                           "real": "a process holding a socket"},
            "figure": {"friendly": "a dark figure", "real": "an intruder (from local logs)"},
            "_order": ["shell", "door", "road", "inhabitant", "figure"],
        },
    }


def summary(w: dict) -> str:
    h = w["host"]
    c = w["counts"]
    life = w["lifeline"]
    rtt = "?" if life.get("rtt") is None else f"{round(float(life['rtt']), 1)}ms"
    lines = [
        "MACHINE VISION — this machine as a place you can walk",
        "=" * 56,
        f"{h['name']}  ·  {h['kernel']}  ·  up {h['uptime']}",
        f"lifeline up={life.get('up')} {life.get('iface')} gw={life.get('gw')} "
        f"rtt={rtt} strikes={life.get('strikes')} guard={life.get('guard_mode')} "
        f"acts={life.get('guard_acts')}",
        f"{c['doors']} doors · {c['roads']} roads · {c['inhabitants']} inhabitants "
        f"· {c['figures']} dark figures · {c['users']} users",
        "",
        "DOORS — every way in (a listening socket + the program behind it):",
    ]
    for d in w["doors"]:
        name = SERVICE_NAMES.get(d["lport"], "?")
        who = d.get("proc") or "?"
        usr = f" ({d['user']})" if d.get("user") else ""
        lines.append(f"    {d['proto']:<3} :{d['lport']:<6} {name:<10} {who}{usr}  [{d['laddr']}]")
    if not w["doors"]:
        lines.append("    (no listening sockets — nothing is answering on this box)")
    lines.append("")
    lines.append("ROADS — live connections (a path already drawn):")
    for r in w["roads"]:
        tag = "INBOUND" if r.get("inbound") else "out    "
        ext = " · external" if r.get("external") else ""
        lines.append(f"    {tag} {r['proto']} {r['laddr']}:{r['lport']} "
                     f"<-> {r['raddr']}:{r['rport']} {r['state']:<12} "
                     f"{r.get('proc') or '?'}{ext}")
    if not w["roads"]:
        lines.append("    (no live connections)")
    lines.append("")
    lines.append("THE DARK FIGURES — intruders, from local defensive evidence only:")
    for f in w["figures"]:
        conf = f["confidence"]
        lines.append(f"    [{f['severity']}] {f['kind']:<8} {f['src']:<16} "
                     f"touched {f['touched']}  ({conf})")
        for e in f["evidence"][:2]:
            lines.append(f"          · {e}")
    if not w["figures"]:
        lines.append("    none — nothing in the local logs is striking at this machine.")
    lines.append("")
    lines.append("INHABITANTS — the processes standing at the doors:")
    for p in w["inhabitants"][:12]:
        doors = ",".join(str(x) for x in p.get("doors", [])) or "-"
        lines.append(f"    pid {p['pid']:<6} {p['name']:<18} {p['user']:<12} "
                     f"doors[{doors}] roads {p.get('roads', 0)}")
    lines.append("")
    lines.append("truth — OBSERVED: ports, programs, users, connections, "
                 "intruder source + door touched.")
    lines.append("        INFERRED: what a program is for; whether a peer is hostile.")
    lines.append("")
    lines.append("sources this world is built from (how to 'look again'):")
    for f in w["sources"]:
        mark = "STALE" if f["stale"] else "fresh"
        lines.append(f"    [{mark:>5}] {f['name']:<28} {f['age']:<10} \u2192 {f['hint']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    w = build()
    if "--summary" in sys.argv:
        print(summary(w))
    else:
        print(json.dumps(w, indent=2))
