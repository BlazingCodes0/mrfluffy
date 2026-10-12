"""wiregate.py — BLACKHORSE, entered from the wire.

A gate on the wire floor leads into blackhorse's trading floor, rebuilt the same
honest way Wire Vision builds the LAN: it reads blackhorse's OWN local files and
nothing else — no exchange call, no brain call, no invented number.

  * the floor of the market  — your ACCOUNT (treasury + portfolio)
  * the platforms            — YOUR TRADING AGENTS only. Each platform is one
                               agent: WAITING TO BUY glows green, WAITING TO
                               SELL glows red, an exit is firing pulses brighter,
                               a disabled agent is a dim shell. Ground truth
                               comes from config/agents.json +
                               logs/portfolio.json + logs/exit_watch.json.
  * the crowd                — the OTHER USERS connected to the market (the
                               online layer). A tiny local relay shares poses
                               between mr.fluffy instances; nobody is invented,
                               and when nobody else is online the floor says so.
  * the menu                 — account balance + agent creation + editing your
                               agents' trading settings.

The online layer is guarded like a small fortress without pretending:
  * the GHOST layer  — when MRFLUFFY_WIRE_KEY is set, every pose and every
                       'who is here' answer is encrypted (a PBKDF2-derived key
                       driving an HMAC-SHA256 keystream) and signed (HMAC), so a
                       listener on the wire cannot read positions or names, and
                       nobody can forge someone else's pose without the key.
  * the WARD layer   — every client also carries a random ghost-id (a per-session
                       token) that binds to its name on first contact and must
                       match on every pose/leave, so you cannot pretend to be a
                       user who is already here. Bodies are size-capped,
                       per-IP request rates are throttled, the floor holds a
                       bounded number of users, and refused attempts are logged
                       to logs/.wiregate.events.log.

Writes ALWAYS take a backup of config/agents.json first, and the honesty block
names exactly what is real (your agents, your balance, live users) and what is
flavour (the floor, the columns, the crowd dressing).

CLI:  python3 wiregate.py            # the market snapshot as JSON
      python3 wiregate.py --summary  # a one-screen human read
      python3 wiregate.py --create --profile slow --capital 50 --name "Daruma"
      python3 wiregate.py --set agent_1 capital=40 enabled=true
      python3 wiregate.py --serve    # run the presence relay on its own

To run a hardened floor, set the same MRFLUFFY_WIRE_KEY on the relay and on each
player:  MRFLUFFY_WIRE_KEY="a phrase you all know" python3 wiregate.py --serve
"""
from __future__ import annotations
import base64, calendar, contextlib, fcntl, hashlib, hmac, json, math, os, secrets
import socket, struct, subprocess, sys, threading, time, urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import wiretls

FLUFFY = Path.home() / "mrfluffy"
BH = Path.home() / "blackhorse"
AGENTS_JSON = BH / "config" / "agents.json"
TREASURY_JSON = BH / "config" / "treasury.json"
TRADING_JSON = BH / "config" / "trading.json"
PORTFOLIO_JSON = BH / "logs" / "portfolio.json"
EXIT_WATCH_JSON = BH / "logs" / "exit_watch.json"
LOOP_STATE_JSON = BH / "logs" / "loop_state.json"
PROFILES_JSON = BH / "config" / "profiles.json"
# blackhorse's own decider defaults — the base layer its agents.policy_for()
# starts from before the profile's cfg and the agent's overrides are layered on.
DECIDER_JSON = BH / "config" / "decider.json"
# the SignalBot's own snapshots — the bot's read of each interval, written by
# blackhorse's signalbot.py (logs/signal_latest.json is the GUI/primary pair;
# logs/signals/<PAIR>.json is each pair's own lane set).
SIGNAL_LATEST_JSON = BH / "logs" / "signal_latest.json"
SIGNALS_DIR = BH / "logs" / "signals"

# the canonical SignalBot lanes, channel name -> the interval it carries
_CH_INTERVAL = {"ripple": "15m", "wave": "60m", "tide": "240m"}

MARKET_FLOOR_Y = -80.0        # the market is a place below the wire's strata ring
MARKET_R = 54.0
RETURN_GATE_POS = [0.0, MARKET_FLOOR_Y + 6.0, -52.0]

# the only settings the platform panels may touch, with (kind, lo, hi)
EDITABLE = {
    "entry_strength_max": ("num", 0.0, 1.0),
    "exit_strength_min": ("num", 0.0, 1.0),
    "min_reward_risk": ("num", 0.5, 10.0),
    "stop_max_pct": ("num", 0.1, 20.0),
    "risk_per_trade_pct": ("num", 0.1, 25.0),
    "max_position_pct": ("num", 1.0, 100.0),
    "require_tide_context": ("bool", 0, 1),
    "spot_only": ("bool", 0, 1),
}
PAIRS = ["DOT/USD", "ETH/USD", "BTC/USD", "SOL/USD", "XRP/USD"]

PROFILES = {}
# the decider defaults blackhorse layers the profile cfg on top of; so a panel
# can show the SAME effective value the blackhorse agent view shows.
PROFILE_DEFAULTS = {}

# ---- the ghost layer: signing of the online traffic --------------------------
# Secrecy is now real TLS (wiretls.py) — a pinned relay certificate — not a
# homemade weave. What remains here is authenticity: when MRFLUFFY_WIRE_KEY is
# set, every pose carries a small HMAC-SHA256 signature, so nobody without the
# phrase can speak on a sealed floor. (Legacy v1 shells — the old XOR weave — are
# still opened, so an un-updated player is refused, not confused.)

GHOST_KEY_ENV = "MRFLUFFY_WIRE_KEY"
GHOST_SALT = b"mrfluffy-wire-ghost-v1"
GHOST_ITERS = 200_000
GHOST_TAG = "ghost"

_WARD_EVENTS = FLUFFY / "logs" / ".wiregate.events.log"


def _ghost_key():
    """32 raw bytes from MRFLUFFY_WIRE_KEY, or None when the floor is open."""
    phrase = os.environ.get(GHOST_KEY_ENV, "")
    if not phrase:
        return None
    try:
        return hashlib.pbkdf2_hmac("sha256", phrase.encode("utf-8"),
                                   GHOST_SALT, GHOST_ITERS, dklen=32)
    except Exception:
        return None


