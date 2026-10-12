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
- **Ghost layer (real TLS + signed authenticity).** `MRFLUFFY_WIRE_KEY` (same phrase
  on the relay and every player) signs each shell so nobody without the phrase can
  speak on a sealed floor; the relay is **HTTPS by default** (`config/wire_tls/relay.pem`
  self-signed, pinned) — real TLS transport. `wiretls.py` generates/loads the cert;
  `MRFLUFFY_WIRE_TLS=0` reverts to plain HTTP; `MRFLUFFY_WIRE_CA` pins a remote relay's
  cert; `MRFLUFFY_WIRE_TLS_INSECURE=1` is an honest opt-out. The homemade XOR weave is
  retired (v2 HMAC signatures); legacy v1 shells are rejected. The ward layer (ghost-id
  binding, per-IP rate limits, per-name bursts, bounded crowd, oversized shells) remains
  in force. The HUD and CLI describe the TLS state + short fingerprint, key requirement,
  and ward count.

### 7. The reorganized floor + the step-off fix (2026-10-11)
User: *"the main wire home is too crowded so lets make room for blackhorse so its
far from others and lets keep the lan wire related stuff together and nicely
spaced."* Then: *"how do i step off the platform i keep getting stuck."*
- **Blackhorse gets a cleared plaza.** The home-device ring in `wirevision.py`
  now reserves an empty wedge (due +x, `MARKET_APRON_HALF ≈ 32°`) : devices sit
  on an evenly-spaced ring around the heart, the wedge stays bare, and the LAN
  cluster (well / heart / media / devices / gates) stays together near the
  centre. The market gate moved from the middle of the room out to that plaza
  (`MARKET_GATE_POS = [23, 0.06, 0]`) and stands on its own **violet arrival
  pad** — wiring rings, a slow sentry sweep and six approach lights —
  ~11–12 units from the nearest LAN object (a device gate) with everything else
  farther. Layout arrangement only; which devices/gates exist is untouched real
  ground truth.
- **Pads no longer glue you down.** Two bugs in `_market_step` kept players
  stuck: movement input was dropped entirely while on a platform, and the
  landing snap re-fired whenever you were inside the pad ring near pad height,
  dragging you back as you tried to leave. Now you are always free to move: you
  come to rest on a pad only by **flying down onto it (C)** from above (a single
  deliberate touch, tracked via `_land_prev_y`), and pressing any key steps you
  off; a pad never re-grabs a player who is leaving it. HUD hint updated:
  "step onto a platform = fly down to it (C) · press any key to step off".
- Verified headless: three home devices at 31.5°/130.5°/229.5°, wedge keeps the
  ring clear of the gate's azimuth, no draw errors at the new plaza; land →
  step off → re-land → climb away with no re-snaring; market still enters from
  the new position and returns to the wire.

### 8. Learn Islam — the room of the Word (2026-10-11)
User: *"add room called learn islam ... i dont want to make a mockery out of it
but in today world we are all wired so i want to read and experience it through
that room ... start with small chapters."*
- Sourced the real text first: alquran.cloud, editions `quran-uthmani` (Hafs,
  Uthmani script), `en.transliteration`, `en.sahih` (Saheeh International);
  stored locally in `quran.py` as a faithful, byte-for-byte copy. Six small
  surahs to start: 1 Al-Faatiha, 103 Al-Asr, 108 Al-Kawthar, 112 Al-Ikhlaas,
  113 Al-Falaq, 114 An-Naas (28 verses). Data structure accepts any surah.
- **The sacred rule in code:** nothing is depicted — no Allah, no prophets,
  no companions. The hall draws only a dark disc, a soft centre light-column,
  faint rings and reader markers; the Word is drawn as words on light.
- The room is reached through a gate on the wire floor on its own cleared plaza
  due −x (word wedge added to `wirevision`; devices now spread with a general
  `_device_angles` helper that keeps all plaza wedges bare). `Home` or the far
  gate leaves, and the presence relay shares the room — "for we are all wired."
- Verified headless: 3 home devices at 71.5°/151.4°/288.5° with both wedges
  clear; word gate 11.2 units and market gate 17.7 units from the nearest LAN
  object; enter → read → leave → market still opens → rebuild resets cleanly.

