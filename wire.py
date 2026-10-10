"""wire.py — Mr.Fluffy's eyes on the wire.

The king of the wire reads the network the way it reads the news: a compact
snapshot of WHO is on the network and WHAT they talk to, handed to the brain as
context alongside the headlines. All sources are LOCAL files, cheap to read,
and tolerate absence (a missing feed is omitted, never fatal — matching the
news.py contract).

Sources:
  * ~/raven/dye/contacts.json       per-device contact table (host/ip/mac + SNI counts)
  * ~/raven/dye/dyed.json           cast/media announcements dye saw
  * ~/raven/crow/crow-*_report.txt  newest eyes/recon crow briefing + verdict
  * ~/raven/ids/eve.json            Suricata alerts (JSON-lines, raw-ish)
  * /tmp/ravenheart/events.log + state.json  lifeline heart health

Fingerprint strategy: it must only change when the wire MEANINGFULLY shifted —
a device join/leave, a NEW domain, an alert, a lifeline flap. SNI hit-count
ticks and routine PING lines must NOT retrigger a readout, or the daemon would
hammer the brain budget for no signal.

CLI:  python3 wire.py        # print the context block
      python3 wire.py --fp   # print the fingerprint only
"""
import hashlib, json
from pathlib import Path

FLUFFY = Path.home() / "mrfluffy"
RAVEN = Path.home() / "raven"
DYE = RAVEN / "dye"
CROW = RAVEN / "crow"
EVENTS = Path("/tmp/ravenheart/events.log")
STATE = Path("/tmp/ravenheart/state.json")

MAX_DEVICES = 6            # devices shown per readout
MAX_SNI_PER_DEVICE = 5     # top SNI names shown per device
MAX_CROW_CHARS = 900       # crow briefing budget
MAX_EVE = 3                # most recent IDS alerts shown


