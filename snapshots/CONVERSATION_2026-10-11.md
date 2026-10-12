# Conversation snapshot — 2026-10-11 (mrfluffyv1.14)

## Conversation summary (the memory handed forward)

## Objective
- Mr.Fluffy "Wire Vision" — continue building **§16 the machine room** (THIS host as a
  place you walk). Across this session: **finished Phase 2 (the birds)**, built
  **Phase 3 (auto-defend)**, and built **Phase 4 (live vision — the realtime knob)**.
  Section 16 is now complete.

## Important Details
- Hard house rules: ground truth only, never invent a number/packet/device; the machine
  vision reads THIS host's own tables (it is not an intrusion and never leaves the box);
  any containment stops at this NIC and is never aimed at another host.
- `machinevision.py` **must stay non-acting** (pure `/proc` + local-log reads). The acting
  hands are `birdguard.py` (containment) and, in Phase 4, the capture reader.
- Widget is **PyQt6** (not PyQt5). Offscreen smoke tests work but GL doesn't render
  (`QOpenGLWidget: No fbo`); the "QPainter … not active" warnings are expected offscreen —
  the Python path still executes and catches errors. A full `paintGL()` still prints
  "painted ok" with no Python exception.
- **Real `git` is corrupt** (`.git/objects` empty files, `HEAD` an invalid pointer;
  `git log/status/fsck` all fail). Do NOT repair it. Versions are kept as clean copies in
  `~/fakegit` (v1.14 newest; v1.12 unrecorded; v1.11 = `9a4c9b1`, v1.10 = `7029213` were
  real, pre-corruption commits).
- Host facts: 4 cores, load ~2–4; `tshark`, `tcpdump`, `iptables` present; `sudo -n` works
  (NOPASSWD). Self IPv4s `127.0.0.1`, `172.20.10.2`; gateway `172.20.10.1`. `/proc/net/dev`,
  `/proc/stat`, `/proc/diskstats`, `/proc/<pid>/io` all readable; `/proc/net/nf_conntrack`
  **missing** (no cheap per-flow byte counts); Python has **no stdlib inotify**.
- Machine-room keys now: `E` interact, `B` rebuild, `X` x-ray, `Home` leave, `K` arm birds
  (two-press), `L` release (two-press), `M` auto-defend (two-press), WASD/Space/C fly.
- The crow's `192.168.1.64 / api.kraken.com / fapi.binance.com / www.coindesk.com` findings
  are **real**, and are this machine's OWN traffic: the crows ran on this host's `wlan0`
  while it held `192.168.1.64`; `api.kraken.com` is BLACKHORSE's configured exchange
  (`exchanges.json` `"active":"kraken"`), `www.coindesk.com` is `news.py`'s Coindesk RSS.
  The crow's "trading app polling prices" verdict was right — the house doing it to itself.

## Work State
### Completed
- **Phase 2 (birds) wiring finished** (`wiregame.py`): `_nearest_machine` gains
  `machine_bird`; `_interact` machine branch calls `_machine_figure_talk` (read-only, or a
  two-press `E` contain when armed → `birdguard.contain()`), `_machine_bird_talk`,
  `_machine_arm_toggle` (`K`), `_machine_release_toggle` (`L`); `K`/`L` in keyPress;
  `_hud_machine` birds line + held count + figure/bird prompts. Smoke-tested; docs updated.
- **Commit ritual v1.13** → SNAPSHOT entry + `~/fakegit/mrfluffyv1.13` (clean copy, no
  `.git`) + `snapshots/CONVERSATION_2026-10-11.md`. Later extended to v1.14.
- **Kraken/CoinDesk investigation** (read-only): confirmed the domains are real and are
  this host's own outbound traffic (blackhorse → Kraken; news.py → Coindesk). No files
  changed.