### 9. The ayah engine — every verse its own world (2026-10-11)
User: *"...like an engine which makes the world match the meaning of the ayah
and have the writing written on the sky, another gate which leads to the next
ayah which then generates another world ... each ayah world should have an exit
back to surah selection room, which should have a random chapter selection which
takes you to the first ayah of a random chapter which the user can continue to
travel through or exit back to the chapters."*
- New module **`quranworld.py`** — the motif engine. A vocabulary of abstract
  motifs (mercy, light, lord, worlds, path, time, loss, patience, truth, dawn,
  darkness, refuge, abundance, one, whisper, anger, water, soul), each a palette
  + one abstract form + a motion feel. `recipe(surah, ayah)` is **deterministic**
  (seed `surah:ayah`): keywords in the English translation pick motifs, the
  surah's base theme is always included, and a primary form + scattered props
  are laid out. `sky_text(surah, ayah)` returns the authentic Arabic,
  transliteration, translation and reference. `describe()` gives the honest
  caption. `quran.py` stays pure scripture — the engine never alters a word.
- **Two rooms.** Entering Learn Islam now opens a **hall of chapters** (six
  surah portals on a ring + one bright random-chapter gate). `E` opens the
  chapter's first ayah; `R` opens a random chapter at its first ayah. Each ayah
  opens its own generated world. Gates: next ayah (`E`, or `[`/`]`
  anywhere), previous ayah, back to the chapters. At a chapter's end, "next"
  returns to the chapters.
- **Words on the sky.** In an ayah world the Arabic is shown large at the top of
  the sky with transliteration, translation and the reference — the ayah held
  up to be read. HUD caption states plainly: the world is *a reverent impression
  of the verse's named images, NOT the meaning (which is with Allah)*.
- Verified headless: hall lists 6 chapters + random gate; open 112 → world with
  14 props; travel wraps to the chapters at a chapter's end; random lands on a
  chapter's first ayah; next/prev gates and back-to-chapters all fire; ayah and
  selection frames render; leave returns to the wire and the market still opens.

### 10. Full screen, and the chapters as a sky of stars (2026-10-11)

- **Wire Vision takes the whole screen.** The Vision tab gained a "⛶ full screen"
  button (and `F11`); `app.py`'s `Fluffy` gained a "⛶ Wire vision full screen"
  button. On toggle, the tab hides its own build bar + codex, and the host hides
  the app's title, side controls, footer and tab bar, so the world alone fills the
  display. `WireVisionTab.fullscreen_changed(bool)` tells the host what to hide;
  `F11` or the button restores the panels, and switching away from the Vision tab
  (or closing) always drops full screen, so the app is never stuck.
- **The chapter hall became a cluster of stars you fly to.** The selection room is
  no longer a flat ring: the six small surahs are hung as bright stars over a
  golden-angle sphere shell (`_word_chapter_pos`, radius `WORD_CLUSTER_R` = 21,
  heights from `WORD_FLOOR_Y+6` up to `+32`), a lucky-dip star on the central
  beacon gives the **random chapter** (`_word_random_pos`), and a deterministic
  280-point star field (`_word_star_points`, seeded) fills the dark. You fly to the
  star you want and press `E`; `_nearest_word` now measures full 3D distance, and
  the in-world labels/HUD say "fly to a star". The old flat `WORD_SEL_R` ring and
  its placement are gone.
- Verified headless: all six chapter-stars reachable in 3D and each resolves as
  its surah; the random and leave gates are nearest-detected; the star field is
  stable across frames; the full-screen toggle round-trips from the in-tab button,
  the app button, and `F11`, and leaving the tab restores the chrome.

### 11. The whole Qur'an, a way out of full screen, and quick travel (2026-10-11)

- **The whole Book is in the room now.** All 114 surahs, 6236 ayahs, are carried
  in `quran_data.json` (3.3 MB), copied byte-for-byte from alquran.cloud
  (`quran-uthmani`, `en.transliteration`, `en.sahih`); `quran.py` now just opens
  that file (same `SURAS`/`SOURCES`/`ORDER`/`all_suras()` interface) and
  `fetch_quran.py` is the provenance script that rebuilds it. The six small
  surahs' hand-written notes are preserved; every other surah gets a factual note.
  Only a BOM is stripped.
- **Full screen can't trap you any more.** The bars that held the old exit button
  are hidden in full screen, so a floating **"✕ exit full screen"** overlay now
  stays over the world (parented to the `_GLDeck` stage, positioned top-centre),
  and `Esc` also drops full screen. `F11` still toggles. Leaving the tab/closing
  restores everything.
