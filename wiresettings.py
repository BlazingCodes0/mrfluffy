"""wiresettings.py — the wire-vision knobs, in one small file.

Only the renderer's own preferences live here (how live the machine room is),
kept apart from the daemon's config so neither can break the other.

The live-vision knob has four positions:

    off       the room is a snapshot — rebuilt only when you press B
    delta     a 1 Hz read of the kernel counters, interpolated at 60 fps
              (bytes/packets on each interface, per-process read/write bytes,
              cpu, disk) — cheap enough for a weak machine
    capture   a real packet capture streamed into the room — heavy, for a
              strong machine
    auto      benchmark THIS host once and pick off / delta / capture

The outward connection is also the player's own choice, kept here so it is never
hardcoded: `net_host` is the one address the outward pier gate really dials, and
`relay_seeds` is the comma-separated list of mesh doors the presence joins (the
wire's own seeding). An environment variable (`MRFLUFFY_NET_HOST`,
`MRFLUFFY_GATE_URL`) still overrides the saved choice.

Choosing a default reads the host: os.cpu_count(), the load average, and one
tiny timed loop. That is a local benchmark only — no network, no tool, no
subprocess, no model. Everything here stands on the same rule as the rest of
Wire Vision: ground truth, locally read, never invented.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

PATH = Path.home() / "mrfluffy" / "config" / "wire_settings.json"

MODES = ("auto", "off", "delta", "capture")
# the game knobs ride alongside the live-vision knob in the same small file:
# how fast you fly and how far the mouse turns you. Both are the player's own
# preference — they change nothing about the ground truth the world is built on.
DEFAULT = {"live_mode": "auto", "live_effective": "delta",
           "capture_max_pps": 400,
           "walk_speed": 1.0, "fly_speed": 1.9,
           "boost_mult": 2.2, "look_sensitivity": 1.0,
           # the outward connection — your choice, never hardcoded. Empty means
           # "use the neutral built-in" (see wiregame.NET_DEFAULT_HOST).
           "net_host": "", "relay_seeds": ""}


def _clamp(v, lo, hi, fallback):
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return fallback


def load() -> dict:
    d = dict(DEFAULT)
    try:
        d.update(json.loads(PATH.read_text()))
    except Exception:
        pass
    if d.get("live_mode") not in MODES:
        d["live_mode"] = "auto"
    if d.get("live_effective") not in ("off", "delta", "capture"):
        d["live_effective"] = "delta"
    try:
        d["capture_max_pps"] = max(30, min(4000, int(d.get("capture_max_pps", 400))))
    except Exception:
        d["capture_max_pps"] = 400
    d["fly_speed"] = _clamp(d.get("fly_speed"), 0.5, 4.0, 1.9)
    d["walk_speed"] = _clamp(d.get("walk_speed"), 0.5, 3.0, 1.0)
    d["boost_mult"] = _clamp(d.get("boost_mult"), 1.0, 6.0, 2.2)
    d["look_sensitivity"] = _clamp(d.get("look_sensitivity"), 0.2, 3.0, 1.0)
    d["net_host"] = str(d.get("net_host") or "").strip()
    d["relay_seeds"] = str(d.get("relay_seeds") or "").strip()
    return d


def save(d: dict) -> None:
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, indent=2))
        tmp.replace(PATH)
    except Exception:
        pass


def _bench_ms(reps: int = 200000, runs: int = 3) -> float:
    """A tiny, deterministic local workload — the fastest of a few runs, so a
    transient load spike does not misjudge the machine."""
    best = None
    for _ in range(max(1, runs)):
        t = time.perf_counter()
        x = 0
        for i in range(reps):
            x += (i * i) & 0xFF
        dt = (time.perf_counter() - t) * 1000.0
        best = dt if best is None else min(best, dt)
    return best


def detect() -> dict:
    """One local benchmark -> a hardware tier. No network, no subprocess.

    The ladder is deliberately conservative: only a strong box is offered the
    heavy packet capture. The cheap delta sampler is near-free (a few /proc
    reads a second), so any multi-core machine gets it; only a genuinely tiny
    single-core box falls all the way back to a snapshot.
    """
    cores = os.cpu_count() or 1
    try:
        load = os.getloadavg()[0]
    except Exception:
        load = 0.0
    per = load / max(1, cores)
    bench = _bench_ms()
    if cores >= 8 and per < 0.5 and bench < 25.0:
        tier = "high"
    elif cores >= 2 or per < 1.0:
        tier = "mid"
    else:
        tier = "low"
    eff = {"high": "capture", "mid": "delta", "low": "off"}[tier]
    return {"tier": tier, "cores": cores, "load": round(load, 2),
            "per_core": round(per, 2), "bench_ms": round(bench, 1),
            "effective": eff}


def resolve(mode: str):
    """Return (effective_mode, detect_info_or_None).

    `auto` runs the benchmark; an explicit choice is honoured as-is, so a weak
    machine can still be asked for delta (or even capture) if the user insists.
    """
    if mode == "auto":
        info = detect()
        return info["effective"], info
    return mode, None


def describe(mode: str, effective: str, info: dict | None = None) -> str:
    if mode == "auto" and info:
        return (f"auto \u2192 {effective}  (this host: {info['cores']} cores, "
                f"load {info['load']}, bench {info['bench_ms']}ms)")
    return {"off": "snapshot (rebuild with B)",
            "delta": "live \u00b7 1 Hz kernel deltas (cheap)",
            "capture": "live \u00b7 real packet capture (heavy)"}.get(
                effective, effective)


if __name__ == "__main__":
    print(json.dumps({"defaults": DEFAULT, "detect": detect()}, indent=2))