def _ghost_xor(key: bytes, nonce: bytes, data: bytes) -> bytes:
    """Legacy v1 weave — kept only to open shells from an un-updated player."""
    out = bytearray()
    ctr = 0
    i = 0
    while i < len(data):
        block = hmac.new(key, nonce + struct.pack(">Q", ctr),
                         hashlib.sha256).digest()
        n = min(32, len(data) - i)
        out += bytes(data[i + j] ^ block[j] for j in range(n))
        i += n
        ctr += 1
    return bytes(out)


def _ghost_envelope(key: bytes, payload: dict) -> dict:
    """Sign a payload (v2): the plaintext rides inside TLS; the HMAC proves the key."""
    nonce = secrets.token_bytes(12)
    plain = json.dumps(payload).encode("utf-8")
    sig = hmac.new(key, nonce + plain, hashlib.sha256).hexdigest()
    return {"v": 2, GHOST_TAG: True,
            "n": base64.b64encode(nonce).decode("ascii"),
            "d": base64.b64encode(plain).decode("ascii"),
            "s": sig}


def _ghost_open(key: bytes, env: dict):
    """Open a signed shell (v2) or a legacy woven shell (v1). None when forged."""
    try:
        if not env or env.get(GHOST_TAG) is not True:
            return None
        nonce = base64.b64decode(env.get("n", ""))
        blob = base64.b64decode(env.get("d", ""))
        sig = env.get("s", "")
        if not nonce:
            return None
        if env.get("v") == 2:
            good = hmac.compare_digest(sig, hmac.new(key, nonce + blob,
                                                     hashlib.sha256).hexdigest())
            if not good:
                return None
            return json.loads(blob)
        ctext = blob
        good = hmac.compare_digest(sig, hmac.new(key, nonce + ctext,
                                                 hashlib.sha256).hexdigest())
        if not good:
            return None
        return json.loads(_ghost_xor(key, nonce, ctext))
    except Exception:
        return None


def _sec_event(msg: str) -> None:
    try:
        _WARD_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with open(_WARD_EVENTS, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
                    f"{msg}\n")
    except Exception:
        pass


def _load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _text(p: Path) -> bytes:
    try:
        return p.read_bytes()
    except Exception:
        return b""


def _ago(sec):
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


def _refresh_profiles() -> dict:
    """The personalities blackhorse ships with — fetched from blackhorse's OWN
    registry (trade/agents.py PROFILES) so we never hardcode a stale list."""
    global PROFILES, PROFILE_DEFAULTS
    env = dict(os.environ)
    code = ("import sys,json; sys.path.insert(0, %r); "
            "import agents; print(json.dumps(agents.PROFILES))" % str(BH / "trade"))
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, cwd=str(BH), env=env, timeout=30)
        PROFILES = json.loads(r.stdout or "{}")
    except Exception:
        PROFILES = PROFILES or {}
    # the decider defaults are the base the profile's cfg sits on: read them
    # straight from blackhorse's own config so a blank override shows the same
    # value blackhorse's agents.policy_for() would resolve.
    try:
        d = _load_json(DECIDER_JSON, {})
        PROFILE_DEFAULTS = d if isinstance(d, dict) else {}
    except Exception:
        PROFILE_DEFAULTS = PROFILE_DEFAULTS or {}
    return PROFILES


def _fingerprint(*pairs) -> str:
    h = hashlib.sha256()
    for name, data in pairs:
        h.update(name.encode())
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return h.hexdigest()[:16]


def _layout(n: int) -> list:
    """Deterministic floating-platform positions around the floor of the market."""
    out = []
    for i in range(n):
        a = -math.pi / 2 + (2 * math.pi * i / n if n else 0.0)
        r = 30.0 if n > 1 else 0.0
        x = round(r * math.cos(a), 3)
        z = round(r * math.sin(a), 3)
        y = round(MARKET_FLOOR_Y + 8.0 + 3.0 * (i % 4), 3)
        out.append([x, y, z])
    return out


def _derive(agent: dict, positions: list, exit_watch: dict) -> dict:
    """Real state from real files:
       off      — the agent is disabled
       buy      — enabled and FLAT: it is waiting to buy
       sell     — enabled and IN POSITION: it is waiting to sell
       selling  — an exit is actually firing (exit_watch action == SELL)"""
    if not agent.get("enabled"):
        return "off"
    mine = [p for p in positions if p.get("agent") == agent.get("id")]
    if not mine:
        return "buy"
    if any((exit_watch.get("positions") or {}).get(p.get("id"), {})
           .get("action") == "SELL" for p in mine):
        return "selling"
    return "sell"


# ---- the SignalBot read, attached to each platform --------------------------
# The platform an agent stands on is tied to an interval (its strategy_intervals,
# else the interval its channels carry). We show that interval's SignalBot read
# exactly as the "Run SignalBot now" pane does — including the small-timeframe
# rule where a 15m-or-smaller lane gates its entry/exit on the 60m lane's own
# strength. Everything is read from the bot's own written snapshot; nothing here
# runs the bot, calls the exchange, or invents a number.

def _num(v, dp=4):
    """compact number print — '?' for missing (mirrors blackhorse's app _n)."""
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return "?" if v is None else str(v)


def _sig_ago(ts) -> str:
    try:
        ep = calendar.timegm(time.strptime(str(ts), "%Y-%m-%dT%H:%M:%SZ"))
        return _ago(time.time() - ep)
    except Exception:
        return "unknown"


def _iv_min(iv):
    """'15m' -> 15; None when the label is not '<n>m'."""
    try:
        s = str(iv or "")
        return int(s.rstrip("m")) if s.endswith("m") else None
    except (TypeError, ValueError):
        return None


def _agent_intervals(a: dict) -> list:
    """The intervals an agent is tied to: its strategy_intervals, else the
    intervals its channels carry, else the small lane the loop actually runs."""
    ov = a.get("policy_overrides") or {}
    ivs = ov.get("strategy_intervals")
    if isinstance(ivs, list) and ivs:
        return [str(x) for x in ivs]
    chs = ov.get("channels")
    if isinstance(chs, list) and chs:
        got = [_CH_INTERVAL[c] for c in chs if c in _CH_INTERVAL]
        if got:
            return got
    return ["15m"]


