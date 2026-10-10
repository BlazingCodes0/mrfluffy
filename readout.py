"""Mr.Fluffy readout engine.

Gathers news (news.py), builds a packet with a memory digest of past readouts and
docs/NEWS_THESIS.md, asks the text-only opencode brain (brain.py), parses the
structured JSON readout, renders it, and persists state/history/latest.

CLI:  python3 readout.py --now       # fetch + read + render (one full cycle)
      python3 readout.py --dry-run   # build packet + fingerprint, no brain, no write
      python3 readout.py --status    # budget + last readout state
      python3 readout.py --history   # last N history rows
      python3 readout.py --latest    # print the last rendered readout
"""
import fcntl, hashlib, json, sys, time
from pathlib import Path

import news
import brain

FLUFFY = Path.home() / "mrfluffy"
LOGS = FLUFFY / "logs"
STATE = LOGS / "news_state.json"
HISTORY = LOGS / "news_history.jsonl"
READOUTS = LOGS / "news_readouts.jsonl"
LATEST = LOGS / "news_readout_latest.json"
THESIS = FLUFFY / "docs" / "NEWS_THESIS.md"
LOCK = LOGS / "news_state.lock"
MEMORY_N = 4  # how many past readouts to feed back


def _fingerprint(ctx: dict) -> str:
    fg = ctx.get("fear_greed", {}).get("value")
    btc = (ctx.get("prices", {}).get("BTC", {}) or {}).get("usd")
    btc_bucket = round(btc / 100) if isinstance(btc, (int, float)) else "?"
    titles = "|".join(sorted(h.get("title", "")[:120] for h in ctx.get("headlines", [])))
    basis = f"{fg}|{btc_bucket}|{titles}"
    return hashlib.sha256(basis.encode("utf-8", "ignore")).hexdigest()[:16]


def _load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


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
    thesis = ""
    if THESIS.exists():
        thesis = THESIS.read_text().strip()[:1800]
    return "PAST READOUTS:\n" + ("\n".join(rows) if rows else "(none yet)") \
        + "\n\nCURRENT THESIS (docs/NEWS_THESIS.md):\n" + (thesis or "(none)")


SCHEMA = """Return exactly ONE raw JSON object (no prose, no markdown fence) with keys:
{
  "one_liner": str,            // one sentence: the single most important thing today
  "dots": [{"headline": str,   // cite by index range e.g. "1,3" or "9-11"
            "read": str}],
  "connect": str,              // how the dots connect into one story
  "rails": str,                // infrastructure/rails (exchanges, ETFs, settlement, custody)
  "privacy": str,              // privacy/custody pressure
  "freedom": str,              // state/enforcement/geopolitics pressure
  "what_changed": str,         // explicit diff vs the MEMORY you were given
  "watch": [str, ...],         // 3-6 specific things that would move the story next
  "headfake": str,             // the headline most likely to be theatre, and why
  "thesis_update": str,        // empty unless NEWS_THESIS.md truly shifts
  "confidence": float          // 0.0-1.0
}
You are Mr.Fluffy the reader. Do NOT run any tool, do NOT open or search for any
file: AGENTS.md, NEWS_THESIS.md and the past readouts are ALL fully inlined in this
prompt under MEMORY. Cite headlines only by their number above. Output the JSON
object as your first and only reply."""


def build_packet(ctx: dict) -> str:
    lines = [f"NOW: {ctx.get('ts')}", "CONTEXT: " + news.summary(ctx), "", "HEADLINES:"]
    for i, h in enumerate(ctx.get("headlines", []), 1):
        lines.append(f"{i}. [{h.get('source')}] {h.get('title')}")
    lines += ["", "MEMORY:", _memory(), "", SCHEMA]
    return "\n".join(lines)


def _parse(text: str) -> dict:
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                t = p
                break
    start, end = t.find("{"), t.rfind("}")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    return json.loads(t)