def _load(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _tail(p: Path, n: int = 6) -> list:
    try:
        lines = p.read_text(errors="ignore").splitlines()
        return [l for l in lines if l.strip()][-n:]
    except Exception:
        return []


def devices_block() -> tuple:
    """(text, fingerprint parts) — who is on the wire and what each talks to."""
    contacts = _load(DYE / "contacts.json", {})
    if not isinstance(contacts, dict) or not contacts:
        return "(no devices captured yet)", []
    rows = [(c.get("t") or "", mac, c) for mac, c in contacts.items()]
    rows.sort(reverse=True)                 # newest contact first (t is sortable)
    lines, fp = [], []
    for _t, mac, c in rows[:MAX_DEVICES]:
        host = c.get("host") or ""
        label = f"{mac}" + (f" ({host})" if host and host not in ("_tcp", "_udp") else "")
        ip = c.get("ip") or "?"
        sni = c.get("sni") or {}
        names = sorted(sni, key=lambda d: -int(sni.get(d, 0)))[:MAX_SNI_PER_DEVICE]
        if names:
            top = ", ".join(f"{d} x{sni.get(d)}" for d in names)
            trailing = "…" if len(sni) > len(names) else ""
            line = f" {label} @ {ip} · {top}{trailing}"
        else:
            line = f" {label} @ {ip} · (no sni seen)"
        lines.append(line)
        fp.append((mac, ip, host))
        fp += [(mac, d) for d in sni]
    return ("\n".join(lines), fp)


def media_block() -> str:
    """Cast/media crumbs dye captured. Compact; usually '(none)'."""
    dyed = _load(DYE / "dyed.json", {})
    media = dyed.get("media") or {}
    if not media:
        return "(none)"
    parts = []
    for k, v in media.items():
        if not isinstance(v, dict):
            parts.append(f"{k}: ?")
            continue
        when = (v.get("t") or "")[:16]
        extra = " ".join(f"{kk}={vv}" for kk, vv in v.items()
                         if kk not in ("t", "tag", "token") and vv not in (None, "", {}, []))
        parts.append(f"{k} ({when}){(' · ' + extra) if extra else ''}")
    return "; ".join(parts[:4])


def crow_block() -> tuple:
    """(text, fingerprint parts) — the newest crow's verdict, kept short."""
    try:
        reports = sorted(CROW.glob("crow-*_report.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        reports = []
    if not reports:
        return "(no crow reports yet)", []
    p = reports[0]
    try:
        body = p.read_text(errors="ignore")
    except Exception:
        return "(crow report unreadable)", []
    head = next((l for l in body.splitlines() if l.startswith("role:")), "").strip()
    brief = next((l for l in body.splitlines() if l.startswith("  —  read-out:")), "")
    verdict = next((l for l in body.splitlines() if l.startswith("  ⚠ VERDICT")), "")
    if brief and "encrypted" in brief:
        brief = brief[:160]
    return (f"{p.name} {head}\n{brief}\n{verdict}", [p.name, verdict])


def ids_block() -> tuple:
    """(text, fingerprint parts) — Suricata alerts on the wire, if any."""
    eve = RAVEN / "ids" / "eve.json"
    alerts = []
    try:
        for line in _tail(eve, n=20):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            s = (r.get("alert") or {})
            sig = s.get("signature")
            src = r.get("src_ip"); dst = r.get("dest_ip")
            alerts.append({"sig": sig, "src": src, "dst": dst,
                           "ts": str(r.get("timestamp") or "")[11:19]})
    except Exception:
        pass
    if not alerts:
        return "(no IDS alerts)", []
    out = []
    for a in alerts[-MAX_EVE:]:
        out.append(f" {a['ts']} {a['sig']} {a.get('src')} -> {a.get('dst')}")
    return ("\n".join(out), [a["sig"] for a in alerts])


def lifeline_block() -> tuple:
    """(text, fingerprint parts) — the heart that keeps the host on the wire."""
    st = _load(STATE, {})
    try:
        rtt = st.get("rtt")
        rtt_s = "?" if rtt is None else f"{round(float(rtt), 1)}ms"
    except Exception:
        rtt_s = "?"
    line = (f"up={st.get('up')} iface={st.get('iface')} gw={st.get('gw')} "
            f"strikes={st.get('strikes')} rtt={rtt_s} "
            f"guard={st.get('guard', {}).get('mode')} acts={st.get('guard', {}).get('acts')}")
    fp = [str(st.get("up")), str(st.get("strikes")),
          str((st.get("guard") or {}).get("acts"))]
    return line, fp


def _blob(text: str) -> str:
    return text if text.strip() else "(none)"


def feed() -> dict:
    """The wire context handed to the brain: a text block + a change-sensitive
    fingerprint. Missing feeds are omitted from both."""
    dev_txt, dev_fp = devices_block()
    media_txt = media_block()
    crow_txt, crow_fp = crow_block()
    ids_txt, ids_fp = ids_block()
    life_txt, life_fp = lifeline_block()

    parts = [f"WIRE — devices (dye):\n{dev_txt}",
             f"WIRE — cast/media (dye): {_blob(media_txt)}",
             f"WIRE — newest crow:\n{crow_txt}",
             f"WIRE — IDs (suricata):\n{ids_txt}",
             f"WIRE — lifeline (ravenheart):\n{life_txt}"]
    text = "\n".join(parts)

    basis = "|".join(str(x) for x in (dev_fp, crow_fp, ids_fp, life_fp))
    return {"text": text, "fingerprint": hashlib.sha256(basis.encode("utf-8", "ignore")).hexdigest()[:16],
            "sources": len(dev_fp) > 0, "media": bool((_load(DYE / "dyed.json", {}).get("media"))),
            "ids": ids_fp, "lifeline": life_fp}


if __name__ == "__main__":
    import sys
    w = feed()
    if "--fp" in sys.argv:
        print(w["fingerprint"])
    else:
        print(w["text"])
        print("\n[fp]", w["fingerprint"])