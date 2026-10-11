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

Writes ALWAYS take a backup of config/agents.json first, and the honesty block
names exactly what is real (your agents, your balance, live users) and what is
flavour (the floor, the columns, the crowd dressing).

CLI:  python3 wiregate.py            # the market snapshot as JSON
      python3 wiregate.py --summary  # a one-screen human read
      python3 wiregate.py --create --profile slow --capital 50 --name "Daruma"
      python3 wiregate.py --set agent_1 capital=40 enabled=true
      python3 wiregate.py --serve    # run the presence relay on its own
"""
from __future__ import annotations
import contextlib, fcntl, hashlib, json, math, os, socket, subprocess, sys
import threading, time, urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FLUFFY = Path.home() / "mrfluffy"
BH = Path.home() / "blackhorse"
AGENTS_JSON = BH / "config" / "agents.json"
TREASURY_JSON = BH / "config" / "treasury.json"
TRADING_JSON = BH / "config" / "trading.json"
PORTFOLIO_JSON = BH / "logs" / "portfolio.json"
EXIT_WATCH_JSON = BH / "logs" / "exit_watch.json"
LOOP_STATE_JSON = BH / "logs" / "loop_state.json"
PROFILES_JSON = BH / "config" / "profiles.json"

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
    global PROFILES
    env = dict(os.environ)
    code = ("import sys,json; sys.path.insert(0, %r); "
            "import agents; print(json.dumps(agents.PROFILES))" % str(BH / "trade"))
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, cwd=str(BH), env=env, timeout=30)
        PROFILES = json.loads(r.stdout or "{}")
    except Exception:
        PROFILES = PROFILES or {}
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
            "other users' characters, relayed live by the presence server",
        ],
        "feels": [
            "the market floor, the columns and the platforms are dressing",
            "green / red / amber are a read of the files above, not a source",
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
        self._base = (base_url or f"http://127.0.0.1:{addr[1]}").rstrip("/")
        self.user = (user or os.environ.get("MRFLUFFY_WIRE_USER")
                     or socket.gethostname() or "wire").replace(" ", "_")
        self._peers: dict = {}
        self._lock = threading.Lock()
        self._server = None
        self._thread = None
        self.started = False
        self._online = None

    def start(self) -> None:
        if self.started:
            return
        try:
            srv = ThreadingHTTPServer(self.addr, _Handler)
            srv.presence = self
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
            with urllib.request.urlopen(self._base + "/ping", timeout=1.0):
                pass
            return True
        except Exception:
            return False

    def announce(self, pose: dict) -> bool:
        """POST our pose to the relay; False means there is no relay (solo floor)."""
        try:
            req = urllib.request.Request(
                self._base + "/pose", method="POST",
                data=json.dumps({"name": self.user, **pose}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1.0):
                pass
            self._online = True
            return True
        except Exception:
            self._online = False
            return False

    def leave(self) -> None:
        try:
            req = urllib.request.Request(
                self._base + "/leave", method="POST",
                data=json.dumps({"name": self.user}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1.0):
                pass
        except Exception:
            pass

    def peers(self) -> list:
        """Other users' characters in the market, pulled from the relay."""
        try:
            with urllib.request.urlopen(self._base + "/peers", timeout=1.0) as r:
                data = json.loads(r.read() or b"{}")
            return [p for p in data.get("peers", [])
                    if p.get("name") and p.get("name") != self.user]
        except Exception:
            return []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_GET(self):
        pr = getattr(self.server, "presence", None)
        if pr is None:
            return self._json(500, {"ok": False})
        if self.path == "/ping":
            return self._json(200, {"ok": True, "users": len(pr._peers),
                                    "you": pr.user})
        if self.path == "/peers":
            return self._json(200, {"peers": pr._snapshot()})
        return self._json(404, {"ok": False})

    def do_POST(self):
        pr = getattr(self.server, "presence", None)
        if pr is None:
            return self._json(500, {"ok": False})
        body = self._read_body()
        name = str(body.get("name") or "wire")[:48]
        if self.path == "/pose":
            pr._upsert(name, body)
            return self._json(200, {"ok": True})
        if self.path == "/leave":
            pr._drop(name)
            return self._json(200, {"ok": True})
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
        pr = Presence()
        pr.start()
        print(f"wiregate presence relay on {pr.addr} (user {pr.user}) — Ctrl-C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pr.stop()
    else:
        print(json.dumps(snapshot(), indent=2))