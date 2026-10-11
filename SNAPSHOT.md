# MR.FLUFFY — Conversation Snapshot

> Span: **2026-10-09 → 2026-10-11** (the rebuilt Mr.Fluffy, two channels + a place).
> Mr.Fluffy lives in `~/mrfluffy`. It is not one feed: it is **two separate
> readouts** (news reader, wire king) plus a third surface, **Wire Vision** — a
> low-poly place built only from the wire channel's own local ground truth.

## App facts

- **Channel 1 — the NEWS reader (the crypto tape).** Files: `readout.py`,
  `news.py`, `logs/news_*`. One JSON readout: `one_liner`, `dots`, `connect`,
  `rails`, `privacy`, `freedom`, `what_changed`, `watch`, `headfake`,
  `thesis_update`, `confidence`. Memory/durable thread: `docs/NEWS_THESIS.md`.
- **Channel 2 — the WIRE king (network analyst).** Files: `wireout.py`,
  `wire.py`, `logs/wire_*`. One JSON readout: `one_liner`, `notes`,
  `what_changed`, `watch`, `headfake`, `move`, `confidence`. `move` is always a
  passive, local, lab-authorized observation.
- **Third surface — WIRE VISION (a place, not a channel).** Files:
  `wirevision.py` (world builder), `wiregame.py` (renderer), a "Vision" tab in
  `app.py`. Low-poly first-person walk of the LAN floor, then the protocol
  strata down to the last electron. **No brain, no readout, no network, no tool**
  — it only reads the same local files `wire.py` reads.
- **Brain:** shared, budget-gated, via a warm local `opencode serve` session
  (`mrfluffy-serve.service`); the reader daemon is `mrfluffy-daemon.service`.
- Documented for the agent in `AGENTS.md`.

## Conversation threads

### 1. News reader + thesis (2026-10-09 23:35)
Built and hardened the crypto-tape readout: news fetch → readout packet → brain →
parse → render → persist, plus `docs/NEWS_THESIS.md` as the durable thread the
brain may *propose* updates to (but never edits). Fixed the readout parser for
trailing prose after JSON; added a thesis-promote UI in `app.py`.

### 2. Crash: stale opencode shutdown → lost track (2026-10-10 00:44)
User: *"you were working on mr.fluffy and you had to shutdown stale opencode which
made you lose track."* Recovery session. Findings:
- The **daemon was fine; the brain call was the problem.** Under the DROP-only
  egress lockdown the model went **agentic** — it ran `bash`/`find` across the
  home looking for `AGENTS.md` (the packet says "per your AGENTS.md schema") and
  the slow/unmapped-network path pushed the call past the **240s timeout**.
- The model *can* produce the perfect JSON — it just wasted ~2.5 min exploring.
- Switched toward the **warm-server pattern** (as in blackhorse): `opencode
  serve` + HTTP API (`POST /api/session`, prompt body key is `prompt`, an
  object) instead of cold `opencode run` spawns. (Also noted `opencode api` CLI
  is gone in 1.18.35.)
- A permanent **readout session** was created (2026-10-10 02:08) to keep the
  memory warm.

### 3. Wire Vision RPG (2026-10-10 20:49)
User: *"mr.fluffy's wire should have a wire vision where i/user can easily
traverse the wire as if it were a game … a low-poly RPG … application →
transport → internet → link → the last electron … no place Mr.Fluffy can't go …
level the field for the uneducated."* Built `wirevision.py` (world model from
local files) and `wiregame.py` (QOpenGLWidget walker): the floor (heart = your
host, devices = dye contacts, gates = what each talks to, crows overhead, IDS
rifts), the central well into the protocol strata, friendly names by default
(`T` reveals the real term). Honesty baked in: observed vs inferred, announced
vs unnamed, your host / the gateway, stale + other-segment flags, and "the whole
world is a **memory**". Follow-ups: the floor is drawn as **rooms** — your
segment lit inside a wall, every other segment a walled **ruin** you enter
through a door; a **sources** list names each local file and how to refresh it.

### 4. Ghost in the Shell re-skin + the dive (2026-10-10 22:17 → 22:32)
User: *"like Ghost in the Shell … this is not story but flavouring reality with
fantasy."* Re-graded to deep cyan-teal "wet glass", green glyph rain as the sea
of information, cyan schematic linework, one amber acquisition reticle; re-skinned
vocabulary (shell, ghost, cyberbrain, dive, stand-alone complex) with the real
term still one keypress away. AGENTS.md gained the "flavour over real ground
truth, never story" clause.

Then (*"i want it vast and infinite … keep pushing"*): the **dive** was rebuilt
into a true GitS descent and made honest:
- The well-dive is an eased fall with the pitch dipping down the shaft,
  duration scaling with depth.
- The sea of information **thickens with depth** (deterministic glyph columns
  revealed far→near; near ones brighter, streaks longer, field slowly turns).
- Past the last electron you **dive into an unbounded sea that never bottoms
  out** — atmosphere only. Below the edge there is **no named entity and no
  data**; every device/domain/port/IP/MAC stays above. `[E]` rises to the edge,
  `[Home]` to the surface. HUD banner states this plainly.
- `AGENTS.md` + `wirevision.py` codex/memory updated to match. Verified under
  Xvfb: all six strata render, the dive completes, deep never bottoms out.

