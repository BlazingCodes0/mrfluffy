"""wirevision.py — the WIRE, rebuilt as a place you can walk.

The wire channel reads the network as text. This turns the very SAME local
ground truth into a low-poly world model you can move through like a game:

    the floor      your LAN — the heart (your host), the devices (dye contacts),
                   the gates (what each device talks to), the crows, the rifts.
    stratum -1     THE TALKING PLACE   (application layer: DNS + TLS names)
    stratum -2     THE SORTING OFFICE  (transport layer: TCP/UDP ports)
    stratum -3     THE ADDRESSING PLAINS (internet layer: IP addresses)
    stratum -4     THE WIRE ITSELF      (link layer: MAC / ARP)
    stratum -5     THE SPARKS           (physical layer: the last electron)

Sources are LOCAL files only, the same ones wire.py reads — never the network,
never a model call, never a tool. Ground truth only: if a device, domain, port,
IP or MAC is not in the files, it is not in the world. All names are friendly by
default; the real technical term is carried alongside and only revealed when the
player asks (so a beginner and an expert stand on the same ground).

CLI:  python3 wirevision.py            # the world model as JSON
      python3 wirevision.py --summary  # a one-screen human read of the world
"""
from __future__ import annotations
import glob, json, math, re, time
from pathlib import Path

import wire

FLUFFY = Path.home() / "mrfluffy"
RAVEN = Path.home() / "raven"
DYE = RAVEN / "dye"
CROW = RAVEN / "crow"
IDS = RAVEN / "ids" / "eve.json"
HEART = Path("/tmp/ravenheart/state.json")

MAX_DOMAINS = 16
MAX_PORTS = 12
MAX_IPS = 14
MAX_MACS = 14
MAX_CROWS = 4
MAX_RIFTS = 6

# the plazas on the home-device ring: reserved empty wedges so each great room
# stands apart from the LAN cluster (well / heart / media / devices / gates).
# The wedges are real floor layout (dressing arrangement), never a data change.
MARKET_APRON_CENTER = 0.0      # due +x — Blackhorse, the market gate
MARKET_APRON_HALF = 0.55       # ~32° either side stays clear for the plaza
WORD_APRON_CENTER = math.pi    # due −x — Learn Islam, the room of the Word
WORD_APRON_HALF = 0.50         # ~28.6° either side stays clear for the hall
NET_APRON_CENTER = -math.pi * 0.5   # due −z — the pier out to the outward gate
NET_APRON_HALF = 0.30          # keep the LAN cluster off the pier
MACHINE_APRON_CENTER = math.pi * 0.5  # due +z — the hatch down into THIS machine
MACHINE_APRON_HALF = 0.30      # the one free wedge: the box under your feet
PLAZA_WEDGES = ((MARKET_APRON_CENTER, MARKET_APRON_HALF),
                (WORD_APRON_CENTER, WORD_APRON_HALF),
                (NET_APRON_CENTER, NET_APRON_HALF),
                (MACHINE_APRON_CENTER, MACHINE_APRON_HALF))


def _device_angles(n):
    """Spread n home devices evenly around the ring, always keeping every
    plaza wedge bare: the LAN stays grouped and nicely spaced, and each of
    the two great rooms (market, Word) keeps a whole empty quadrant."""
    if n < 1:
        return []

    def _norm(a):
        return a % (2 * math.pi)

    def _inside(a):
        for c, h in PLAZA_WEDGES:
            d = (a - c + math.pi) % (2 * math.pi) - math.pi
            if abs(d) < h:
                return True
        return False

    cuts = sorted({0.0, 2 * math.pi} | {_norm(c - h) for c, h in PLAZA_WEDGES}
                  | {_norm(c + h) for c, h in PLAZA_WEDGES})
    allowed = [(a, b) for a, b in zip(cuts, cuts[1:])
               if b - a > 1e-9 and not _inside((a + b) / 2.0)]
    length = sum(b - a for a, b in allowed)
    out = []
    for j in range(n):
        p = (j + 0.5) / n * length
        for a, b in allowed:
            if p <= (b - a) + 1e-9:
                out.append(a + min(p, b - a))
                break
            p -= (b - a)
    return out