def _pick_channel(chans: dict, iv: str, prefer: list):
    """The channel carrying interval `iv`, preferring the agent's own channels."""
    cands = [(n, c) for n, c in chans.items() if str(c.get("interval")) == iv]
    if not cands:
        return None, None
    for want in prefer:
        for n, c in cands:
            if n == want:
                return n, c
    for canon in _CH_INTERVAL:
        for n, c in cands:
            if n == canon:
                return n, c
    return cands[0]


def _signal_lean(c: dict) -> dict:
    """The direction the SignalBot's own fields point, as a single lean.

    Not a promise and not an order — a transparent vote over the bot's named
    readouts (trend, strength direction, MA-cross bias, range signal, advisor
    band, buy/sell score). The basis names the fields that carried it."""
    mr = c.get("marketResult") or {}
    votes = []
    ts_ = str(mr.get("trendState") or "").lower()
    if ts_ in ("up", "bull", "rising"):
        votes.append(("trend " + ts_, 1.0))
    elif ts_ in ("down", "bear", "falling"):
        votes.append(("trend " + ts_, -1.0))
    sd = str(c.get("strengthDirection") or "").lower()
    if sd == "rising":
        votes.append(("strength rising", 1.0))
    elif sd == "falling":
        votes.append(("strength falling", -1.0))
    mx = c.get("maCross") or {}
    if mx.get("available"):
        v = str(mx.get("verdict") or "")
        w = 1.0 if v.startswith("real") else (0.5 if v.startswith("borderline") else 0.0)
        if mx.get("bias") == "bullish":
            votes.append(("MA-cross bullish", w))
        elif mx.get("bias") == "bearish":
            votes.append(("MA-cross bearish", -w))
    rs = str(c.get("rangeSignal") or "").upper()
    if rs == "BUY":
        votes.append(("range BUY", 0.5))
    elif rs == "SELL":
        votes.append(("range SELL", -0.5))
    adv = c.get("advisor") or {}
    price = c.get("currPrice")
    if price not in (None, "", 0) and adv.get("buy") and adv.get("sell"):
        try:
            if float(price) <= float(adv["buy"]):
                votes.append(("at buy band", 0.5))
            elif float(price) >= float(adv["sell"]):
                votes.append(("at sell band", -0.5))
        except (TypeError, ValueError):
            pass
    try:
        bs, ss = float(c.get("buyScore") or 0), float(c.get("sellScore") or 0)
        if bs - ss >= 0.4:
            votes.append(("buyScore dominant", 0.5))
        elif ss - bs >= 0.4:
            votes.append(("sellScore dominant", -0.5))
    except (TypeError, ValueError):
        pass
    score = round(sum(w for _, w in votes), 2)
    if score >= 0.75:
        d = "up"
    elif score <= -0.75:
        d = "down"
    else:
        d = "flat"
    votes.sort(key=lambda kv: -abs(kv[1]))
    basis = ", ".join(n for n, _ in votes[:3]) or "no directional field"
    return {"dir": d, "score": score, "basis": basis}


def _signal_lines(c: dict, name: str) -> list:
    """The 'Run SignalBot now' block for one interval, from the snapshot fields."""
    mr = c.get("marketResult") or {}
    r = c.get("RSI") or {}
    adv = c.get("advisor") or {}
    iv = c.get("interval")
    is15 = str(iv) == "15m"
    lines = [f"{name:8s} {str(iv or '?'):>5}  {c.get('action', '?'):5s} "
             f"conf={c.get('confidence')}  "
             f"strength={round(c.get('strength') or 0, 3)} ({c.get('strengthDirection')})"]
    gate = c.get("strengthGate60")
    if gate:
        lines.append(f"    trend={mr.get('trendState')} RSI={r.get('currentRSI')} · "
                     f"entry eligible={c.get('entryEligible')}→60m:{c.get('entryEligible60')} · "
                     f"exit eligible={c.get('exitEligible')}→60m:{c.get('exitEligible60')}")
        lines.append(f"    60m strength gate (small-tf rule): {gate.get('note')}")
    else:
        lines.append(f"    trend={mr.get('trendState')} RSI={r.get('currentRSI')} · "
                     f"entry eligible={c.get('entryEligible')} · "
                     f"exit eligible={c.get('exitEligible')}")
    sv = mr.get("spreadVerdict")
    if is15 and sv:
        lines.append(f"    SPREAD latest={_num(mr.get('latestSpread'))} "
                     f"(was {_num(mr.get('intialSpread'))}) · verdict {sv.get('verdict')} · "
                     f"bias {sv.get('directionBias')} chop {sv.get('chopLevel')} "
                     f"str {sv.get('strength')} ({sv.get('bars')} bars)")
    elif mr.get("spreadChange") is not None:
        lines.append(f"    SPREAD latest={_num(mr.get('latestSpread'))} "
                     f"(was {_num(mr.get('intialSpread'))}) · change "
                     f"{mr.get('spreadChange'):+.4f} / {mr.get('spreadCount')} bars")
    sm = c.get("spreadMA") or {}
    if sm.get("available"):
        lines.append(f"    MA10−MA30 diff={sm.get('diff'):+.4f} "
                     f"({sm.get('diffPct'):+.3f}%) · {sm.get('signal')}")
    if is15:
        lines.append(f"    scenario: {c.get('setupScenario')}")
        bw = c.get("bottomWatch") or {}
        if bw.get("armed"):
            lines.append(f"    bottom-watch: ARMED · price {_num(bw.get('price'))} "
                         f"vs low {_num(bw.get('low'))} · strength {_num(bw.get('strength'), 2)}")
        else:
            lines.append(f"    bottom-watch: off (strength {_num(bw.get('strength'), 2)} "
                         f"≥ 0.15 or price off floor)")
    mx = c.get("maCross") or {}
    if is15 and mx.get("verdict"):
        lines.append(f"    macross MA20={_num(mx.get('ma20'))} MA50={_num(mx.get('ma50'))} · "
                     f"{mx.get('verdict')} · cross {mx.get('cross')}")
    else:
        lines.append(f"    macross MA20={_num(mx.get('ma20'))} MA50={_num(mx.get('ma50'))} · "
                     f"{mx.get('bias')} · cross {mx.get('cross')}")
    lines.append(f"    range={c.get('rangeSignal')} bias={c.get('rangeBias')} · "
                 f"stop {_num(mr.get('stopLoss'))} target {_num(mr.get('takeProfit'))}")
    lines.append(f"    advisor buy {adv.get('buy')} sell {adv.get('sell')}")
    return lines


