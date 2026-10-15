# Mr.Fluffy: The Wire

Mr.Fluffy: The Wire is a local-first network sense-making tool. It's split into **two separate readouts** plus a third surface: **Wire Vision** — a low-poly first-person place you can walk, built entirely from local ground truth.

- **Channel 1 — NEWS reader** (`readout.py`, `news.py`) — Reads headlines and prices, producing a compact JSON readout.
- **Channel 2 — WIRE king** (`wireout.py`, `wire.py`) — Reads your local network state from `~/raven/` (dye contacts, crow reports, IDS alerts, lifeline heart) and produces its own JSON readout. The `move` field is always a passive, local, lab-authorized observation.
- **Wire Vision** (`wirevision.py`, `wiregame.py`, `app.py`) — A playable 3D view of the wire. It never calls the brain, never runs tools over the network, and never invents data. Everything is drawn from the same local files the WIRE channel reads.

## How it connects to BlackHorse

Mr.Fluffy connects to [BlackHorse](https://github.com/BlazingCodes0/blackhorse) **by reading BlackHorse's own local files on disk**. There is no remote API connection by default.

### What it reads

`wiregate.py` expects BlackHorse at `~/blackhorse/`. The Market is built by `wiregate.snapshot()` from:

| File | Purpose |
|---|---|
| `~/blackhorse/config/agents.json` | Trading agents and their settings |
| `~/blackhorse/config/treasury.json` | Treasury/cash state |
| `~/blackhorse/config/trading.json` | Live/test mode and trading config |
| `~/blackhorse/config/profiles.json` | Agent profile definitions |
| `~/blackhorse/config/decider.json` | Decider defaults used to compute effective values |
| `~/blackhorse/logs/portfolio.json` | Open positions and allocations |
| `~/blackhorse/logs/exit_watch.json` | Exit watch flags |
| `~/blackhorse/logs/loop_state.json` | Loop heartbeat and last decision |
| `~/blackhorse/logs/signal_latest.json` | Latest SignalBot read (primary pair) |
| `~/blackhorse/logs/signals/*.json` | Per-pair SignalBot lane reads |
| `~/blackhorse/logs/sb_rows_1440m_dump.json` | 1440m candle rows used by the scenarios panel |

### Gated writes (safe editing)

When you edit or create an agent from inside Wire Vision, **only** `~/blackhorse/config/agents.json` is written. Before writing:

1. Creates a timestamped backup: `agents.json.bak.<YYYYMMDD-HHMMSS>`
2. Acquires an `fcntl` write lock
3. Validates editable fields against the allowed set
4. Enforces BlackHorse profile names
5. Rejects capital over-allocation against the treasury

Nothing is written automatically. Only when you explicitly press **Save** or **Create**.

### SignalBot replay (not execution)

The Market shows:
- **Per-platform SignalBot read** — The same values BlackHorse's "Run SignalBot now" pane shows (action, confidence, strength, RSI, spread, MA crosses, ranges/stops/targets, advisor bands, and the 60m-strength gate for 15m-or-smaller lanes)
- **LEAN arrow** — Computed from SignalBot's own fields (`wiregate._signal_lean()`), shown as green up/red down/amber flat/grey none
- **6-scenario panel** — Faithful replay of BlackHorse's scenario rubric with "active now" per interval (1440m labelled from saved rows since it's not a live channel)

**Mr.Fluffy never runs BlackHorse, never places trades, and never calls the exchange.** It only replays BlackHorse's written snapshots.

### Local presence (optional)

- **Relay:** `python3 wiregate.py --serve` runs a tiny `ThreadingHTTPServer` on `127.0.0.1:17833` with endpoints: `/ping`, `/peers`, `/pose`, `/leave`. Peers expire after ~12 seconds.
- **Multi-instance:** Launch another Mr.Fluffy on the same machine (or point via `MRFLUFFY_GATE_URL`) to see each other's avatars on the Market floor.
- **Ghost layer (optional):** Set `MRFLUFFY_WIRE_KEY` to the same phrase on relay and all clients to enable encrypted + HMAC-signed poses (prevents reading/forging positions/names).
- **Ward layer:** Per-session `ghost-id` bound to username, size/rate limits, bounded crowd size, and all refused attempts logged to `logs/.wiregate.events.log`.

