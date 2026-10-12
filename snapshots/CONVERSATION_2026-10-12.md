# Conversation snapshot — 2026-10-11 → 2026-10-12 (mrfluffyv1.15)

## Objective
- Mr.Fluffy "Wire Vision" — keep growing the playable wire. Across this run:
  fold in the **market signal readouts + lean arrows** and the **candle room**,
  fix the **agent-settings `?`**, then turn the wire into a **game**: **drop the
  news channel** entirely, **boot straight into Wire Vision full screen**, add an
  **in-game menu**, and make **flight fun** (speed, Shift boost, motion/speed
  lines, smooth captured mouse-look). Finally, fix the **menu composite/size
  glitch** (it only appeared after a window resize).

## Important Details
- Hard house rules (unchanged): ground truth only, never invent a number/packet/
  device; observed vs inferred kept distinct; the world is a *memory* except the
  outward gate; the machine room reads THIS host's own tables and only ever
  drops packets *from* a source at THIS NIC; the Qur'an is never depicted.
- Widget is **PyQt6**. Offscreen smoke tests run the Python path but GL does not
  render (`QOpenGLWidget: No fbo`); that is expected.
- **Real `git` was corrupt** (`.git/objects` had three 0-byte files; `HEAD` =
  `6734eae9…` pointed at an empty object; `git status/log/fsck` all failed) — and
  was **repaired this session** (see the Git repair section in `SNAPSHOT.md`): the
  branch was repointed to the newest intact commit (`64fa7083`), the empty objects
  and stale index removed, the reflog nulls stripped, and the real history is back
  with a fresh commit (`8ad1672`) on top. A backup of the broken `.git` sits at
  `/home/a/mrfluffy-git-broken-20261012-000523.tgz`.
- Versions are also kept as **clean copies in `~/fakegit`** — newest now
  **`~/fakegit/mrfluffyv1.15`** (v1.14.2 was the prior one; v1.14 / v1.13 / …).
- Versioning ritual (this is "commit" for this repo): **SNAPSHOT.md entry +
  `snapshots/CONVERSATION_<date>.md` + a clean `~/fakegit/mrfluffyvX.Y` copy
  (excludes `.git`; the previous copies do include `logs/` and `__pycache__`).**

## Work State
### Completed
- **Market: SignalBot read + lean arrow, in-world** (`wiregate.py`, `wiregame.py`).
  `wiregate.snapshot()` now attaches, per interval its agent trades
  (`policy_overrides.strategy_intervals`, else the interval in `channels`), the
  bot's own saved read (`logs/signal_latest.json` / `logs/signals/<PAIR>.json`):
  action, confidence, strength, RSI, spread, MA10−MA30, MA20/MA50 cross,
  range/stop/target, advisor bands, and the 60m strength gate. `_signal_lean()` is
  a transparent vote over the bot's named fields; `wiregame._market_signal_panels`
  floats the readout beside each platform and a bold green/red/amber/grey arrow
  stands over it. It is the bot's *written snapshot, replayed* — the world never
  runs the bot.
- **Candle room** (`candlevision.py` new + `wiregame.py`). The market's centre
  column is a door; the interval is chosen there (`available()` / `build(iv)` for
  15m/60m/240m/1440m). `blackhorse/logs/candles_<iv>.json` (real Kraken OHLCV) is
  joined to SignalBot's own rows (`sb_rows.json` / `sb_rows_<iv>_dump.json`) with
  the **±5% price guard** from `blackhorse/trade/validate_playbook.py`; it shows
  `rows_joined / n`. Fly to a candle for its OHLCV (observed) + the bot's read +
  what happened next (inferred); B rebuilds, Home leaves.
- **Agent-settings `?` fix** (`wiregate.py`, `wiregame.py`). Root cause: the
  editor read `prof["policy"]` but the effective policy is
  `agents.policy_for()` = decider defaults → profile `cfg` → agent
  `policy_overrides`. Added `wiregate.PROFILE_DEFAULTS` (from
  `blackhorse/config/decider.json`, set by `_refresh_profiles()`);
  `_open_editor` builds `base = dict(PROFILE_DEFAULTS)` then `base.update(cfg or
  policy)`; `_do_save` only writes fields that actually changed from the effective
  value when there was no original override. Verified: agent_6 shows 0.15/0.80;
  an unchanged save writes only the real overrides.
- **News channel dropped — the wire is the app now.**
  - `app.py` rewritten: no news panel/worker/timer; title "Mr.Fluffy — the wire";
    boots straight into **Wire Vision full screen**; left panel is wire controls
    only; `closeEvent` shuts down cleanly.
  - `daemon.py`: news cycle removed; only the **wire** cycle runs (`wireout.run`).
  - `wireout.py`: no longer imports `readout`/`news` — it carries its own local
    `_load_json`/`_parse` (using the `notes` key). Verified at startup that
    `news` and `readout` are **not** in `sys.modules`.
  - `readout.py` / `news.py` remain **on disk, unreferenced at runtime**.