def _load_signals() -> dict:
    latest = _load_json(SIGNAL_LATEST_JSON, {})
    return {"latest": latest if isinstance(latest, dict) else {}}


def _signal_for_pair(pair, sig: dict) -> dict:
    """The pair's own lane set when it exists, else the primary (latest) one."""
    latest = sig.get("latest") or {}
    if pair:
        key = str(pair).replace("/", "-").upper()
        d = _load_json(SIGNALS_DIR / f"{key}.json", None)
        if isinstance(d, dict) and d.get("available") and d.get("channels"):
            return d
        if latest.get("available") and \
                str(latest.get("pair") or "").upper() == str(pair).upper():
            return latest
    return latest if latest.get("available") else {}


def _agent_signal(a: dict, sig: dict) -> dict:
    """The SignalBot read for the interval(s) this agent's platform is tied to."""
    pair = (a.get("pairs") or [None])[0]
    snap = _signal_for_pair(pair, sig)
    if not snap or not snap.get("channels"):
        return {"available": False,
                "reason": "no SignalBot snapshot on file for this pair yet"}
    chans = snap["channels"]
    ov = a.get("policy_overrides") or {}
    prefer = ov.get("channels") if isinstance(ov.get("channels"), list) else []
    reads = []
    for iv in _agent_intervals(a):
        name, c = _pick_channel(chans, iv, prefer)
        if not c:
            continue
        reads.append({
            "interval": iv, "channel": name,
            "action": c.get("action"), "confidence": c.get("confidence"),
            "strength": c.get("strength"),
            "strength_direction": c.get("strengthDirection"),
            "range_signal": c.get("rangeSignal"),
            "entry_eligible": c.get("entryEligible"),
            "entry_eligible60": c.get("entryEligible60"),
            "exit_eligible": c.get("exitEligible"),
            "exit_eligible60": c.get("exitEligible60"),
            "gate": c.get("strengthGate60"),
            "lean": _signal_lean(c),
            "lines": _signal_lines(c, name),
        })
    if not reads:
        return {"available": False,
                "reason": "the agent's interval is not in the SignalBot snapshot"}
    # primary = the smallest interval — the entry / timing lane the arrow speaks for
    reads.sort(key=lambda r: (_iv_min(r["interval"]) if _iv_min(r["interval"]) is not None
                              else 9e9, r["interval"]))
    primary = reads[0]
    lean = primary["lean"]
    gate = primary.get("gate") or {}
    block = ""
    if gate:
        if lean["dir"] == "up" and not gate.get("buy_allowed", True):
            block = " · entry blocked by the 60m gate"
        elif lean["dir"] == "down" and not gate.get("sell_allowed", True):
            block = " · exit blocked by the 60m gate"
    summary = (f"{primary['interval']} {primary.get('action', '?')} "
               f"conf={primary.get('confidence')} str={round(primary.get('strength') or 0, 3)} "
               f"{primary.get('strength_direction')} · LEAN {lean['dir'].upper()}{block}")
    return {
        "available": True, "pair": snap.get("pair"), "exchange": snap.get("exchange"),
        "strategy": snap.get("strategy"), "ts": snap.get("ts"), "age": _sig_ago(snap.get("ts")),
        "intervals": [r["interval"] for r in reads],
        "primary_interval": primary["interval"],
        "lean": lean, "summary": summary, "reads": reads,
    }


def snapshot() -> dict:
    """The market as a place: account + your platforms, from blackhorse's files."""
    agents_doc = _load_json(AGENTS_JSON, {})
    agents_all = agents_doc.get("agents", {})
    treasury = _load_json(TREASURY_JSON, {})
    trading = _load_json(TRADING_JSON, {})
    portfolio = _load_json(PORTFOLIO_JSON, {})
    exit_watch = _load_json(EXIT_WATCH_JSON, {})
    loop_state = _load_json(LOOP_STATE_JSON, {})
    live = str(trading.get("mode", "")).upper() == "LIVE"
    profs = _refresh_profiles()
    sig = _load_signals()

    positions = portfolio.get("positions", [])
    n = len(agents_all)
    layout = _layout(n)
    agents = []
    for i, (aid, a) in enumerate(sorted(agents_all.items(),
                                        key=lambda kv: kv[0])):
        state = _derive(a, positions, exit_watch)
        mine = [p for p in positions if p.get("agent") == aid]
        pos_rows = []
        for p in mine:
            ew = (exit_watch.get("positions") or {}).get(p.get("id"), {})
            net = ew.get("net_pct_if_sold_at_bid")
            if net is None:
                mark = p.get("mark")
                entry = p.get("entry")
                net = None if not (mark and entry) else (float(mark) / float(entry) - 1) * 100
            pos_rows.append({
                "id": p.get("id"), "pair": p.get("pair"), "side": p.get("side"),
                "qty": p.get("qty"), "entry": p.get("entry"), "mark": p.get("mark"),
                "net_pct": round(net, 2) if net is not None else None,
                "exit": (ew or {}).get("action", ""),
                "mode": p.get("mode") or "?",
            })
        nets = [p["net_pct"] for p in pos_rows if p.get("net_pct") is not None]
        prof = profs.get(a.get("profile")) or {}
        agents.append({
            "id": aid, "name": a.get("name") or aid, "kind": a.get("kind"),
            "profile": a.get("profile"), "profile_label": prof.get("label") or a.get("profile"),
            "enabled": a.get("enabled"), "capital": a.get("capital"), "mode": a.get("mode"),
            "pairs": a.get("pairs") or [], "created": a.get("created"),
            "state": state, "position_count": len(mine),
            "net_pct": round(sum(nets) / len(nets), 2) if nets else None,
            "positions": pos_rows,
            "signal": _agent_signal(a, sig),
            "pos": [layout[i][0], layout[i][1], layout[i][2]],
            "radius": 4.2,
        })

    wins = portfolio.get("wins")
    losses = portfolio.get("closed") - portfolio.get("wins", 0) \
        if wins is not None and portfolio.get("closed") is not None else None
    holdings = treasury.get("holdings") or {}
    cash = float(treasury.get("cash", 0.0) or 0.0)
    allocated = float(treasury.get("allocated", 0.0) or 0.0)
    account = {
        "currency": treasury.get("currency") or "USD",
        "cash": round(cash, 2),
        "allocated": round(allocated, 2),
        "equity_est": round(cash + allocated, 2),
        "reserve_floor": treasury.get("reserve_floor"),
        "holdings": {k: round(v, 6) for k, v in holdings.items()},
        "realized_pnl": portfolio.get("realized_pnl"),
        "fees_paid": portfolio.get("fees_paid"),
        "closed": portfolio.get("closed"),
        "wins": wins,
        "losses": losses,
        "open_positions": len(positions),
        "mode": trading.get("mode") or "?",
        "autonomous": trading.get("autonomous"),
        "live": live,
        "updated": treasury.get("updated") or "",
    }

    loop = {
        "heartbeat": loop_state.get("heartbeat"),
        "decision": loop_state.get("decision"),
        "reason": loop_state.get("reason"),
        "ts": loop_state.get("ts"),
        "per_pair": loop_state.get("per_pair") or {},
    }

    inputs = [
        ("agents.json", _text(AGENTS_JSON)),
        ("treasury.json", _text(TREASURY_JSON)),
        ("trading.json", _text(TRADING_JSON)),
        ("portfolio.json", _text(PORTFOLIO_JSON)),
        ("exit_watch.json", _text(EXIT_WATCH_JSON)),
        ("loop_state.json", _text(LOOP_STATE_JSON)),
        ("signal_latest.json", _text(SIGNAL_LATEST_JSON)),
    ]
    fp = _fingerprint(*inputs)

    return {
        "generated": time.time(),
        "fingerprint": fp,
        "live": live,
        "mode": trading.get("mode"),
        "floor_y": MARKET_FLOOR_Y,
        "radius": MARKET_R,
        "return_gate": RETURN_GATE_POS,
        "account": account,
        "loop": loop,
        "agents": agents,
        "profiles": {k: {"label": v.get("label"), "description": v.get("description")}
                     for k, v in profs.items()},
        "editable": EDITABLE,
        "pairs": PAIRS,
        "sources": _sources(),
        "honesty": _honesty(),
    }


