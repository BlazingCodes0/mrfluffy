"""candlevision.py — the candle room: DOT/USD's history read as a place.

Built ONLY from local files, the wire's ground-truth rule: the candle history
(blackhorse/logs/candles_<iv>.json) and SignalBot's own saved rows
(blackhorse/logs/sb_rows*.json), joined by bar index the same way the house's
own trade/validate_playbook.py joins them. Nothing here runs the bot, calls the
exchange, or invents a bar: every candle is a real Kraken OHLCV bar, and every
mood is a field the bot already wrote.

For the interval the reader chooses the room is a walk down the tape: one tower
per candle (green close-up, red close-down, a wick to the true high/low), the
newest bar glowing as it ticks, and the market's "feel" painted from the bot's
own per-candle row — its range strength, its range signal, the zone price sat
in, and what actually happened next (the forward returns). Observed (a bar's
OHLCV) is kept apart from inferred (what it means); see honesty().

No network. No tools. No model.
"""
from __future__ import annotations
import hashlib
import json
import math
import time
from pathlib import Path

BH = Path.home() / "blackhorse"
LOGS = BH / "logs"
CANDLES_DIR = LOGS
ROWS_JSON = LOGS / "sb_rows.json"
SIGNAL_LATEST_JSON = LOGS / "signal_latest.json"
SIGNALS_DIR = LOGS / "signals"

PAIR = "DOT/USD"
PAIR_KEY = "DOT-USD"
EXCHANGE = "kraken"

# the intervals the tape can be read at (the ones with a candle dump on disk)
INTERVALS = ("15m", "60m", "240m", "1440m")
# the SignalBot channel that carries each interval (ripple 15m, wave 60m, tide 240m)
CHANNEL_BY_IV = {"15m": "ripple", "60m": "wave", "240m": "tide", "1440m": "tide"}

# ---- geometry (the room) ----------------------------------------------------
FLOOR_Y = -190.0                 # the candle room sits below the machine
BASE_Y = FLOOR_Y + 3.0           # where the lowest price sits
TOP_Y = FLOOR_Y + 52.0           # where the highest price sits
SPAN = TOP_Y - BASE_Y
SPACING = 0.47                   # room units between two bars
ENTRY_PAD = 7.0                  # how far past the newest bar you enter

# ---- palette (a candle's own colours; mood only tints, never invents) -------
UP = (0.26, 0.92, 0.46)
DOWN = (0.95, 0.30, 0.32)
GREY = (0.45, 0.48, 0.56)
AMBER = (0.98, 0.76, 0.22)


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


def _num(v, dp=4):
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return "?" if v is None else str(v)


def _fingerprint(*pairs) -> str:
    h = hashlib.sha256()
    for name, data in pairs:
        h.update(name.encode())
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return h.hexdigest()[:10]


def _fmt_time(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(ts))) + "Z"
    except Exception:
        return "?"


# ---- where the bars and rows live -------------------------------------------
def _candles_path(iv: Path | str) -> Path:
    return CANDLES_DIR / f"candles_{iv}.json"


def _rows_path(iv: str) -> Path:
    """Prefer the small per-interval dump; fall back to the all-in-one file."""
    dump = LOGS / f"sb_rows_{iv}_dump.json"
    if dump.exists():
        return dump
    return ROWS_JSON


def _load_rows(iv: str) -> list:
    """The bot's saved per-candle rows for one interval, as a list of dicts."""
    dump = LOGS / f"sb_rows_{iv}_dump.json"
    if dump.exists():
        d = _load_json(dump, [])
        return d if isinstance(d, list) else []
    allrows = _load_json(ROWS_JSON, {})
    if isinstance(allrows, dict):
        d = allrows.get(iv)
        if isinstance(d, list):
            return d
    return []


def available() -> list:
    """The intervals that actually have a candle dump on disk, newest first,
    each with the real bar count and how many rows the bot left for it."""
    out = []
    for iv in INTERVALS:
        cp = _candles_path(iv)
        if not cp.exists():
            continue
        candles = _load_json(cp, [])
        rows = _load_rows(iv)
        try:
            mt = cp.stat().st_mtime
        except OSError:
            mt = None
        out.append({
            "interval": iv,
            "bars": len(candles) if isinstance(candles, list) else 0,
            "rows": len(rows),
            "mtime": mt,
            "age": _ago(time.time() - mt) if mt else "unknown",
        })
    return out