_RE_DOMAIN = re.compile(r"\b([a-z0-9][a-z0-9.-]*\.[a-z]{2,})\b")
_RE_DOMAIN_COUNT = re.compile(r"\b([a-z0-9][a-z0-9.-]*\.[a-z]{2,})\s*[x×]\s*(\d+)")
_RE_IPV4 = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
_RE_MAC = re.compile(r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
_RE_PORT = re.compile(r"\b(\d{1,5})/(tcp|udp)\b")


def _load(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _text(p: Path) -> str:
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return ""


def _self_macs() -> set:
    """This host's own interface MACs (read from /sys — local, no network)."""
    macs = set()
    for p in glob.glob("/sys/class/net/*/address"):
        try:
            m = Path(p).read_text().strip().lower()
        except Exception:
            continue
        if m and m != "00:00:00:00:00:00":
            macs.add(m)
    return macs


def _self_ips() -> set:
    """This host's own IPv4 addresses (kernel ioctl on interfaces — local, no
    packets sent). Used only to say which recorded devices are on a segment we
    are actually on right now vs. an old one."""
    import socket, fcntl, struct
    ips = set()
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
            ips.add(socket.inet_ntoa(res[20:24]))
        except Exception:
            pass
        finally:
            if s is not None:
                s.close()
    return ips


def _parse_ts(s: str):
    try:
        return time.mktime(time.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


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


def _subnet(ip: str) -> str:
    return ip.rsplit(".", 1)[0] if "." in ip else ip


def _ring(i: int, n: int, radius: float, phase: float = 0.0):
    """Deterministic placement on a ring. Returns (x, z)."""
    if n <= 0:
        return (0.0, 0.0)
    a = phase + (2 * math.pi * i / n)
    return (round(radius * math.cos(a), 3), round(radius * math.sin(a), 3))


# ---- floor: the LAN --------------------------------------------------------

def _devices(gw: str = "") -> list:
    contacts = _load(DYE / "contacts.json", {})
    if not isinstance(contacts, dict):
        return []
    selves = _self_macs()
    my_ips = _self_ips()
    my_subnets = {_subnet(ip) for ip in my_ips}
    now = time.time()
    rows = []
    for mac, c in contacts.items():
        if not isinstance(c, dict):
            continue
        sni = c.get("sni") or {}
        names = sorted(sni, key=lambda d: -int(sni.get(d, 0)))[:6]
        traffic = sum(int(v) for v in sni.values()) if sni else 0
        host = c.get("host") or ""
        ip = c.get("ip") or "?"
        # a name starting with "_" is NOT a name — dye caught only an L4 crumb
        announced = host if host and not host.startswith("_") else ""
        is_self = mac.lower() in selves
        ts = _parse_ts(c.get("t") or "")
        age = None if ts is None else now - ts
        fresh = age is not None and age <= 3600
        on_my_segment = _subnet(ip) in my_subnets if ip != "?" else False
        role = "gateway" if (gw and ip == gw) else "device"
        flags = []
        if role == "gateway":
            flags.append("the way out")
        if not on_my_segment and ip != "?":
            flags.append("other segment (recorded)")
        if not fresh and age is not None:
            flags.append("stale")
        rows.append({
            "mac": mac, "ip": ip, "host": host, "announced": announced,
            "vendor": c.get("vendor") or "",
            "sni": [{"name": d, "count": int(sni.get(d, 0))} for d in names],
            "sni_total": traffic, "t": c.get("t") or "",
            "is_self": is_self, "role": role, "segment": _subnet(ip),
            "last_seen": _ago(age), "age_s": None if age is None else int(age),
            "fresh": fresh, "on_my_segment": on_my_segment,
            "flags": flags,
            # what we actually OBSERVED (fact) vs what we INFER (a story)
            "observed": {"mac": True, "ip_seen": ip,
                         "sni_names": len(sni), "sni_hits": traffic},
        })
    rows.sort(key=lambda r: (not r["is_self"], r["role"] != "gateway",
                             -r["sni_total"], r["ip"]))
    # --- lay the floor out as ROOMS: your segment inside, old segments as ruins
    home = next((s for s in {r["segment"] for r in rows} if s in my_subnets), None)
    if home is None and rows:
        counts: dict = {}
        for r in rows:
            counts[r["segment"]] = counts.get(r["segment"], 0) + 1
        home = max(counts, key=counts.get)
    home_rows = [r for r in rows if r["segment"] == home]
    # your segment = the lit inner room you stand in. Devices sit on an even
    # ring around the heart, but the plaza wedges stay empty so the market gate
    # and the room of the Word each have their own cleared quadrant — the LAN
    # stays together, the two great rooms stand apart.
    m = len(home_rows)
    angles = _device_angles(m)
    for j, r in enumerate(home_rows):
        a = angles[j]
        r["pos"] = [round(18.0 * math.cos(a), 3), round(18.0 * math.sin(a), 3)]
        r["room"] = home
        r["room_home"] = True
        r["angle"] = a
    # each old segment = its own walled ruin on the outer ring
    ruin_segs: dict = {}
    for r in rows:
        if r["segment"] != home:
            ruin_segs.setdefault(r["segment"], []).append(r)
    order = sorted(ruin_segs, key=lambda s: -len(ruin_segs[s]))
    nseg = len(order)
    segments = [{"subnet": home, "is_home": True, "count": m,
                 "angle": -math.pi / 2,
                 "macs": [r["mac"] for r in home_rows],
                 "newest_s": min([r["age_s"] for r in home_rows
                                  if r.get("age_s") is not None], default=None)}]
    for si, sub in enumerate(order):
        base = -math.pi / 2 + 2 * math.pi * (si + 1) / (nseg + 1)
        ds = ruin_segs[sub]
        mm = len(ds)
        for j, r in enumerate(ds):
            frac = (j + 0.5) / mm if mm else 0.5
            a = base + (frac - 0.5) * 0.9
            r["pos"] = [round(39.0 * math.cos(a), 3), round(39.0 * math.sin(a), 3)]
            r["room"] = sub
            r["room_home"] = False
            r["angle"] = a
        new_s = min([r["age_s"] for r in ds if r.get("age_s") is not None], default=None)
        segments.append({"subnet": sub, "is_home": False, "count": mm,
                         "angle": base, "newest_s": new_s,
                         "macs": [r["mac"] for r in ds]})
    for seg in segments:
        seg["newest"] = _ago(seg.get("newest_s"))
    for r in rows:
        if r["is_self"]:
            r["label"] = "this machine (you)"
            r["identity"] = "self"
        elif r["role"] == "gateway":
            r["label"] = "the way out (gateway)"
            r["identity"] = "announced" if r["announced"] else "role"
        elif r["announced"]:
            r["label"] = r["announced"]
            r["identity"] = "announced"     # a name it SAID, not a verified identity
        else:
            r["label"] = r["mac"]
            r["identity"] = "unknown"       # MAC only — we do not know what it is
        r["kind"] = "beacon" if r["sni_total"] > 0 else "dweller"
        # GitS framing: a shell that talks to the net is a cyberbrain; one we cannot
        # name has no ghost we can read.
        r["ghost"] = ("cyberbrain \u00b7 " + f"{r['sni_total']} signals to the net"
                      if r["sni_total"] > 0 else "silent shell")
        r["weight"] = r["sni_total"]
        r["sub"] = (f"{r['ip']} · last seen {r['last_seen']}"
                    + (" · " + " · ".join(r["flags"]) if r["flags"] else ""))
    return rows, segments


def _sources() -> list:
    """The local files this world is built from, and how fresh each one is.
    This is the 'look again' surface: it says what is stale and what refreshes
    it, WITHOUT running anything."""
    try:
        reports = sorted(CROW.glob("crow-*_report.txt"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        reports = []
    newest_crow = reports[0] if reports else None
    feeds = [
        ("dye \u00b7 who is on the wire", DYE / "contacts.json",
         "run dye \u2014 a passive look at this laptop's own interfaces"),
        ("dye \u00b7 cast crumbs", DYE / "dyed.json",
         "run dye"),
        ("crow \u00b7 newest report", newest_crow,
         "fly a crow \u2014 recon / eyes"),
        ("ids \u00b7 suricata alerts", IDS,
         "run Suricata"),
        ("heart \u00b7 the lifeline", HEART,
         "ravenheart twin \u2014 always beating"),
    ]
    now = time.time()
    out = []
    for name, p, hint in feeds:
        path = Path(p) if p else None
        exists = bool(path) and path.exists()
        age = None
        if exists:
            try:
                age = now - path.stat().st_mtime
            except Exception:
                age = None
        out.append({"name": name, "path": str(path) if path else "",
                    "exists": exists, "age": _ago(age),
                    "age_s": None if age is None else int(age),
                    "stale": (age is None) or age > 3600, "hint": hint})
    return out


def _gates(devices: list) -> list:
    gates = []
    for d in devices:
        bias = 4.4
        dx, dz = d["pos"]
        base = math.atan2(dz, dx) + math.pi     # face back toward the heart
        for j, s in enumerate(d["sni"][:4]):
            a = base + (j - 1.5) * 0.34
            x = round(dx + bias * math.cos(a), 3)
            z = round(dz + bias * math.sin(a), 3)
            gates.append({"device": d["mac"], "domain": s["name"],
                          "count": s["count"], "pos": [x, z]})
    return gates


def _media() -> list:
    dyed = _load(DYE / "dyed.json", {})
    media = dyed.get("media") or {}
    out, items = [], list(media.items())[:4]
    for i, (k, v) in enumerate(items):
        if not isinstance(v, dict):
            v = {}
        x, z = _ring(i, max(1, len(items)), 9.0, phase=math.pi * 0.75)
        out.append({"name": k, "model": v.get("model") or "",
                    "when": (v.get("t") or "")[:16], "tag": v.get("tag") or "",
                    "pos": [x, z]})
    return out


def _crow_report() -> dict | None:
    try:
        reports = sorted(CROW.glob("crow-*_report.txt"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        reports = []
    if not reports:
        return None
    p = reports[0]
    body = _text(p)
    try:
        mtime = p.stat().st_mtime
    except Exception:
        mtime = None
    name = next((l.split("—")[-1].strip() for l in body.splitlines()
                 if l.startswith("RAVEN CROW REPORT")), p.stem)
    role = target = ""
    m = re.search(r"role:\s*(\S+)\s+target:\s*(\S+)", body)
    if m:
        role, target = m.group(1), m.group(2)
    verdict, score, conf = "", None, None
    for l in body.splitlines():
        if "VERDICT" in l:
            verdict = l.strip(" ⚠").strip()
            ms = re.search(r"\((\d+)/100\)", l)
            if ms:
                score = int(ms.group(1))
            break
    mc = re.search(r"~?(\d+)%\s*confidence", body)
    if mc:
        conf = int(mc.group(1))
    briefing = [l.strip(" —").strip() for l in body.splitlines()
                if l.strip().startswith("—")][:6]
    return {"name": name, "role": role, "target": target, "verdict": verdict,
            "score": score, "confidence": conf, "briefing": briefing,
            "file": p.name, "body": body, "mtime": mtime}


def _crows() -> list:
    newest = _crow_report()
    out = []
    if not newest:
        return out
    score = newest.get("score")
    sev = 0
    if isinstance(score, int):
        sev = 3 if score >= 65 else 2 if score >= 45 else 1
    for i in range(min(MAX_CROWS, max(1, sev + 1))):
        x, z = _ring(i, 4, 30.0, phase=math.pi * 0.2 + i * 0.4)
        out.append({"name": newest["name"] if i == 0 else f"crow-{i + 1}",
                    "role": newest["role"], "target": newest["target"],
                    "verdict": newest["verdict"] if i == 0 else "",
                    "score": score, "confidence": newest["confidence"],
                    "briefing": newest["briefing"] if i == 0 else [],
                    "pos": [x, z], "severity": sev})
    return out


def _rifts() -> list:
    alerts = []
    try:
        lines = [l for l in _text(IDS).splitlines() if l.strip()][-40:]
        for line in lines:
            r = json.loads(line)
            s = r.get("alert") or {}
            alerts.append({"sig": s.get("signature") or "?",
                           "src": r.get("src_ip"), "dst": r.get("dest_ip"),
                           "ts": str(r.get("timestamp") or "")[11:19]})
    except Exception:
        alerts = []
    out = []
    for i, a in enumerate(alerts[-MAX_RIFTS:]):
        x, z = _ring(i, max(1, len(alerts)), 34.0, phase=math.pi * 0.4)
        out.append({**a, "pos": [x, z]})
    return out


def _heart() -> dict:
    st = _load(HEART, {})
    try:
        rtt = None if st.get("rtt") is None else float(st.get("rtt"))
    except Exception:
        rtt = None
    return {"up": bool(st.get("up")), "iface": st.get("iface") or "?",
            "gw": st.get("gw") or "?", "rtt": rtt,
            "strikes": st.get("strikes"), "mode": (st.get("guard") or {}).get("mode"),
            "acts": (st.get("guard") or {}).get("acts")}


# ---- strata: the protocol stack, top to bottom -----------------------------

def _domains(devices: list, crow: dict | None) -> list:
    tally: dict[str, int] = {}
    for d in devices:
        for s in d["sni"]:
            tally[s["name"]] = tally.get(s["name"], 0) + s["count"]
    if crow:
        for name, cnt in _RE_DOMAIN_COUNT.findall(crow["body"]):
            tally[name] = max(tally.get(name, 0), int(cnt))
    return sorted(({"label": k, "value": v} for k, v in tally.items()),
                  key=lambda r: -r["value"])[:MAX_DOMAINS]


def _ports(crow: dict | None) -> list:
    seen: dict[str, int] = {}
    if crow:
        for num, proto in _RE_PORT.findall(crow["body"]):
            seen[f"{num}/{proto}"] = seen.get(f"{num}/{proto}", 0) + 1
    # names that matter for the sorting office, if the wire used them
    named = {"443/tcp": "ssl/https", "80/tcp": "http", "53/udp": "dns",
             "21/tcp": "ftp", "22/tcp": "ssh", "23/tcp": "telnet",
             "1900/tcp": "upnp", "3986/tcp": "mapper", "5353/udp": "mdns"}
    out = []
    for key, _n in sorted(seen.items(), key=lambda kv: -kv[1]):
        out.append({"label": key, "value": named.get(key, "port")})
    return out[:MAX_PORTS]


def _addresses(devices: list, heart: dict, crow: dict | None) -> list:
    ips: dict[str, str] = {}
    for d in devices:
        if d["ip"] and d["ip"] != "?":
            ips[d["ip"]] = d["label"]
    if heart.get("gw"):
        ips.setdefault(heart["gw"], "gateway")
    if crow:
        for ip in _RE_IPV4.findall(crow["body"]):
            ips.setdefault(ip, "")
    out = [{"label": ip, "value": host} for ip, host in ips.items()]
    return out[:MAX_IPS]


def _links(devices: list, crow: dict | None) -> list:
    macs: dict[str, str] = {}
    for d in devices:
        macs[d["mac"]] = d["label"]
    if crow:
        for mac in _RE_MAC.findall(crow["body"]):
            macs.setdefault(mac.lower(), "")
    out = [{"label": mac, "value": host} for mac, host in macs.items()]
    return out[:MAX_MACS]


CODEX = {
    "floor": {"friendly": "the shell",
              "real": "link-local LAN (your segment)",
              "blurb": "A shell is the body; a ghost is what lives in it. Here the "
                       "shells are the neighbours dye has met, and the heart is your "
                       "own host — the one shell you are inside."},
    "app": {"friendly": "the sea of information",
            "real": "application layer — DNS names & TLS server names",
            "blurb": "The names a shell speaks into the net when it wants something. "
                     "A domain is a spoken name; the tunnel itself stays encrypted. "
                     "The net is vast and infinite."},
    "transport": {"friendly": "the sorting office",
                  "real": "transport layer — TCP / UDP ports",
                  "blurb": "Where a spoken name gets a door number. The port says "
                           "which service on a host is being knocked on."},
    "internet": {"friendly": "the addressing plains",
                 "real": "internet layer — IP addresses & routes",
                 "blurb": "Flat numbers that find a machine anywhere on the wire, "
                          "hop by hop."},
    "link": {"friendly": "the last hop",
             "real": "link layer — MAC addresses & ARP",
             "blurb": "The last hop on your own segment: the hardware address a "
                      "frame is handed to. Everything you know of a shell starts here."},
    "physical": {"friendly": "the ghost in the machine",
                 "real": "physical layer — the last electron",
                 "blurb": "The edge. The final electron at the tip of the wire, where "
                          "the pattern becomes matter. Step past it and the dive opens "
                          "onto the sea of information — vast and infinite, and it never "
                          "bottoms out. Below the edge there are no named entities, only "
                          "the descent: the sea carries no data. There is no place "
                          "Mr.Fluffy cannot go."},
}


def _strata(domains, ports, ips, macs) -> list:
    def obelisks(rows, kind):
        n = len(rows)
        out = []
        for i, r in enumerate(rows):
            x, z = _ring(i, n, 13.0, phase=-math.pi / 2)
            val = r.get("value", "")
            weight = val if isinstance(val, (int, float)) else 1
            out.append({"label": r["label"], "value": val, "weight": weight,
                        "sub": str(val), "kind": kind, "pos": [x, z]})
        return out
    return [
        {"key": "app", "depth": -10, "index": 1,
         "artifacts": obelisks(domains, "domain")},
        {"key": "transport", "depth": -20, "index": 2,
         "artifacts": obelisks(ports, "port")},
        {"key": "internet", "depth": -30, "index": 3,
         "artifacts": obelisks(ips, "ip")},
        {"key": "link", "depth": -40, "index": 4,
         "artifacts": obelisks(macs, "mac")},
        {"key": "physical", "depth": -50, "index": 5,
            "artifacts": [{"label": "the last electron", "value": "",
                           "sub": "the edge \u00b7 step past it and the sea has no bottom",
                           "kind": "electron", "pos": [0.0, 0.0]}]},
    ]


def _truth(devices: list) -> dict:
    n = len(devices)
    n_unknown = sum(1 for d in devices if d["identity"] == "unknown")
    n_announced = sum(1 for d in devices if d["identity"] == "announced")
    n_self = sum(1 for d in devices if d["identity"] == "self")
    n_other = sum(1 for d in devices if not d.get("on_my_segment"))
    n_stale = sum(1 for d in devices if not d.get("fresh"))
    notes = [
        f"{n_unknown} of {n} devices have NO name at all — only a MAC "
        f"('_tcp'/'_udp' is a protocol crumb, not an identity).",
        f"{n_announced} carry a name the device ANNOUNCED, not a verified identity.",
        f"{n_self} is THIS machine — your own MAC, the wire's reflection of you.",
        "the heart = this host's lifeline (ravenheart.py), not Mr.Fluffy.",
    ]
    if n_other:
        notes.append(f"{n_other} device(s) were recorded on a DIFFERENT segment than "
                     f"you are on now — that IP is a memory, not a live address.")
    if n_stale:
        notes.append(f"{n_stale} device(s) are stale (last seen over an hour ago).")
    return {
        "observed": ["a MAC address",
                     "the IP it was last seen at, and when it was seen",
                     "the TLS server names (SNI) it asked for, and how often"],
        "inferred": ["what kind of device it is (phone / TV / PC)",
                     "what the traffic means (e.g. 'a trading app')",
                     "any human name"],
        "notes": notes,
    }


def _complexes(devices: list) -> list:
    """A pattern with no single origin: a name that two or more shells both reach.
    Real, derived from the files — Ghost in the Shell's 'Stand Alone Complex':
    a coherent whole that emerges with no leader. Ground truth only."""
    by_domain: dict = {}
    for d in devices:
        for s in d.get("sni", []):
            by_domain.setdefault(s["name"], set()).add(d["label"])
    out = []
    for dom, who in by_domain.items():
        if len(who) >= 2:
            out.append({"domain": dom, "devices": sorted(who), "count": len(who)})
    out.sort(key=lambda c: (-c["count"], c["domain"]))
    return out[:6]


def build() -> dict:
    wf = wire.feed()
    heart = _heart()
    devices, segments = _devices(heart.get("gw") or "")
    gates = _gates(devices)
    media = _media()
    crow = _crow_report()
    crows = _crows()
    rifts = _rifts()
    domains = _domains(devices, crow)
    ports = _ports(crow)
    ips = _addresses(devices, heart, crow)
    macs = _links(devices, crow)
    strata = _strata(domains, ports, ips, macs)
    codex = dict(CODEX)
    codex["_order"] = ["floor", "app", "transport", "internet", "link", "physical"]
    selves = [d for d in devices if d["is_self"]]
    heart["what"] = ("your HOST's network lifeline (ravenheart.py on this PC) — "
                     "not Mr.Fluffy, which is just the reader app on the same machine")
    ages = [d["age_s"] for d in devices if d.get("age_s") is not None]
    if crow and crow.get("mtime"):
        ages.append(int(time.time() - crow["mtime"]))
    newest = min(ages) if ages else None
    memory = {
        "newest_s": newest, "newest": _ago(newest),
        "note": "This world is a MEMORY. The net is vast and infinite — Wire "
                "Vision replays the last thing dye and the crows observed and "
                "touches nothing. One exception: the outward gate past the edge "
                "(due \u2212z) really dials the net (real DNS + HTTP/HTTPS, no "
                "browser). Everywhere else the sea never bottoms out, holds no "
                "named entity, and carries no data.",
        "counts_note": "SNI counts are cumulative observations (seen N times), not a rate.",
    }
    return {
        "generated": time.time(),
        "fingerprint": wf.get("fingerprint"),
        "self": {"macs": sorted(_self_macs()),
                 "recorded": [{"mac": d["mac"], "ip": d["ip"]} for d in selves]},
        "truth": _truth(devices),
        "memory": memory,
        "segments": segments,
        "sources": _sources(),
        "complexes": _complexes(devices),
        "source": {"devices": len(devices), "gates": len(gates),
                   "domains": len(domains), "ports": len(ports),
                   "ips": len(ips), "macs": len(macs), "rifts": len(rifts),
                   "crows": len(crows), "media": len(media)},
        "heart": heart,
        "devices": devices,
        "gates": gates,
        "media": media,
        "crows": crows,
        "rifts": rifts,
        "crow_report": {k: crow[k] for k in
                        ("name", "role", "target", "verdict", "score",
                         "confidence", "briefing", "file")} if crow else None,
        "strata": strata,
        "codex": codex,
    }


def summary(w: dict) -> str:
    s = w["source"]
    h = w["heart"]
    rtt = "?" if h.get("rtt") is None else f"{round(float(h['rtt']), 1)}ms"
    lines = [
        "WIRE VISION — the wire as a place you can walk",
        "=" * 52,
        f"fingerprint {w.get('fingerprint')}  ·  built {time.strftime('%Y-%m-%d %H:%M', time.localtime(w['generated']))}",
        "",
        f"the floor   heart up={h.get('up')} {h.get('iface')} gw={h.get('gw')} rtt={rtt} "
        f"guard={h.get('mode')} acts={h.get('acts')}",
        f"            {s['devices']} devices · {s['gates']} gates · {s['media']} cast · "
        f"{s['crows']} crows · {s['rifts']} rifts",
    ]
    for d in w["devices"]:
        top = ", ".join(f"{x['name']}x{x['count']}" for x in d["sni"][:3]) or "no sni"
        tag = {"self": "you", "announced": "announced name",
               "role": "role only", "unknown": "MAC only"}.get(d.get("identity"), d.get("identity"))
        extra = ("  [" + " · ".join(d.get("flags", [])) + "]") if d.get("flags") else ""
        lines.append(f"            • {d['label']} @ {d['ip']} · {top}")
        lines.append(f"              ({tag} · last seen {d.get('last_seen','?')}{extra})")
    lines.append("")
    lines.append("the floor is ROOMS \u2014 your segment inside, old ones as walled ruins:")
    for seg in w.get("segments", []):
        tag = ("YOUR SEGMENT \u2014 the lit room" if seg["is_home"]
               else f"RUIN \u2014 old segment, last seen {seg.get('newest')}")
        lines.append(f"    {seg['subnet']:<24} {seg['count']} device(s)  \u00b7 {tag}")
    lines.append("")
    lines.append("sources this world is built from (how to 'look again'):")
    for f in w.get("sources", []):
        mark = "STALE" if f["stale"] else "fresh"
        lines.append(f"    [{mark:>5}] {f['name']:<26} {f['age']:<10} \u2192 {f['hint']}")
    cx_list = w.get("complexes", [])
    if cx_list:
        lines.append("")
        lines.append("stand alone complexes — a name two or more shells both reach (no single origin):")
        for c in cx_list:
            lines.append(f"    {c['domain']:<28} \u2190 {', '.join(c['devices'])}")
    else:
        lines.append("")
        lines.append("stand alone complexes: none — every name is reached by a single shell.")
    for st in w["strata"]:
        cx = w["codex"][st["key"]]
        art = ", ".join(a["label"] for a in st["artifacts"][:5]) or "(empty)"
        lines.append("")
        lines.append(f"[{st['index']}] {cx['friendly'].upper()}  ({cx['real']})")
        lines.append(f"    {art}")
    lines += ["", "codex: friendly name -> real term"]
    for k in w["codex"]["_order"]:
        c = w["codex"][k]
        lines.append(f"    {c['friendly']:<20} = {c['real']}")
    lines += ["", "there is no place Mr.Fluffy cannot go —",
              "step past the last electron and the sea of information never bottoms out;",
              "below the edge it carries no data, only the descent."]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    w = build()
    if "--summary" in sys.argv:
        print(summary(w))
    else:
        print(json.dumps(w, indent=2))