def _sources() -> list:
    """The blackhorse files this market is built from, and how fresh each one is."""
    now = time.time()
    feeds = [
        ("agents \u00b7 the bodies", AGENTS_JSON,
         "blackhorse GUI \u2014 create / edit / enable agents"),
        ("treasury \u00b7 the wallet", TREASURY_JSON,
         "the night loop rebalances"),
        ("portfolio \u00b7 open positions", PORTFOLIO_JSON,
         "the loop writes it each pass"),
        ("exit_watch \u00b7 exits", EXIT_WATCH_JSON,
         "the exit manager watches it"),
        ("loop_state \u00b7 the heartbeat", LOOP_STATE_JSON,
         "the loop writes it each pass"),
        ("signal \u00b7 the bot's read", SIGNAL_LATEST_JSON,
         "run SignalBot in the blackhorse GUI, or let the loop run a pass"),
    ]
    out = []
    for name, p, hint in feeds:
        exists = p.exists()
        age = None
        if exists:
            try:
                age = now - p.stat().st_mtime
            except Exception:
                age = None
        out.append({"name": name, "path": str(p), "exists": exists,
                    "age": _ago(age),
                    "age_s": None if age is None else int(age),
                    "stale": (age is None) or age > 21600, "hint": hint})
    return out


def _honesty() -> dict:
    return {
        "real": [
            "your agents from config/agents.json (enabled, capital, mode, profile)",
            "open positions from logs/portfolio.json and logs/exit_watch.json",
            "your balance from config/treasury.json (cash, allocated, holdings)",
            "the loop's own heartbeat and decision from logs/loop_state.json",
            "each platform's interval read (action, strength, RSI, spread, MA cross, "
            "and the 60m strength gate) from the SignalBot's own snapshot",
            "other users' characters, relayed live by the presence server",
        ],
        "feels": [
            "the market floor, the columns and the platforms are dressing",
            "green / red / amber are a read of the files above, not a source",
            "the up/down arrow is the SignalBot's LEAN over its own named fields "
            "\u2014 not a promise and not an order",
            "the crowd is the relay's users; nobody is invented",
        ],
        "note": ("This floor is a MEMORY model of blackhorse's own files, like the wire. "
                 "It never calls the exchange and never trades. When the loop writes next, "
                 "you may 'rebuild the market' (B) to feel it again."),
    }


# ---- gated writes: a backup first, then a single atomic rewrite -------------

def _write_lock():
    LOGS = FLUFFY / "logs"
    LOGS.mkdir(parents=True, exist_ok=True)
    return str(LOGS / ".wiregate.write.lock")


