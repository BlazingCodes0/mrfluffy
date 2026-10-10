# MR.FLUFFY — Conversation Snapshot

> Span: **2026-10-09 → 2026-10-10** (the rebuilt Mr.Fluffy, two channels + a place).
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

## Current state (end of 2026-10-10)

- `wirevision.py` / `wiregame.py` untracked; `AGENTS.md` + `app.py` modified;
  last commit on `master`: *"mrfluffy: split into two channels — the news reader
  and the wire king."*
- Raven (the separate `~/raven` lab assistant) was shut down by the user via its
  GUI; Mr.Fluffy files were left untouched, and Wire Vision never touches raven
  or the network.
- Open threads: (a) make the amber reticle lock/label the nearest real object in
  3D; (b) keep polishing the endless dive. House rules stand: ground truth only,
  no invented data, flavour not story.