- **Quick travel without flying.** A floating quick bar over the world gives
  `◀ prev ayah`, `next ayah ▶` (→ "finish ➞ chapters" at a chapter's end),
  `chapters`, `random chapter`, and `leave the room`; and the codex panel now
  holds a **list of all 114 chapters** — pick one and open its first ayah, no
  flying needed. The bar shows only in the Word room, and only the moves that fit
  the mode.
- **A sky of 114 stars stays smooth.** The chapter cluster names only the few
  stars nearest you; the far stars draw as small points (level-of-detail), the
  nearest ~12 in full. The ayah sky panel sizes the Arabic to fit, so even 2:282
  (the Book's longest verse) is shown whole.
- Verified headless: all 114 chapter-stars reachable in 3D; every surah's recipe
  builds (0 failures); the full-screen exit button and `Esc` both drop full
  screen and the button floats inside the deck; the quick bar and chapter list do
  prev/next/chapters/random/leave; a chapter list click opens the surah's first
  ayah; opening surah 2 (286 ayahs) and travelling works; rendering 2:282 works.

### 12. Reading the ayah, uninterrupted (2026-10-11)

- **The chapters were scattered wide.** The 114 chapter-stars no longer sit close
  on a sphere shell; they are spread through a tall volume of sky (radius
  `WORD_CLUSTER_R` = 26, heights `WORD_FLOOR_Y+5` … `WORD_CLUSTER_TOP`, i.e. ~51
  units tall) using a fixed **best-candidate (blue-noise)** scatter
  (`_word_chapter_points`, cached; closest pair ≈ 7.9 units, well clear of the
  6.0 pick radius). Same sky every time, but you now fly a real little adventure
  between chapters.
- The centre **reticle was removed from the Word room** (the wire and market keep
  theirs) — it sat over the reading and made the English hard to read. The
  interaction prompt moved out of the reading column (left margin in an ayah,
  below the title in the chapter room), and the reading panel was deepened
  (alpha 150 → 190) so the translation stands out over the world.
- **The mouse wheel no longer travels the ayah.** With the next/prev buttons, the
  `[`/`]` keys and the gates all present, scrolling only got in the way; it is now
  left to the page. The HUD control line was updated to match.

### 13. The outward gate — the one place the wire is real (2026-10-11)

- **The wall, and the one door in it.** Everything the world shows is a memory.
  The one exception is a new **outward gate**: a pier runs off the floor's far
  edge (due −z) out over the open sea to a portal that **really dials the net**.
  `wiregame._draw_net_gate` draws the pier + gate; the fly clamp is lifted along a
  narrow wedge (`NET_WEDGE_HALF`) so you can walk out to radius ~54 (the floor edge
  is 46) — genuinely outside the boundary. A cleared wedge (`NET_APRON_*` in
  `wirevision.py`) keeps the LAN cluster off the pier.
- **`wirenet.py` (new).** Real networking with the standard library only — no
  browser: `resolve()` (real DNS), `fetch()` (real HTTP/HTTPS, cert-checked,
  capped, timed out), `whoami()` (asks Cloudflare's trace for our real public IP).
  Guards: http/https only, private/loopback refused unless
  `MRFLUFFY_NET_ALLOW_PRIVATE=1`. **Everything runs on ONE daemon worker thread**
  (`wirenet.Net`) so the render loop never blocks — important on a slow machine.
  Verified live: DNS + `https://example.com` 200 and the trace endpoint returning
  our real address (`206.75.186.210`, colo YYC).
- **In the world.** Approaching within `NET_PROBE_R` starts a real probe on the
  worker and shows the real answer (status, ms, IP, bytes) in the HUD; `E` at the
  gate steps into the Exchange (section 14). Target host is `MRFLUFFY_NET_HOST` (a
  neutral reachability endpoint by default). Nothing is ever dialed that the user
  did not name.
- Verified headless: nearest-detection finds the gate (`net`), a real probe returns
  `200 in ~300ms`, the pier lets you out to radius 54 while off-pier stays capped at
  44.5, and market / word / deep all still render.

### 14. The Exchange — a hall of gates, and DuckDuckGo behind one (2026-10-11)

- **The hall.** `E` at the outward gate now opens into **the Exchange**
  (`EXCHANGE_*` consts, `_enter_exchange`/`_leave_exchange`/`_exchange_step`/
  `_draw_exchange`): a round hall past the edge with a beacon, a slow field of pale
  data-motes, a return gate back to the pier (due +z), and a ring of **service
  gates** (`EXCHANGE_GATES`) — each a theta of light that leads to a real service on
  the net. The ring holds **one gate for now**, and it is **DuckDuckGo**.
- **DuckDuckGo, for real.** Stepping into the gate opens a terminal in-world: type a
  query, press Enter, and `wirenet.duckduckgo()` really POSTs to
  `https://lite.duckduckgo.com/lite/` (no JS, no browser) and returns the real
  titles/URLs/snippets. One retry covers DDG's intermittent empty challenge page.
  Pressing a number reads that result's page — `wirenet.fetch()` grabs the real HTML
  and `_web_extract()` reduces it to readable text (scripts/styles/markup stripped)
  — served on the same in-world surface. Everything is drawn by QPainter over the GL
  scene (`_hud_exchange`, `_hud_ddg`, `_hud_ddg_reader`), never a browser window.
- `wirenet.fetch()` gained form-POST support (`data=`) and gzip/deflate decoding; the
  `Net` worker gained a `search` job; `wirenet.py --search` and the selftest exercise
  it. `AGENTS.md` §the wall documents the gate→Exchange→DuckDuckGo path.
- Verified headless (xvfb/llvmpipe): enter hall → nearest finds the `service` gate →
  open it → search returns 10 real results (~0.8–0.9 s) → open a result → reader
  shows ~40 KB of real text; hall / terminal / reader all render without exceptions,
  and market / word / deep still render.

### 15. The packet theatre — the web seen as it truly goes (2026-10-11)

- **Not a browser; a place.** The Exchange's gate no longer opens a terminal-with-a-
  results-list. Standing at a gate's **console** you type a search; the search is
  performed for real and then its **every measured phase flies across the hall as a
  stream of packet motes** — DNS query → DNS answer → SYN → SYN/ACK → ACK → TLS
  hello → request → `200`. Results are no longer a numbered list: each hangs as a
  **tablet** on the hall's ring, and you **fly to one and press `E`** to reach it.
- **Real, measured phases.** `wirenet.trace()` (new) is a raw-socket request that
  times each real phase and counts its real bytes: `dns` (host, ip, answers), `tcp`
  (ip, port), `tls` (version, cipher), `request` (method, path, bytes), `response`
  (status, bytes). `duckduckgo()` and the new `Net` `read` job both go through it, so
  search and page-read alike return a `phases` list. `_load_phases` turns those into
  the packet stream; the motes carry no invented number — every ms and byte on screen
  was measured on the wire.
- **The packet ledger.** A live in-world panel lists each phase as it lands: `dns
  query · host`, `tcp connect · ip:port`, `handshake · N ms`, `tls … · N ms`, `POST
  /lite/ · Nb`, `response · http 200 · N ms · Nb`, plus the far service's host and IP.
- **Text on light, not a window.** Opening a tablet reaches the page for real and its
  packets cross the hall; the page's readable text (markup/scripts stripped by
  `_web_extract`) **assembles on a slab of light** (`_hud_mono`) — no browser chrome.
- **Typing by proximity, flying to explore.** You type only while within
  `EXCHANGE_CONSOLE_R` of the console (`_at_console`); step/fly away and `WASD`
  returns, so you roam among the tablets. `1–9/0` open a tablet by number, `[`/`]`
  turn DuckDuckGo result pages, `Esc` closes the page then the gate, `Home` leaves.
- **In the world.** `_draw_packets` draws the console → far-service link, the far
  service as a monolith of light on the ring's edge, and each mote at the place it
  truly is along the wire. `_place_tablets` hangs up to 10 result-tablets on the ring
  and names them by projection (`_hud_tablets`).
- Verified headless (xvfb/llvmpipe): enter hall → open `ddg` → search `linux kernel`
  → 11 results, 10 tablets, 9 phase-events → 6 ledger rows with real timings (e.g.
  `tls TLSv1.3 · AES-256-GCM · 110.7 ms`, `response · http 200 · 685.2 ms · 27328b`);
  fly to a tablet + `E` → real `200 · 630ms · 19592b` page (1689 chars) with its own
  packet replay; offscreen paint exercises the tablet-label projection. Market / word /
  deep untouched.

### 16. The machine world — Phase 0: the box under your feet (2026-10-11)

- **The ask, and the line drawn first.** The user wanted the wire birds (crow/raven/
  finch) to do *real attacking*, and to "go through any wall while traveling the net"
  for "whitehat defense." Declined: turning Mr.Fluffy into an offensive/penetration
  tool — bruteforce, payloads, hack-back/retaliation — is building intrusion
  capability against other hosts, and retaliation on a spoofed source burns innocents.
  The house rule stands (`wireout.py:60`): a wire move is a passive, local,
  lab-authorized observation, never an attack on a remote host.
- **The agreed pivot — a local, defensive machine world.** Travel through **THIS**
  machine as a place: intruders as **dark figures** in the field; crow/finch flying out
  to do defense (auto **and** a manual "send the birds" menu); and an **x-ray** to see
  through walls to the door/service an intruder has touched. Everything local and
  defensive; no attack ever leaves the box; the x-ray shows where an intruder has
  *touched*, not their intent (labelled observed vs inferred).
- **Phase 0 DONE — `machinevision.py` (new).** Mirrors `wirevision.py` but points at the
  box under your feet. Reads **THIS host live** from `/proc` (`net/tcp`,`tcp6`,`udp`,
  `udp6`, per-pid `fd`→inode→pid, `comm`/`cmdline`/`status`/`exe`), `/etc/passwd`,
  `/sys/class/net`, `/proc/uptime`+`osrelease`, plus raven's own local logs
  (`/tmp/ravenheart/state.json`+`events.log`, `~/raven/ids/eve.json`,
  `~/raven/dye/contacts.json`, `~/raven/{finch,shield}/baseline.json`). It produces:
  **doors** (listening sockets + owning program), **roads** (live connections, inbound
  flagged), **inhabitants** (processes standing at sockets), **users**, **lifeline**
  read, and **dark figures** (intruders) *only* from local defensive evidence —
  lifeline strikes/guard acts, hostile lines in `events.log` that name a source,
  Suricata alerts, and public inbound roads (the last marked **inferred**).
- **Honesty rules baked in:** a `CRIT` lifeline blip ("no default route") is **not** a
  figure; an event must name a source IP/MAC to become a figure; the lifeline `strikes`/
  `guard.acts` counter is its own figure; the connection-table inbound is the weakest
  sort and says so. Touches no network, sends no packet, runs no tool, calls no model.
  CLI: `python3 machinevision.py --summary` (or bare, for JSON).
- **Verified** on this box: 4 doors (`opencode :4199`, `ollama :11434`, two UDP), 6
  roads (all outbound), 3 inhabitants, **0 dark figures** (nothing in the local logs is
  striking), 60 users (system accounts), JSON-serializable, summary renders clean.

- **Phase 1 DONE (2026-10-11) — the machine room in `wiregame.py`.** The entry-point
  decision the user was asked for was answered **"both"**: the machine is entered either
  way. Recap of what was built:
  - **A hatch on the wire floor, due +z** — the one free plaza wedge (market +x, Word −x,
    pier −z). `MACHINE_HATCH_POS = [0.0, 0.06, 23.0]`; a lit hex rim + pulsing shaft in
    `_machine_hatch()`, a floor label, and an `E` prompt. `E` enters (`_enter_machine`),
    `Home` / the up-hatch gate leaves (`_leave_machine`), `B` rebuilds live, `X` toggles
    x-ray.
  - **A button in the Vision tab bar** — `b_machine` ("⧉ the machine" / "↩ leave the
    machine"), handled by `_machine_btn`, kept in sync via the new `machine_changed`
    signal + `_refresh_machine_ui`.
  - **The room** (`MACHINE_FLOOR_Y = -160.0`, below the Exchange): terminal-green theme,
    a diagnostic ring grid floor, the shell's wall broken at each door, roads as live
    paths (inbound red / external blue / internal teal) with a crawling pulse, the core
    as a breathing hex monolith (THIS host), a door for every listening socket bearing
    the program that owns it, extra inhabitants beside the core, and **dark figures** for
    intruders — all read straight from `machinevision.build()`.
  - **x-ray** (`X`): draws the line through the wall to the door a figure has *touched*,
    only when a real port is visible in `figures[].touched` — never a guess.
  - **HUD** (`_hud_machine`): the machine's name + the honesty line (observed pid/socket/
    port vs inferred meaning; "read live from /proc, not the network"), live counts,
    kernel/uptime/x-ray state, in-world labels over the nearest doors/figures, and a
    nearest prompt.
  - **Verified**: compiles/imports; offscreen smoke test enters, draws (sky + scene +
    x-ray), lists labels, walks door→figure→return, and leaves cleanly; the tab button
    toggles both ways. `set_world` resets the room; `_net_tick` / glyph rain / `_toggle_fly`
    all early-out while inside.
  - **Next (Phase 2):** bird dispatch — see below (now DONE, read-only with an arm gate).
  - **Phase 3:** the auto-defend engine — detect → contain **on this host only** (host
    firewall block / quarantine), logged, scope-gated. No packet aimed at anyone else.
    **DONE** — see below.
  - **Phase 3 DONE (2026-10-11) — auto-defend, gated behind arm + auto.** `M` (two
    presses: confirm, then on) turns it on, but **only while the birds are armed** — two
    explicit consents. A 3s heartbeat (`_machine_autoguard_beat`) reads THIS host live
    (`machinevision.build()`) and, for every dark figure backed by real defensive
    evidence (`confidence == "observed"`; the `inferred` live-road figures are never
    auto-acted on), calls `birdguard.contain()` with an `[auto]` reason — one action per
    beat, per-source 30s cooldown, and all of birdguard's guardrails (own/gateway/
    reserved sources refused; skipped quietly). A successful catch rebuilds the room so
    the figure shows HELD, releasable with `L`. Standing the birds down (`K`) drops
    auto-defend; leaving the machine turns it off. HUD shows the auto state; it never
    sends a packet and never aims at another host. Verified offscreen: M refused while
    unarmed, two-press arm then two-press auto, observed figure auto-contained (dry),
    inferred/held/self/unusable sources all skipped, no double-fire under cooldown, and
    no action at all while unarmed. `MRFLUFFY_BIRDGURD_LIVE=0` keeps it a dry run.
  - **Phase 4 DONE (2026-10-11) — live vision (the knob).** The machine room is no longer
    a still snapshot: a "live" selector in the Vision bar (4 positions: `auto`, `off`,
    `delta`, `capture`) plus a persisting `config/wire_settings.json` (`wiresettings.py`,
    new). `off` = snapshot (`B` rebuilds). `delta` = a 1 Hz read of the kernel counters
    (`/proc/net/dev` bytes+packets per interface, `/proc/<pid>/io` for the inhabitants in
    the room, `/proc/stat`, `/proc/diskstats`), deltas smoothed and painted at 60 fps:
    motes on the ring ∝ real pkt/s, the core ring brightens with real cpu, the disk I/O
    spine rises with real bytes, and a busy writer is named in the HUD
    (`writing: <proc> N MB/s` — a file copy, seen live). `capture` = a bounded `tshark`
    stream (`_PacketReader`, `sudo -n`, only while inside the room) drawn as real packet
    motes; falls back honestly on error. `auto` benchmarks THIS host once (cores, load, a
    tiny timed loop — local only) and picks: 8+ cores/low load/fast → `capture`; any
    multi-core → `delta`; only a 1-core box → `off`. Verified offscreen: startup auto →
    `delta` (this host: 4 cores), knob switches modes and persists, delta deltas compute,
    `off` stops the timer, capture starts only inside the room and stops on leave, and the
    packet line-parser round-trips. Nothing is invented — every number is a counter read.

- **Phase 2 DONE (2026-10-11) — the birds, read-only with an explicit arm gate.** The
  user chose **"read-only now, arm later"**: the birds observe and draft; nothing acts
  until the room is explicitly armed, and even then only finch acts, host-local.
  - **`machinevision.py`** gains a read-only `birds` block (`_crow_bird`, `_finch_bird`,
    `_raven_bird`): the newest crow report's age/verdict/`CROW RETURNED` line; finch's
    baseline ssid/trusted/net, quarantine file count+bytes, exec-watch count; raven's
    heartbeat `up`/gw/guard/strikes + the `control.json` switches. Two new source rows.
    It only *reads* — the machine vision still never acts.
  - **`birdguard.py` (new)** — finch's hand, and the ONLY acting module: `contain(ip)`
    adds one team-owned rule to a private `MRFLUFFY-QUAR` iptables chain hooked into
    INPUT, so packets arriving **from that source at THIS NIC** are dropped. Never sends
    a packet, never touches another host; `release(ip)` / `release_all()` undo it. Every
    attempt is logged to `logs/birdguard.log`, the live set to `logs/birdguard.json`.
    Guardrails refuse (and log) non-IPv4, loopback/multicast/link-local/reserved, our own
    addresses, and the default gateway (containing it would cut our lifeline). `sudo -n`
    only (the host grants NOPASSWD iptables). `MRFLUFFY_BIRDGURD_LIVE=0` forces dry-run.
  - **The room** (`wiregame.py`): three low-poly birds (crow / finch / raven) perch above
    the core in a fixed ring; `E` on a bird plays its read-only finding. `K` arms (two
    presses: confirm, then arm) / stands down; `L` releases all (two presses). When armed,
    `E` on a **dark figure** asks finch to contain it — first press arms a 5s confirm,
    second press fires `birdguard.contain()` (a host-local DROP, shown as HELD, releasable
    with `L`). HUD shows the birds' live state + armed/held counts; shields/labels mark
    HELD figures green and the finch "ARMED". `_enter_machine` mirrors the real ledger,
    `_leave_machine` stands the birds down.
  - **Verified**: compiles/imports; offscreen smoke enters, paints (birds + scene), talks
    to a bird, arms, contains a figure two-press (dry), releases, leaves. `birdguard`'s
    guardrails unit-tested (gateway/self/loopback/broadcast refused; ledger round-trips
    with a fake `_sudo`). No real iptables rule was written during testing.

## Current state (end of 2026-10-11)

- `wiregame.py` modified for the ayah engine (word room), again for full screen +
  the star-cluster chapter sky, again for the whole-Qur'an cluster, the
  full-screen exit overlay, and the quick-travel bar, again for the
  reading/scroll fixes, again to scatter the chapters wide, again for the
  outward gate, again for the Exchange + its DuckDuckGo gate, and again for the
  packet theatre (section 15); `app.py`
  modified for full-screen chrome hiding; `quranworld.py`
  new; `quran.py` rewritten to open the data; `quran_data.json` (all 114 surahs)
  and `fetch_quran.py` new; **`wirenet.py` new** (the real dialer, now with
  form-POST, a DuckDuckGo search job, and the phase-timing `trace()`).
  `AGENTS.md` + `SNAPSHOT.md` updated with these sections.
- Committed `9a4c9b1` (build the Exchange + DuckDuckGo), snapshot
  `~/fakegit/mrfluffyv1.11` = `9a4c9b1`; `7029213` = v1.10. The packet-theatre work
  (section 15) is on top.
- Committed `mrfluffyv1.13` (machine world, section 16 — Phase 1 room + Phase 2 birds).
  `~/fakegit/mrfluffyv1.13` is the fresh copy. Note: this repo's real `git` is corrupt
  (`.git/objects` empty files, `HEAD` an invalid pointer; `git log/status/fsck` all fail)
  — so versions are kept as clean copies in `~/fakegit` (v1.13 newest; v1.12 unrecorded;
  v1.11 = `9a4c9b1` and v1.10 = `7029213` were real, pre-corruption commits).
  The conversation behind v1.13 is snapshotted to `snapshots/CONVERSATION_2026-10-11.md`.
- Committed `mrfluffyv1.14.2` (real TLS for the presence relay: HTTPS + pinned
  self-signed certs via `wiretls.py`; TLS replaces the homemade XOR weave, HMAC
  signatures retained; `MRFLUFFY_WIRE_TLS_CA`/`MRFLUFFY_WIRE_TLS_INSECURE` control
  trust). `~/fakegit/mrfluffyv1.14.2` is the fresh copy.
- **Machine world (section 16) — Phase 1 + Phase 2 DONE.** `machinevision.py` (a local,
  defensive model of THIS host from `/proc` + raven's logs; 0 dark figures right now) and
  `birdguard.py` **new** (finch's hand — the single host-local, reversible, logged
  containment primitive). `wiregame.py` has the machine room: a hatch on the wire floor
  due +z **and** a Vision-tab button, doors/roads/inhabitants, dark figures, the `X`
  x-ray, and the **birds** (crow/finch/raven, read-only until `K` arms them; finch may
  then contain a dark figure host-locally, `L` releases), **Phase 3 auto-defend**
  (`M`, armed-only; finch detects & contains observed figures on its own, host-local),
  and **Phase 4 live vision** (the Vision-bar live knob + `wiresettings.py`: off / delta
  / capture / auto, reading the host's own kernel counters). Section 16 is complete.
- Open threads: (a) more gates on the Exchange ring (the hall is built for a
  crowd of services — a search is the first); (b) make the amber reticle
  lock/label the nearest real object in 3D; (c) polish the market further (crowd
  density, a sounding bell at the centre column, the gate glow — dressing on top of
  the real snapshot); (d) optionally switch the relay to real TLS later (the ghost
  weave is stdlib-protected, honest about being a weave, not a vow); (e) let surah
  themes/motifs be tuned. House rules stand: ground truth only, no invented data,
  flavour not story; the market's platforms/balance/crowd are real, the floor and
  colours are dressing; the Quran room's text is a faithful local copy of the whole
  mushaf, nothing in it is ever depicted, and each generated world is an honest
  impression of the verse's named images — never a claim about its meaning; and the
  outward gate is the first step out for real — it opens into the Exchange, whose
  gates (DuckDuckGo, so far) really serve the web, and nothing is ever dialed that
  the user did not name.

## Current state (v1.15 — 2026-10-12)

The wire became the whole app and a **game**.
- **Market readouts + lean arrows** (`wiregate.py` + `wiregame.py`): each platform
  shows its per-interval SignalBot read (the bot's own written snapshot, replayed)
  and a bold green/red/amber/grey LEAN arrow; `wiregate._signal_lean()` is a
  transparent vote over the bot's named fields. The world never runs the bot.
- **Candle room** (`candlevision.py` new + `wiregame.py`): the market's centre
  column is a door; the interval is chosen there. `blackhorse/logs/candles_<iv>.json`
  (real Kraken OHLCV) is joined to SignalBot's own rows with the ±5% guard from
  `trade/validate_playbook.py` (shows `rows_joined / n`); fly to a candle for its
  OHLCV (observed) + the bot's read + what happened next (inferred).
- **Agent-settings `?` fix** (`wiregate.py` + `wiregame.py`): `PROFILE_DEFAULTS`
  from `decider.json` + `base = cfg/policy`; the editor shows the effective value
  (agent_6 = 0.15/0.80) and `_do_save` writes only the fields that really changed.
- **News channel dropped.** `app.py` rewritten (no news/uplink UI), boots straight
  into **Wire Vision full screen**; `daemon.py` runs only the wire cycle;
  `wireout.py` carries its own `_load_json`/`_parse` (no `readout`/`news` import).
  `readout.py`/`news.py` remain on disk but unreferenced at runtime.
- **In-game menu** (`wiregame.py`): Tab or "☰ menu" → Settings (walk/fly/boost/look
  speed, live vision, real names), Controls (every key + ↑↓←→), Resume, Toggle full
  screen, and Close Mr.Fluffy (→ app quit).
- **Flight is fun** (`wiresettings.py` + `wiregame.py`): walk/fly/boost/look knobs
  (clamped, persisted); **Shift** boosts walking and flying; seeded **speed lines**
  fly only when you are really moving fast; a small `N u/s ⚡ ×boost` tag.
- **Smooth mouse-look**: **left-click** captures the mouse (hidden, pinned to
  centre) and moving turns the view while you keep walking/flying; **Esc** or
  **right-click** frees it; the menu frees it and closing re-grabs it.
- **Menu glitch fixed**: overlays/the market panel are children of the
  `QOpenGLWidget` (they compose every frame), and `_reflow_overlays()` activates the
  layout + re-places on the **next event-loop tick** (`QTimer.singleShot(0, …)`) once
  children are polished — so a switched page is sized right at once (291 → 343 →
  496), with no resize nudge.
- Snapshot of this run: `~/fakegit/mrfluffyv1.15` (clean copy, no `.git`) +
  `snapshots/CONVERSATION_2026-10-12.md`. `AGENTS.md` still documents the removed
  news channel — a news-removal pass is the natural doc follow-up.

## Git repair (2026-10-12)

The repo's `git` had gone corrupt (three loose objects truncated to 0 bytes —
the commit `HEAD` pointed at, a tree, and a blob — plus stray nulls in the
reflog). It was **repaired**, not re-initialised, so the full history is back:
- the `.git` dir was backed up first to `~/mrfluffy-git-broken-20261012-000523.tgz`;
- `master` was repointed at the newest **intact** commit `64fa708` (machinevision
  Phase 0 — the newest entry in `.git/logs/HEAD`; the truncated `6734eae9…` was
  never reachable from any real commit);
- the three empty objects and the stale index were removed, and the stray null
  bytes stripped from the reflogs.
- `git fsck` is clean; the branch now carries the whole history plus
  **`8ad1672` mrfluffy: … the wire a game (v1.15)** as the working-tree commit.

The old (broken) `.git` is backed up at `~/mrfluffy-git-broken-20261012-000523.tgz`;
do not delete it until the repair has proven itself.