# ---- the mood: the bot's own fields, read as a feeling ----------------------
def _mood(row: dict | None) -> dict | None:
    """A candle's feel, from SignalBot's own row. Not a promise, not a signal —
    a re-reading of the fields the bot already wrote for this bar."""
    if not row:
        return None
    s = row.get("strength")
    rs = str(row.get("rangeSignal") or "?").upper()
    zone = row.get("zone") or "?"
    f5 = row.get("return5")
    f20 = row.get("return20")
    if s is None:
        energy = "no read"
    else:
        s = float(s)
        energy = ("surging" if s >= 0.80 else "strong" if s >= 0.60
                  else "building" if s >= 0.35 else "quiet")
    # what actually happened next (the after-feeling)
    if f5 is None:
        after = "next: no forward data"
        col = GREY
    elif f5 > 0.5:
        after = f"then up {f5:.2f}%"
        col = UP
    elif f5 < -0.5:
        after = f"then down {abs(f5):.2f}%"
        col = DOWN
    else:
        after = "then flat"
        col = AMBER
    lean = {"BUY": "reaching for the floor", "SELL": "pushed at the roof"}.get(rs, "holding")
    word = f"{energy} \u00b7 {lean} \u00b7 {zone}"
    return {"energy": energy, "lean": rs, "zone": zone,
            "fwd5": f5, "fwd20": f20, "after": after, "word": word, "col": col}


def _bar_mood(c: dict) -> dict:
    """A feel read straight off the bar itself (observed), for a candle the bot
    left no row for — the shape of the move, nothing invented."""
    rng = (c["high"] - c["low"]) or 1e-9
    body = abs(c["close"] - c["open"])
    up = c["close"] >= c["open"]
    decis = body / rng
    energy = "decisive" if decis > 0.6 else "measured" if decis > 0.3 else "indecisive"
    pos = (c["close"] - c["low"]) / rng
    lean = ("closed strong" if pos > 0.66 else "closed weak" if pos < 0.33
            else "closed mid")
    return {"energy": energy, "lean": lean, "zone": "\u2014",
            "fwd5": None, "fwd20": None, "after": "bar read (no bot row yet)",
            "word": f"{energy} \u00b7 {lean}", "col": UP if up else DOWN,
            "derived": True}


def _join_rows(candles: list, rows: list):
    """Join the bot's rows to the candles by bar index, with the house's own
    \u00b15% price guard (trade/validate_playbook.py). Returns (by_index, joined)."""
    by_key = {}
    for r in rows:
        k = r.get("key")
        if isinstance(k, int):
            by_key[k] = r
    by_index = {}
    joined = 0
    for i, c in enumerate(candles):
        r = by_key.get(i)
        if r is None:
            continue
        try:
            price = float(r.get("price"))
            close = float(c.get("close"))
            if price and abs(close - price) / price < 0.05:
                by_index[i] = r
                joined += 1
        except (TypeError, ValueError):
            continue
    return by_index, joined


# ---- the current read (the "now" ticker at the newest bar) ------------------
def now_read(iv: str) -> dict:
    """SignalBot's CURRENT written read for this interval, from its own snapshot
    (never re-run here). Empty when the snapshot carries no such channel."""
    snap = _load_json(SIGNALS_DIR / f"{PAIR_KEY}.json", None)
    if not (isinstance(snap, dict) and snap.get("channels")):
        latest = _load_json(SIGNAL_LATEST_JSON, {})
        snap = latest if isinstance(latest, dict) and latest.get("channels") else {}
    chans = snap.get("channels") or {}
    name = CHANNEL_BY_IV.get(iv)
    c = chans.get(name) if name else None
    if c is None:
        for n, cc in chans.items():
            if str(cc.get("interval")) == iv:
                c, name = cc, n
                break
    if not isinstance(c, dict):
        return {}
    mr = c.get("marketResult") or {}
    r = c.get("RSI") or {}
    return {
        "channel": name, "interval": c.get("interval", iv),
        "action": c.get("action"), "confidence": c.get("confidence"),
        "strength": c.get("strength"), "strength_direction": c.get("strengthDirection"),
        "trend": mr.get("trendState"), "rsi": r.get("currentRSI"),
        "range_signal": c.get("rangeSignal"),
        "entry_eligible": c.get("entryEligible"),
        "ts": snap.get("ts"), "age": _ago(_ts_age(snap.get("ts"))),
        "pair": snap.get("pair", PAIR), "exchange": snap.get("exchange", EXCHANGE),
    }


def _ts_age(ts):
    try:
        ep = time.strptime(str(ts), "%Y-%m-%dT%H:%M:%SZ")
        epoch = time.mktime(ep) - time.timezone
        return max(0.0, time.time() - epoch)
    except Exception:
        return None


