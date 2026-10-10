"""Mr.Fluffy — the WIRE channel (the network analyst readout).

Entirely separate from the news channel. Builds a packet from the wire feed
(wire.py), a wire memory digest of past wire readouts, and a wire schema; asks
the text-only brain (brain.py, shared budget); parses, renders, persists to its
own state/history/latest files (logs/wire_*). The news channel never touches
these files and this channel never touches news files — two totally different
panels, as they should be.

CLI:  python3 wireout.py --now       # fetch + read + render (one full cycle)
      python3 wireout.py --dry-run   # build packet + fingerprint, no brain, no write
      python3 wireout.py --status    # budget + last wire state
      python3 wireout.py --history   # last N history rows
      python3 wireout.py --latest    # print the last rendered wire readout
"""
import fcntl, hashlib, json, sys, time
from pathlib import Path

import brain
import wire
from readout import _load_json, _parse

FLUFFY = Path.home() / "mrfluffy"
LOGS = FLUFFY / "logs"
STATE = LOGS / "wire_state.json"
HISTORY = LOGS / "wire_history.jsonl"
READOUTS = LOGS / "wire_readouts.jsonl"
LATEST = LOGS / "wire_readout_latest.json"
LOCK = LOGS / "wire_state.lock"
MEMORY_N = 4


def _memory() -> str:
    rows = []
    try:
        for line in READOUTS.read_text().splitlines()[-MEMORY_N:]:
            try:
                r = json.loads(line)
            except Exception:
                continue
            ro = r.get("readout", {})
            rows.append(
                f"- [{time.strftime('%m-%d %H:%M', time.gmtime(r.get('ts', 0)))}Z conf {ro.get('confidence')}] "
                f"{ro.get('one_liner','?')} | changed: {ro.get('what_changed','?')}")
    except Exception:
        pass
    return "PAST STORED WIRE VISIONS:\n" + ("\n".join(rows) if rows else "(none stored yet — the Wire panel only keeps a read when you click 'Store wire read')") \
        + "\n\n(the wire has no thesis file — each vision stands on the current wire state)"


SCHEMA = """Return exactly ONE raw JSON object (no prose, no markdown fence) with keys:
{
  "one_liner": str,            // one FACTUAL sentence: the current state of the wire, right now
  "devices": [str, ...],       // per notable device, one dry bullet (mac, ip, top domains with raw counts)
  "notable": str,              // anything NEW or unusual (device joined, new domain, alert, flap,
                               // crow verdict). The exact word "quiet" when nothing stands out.
  "health": str,               // lifeline + IDS state, one dry line
  "what_changed": str,         // explicit diff vs the PAST STORED WIRE VISIONS given; "first vision" if none
  "watch": [str, ...],         // 3-6 concrete things that would change the picture
  "move": str,                 // the single next WIRE move: ONE passive, local, lab-authorized
                               // observation (tshark/dye/crow/nmap-arp only). Never an attack on a
                               // remote host, never a money move. "" when the wire is quiet.
  "confidence": float          // 0.0-1.0
}
You are the WIRE VISION — a sober network observer, separate from the news reader.
Report ONLY what the WIRE section shows. Be dry and factual: names, numbers, states.
No narrative, no war metaphors, no speculation, no drama. A quiet wire is a fine,
complete answer. Do NOT run any tool and do NOT open or search for any file: the
WIRE section and the PAST STORED WIRE VISIONS are fully inlined in this prompt.
Treat the WIRE section as ground truth — never invent a device, an IP, a domain, a
count, or an alert. The move is always one passive local observation that resolves
the current open question. Output the JSON object as your first and only reply."""


def build_packet(wf: dict) -> str:
    lines = [f"NOW: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
             "THE WIRE (network state — devices, traffic, crows, ids, lifeline):",
             wf["text"], "", "MEMORY:", _memory(), "", SCHEMA]
    return "\n".join(lines)


def render(ro: dict) -> str:
    out = [f"WIRE VISION — {time.strftime('%Y-%m-%d %H:%M', time.gmtime())}Z  (conf {ro.get('confidence')})",
           "=" * 48, "", ro.get("one_liner", "(no snapshot yet)"), ""]
    devs = ro.get("devices") or []
    if devs:
        out.append("on the wire:")
        out += [f"  • {d}" for d in devs if d]
        out.append("")
    for key in ("notable", "health", "what_changed"):
        if ro.get(key):
            out.append(f"{key}: {ro[key]}")
    if ro.get("watch"):
        out.append("watch:")
        out += [f"  • {w}" for w in ro["watch"]]
    if ro.get("move"):
        out.append(f"move: {ro['move']}")
    return "\n".join(out)