### 5. The market — a gate into BlackHorse (2026-10-11)
User: *"add a gate to the wire that leads into 'blackhorse' — a trading market…
steps inside the gate connect to an 'online game'… users can see each other's
characters… floating platforms (only the user's OWN agents under them)… flying to
a platform and stepping on it opens a panel to edit that agent's trading
settings… also a menu floating which we can hide that brings up the agent
creation and the balance in the account."* Findings + build:
- BlackHorse is **LIVE with real money** (`config/trading.json` mode=LIVE,
  autonomous=true): account cash 29.22 USD, ~69.74 allocated, agents agent_1 +
  agent_6 enabled and waiting to sell, the rest off. No network-facing server
  existed, so a tiny **presence relay** (`wiregate.Presence`) was built.
- New `wiregate.py`: the blackhorse market model + the online layer + **gated
  writes**. CLI: `python3 wiregate.py [--summary|--create|--set|--serve]`.
  Reads read blackhorse's files straight; writes back up `agents.json` first
  (`agents.json.bak.<stamp>`), take an `fcntl` write lock, validate against the
  editable keys + the blackhorse registry's PROFILES, and reject capital
  over-allocation vs the treasury.
- Presence relay on 127.0.0.1:17833 (stdlib ThreadingHTTPServer): `/ping`,
  `/peers`, `/pose`, `/leave`; peers expire after 12s; `MRFLUFFY_WIRE_USER`
  names you; `MRFLUFFY_GATE_URL` overrides the relay base. Debugged: `peers()`
  once read the client's own empty map instead of the relay — now fetches
  `/peers` and filters self, verified green with two clients.
- `wiregame.py` grew the market scene: a gate on the LAN floor by the well
  (`[E]` beside it opens the market), dark disc floor at `MARKET_FLOOR_Y=-80.0`,
  a centre account column breathing with the loop heartbeat, one floating pad per
  trading agent (colour = buy/sell/selling/off, pulsing + selection ring), the
  return gate, and other users' characters drawn from the relay. HUD shows
  account cash/allocated, loop decision, online/alone, legend + the honesty line.
  Keys: `E` step/settings, `B` rebuild market, `H` hide/show the market menu,
  `Home` leave the market.
- `WireVisionTab` gained the floating market panel (hidden by default): live
  balance, a per-agent editor (capital, enabled, profile, pairs, policy
  overrides) and a New-agent form — every Save/Create is an explicit gated write.
- Verified headless under Xvfb: world builds, market opens from snapshot (5
  agents, cash 29.22), landing on a pad selects the agent, E opens the editor,
  H toggles the menu, a second relay user appears as a peer, labels render, Home
  leaves, and no config was touched (disk untouched during the smoke test).

### 6. The ghost + ward layers — sealing the online game (2026-10-11)
User: *"add data encryption layer which assigns a random blah blah you the ghost
in the shell stuff to secure our game because we don't want to make it easy for
anyone to hack our users or the other way around — a defense system against
malicious users who are not here to just play."* Built on top of the presence
relay, all stdlib, all tested:
- **Ghost layer (encryption + signing).** `MRFLUFFY_WIRE_KEY` (same phrase on the
  relay and every player) derives a 32-byte key via PBKDF2-HMAC-SHA256
  (200k iters); every `/pose` and `/peers` payload is sealed as an envelope
  (random 12-byte nonce, bytes woven with an HMAC-SHA256 keystream, signed with
  an HMAC, constant-time verification). A listener on the wire sees only
  ciphertext; a pose not signed with the key is refused (401). Keyless client ↔
  sealed floor and sealed client ↔ open floor both refuse honestly — mismatch is
  visible, never silent. Each client also carries a **random per-session ghost-id**
  (`secrets.token_hex(16)`) bound to its name on first contact; posing/leaving
  under someone else's name with the wrong ghost-id is refused (403) and cannot
  stomp the real user's pose.
- **Ward layer (defense).** Body size cap (413 over 4 KiB), per-IP request rate
  throttle (429), per-name burst cap, a bounded crowd (`MAX_PEERS`), expulsion of
  expired peers, and every refused attempt appended to
  `logs/.wiregate.events.log` and counted in the relay's `ward` counter.
- **Visible in the game.** The market HUD shows `ghost layer: hardened ·
  payloads encrypted + signed (PBKDF2→HMAC weave) · ward refused N attempt(s)`
  (amber when the floor is open) plus the legend/honesty/controls block; the
  floating menu carries the same line. `wiregate.py --serve` prints the layer
  status + how players join (`MRFLUFFY_GATE_URL`, `MRFLUFFY_GATE_ADDR/PORT`).
- Tests: plain cross-visibility unchanged; forged ghost-id → 403 with the real
  pose untouched; oversized shell → 413; keyless client refused by a sealed
  floor; sealed pair cross-visibility with `/peers` staying encrypted; wrong-
  phrase sealed pose → 401 with the real pose kept; Xvfb render + menu smoke
  on a hardened floor.

## Current state (end of 2026-10-11)

- `wiregame.py` modified + `wiregate.py` new (untracked); `AGENTS.md` +
  `SNAPSHOT.md` updated. Last commit on `master`: *"mrfluffy: add the market —
  a BlackHorse gate inside the wire"* (142089c).
- Open threads: (a) make the amber reticle lock/label the nearest real object in
  3D; (b) polish the market (platform spacing, crowd density, a sounding bell at
  the centre column — all dressing on top of the real snapshot); (c) optionally
  switch the relay to real TLS later (the ghost weave is stdlib-protected, honest
  about being a weave, not a vow). House rules stand: ground truth only, no
  invented data, flavour not story; the market's platforms/balance/crowd are
  real, the floor and colours are dressing.