# ---- build the room ---------------------------------------------------------
def build(iv: str) -> dict:
    """The candle room for one interval, from local ground truth only."""
    cp = _candles_path(iv)
    candles = _load_json(cp, [])
    if not isinstance(candles, list) or not candles:
        raise RuntimeError(f"no candle history for {iv} ({cp})")
    # keep only well-formed bars, oldest -> newest
    clean = []
    for c in candles:
        try:
            clean.append({
                "time": int(c.get("time")),
                "open": float(c.get("open")),
                "high": float(c.get("high")),
                "low": float(c.get("low")),
                "close": float(c.get("close")),
                "volume": float(c.get("volume") or 0.0),
            })
        except (TypeError, ValueError):
            continue
    clean.sort(key=lambda c: c["time"])
    n = len(clean)
    rows = _load_rows(iv)
    by_index, joined = _join_rows(clean, rows)

    lows = [c["low"] for c in clean]
    highs = [c["high"] for c in clean]
    pmin, pmax = min(lows), max(highs)
    if pmax <= pmin:
        pmax = pmin + 1e-9

    def ymap(p):
        return BASE_Y + (float(p) - pmin) / (pmax - pmin) * SPAN

    bars = []
    for i, c in enumerate(clean):
        row = by_index.get(i)
        mood = _mood(row) or _bar_mood(c)
        up = c["close"] >= c["open"]
        bars.append({
            "i": i, "x": i * SPACING,
            "time": c["time"], "tstr": _fmt_time(c["time"]),
            "o": c["open"], "h": c["high"], "l": c["low"], "c": c["close"],
            "v": c["volume"], "up": up,
            "y_open": ymap(c["open"]), "y_close": ymap(c["close"]),
            "y_high": ymap(c["high"]), "y_low": ymap(c["low"]),
            "row": row, "mood": mood,
        })

    now = now_read(iv)
    x0, x1 = 0.0, (n - 1) * SPACING
    fp = _fingerprint(
        (f"candles_{iv}", _text(cp)[:65536]),
        (f"rows_{iv}", _text(_rows_path(iv))[:65536]),
    )
    return {
        "ok": True,
        "interval": iv,
        "pair": PAIR, "exchange": EXCHANGE,
        "bars": bars, "n": n,
        "rows_total": len(rows), "rows_joined": joined,
        "price": {"min": pmin, "max": pmax,
                  "first": clean[0]["close"], "last": clean[-1]["close"]},
        "geometry": {"x0": x0, "x1": x1, "spacing": SPACING,
                     "floor_y": FLOOR_Y, "base_y": BASE_Y, "top_y": TOP_Y,
                     "span": SPAN, "pmin": pmin, "pmax": pmax,
                     "entry_x": x1 + ENTRY_PAD},
        "now": now,
        "start": clean[0]["time"], "end": clean[-1]["time"],
        "fresh": _ago(time.time() - cp.stat().st_mtime) if cp.exists() else "unknown",
        "fingerprint": fp,
    }


def sources() -> list:
    """Every local file the room is built from, and what would refresh it."""
    out = []
    for iv in INTERVALS:
        cp = _candles_path(iv)
        rp = _rows_path(iv)
        if not cp.exists():
            continue
        try:
            age = _ago(time.time() - cp.stat().st_mtime)
        except OSError:
            age = "unknown"
        out.append({"name": f"candles {iv}", "detail": f"{cp.name} \u00b7 {age}",
                    "fresh": age.endswith("s ago") or age.endswith("m ago")})
        if rp.exists():
            try:
                rage = _ago(time.time() - rp.stat().st_mtime)
            except OSError:
                rage = "unknown"
            out.append({"name": f"bot rows {iv}", "detail": f"{rp.name} \u00b7 {rage}",
                        "fresh": rage.endswith("s ago") or rage.endswith("m ago")})
    return out


def honesty() -> dict:
    return {
        "real": ("each candle is a real Kraken OHLCV bar; the bot read and the mood "
                 "are SignalBot's OWN saved rows, joined to the bars by index (\u00b15%)"),
        "feels": ("the room, the glow and the colours are dressing; green = close "
                  "above open, red = close below"),
        "refresh": ("re-dump candles + rows with the SignalBot research tools to "
                    "refresh the tape (this room never fetches or runs the bot)"),
    }


def summary(w: dict) -> str:
    if not w:
        return "the candle room"
    now = w.get("now") or {}
    base = (f"{w.get('pair')} @ {w.get('interval')} \u00b7 {w.get('n')} bars \u00b7 "
            f"{_fmt_time(w.get('start'))} \u2192 {_fmt_time(w.get('end'))} "
            f"\u00b7 {w.get('rows_joined')}/{w.get('n')} carry a bot read")
    if now:
        base += (f" \u00b7 now {now.get('action')} str={_num(now.get('strength'), 3)} "
                 f"{now.get('strength_direction')} ({now.get('age')})")
    return base