def render(ro: dict) -> str:
    out = [f"MR.FLUFFY READOUT — {time.strftime('%Y-%m-%d %H:%M', time.gmtime())}Z  (conf {ro.get('confidence')})",
           "=" * 66, "", ro.get("one_liner", "(no one-liner)"), ""]
    dots = ro.get("dots") or []
    if dots:
        out.append("— the dots —")
        for d in dots:
            out.append(f"  [{d.get('headline','?')}] {d.get('read','')}")
        out.append("")
    for key in ("connect", "rails", "privacy", "freedom", "what_changed"):
        if ro.get(key):
            out.append(f"— {key} —\n  {ro[key]}")
    if ro.get("watch"):
        out.append("— watch —")
        out += [f"  • {w}" for w in ro["watch"]]
    if ro.get("headfake"):
        out.append(f"— headfake —\n  {ro['headfake']}")
    if ro.get("thesis_update"):
        out.append(f"— thesis update —\n  {ro['thesis_update']}")
    return "\n".join(out)


def _write_state(fp, ctx, readout_ts=None, advance_fp=False):
    st = _load_json(STATE, {})
    if advance_fp:
        st["fingerprint"] = fp
    st["last_check_ts"] = time.time()
    st["headline_count"] = len(ctx.get("headlines", []))
    if readout_ts:
        st["last_readout_ts"] = readout_ts
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2))


def _persist(ctx: dict, fp: str, res: dict) -> dict:
    ro = res["readout"]
    entry = {"ts": time.time(), "fingerprint": fp,
             "headlines": [h.get("title") for h in ctx.get("headlines", [])],
             "readout": ro}
    READOUTS.parent.mkdir(parents=True, exist_ok=True)
    with READOUTS.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    LATEST.write_text(json.dumps(entry, indent=2))
    with HISTORY.open("a") as fh:
        fh.write(json.dumps({"ts": entry["ts"], "fingerprint": fp,
                             "confidence": ro.get("confidence"),
                             "one_liner": ro.get("one_liner"),
                             "what_changed": ro.get("what_changed")}) + "\n")
    return entry


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
    ctx = news.get(0 if force else 300)
    fp = _fingerprint(ctx)
    st = _load_json(STATE, {})
    changed = force or st.get("fingerprint") != fp
    if dry_run:
        return {"fingerprint": fp, "changed": changed, "packet": build_packet(ctx)}
    if not changed:
        _write_state(fp, ctx, advance_fp=True)
        return {"skipped": "no change", "fingerprint": fp}

    packet = build_packet(ctx)
    ans = brain.ask(packet)
    if ans.get("source") not in ("opencode", "http", "sandbox") or not ans.get("text"):
        _write_state(fp, ctx)  # record the check but don't advance fp -> retry
        return {"error": ans.get("error") or "no text", "fingerprint": fp}
    try:
        ro = _parse(ans["text"])
    except Exception as e:
        _write_state(fp, ctx)  # don't advance fp -> retry
        return {"error": f"parse failed: {e}", "fingerprint": fp, "raw": ans["text"][:400]}
    ro.setdefault("confidence", 0.0)
    entry = _persist(ctx, fp, {"readout": ro})
    _write_state(fp, ctx, readout_ts=entry["ts"], advance_fp=True)
    return {"ok": True, "fingerprint": fp, "entry": entry, "text": render(ro)}


def _cli():
    a = sys.argv[1:] or ["--now"]
    if "--status" in a:
        print(json.dumps({"budget": brain.status(), "state": _load_json(STATE, {})}, indent=2))
    elif "--history" in a:
        rows = []
        try:
            for line in HISTORY.read_text().splitlines()[-10:]:
                rows.append(json.loads(line))
        except Exception:
            pass
        print(json.dumps(rows, indent=2))
    elif "--latest" in a:
        print(_load_json(LATEST, {}).get("readout", {}).get("one_liner", "(no readout yet)"))
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