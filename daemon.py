"""Mr.Fluffy daemon.

Every check_interval_seconds: refresh news, if the fingerprint changed AND the
budget allows, run a full readout cycle. Logged to logs/daemon.log. Uses a flock
so two daemons can never overlap.

CLI:  python3 daemon.py              # run forever
      python3 daemon.py --once       # one check cycle then exit
"""
import fcntl, json, time
from pathlib import Path

import news
import readout
import brain

FLUFFY = Path.home() / "mrfluffy"
LOG = FLUFFY / "logs" / "daemon.log"
LOCK = FLUFFY / "logs" / "daemon.lock"


def _log(msg: str):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with LOG.open("a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _interval() -> int:
    cfg = FLUFFY / "config" / "fluffy_settings.json"
    try:
        return int(json.loads(cfg.read_text()).get("check_interval_seconds", 300))
    except Exception:
        return 300


def one_cycle():
    try:
        if brain.clear_stale_guard():
            _log("healed stale egress lockdown (prior process died mid-call)")
        r = readout.run(force=False)
    except Exception as e:
        _log(f"cycle error: {e}")
        return
    if r.get("text"):
        _log(f"readout ok fp={r['fingerprint']} conf={r['entry']['readout'].get('confidence')}")
    elif r.get("skipped"):
        _log(f"skipped (no change) fp={r['fingerprint']}")
    else:
        _log(f"no readout: {r}")


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    lock_fh = open(LOCK, "a+")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another daemon is already running"); return
    if "--once" in __import__("sys").argv:
        one_cycle()
        return
    _log("daemon up")
    while True:
        try:
            one_cycle()
        except Exception as e:
            _log(f"cycle error: {e}")
        time.sleep(_interval())


if __name__ == "__main__":
    main()