## Requirements

- **OS:** Linux (paths assume `~` = `/home/<user>/`)
- **Python:** 3.10+
- **GUI:** `PyQt6`, `PyOpenGL`, `numpy`
- **Optional (Machine capture):** `tshark` — only needed if you set Machine live mode to `capture`
- **Optional:** `~/blackhorse/` with `config/` and `logs/` populated to use the Market
- **Optional:** `~/raven/` with `dye/`, `crow/`, `ids/` and `/tmp/ravenheart/` for WIRE channel + LAN population
- **Optional:** `opencode serve` running for WIRE/NEWS readouts (persistent opencode serve via `brain.py`)

## Quick Start

1. **Clone** to `~/mrfluffy`
   ```bash
   git clone https://github.com/BlazingCodes0/mrfluffy.git ~/mrfluffy
   cd ~/mrfluffy
   ```

2. **Install dependencies**
   ```bash
   pip install PyQt6 PyOpenGL numpy
   ```

3. **(Optional) Link BlackHorse** — If BlackHorse lives elsewhere, symlink it:
   ```bash
   ln -s /path/to/blackhorse ~/blackhorse
   ```

4. **(Optional) Start persistent opencode serve** — For readouts:
   ```bash
   opencode serve
   ```

5. **Launch Mr.Fluffy**
   ```bash
   python3 app.py
   ```

On first launch, it opens the **Vision** tab fullscreen and builds the LAN floor from local files.

## Using Wire Vision

### Controls

| Key | Action |
|---|---|
| `WASD` | Move/fly |
| `Space` / `C` | Ascend/descend (when flying) |
| Mouse drag / Arrows | Look |
| `E` | Interact (gates, platforms, pearls, hatches) |
| `T` | Toggle friendly names ↔ real terms (SNI/IP/MAC/domain) |
| `B` | Rebuild current scene from disk |
| `Home` | Return to surface/leave room |
| `F11` | Toggle fullscreen (hides app chrome; `Esc` or `✕` exits) |
| `H` | Toggle floating panels |
| `Esc` | Close floating panels/modals |
| `X` | Toggle x-ray (Machine room) |
| `K` | Arm/stand down birds (Machine room, 2-press confirm) |
| `L` | Release all contained sources (2-press confirm) |
| `M` | Toggle auto-defend while armed (2-press confirm) |

### Places to Explore