- **In-game menu** (`wiregame.py`). A floating `_GameMenu(QFrame)` over the world:
  **Tab** or the top-left **"☰ menu"** opens it; **Esc/Tab** closes it. Pages:
  **Settings** (walk speed, fly speed, boost, look sensitivity, live vision, real
  names), **Controls** (every key, with ↑↓←→), and home with **Resume**, **Toggle
  full screen**, and **Close Mr.Fluffy** (→ `close_requested` → app quits). While
  it is open it holds the keyboard and frees the mouse.
- **Flight is fun** (`wiresettings.py`, `wiregame.py`).
  - `wiresettings.DEFAULT` gains `walk_speed` 1.0, `fly_speed` 1.9, `boost_mult`
    2.2, `look_sensitivity` 1.0 (clamped); persisted in
    `config/wire_settings.json`.
  - `WireGLWidget` reads them (`reload_game_settings`); `_boost()` returns
    `boost_mult` while **Shift** is held. Room/flight speed =
    `13.0 * move_mult * boost * dt`; walk = `9.0 * walk_mult * boost * dt`.
  - **Speed lines**: `_init_speedlines()` builds 96 seeded radial streaks;
    `_speed_lines()` draws them, intensity gated on the real carried speed
    (`_speed_now`), so they fly only when you actually move fast; a small
    `N u/s` tag + `⚡ ×boost` reads out at bottom-left.
- **Smooth mouse-look** (`wiregame.py`). Replaced click-drag with a **captured**
  look: **left-click** the world grabs the mouse (cursor hidden + pinned to
  centre); moving the mouse turns the view in any direction **while you keep
  walking or flying** — no edge to run into. **Esc** or **right-click** frees it;
  opening the menu frees it, closing re-grabs it. Esc frees the mouse *first*
  (a second Esc leaves full screen). A hint line shows while uncaptured.
- **Menu glitch fixed** (`wiregame.py`). Two causes:
  1. The frame's layout sizeHint was **stale** right after a page switch, so
     `place_overlays` sized it to ~26px (border only) until a resize relaid it.
  2. Overlays were **siblings** of the `QOpenGLWidget`; a widget shown *after*
     the GL FBO exists only composited on the next resize.
  Fix: reparent overlays/the market panel to the **GL widget** (the documented
  path for widgets over a `QOpenGLWidget`) and add `_reflow_overlays()` which
  activates the layout, re-places, repaints the stack, and **re-places on the
  next event-loop tick** (`QTimer.singleShot(0, …)`) once children are polished.
  Verified: menu pages now size correctly at once (291 → 343 → 496 → 291) with no
  resize nudge.
- Verified offscreen: `py_compile` clean for `wiregame.py`, `wiregate.py`,
  `wiresettings.py`, `app.py`, `daemon.py`, `wireout.py`; the `vtest`/`vtest2`/
  `vtest3` smoke suites still pass; menu/look/speed scratch tests pass; app+daemon
  import with `news`/`readout` absent.

### Blocked
- None code-wise. Real `git` was corrupt but is now **repaired** (see Important
  Details + the `SNAPSHOT.md` "Git repair" section).
- `AGENTS.md` still describes the **removed news channel** (Channel 1) — it is
  otherwise current (market / Word / machine / wire sections are present). A
  news-removal pass on `AGENTS.md` is the natural doc follow-up.

## Next Move (suggested)
- Update `AGENTS.md`: drop Channel 1 (news) and document the game menu, the
  captured mouse-look, the speed/boost knobs and speed lines.
- Then the open threads from `SNAPSHOT.md`: more Exchange gates; the amber
  reticle locking the nearest real object in 3D; market polish; surah motif
  tuning; optional per-connection motion if `nf_conntrack` ever appears.
- If asked to version again: bump to `~/fakegit/mrfluffyv1.16` + SNAPSHOT entry +
  this file.

## Relevant Files
- `/home/a/mrfluffy/wiregame.py`: the whole Vision world — market readouts/lean
  arrows, candle room, game menu, speed lines, captured mouse-look, overlay reflow.
- `/home/a/mrfluffy/wiregate.py`: market model — signal attach + `_signal_lean`,
  `PROFILE_DEFAULTS`/`_refresh_profiles`, effective-policy edit boundary.
- `/home/a/mrfluffy/candlevision.py`: NEW — candle-room model (OHLCV × bot rows join).
- `/home/a/mrfluffy/wiresettings.py`: the game knobs (walk/fly/boost/look) + live-vision mode.
- `/home/a/mrfluffy/app.py`: rewritten — no news, boots into Wire Vision full screen.
- `/home/a/mrfluffy/daemon.py`: wire-only cycle.
- `/home/a/mrfluffy/wireout.py`: self-contained wire readout (no `readout`/`news` import).
- `/home/a/mrfluffy/config/wire_settings.json`: the persisted game knobs + live mode.
- `/home/a/mrfluffy/SNAPSHOT.md`, `/home/a/mrfluffy/AGENTS.md`: state docs (AGENTS.md news section now stale).
- `~/fakegit/mrfluffyv1.15` = this conversation's clean snapshot (excludes `.git`).