def _locked():
    @contextlib.contextmanager
    def _cm():
        fh = open(_write_lock(), "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
            fh.close()
    return _cm()


def backup_agents() -> str:
    """Copy config/agents.json beside itself before any change is kept."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = AGENTS_JSON.with_name(f"agents.json.bak.{stamp}")
    if AGENTS_JSON.exists():
        dst.write_bytes(_text(AGENTS_JSON))
    return str(dst)


def _norm_override(key: str, value):
    if key not in EDITABLE:
        raise ValueError(f"'{key}' is not an editable setting")
    kind, lo, hi = EDITABLE[key]
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).lower() in ("1", "true", "yes", "on")
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{key}' must be a number")
    if not (lo <= v <= hi):
        raise ValueError(f"'{key}' must be between {lo} and {hi}")
    return v


def apply_settings(agent_id: str, *,
                   enabled=None, capital=None, profile=None, pairs=None,
                   overrides=None) -> dict:
    """Edit one agent's trading settings. Always backs up agents.json first."""
    if not AGENTS_JSON.exists():
        return {"ok": False, "error": f"no blackhorse config/agents.json at {AGENTS_JSON}"}
    with _locked():
        doc = _load_json(AGENTS_JSON, {"agents": {}})
        a = doc.get("agents", {}).get(agent_id)
        if not a:
            return {"ok": False, "error": f"unknown agent {agent_id}"}
        _refresh_profiles()
        if capital is not None:
            cap = float(capital)
            if cap < 0:
                return {"ok": False, "error": "capital cannot be negative"}
            a["capital"] = cap
            if cap == 0:
                a["enabled"] = False
        if enabled is not None:
            a["enabled"] = bool(enabled)
            if not a["enabled"]:
                a["enabled"] = False
        if profile is not None:
            if profile not in PROFILES:
                return {"ok": False, "error": f"unknown profile '{profile}'"}
            a["profile"] = profile
            a["policy_overrides"] = {}
        if pairs is not None:
            pairs = [p for p in (pairs or []) if isinstance(p, str) and p]
            if not pairs:
                return {"ok": False, "error": "at least one pair is required"}
            a["pairs"] = pairs
        if overrides:
            overrides = dict(overrides)
            if "channels" in overrides and isinstance(overrides["channels"], list):
                ov = a.setdefault("policy_overrides", {})
                ov["channels"] = [c for c in overrides["channels"]
                                  if isinstance(c, str) and c]
                for k in (k for k in overrides if k != "channels"):
                    ov[k] = _norm_override(k, overrides[k])
            else:
                for k, v in (overrides or {}).items():
                    a.setdefault("policy_overrides", {})[k] = _norm_override(k, v)
        doc["agents"][agent_id] = a
        try:
            backup_agents()
            AGENTS_JSON.write_text(json.dumps(doc, indent=2) + "\n")
        except Exception as e:
            return {"ok": False, "error": f"write failed: {e}"}
    return {"ok": True, "agent": agent_id, "name": a.get("name"),
            "capital": a.get("capital"), "enabled": a.get("enabled"),
            "profile": a.get("profile")}


def create_agent(profile: str, capital: float, name: str = "",
                 pairs=None, allow_over: bool = False) -> dict:
    """Create a NEW trading agent (capacity checked against the treasury)."""
    if not AGENTS_JSON.exists():
        return {"ok": False, "error": f"no blackhorse config/agents.json at {AGENTS_JSON}"}
    with _locked():
        _refresh_profiles()
        if profile not in PROFILES:
            return {"ok": False, "error": f"unknown profile '{profile}'"}
        cap = float(capital)
        if cap < 0:
            return {"ok": False, "error": "capital cannot be negative"}
        doc = _load_json(AGENTS_JSON, {"agents": {}, "next_id": 1})
        agents_all = doc.setdefault("agents", {})
        treasury = _load_json(TREASURY_JSON, {})
        cash = float(treasury.get("cash", 0.0) or 0.0)
        would = sum(float(a.get("capital", 0)) for a in agents_all.values()
                    if a.get("kind") == "trading") + cap
        if not allow_over and would > cash + 1e-9:
            return {"ok": False,
                    "error": f"over-allocation: agents would claim {would:.2f} "
                             f"{treasury.get('currency', 'USD')} but the treasury "
                             f"only has {cash:.2f} cash free"}
        n = int(doc.get("next_id", 1))
        aid = f"agent_{n}"
        doc["next_id"] = n + 1
        prof_label = (PROFILES.get(profile, {}).get("label") or profile)
        agents_all[aid] = {
            "id": aid, "name": name or prof_label.split("/")[0].split(" ")[0] + f" {n}",
            "kind": "trading", "profile": profile, "enabled": False,
            "capital": cap, "mode": "LIVE", "policy_overrides": {},
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pairs": [p for p in (pairs or ["DOT/USD"]) if p in PAIRS] or ["DOT/USD"],
        }
        try:
            backup_agents()
            AGENTS_JSON.write_text(json.dumps(doc, indent=2) + "\n")
        except Exception as e:
            return {"ok": False, "error": f"write failed: {e}"}
    return {"ok": True, "agent": aid, "name": agents_all[aid]["name"],
            "profile": profile, "capital": cap, "enabled": False}


# ---- the online layer: a tiny local relay for characters -------------------

class Presence:
    """A minimal presence relay: mr.fluffy instances announce their pose in the
    market and see who else is on the floor. No room, no auth, no web — just
    (name -> xyz) with a leash so a dropped client walks out of the crowd."""

    def __init__(self, addr=("127.0.0.1", 17833), base_url=None, user=None):
        self.addr = addr
        self.tls = wiretls.enabled()
        if base_url:
            self._base = base_url.rstrip("/")
        else:
            scheme = "https" if self.tls else "http"
            self._base = f"{scheme}://127.0.0.1:{addr[1]}"
        self.user = (user or os.environ.get("MRFLUFFY_WIRE_USER")
                     or socket.gethostname() or "wire").replace(" ", "_")
        self.key = _ghost_key()
        self.ghost = self.key is not None
        self.tok = secrets.token_hex(16)      # our random ghost-id for this session
        self.ward = 0                         # times the relay's ward turned us away
        self._server_ctx = wiretls.server_context() if self.tls else None
        self._cli_ctx, self._tls_info = (
            wiretls.client_context() if self._base.startswith("https") else (None, {}))
        self._peers: dict = {}
        self._tok: dict = {}                  # name -> bound ghost-id
        self._rate: dict = {}                 # ip -> (window, count)
        self._burst: dict = {}                # name -> (window, count)
        self._lock = threading.Lock()
        self._server = None
        self._thread = None
        self.started = False
        self._online = None

    def _urlopen(self, target, timeout=1.0):
        """urlopen on our pinned TLS context when the relay is https."""
        if self._cli_ctx is not None:
            return urllib.request.urlopen(target, timeout=timeout,
                                          context=self._cli_ctx)
        return urllib.request.urlopen(target, timeout=timeout)

    def start(self) -> None:
        if self.started:
            return
        try:
            srv = _PresenceServer(self.addr, _Handler)
            srv.presence = self
            srv.ssl_ctx = self._server_ctx
            if srv.ssl_ctx is not None:
                srv.socket = srv.ssl_ctx.wrap_socket(srv.socket, server_side=True)
            self._server = srv
            self._thread = threading.Thread(target=srv.serve_forever, daemon=True)
            self._thread.start()
            self.started = True
        except OSError:
            self.started = False

    def stop(self) -> None:
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
        self.started = False

    def _expire(self):
        now = time.time()
        dead = [k for k, v in self._peers.items() if now - v["t"] > 12.0]
        for k in dead:
            self._peers.pop(k, None)

    def _upsert(self, name: str, pose: dict) -> None:
        with self._lock:
            self._expire()
            self._peers[name] = {"x": pose.get("x", 0.0), "y": pose.get("y", 0.0),
                                 "z": pose.get("z", 0.0), "t": time.time()}

    def _drop(self, name: str) -> None:
        with self._lock:
            self._peers.pop(name, None)

    def _snapshot(self) -> list:
        with self._lock:
            self._expire()
            now = time.time()
            return [{"name": k, "x": v["x"], "y": v["y"], "z": v["z"]}
                    for k, v in self._peers.items() if k != self.user]

    def online(self) -> bool:
        """True if we last announced successfully (solo floor is still honest)."""
        return bool(self._online)

    def _ping(self) -> bool:
        try:
            with self._urlopen(self._base + "/ping", timeout=1.0):
                pass
            return True
        except Exception:
            return False

    def _seal(self, payload: dict) -> bytes:
        """Envelope a payload when the ghost layer is on, else plain JSON."""
        body = _ghost_envelope(self.key, payload) if self.key else payload
        return json.dumps(body).encode()

    def _unwrap(self, doc: dict):
        if not doc:
            return {}
        if doc.get(GHOST_TAG) is True:
            return _ghost_open(self.key, doc) if self.key else None
        return doc if not self.key else None

    def announce(self, pose: dict) -> bool:
        """POST our sealed pose to the relay; False when the relay refuses us."""
        try:
            self._online = False
            req = urllib.request.Request(
                self._base + "/pose", method="POST",
                data=self._seal({"name": self.user, "tok": self.tok,
                                 "pose": pose}),
                headers={"Content-Type": "application/json"})
            with self._urlopen(req, timeout=1.0) as r:
                got = json.loads(r.read() or b"{}")
                self.ward = int(got.get("ward", 0) or 0)
            self._online = True
            return True
        except Exception:
            self._online = False
            return False

    def leave(self) -> None:
        try:
            req = urllib.request.Request(
                self._base + "/leave", method="POST",
                data=self._seal({"name": self.user, "tok": self.tok}),
                headers={"Content-Type": "application/json"})
            with self._urlopen(req, timeout=1.0):
                pass
        except Exception:
            pass

    def peers(self) -> list:
        """Other users' characters in the market, pulled from the relay."""
        try:
            with self._urlopen(self._base + "/peers", timeout=1.0) as r:
                doc = json.loads(r.read() or b"{}")
            data = self._unwrap(doc)
            if data is None:
                return []
            return [p for p in data.get("peers", [])
                    if p.get("name") and p.get("name") != self.user]
        except Exception:
            return []

    def describe(self) -> str:
        if self.tls and self._server_ctx is not None:
            line = wiretls.describe()
        elif self.tls:
            line = "tls: wanted \u00b7 cert could not be built (openssl/cryptography missing)"
        else:
            line = "tls: off \u00b7 plain HTTP floor"
        if self.key:
            line += " \u00b7 ghost: signed (shared key)"
        elif self.tls:
            line += " \u00b7 ghost: open (traffic still sealed by TLS)"
        else:
            line += (" \u00b7 ghost: open \u00b7 set MRFLUFFY_WIRE_KEY on the relay "
                     "and every player to sign the floor")
        return line + f" \u00b7 ward refused {self.ward} attempt(s)"


class _PresenceServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that keeps a TLS context and swallows handshake noise."""
    daemon_threads = True
    allow_reuse_address = True
    ssl_ctx = None

    def handle_error(self, request, client_address):
        # a bad handshake or a rude client is not the relay's problem — ignore it
        pass


RATE_WINDOW = 10.0        # seconds
RATE_MAX = 200            # requests per window per IP
BURST_MAX = 40            # poses per window per name
MAX_POSE_BYTES = 4096     # reject oversized shells
MAX_PEERS = 64            # the floor holds a bounded crowd

class _Handler(BaseHTTPRequestHandler):
    def setup(self):
        """The server's listening socket is wrapped for TLS; do not re-wrap."""
        super().setup()

    def log_message(self, *a):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ward(self, pr) -> bool:
        """Ward off clients that are hammering the floor. True = allow."""
        ip = (self.client_address[0] if self.client_address else "?")
        now = time.time()
        with pr._lock:
            w0, cnt = pr._rate.get(ip, (now, 0))
            if now - w0 > RATE_WINDOW:
                w0, cnt = now, 0
            cnt += 1
            pr._rate[ip] = (w0, cnt)
            if cnt > RATE_MAX:
                pr.ward += 1
                _sec_event(f"rate-refused ip={ip}")
                return False
        return True

    def _read_body(self):
        """Read a body, refusing anything oversized (ward) or malformed."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if n <= 0 or n > MAX_POSE_BYTES:
            return None
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return None

    def _open_body(self, pr, body):
        """Decode a sealed (ghost) or open body, in the mode the relay runs."""
        if pr.key:
            got = _ghost_open(pr.key, body)
            if got is None:
                pr.ward += 1
                _sec_event("sealed-shell refused (bad key / forged signature)")
                return None, "sealed-shell refused"
            return got, None
        if body and body.get(GHOST_TAG) is True:
            pr.ward += 1
            _sec_event("shell refused \u2014 relay is open, sender sealed")
            return None, "unexpected sealed shell"
        return body or {}, None

    def do_GET(self):
        pr = getattr(self.server, "presence", None)
        if pr is None:
            return self._json(500, {"ok": False})
        if not self._ward(pr):
            return self._json(429, {"ok": False, "error": "ward refuses"})
        if self.path == "/ping":
            return self._json(200, {"ok": True, "users": len(pr._peers),
                                    "you": pr.user, "ghost": pr.ghost,
                                    "ward": pr.ward})
        if self.path == "/peers":
            data = {"peers": pr._snapshot(), "ghost": pr.ghost}
            body = _ghost_envelope(pr.key, data) if pr.key else data
            return self._json(200, body)
        return self._json(404, {"ok": False})

    def do_POST(self):
        pr = getattr(self.server, "presence", None)
        if pr is None:
            return self._json(500, {"ok": False})
        if not self._ward(pr):
            return self._json(429, {"ok": False, "error": "ward refuses"})
        raw = self._read_body()
        if raw is None:
            return self._json(413, {"ok": False, "error": "shell too large"})
        content, err = self._open_body(pr, raw)
        if content is None:
            return self._json(401, {"ok": False, "error": err})
        name = str(content.get("name") or "wire")[:48]
        tok = str(content.get("tok") or "")[:128]
        if not tok:
            return self._json(401, {"ok": False, "error": "ghost-id required"})
        with pr._lock:
            bound = pr._tok.get(name)
            if bound is None:
                pr._tok[name] = tok
            elif not hmac.compare_digest(bound, tok):
                pr.ward += 1
                _sec_event(f"ghost-id refused name={name}")
                return self._json(403, {"ok": False,
                                        "error": "ghost-id already bound"})
            now = time.time()
            w0, cnt = pr._burst.get(name, (now, 0))
            if now - w0 > RATE_WINDOW:
                w0, cnt = now, 0
            pr._burst[name] = (w0, cnt + 1)
            tooburst = cnt + 1 > BURST_MAX
        if tooburst:
            pr.ward += 1
            _sec_event(f"burst-refused name={name}")
            return self._json(429, {"ok": False, "error": "ward refuses"})
        if self.path == "/pose":
            if name not in pr._peers and len(pr._peers) >= MAX_PEERS:
                pr.ward += 1
                _sec_event(f"floor-full refused name={name}")
                return self._json(429, {"ok": False, "error": "floor is full"})
            pr._upsert(name, content.get("pose") or {})
            return self._json(200, {"ok": True, "ward": pr.ward})
        if self.path == "/leave":
            pr._drop(name)
            return self._json(200, {"ok": True, "ward": pr.ward})
        return self._json(404, {"ok": False})


def summary(w: dict) -> str:
    acc = w["account"]
    loop = w["loop"]
    lines = [
        "WIREGATE — BLACKHORSE, entered from the wire",
        "=" * 56,
        f"fingerprint {w['fingerprint']}  ·  built "
        f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(w['generated']))}",
        "",
        f"ACCOUNT  {acc['currency']}  ·  mode {w['mode']}"
        + (" (LIVE — real money)" if w["live"] else ""),
        f"  cash {acc['cash']:.2f}   allocated {acc['allocated']:.2f}   "
        f"equity(est) {acc['equity_est']:.2f}",
        f"  realized pnl {acc['realized_pnl']}   fees {acc['fees_paid']}   "
        f"closed {acc['closed']} ({acc['wins']}w/{acc['losses']}l)   "
        f"open {acc['open_positions']}",
        f"  holdings: " + (", ".join(f"{k} {v}" for k, v in acc['holdings'].items()) or "none"),
        "",
        f"LOOP   heartbeat {loop.get('heartbeat')}   decision {loop.get('decision')}",
        f"       {loop.get('reason') or ''}   ts {loop.get('ts') or ''}",
        "",
        "YOUR PLATFORMS (each one is one of YOUR trading agents):",
    ]
    if not w["agents"]:
        lines.append("    (no agents on file yet — create one from the menu)")
    for a in w["agents"]:
        tag = {"off": "off", "buy": "waiting to BUY", "sell": "waiting to SELL",
               "selling": "SELLING now"}.get(a["state"], a["state"])
        cap = f"{a['capital']:.0f}" if isinstance(a["capital"], (int, float)) else "?"
        pos = f" · {a['position_count']} open" if a["position_count"] else ""
        net = f" · net {a['net_pct']}%" if a["net_pct"] is not None else ""
        lines.append(f"    {a['id']:<9} {a['name']:<18} {tag:<15} "
                     f"{cap} {a.get('mode','?')} {a.get('profile','')} "
                     f"{','.join(a.get('pairs', []))}{pos}{net}")
    lines += ["", "real: " + " · ".join(w["honesty"]["real"][:3]),
              "dressed: " + " · ".join(w["honesty"]["feels"]),
              "", "sources (how to look again):"]
    for f in w["sources"]:
        mark = "STALE" if f["stale"] else "fresh"
        lines.append(f"    [{mark:>5}] {f['name']:<32} {f['age']:<10} → {f['hint']}")
    lines += ["", "step through the gate and the market is yours to walk —",
              "fly to a platform, step on it, and its trading settings open in your hand."]
    return "\n".join(lines)


def _cli_create(args):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--capital", type=float, default=0.0)
    ap.add_argument("--name", default="")
    a = ap.parse_args(args)
    print(json.dumps(create_agent(a.profile, a.capital, a.name), indent=2))


def _cli_set(args):
    if len(args) < 2:
        sys.exit("usage: wiregate.py --set <agent_id> <key=value> [...]")
    agent_id = args[0]
    kw = {}
    overrides = {}
    for tok in args[1:]:
        if "=" not in tok:
            sys.exit(f"bad token {tok!r} (want key=value)")
        k, v = tok.split("=", 1)
        if k in ("enabled",):
            kw["enabled"] = v.strip().lower() in ("1", "true", "yes", "on")
        elif k == "capital":
            kw["capital"] = float(v)
        elif k == "profile":
            kw["profile"] = v
        elif k == "pairs":
            kw["pairs"] = [p.strip() for p in v.split(",")]
        else:
            overrides[k] = v
    if overrides:
        kw["overrides"] = overrides
    print(json.dumps(apply_settings(agent_id, **kw), indent=2))


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--summary":
        print(summary(snapshot()))
    elif argv and argv[0] == "--create":
        _cli_create(argv[1:])
    elif argv and argv[0] == "--set":
        _cli_set(argv[1:])
    elif argv and argv[0] == "--serve":
        host = os.environ.get("MRFLUFFY_GATE_ADDR", "127.0.0.1")
        port = int(os.environ.get("MRFLUFFY_GATE_PORT", "17833"))
        pr = Presence(addr=(host, port))
        pr.start()
        if not pr.started:
            sys.exit(f"could not bind the presence relay on {pr.addr} — "
                     "is another relay already running?")
        print(f"wiregate presence relay on {pr.addr} (user {pr.user})")
        print(pr.describe())
        scheme = "https" if (pr.tls and pr._server_ctx is not None) else "http"
        print(f"players join with MRFLUFFY_GATE_URL={scheme}://<this-host>:PORT "
              "plus MRFLUFFY_WIRE_KEY (same phrase, relay + players)")
        if scheme == "https":
            print(f"a player on another host must also pin the relay cert: "
                  f"MRFLUFFY_WIRE_CA={wiretls.CERT_PEM}  (sha256 "
                  f"{wiretls.fingerprint()})")
        print("Ctrl-C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pr.stop()
    else:
        print(json.dumps(snapshot(), indent=2))