| Place | How to reach | Notes |
|---|---|---|
| **LAN Floor** | Default | Heart = this host. Devices = dye contacts. Gates = SNI/domain targets. Current segment lit inside wall; other segments are walled ruins. |
| **Market (BlackHorse)** | Gate on LAN floor (+x, dark violet pad) | Your agents as floating platforms. Green=buy-wait, red=sell-wait (pulses on SELL flag), dim=disabled. Land + `E` to edit. Other users appear via presence relay. |
| **Candle Room** | Centre column in Market | Choose interval (15m/60m/240m/1440m) from dumps. Walk towers per candle; newest glows. Fly to candle + `E` for OHLCV + joined SignalBot row + forward excursion. |
| **Learn Islam (Qur'an)** | Quiet plaza (-x) | 114 surahs as stars. Pick from codex or `R` for random. Each ayah opens an abstract world generated from verse images (no figures/faces). Arabic + transliteration + translation shown. Amber gate links to IslamQA. |
| **Machine (this host)** | Hatch (+z) | Live `/proc` view: sockets, connections, PIDs, roads, inhabitants. Dark figures only from local defensive evidence. `X` shows touched door. Birds: `K` to arm, `E` on figure then `E` again to CONTAIN source via host-local `birdguard` (iptables DROP in `MRFLUFFY-QUAR`). `M` auto-defend while armed. `L` release all. Live modes: `off`/`delta`/`capture`/`auto`. |
| **Exchange (past edge)** | Outward pier (-z) | Hall of gates dialing real net via `wirenet` (real DNS/TCP/TLS, stdlib only). DuckDuckGo lite search. Pearl ring (stock IslamQA + user pearls) fetches pages as text. Request phases shown as packet motes. |
| **Dive/Sea** | Fall down central well | Descend through protocol strata to edge. Past edge: **unbounded sea with no named entities and no data** below edge (atmosphere only). Faint beacon `CREATE · BUILD · LEARN · LOVE` far down. `[E]` rises to edge, `[Home]` to surface. |

## CLI Tools

| Command | Purpose |
|---|---|
| `python3 wiregate.py` | Market snapshot as JSON (reads BlackHorse files) |
| `python3 wiregate.py --summary` | Human-readable market summary |
| `python3 wiregate.py --serve` | Run presence relay on `127.0.0.1:17833` |
| `python3 wire.py` | Build WIRE context from `~/raven/` |
| `python3 wire.py --fp` | Show fingerprint only |
| `python3 wireout.py --now` | Full wire readout cycle (uses brain) |
| `python3 wireout.py --dry-run` | Build packet without brain/write |
| `python3 wireout.py --status` | Budget + last wire state |
| `python3 wirenet.py --selftest` | Test real net reachability |
| `python3 wirenet.py --resolve HOST` | Real DNS lookup |
| `python3 wirenet.py --get URL` | Real HTTP(S) fetch (stdlib) |
| `python3 candlevision.py` | Inspect candle + SignalBot join stats |

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `MRFLUFFY_WIRE_USER` | `fluffy` | Username announced on presence relay |
| `MRFLUFFY_GATE_URL` | (none) | Override relay base (e.g. `http://127.0.0.1:17833`) |
| `MRFLUFFY_WIRE_KEY` | (none) | Ghost layer key (same on relay+clients) — enables encrypted+signed poses |
| `MRFLUFFY_NET_HOST` | `https://1.1.1.1/cdn-cgi/trace` | Neutral reachability target for outward gate |
| `MRFLUFFY_NET_ALLOW_PRIVATE` | `0` | Set to `1` to allow dialing private/loopback via wirenet |
| `MRFLUFFY_BIRDGURD_LIVE` | `1` | `0` = dry-run for host-local containment |
| `MRFLUFFY_WIRE_ADDR` | (auto) | Bind relay to specific interface |
| `MRFLUFFY_WIRE_PORT` | (auto) | Bind relay to specific port |

## Systemd (optional)

- `mrfluffy-daemon.service` — Reader daemon running wire/news cycles
- `mrfluffy-serve.service` — Warm `opencode serve` session for brain calls

Edit `User`, `WorkingDirectory`, and paths to match your system before enabling.

## Safety & Honesty

- **Ground truth only.** If something isn't in the local files (`wire.py` reads, BlackHorse files, `/proc`, raven logs), it doesn't appear. "Wire quiet" / "no news" are valid states.
- **Observed vs inferred.** Facts (MAC/IP/last-seen/SNI, sockets/PIDs, OHLCV bars, written bot rows) are separated from inference (device type, meaning, intent).
- **Host-only defense.** `birdguard` only touches iptables on **this** host, only DROPs packets *from* a contained source at this NIC. It refuses own/gateway/reserved sources, requires confirmations, and supports dry-run. Auto-defend only runs while birds are armed.
- **Qur'an integrity.** The Learn Islam room uses only abstract forms — never figures, faces, or symbols of Allah, prophets, or companions. Arabic text is shown faithfully; translations are clearly labelled.
- **Exchange guardrails.** stdlib-only (no browser/JS). Timeouts, byte ceilings, redirect limits, and private-address refusal unless explicitly opted in.
- **BlackHorse safety.** All writes to `agents.json` are gated with backups, locks, validation, and over-allocation checks.
- **No network by default.** Wire Vision is a memory. Only the outward Exchange gate (and wirenet) deliberately dials the real net, with explicit guardrails.

## Development Notes

- **Brain:** Budget-gated and shared between channels; uses warm-server pattern (`opencode serve`).
- **Fingerprinting:** `wire.py` avoids retriggering brain on trivial SNI hit-count ticks.
- **Rooms model:** Other network segments appear as walled ruins you can revisit.
- **Dive:** Unbounded below edge; no entities/data below — purely atmosphere.
- **Scenarios:** Replayed from SignalBot's rubric/fields; 1440m derived from saved rows (not a live channel).

---

Mr.Fluffy treats the wire as something to walk through honestly: observe locally, don't guess, don't attack, and keep the two readouts separate.