- **Phase 3 — auto-defend** (`wiregame.py`): `machine_autoguard` + `_machine_auto_until` +
  `_auto_attempts` state; a 3s `_auto_timer` → `_machine_autoguard_beat()`; `M` toggles it
  (`_machine_autoguard_toggle`, two-press) **only while the birds are armed**; the beat
  reads `machinevision.build()` live and contains each **observed** figure (never the
  `inferred` road figures) via `birdguard.contain(..., reason="[auto] …")` — one action per
  beat, 30s per-source cooldown, all birdguard guardrails; a catch rebuilds the room
  (HELD). Disarm (`K`) and leaving the room drop auto. HUD auto line. Verified offscreen:
  M refused unarmed; two-press arm + two-press auto; observed contained (dry); inferred /
  held / self / unusable skipped; no double-fire; nothing acts unarmed.
- **Phase 4 — live vision (the knob)** (`wiregame.py` + **`wiresettings.py` new**):
  `live_mode`/`live_effective`/`_live`/`_live_prev`; a `_live_timer`; `_apply_saved_live_mode`
  at startup; `set_live_mode`. Modes: **off** (snapshot), **delta** (1 Hz read of
  `/proc/net/dev` bytes+packets, `/proc/<pid>/io` per inhabitant, `/proc/stat`,
  `/proc/diskstats`; deltas smoothed and painted at 60 fps — ring motes ∝ real pkt/s, core
  ring ∝ real cpu, disk I/O spine ∝ real bytes, HUD `writing: <proc> N MB/s` names a live
  file copy), **capture** (`_PacketReader`: bounded `tshark` stream, `sudo -n`, only inside
  the room, drawn as real packet motes; honest fallback on error), **auto**. `auto`
  benchmarks THIS host once (`wiresettings.detect()`: cores, loadavg, min-of-3 tiny timed
  loop — local only) → 8+ cores/low load/fast = `capture`; any multi-core = `delta`; only a
  1-core box = `off`. A **live knob** (`QComboBox`) in the Vision bar; persisted to
  `config/wire_settings.json`; tooltip shows the resolved decision. Verified offscreen:
  startup `auto → delta` on this 4-core host; knob switches + persists; deltas compute;
  `off` stops the timer; capture starts only inside the room and stops on leave; parser
  round-trips. No real capture spawned in tests.
- Docs updated throughout: `AGENTS.md` (birds / auto-defend / live-vision paragraphs),
  `SNAPSHOT.md` (§16 Phases 2–4 marked DONE + v1.13/v1.14 commit notes).

### Blocked
- None code-wise. Real `git` is corrupt (versions = `~/fakegit` clean copies).
- Testing caution: never run `birdguard.contain(apply=True)` or start a real `capture` in
  smoke tests; use `MRFLUFFY_BIRDGURD_LIVE=0` and monkeypatched `_PacketReader.start`.

## Next Move (suggested)
- Section 16 is complete. Natural next work: the open threads in `SNAPSHOT.md` (more
  Exchange gates; the amber reticle locking the nearest real object in 3D; market polish;
  optional real-TLS relay; surah motif tuning). Or: give the live layer per-connection
  motion if `/proc/net/nf_conntrack` ever becomes available.
- If asked to version again: bump to `~/fakegit/mrfluffyv1.15` + SNAPSHOT entry + this file.

## Relevant Files
- `/home/a/mrfluffy/wiregame.py`: the whole Vision world — machine room, birds, auto-defend, live vision, the knob.
- `/home/a/mrfluffy/wiresettings.py`: NEW — the live-vision knob's persistence + the local auto-detect benchmark.
- `/home/a/mrfluffy/birdguard.py`: finch's hand — host-local reversible iptables containment + guardrails + ledger.
- `/home/a/mrfluffy/machinevision.py`: reads THIS host (/proc + raven logs) + the read-only birds block; must stay non-acting.
- `/home/a/mrfluffy/config/wire_settings.json`: the persisted live mode.
- `/home/a/mrfluffy/SNAPSHOT.md`, `/home/a/mrfluffy/AGENTS.md`: state docs (now current through Phase 4).
- `/home/a/raven/*` (=~/raven): crow/finch/raven state read read-only by `machinevision._birds()`.
- `~/fakegit/mrfluffyv1.14` = this conversation's clean snapshot (excludes `.git`).