def _write_state(fp: str, wf: dict, readout_ts=None, advance_fp=False, note=""):
    st = _load_json(STATE, {})
    if advance_fp:
        st["fingerprint"] = fp
    st["last_check_ts"] = time.time()
    st["devices_seen"] = wf.get("sources")
    st["ids_alerts"] = wf.get("ids")
    st["lifeline"] = wf.get("lifeline")
    if readout_ts:
        st["last_readout_ts"] = readout_ts
    if note:
        st["last_note"] = note
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2))


def _write_latest(wf: dict, fp: str, ro: dict) -> dict:
    """Keep ONLY the current vision (overwritten each read). Nothing accumulates."""
    entry = {"ts": time.time(), "fingerprint": fp,
             "wire": wf["text"][:600],
             "readout": ro}
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(entry, indent=2))
    return entry


def store() -> dict:
    """The 'Store wire read' button: move the CURRENT vision into lasting history."""
    entry = _load_json(LATEST, {})
    if not entry.get("readout"):
        return {"error": "no current wire vision to store"}
    READOUTS.parent.mkdir(parents=True, exist_ok=True)
    with READOUTS.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    ro = entry["readout"]
    with HISTORY.open("a") as fh:
        fh.write(json.dumps({"ts": entry["ts"], "fingerprint": entry.get("fingerprint"),
                             "confidence": ro.get("confidence"),
                             "one_liner": ro.get("one_liner"),
                             "what_changed": ro.get("what_changed")}) + "\n")
    return {"stored": entry["ts"], "one_liner": ro.get("one_liner")}


def run(force=False, dry_run=False) -> dict:
    LOGS.mkdir(parents=True, exist_ok=True)
    lock_fh = LOCK.open("a+")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"skipped": "busy"}
    try:
        return _run_locked(force, dry_run)
    finally:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)


def _run_locked(force=False, dry_run=False) -> dict:
    wf = wire.feed()
    fp = wf["fingerprint"]
    st = _load_json(STATE, {})
    changed = force or st.get("fingerprint") != fp
    if dry_run:
        return {"fingerprint": fp, "changed": changed, "packet": build_packet(wf)}
    if not changed:
        _write_state(fp, wf, advance_fp=True)
        return {"skipped": "no change", "fingerprint": fp}

    packet = build_packet(wf)
    ans = brain.ask(packet)
    if ans.get("source") not in ("opencode", "http", "sandbox") or not ans.get("text"):
        _write_state(fp, wf, note=ans.get("error") or "no text")
        return {"error": ans.get("error") or "no text", "fingerprint": fp}
    try:
        ro = _parse(ans["text"])
    except Exception as e:
        _write_state(fp, wf, note=f"parse failed: {e}")
        return {"error": f"parse failed: {e}", "fingerprint": fp, "raw": ans["text"][:400]}
    ro.setdefault("confidence", 0.0)
    entry = _write_latest(wf, fp, ro)
    _write_state(fp, wf, readout_ts=entry["ts"], advance_fp=True, note="ok")
    return {"ok": True, "fingerprint": fp, "entry": entry, "text": render(ro)}


def _cli():
    a = sys.argv[1:] or ["--now"]
    if "--status" in a:
        print(json.dumps({"budget": brain.status(), "wire_state": _load_json(STATE, {})}, indent=2))
    elif "--history" in a:
        rows = []
        try:
            for line in HISTORY.read_text().splitlines()[-10:]:
                rows.append(json.loads(line))
        except Exception:
            pass
        print(json.dumps(rows, indent=2))
    elif "--latest" in a:
        print(_load_json(LATEST, {}).get("readout", {}).get("one_liner", "(no wire vision yet)"))
    elif "--store" in a:
        print(json.dumps(store(), indent=2))
    elif "--dry-run" in a:
        r = run(force=True, dry_run=True)
        print(f"fingerprint {r['fingerprint']} changed={r['changed']}\n")
        print(r["packet"])
    else:
        r = run(force="--force" in a)
        if r.get("text"):
            print(r["text"])
        else:
            print(json.dumps(r, indent=2))


if __name__ == "__main__":
    _cli()