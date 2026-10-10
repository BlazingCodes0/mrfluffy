"""Mr.Fluffy brain — the opencode client + call budget.

Drives a PERSISTENT headless opencode server over HTTP (the same idiom
blackhorse's skin/brain.py settled on): a warm session keeps the model + its
context loaded, so readouts are fast, tool-capable, and never pay a cold-start
`opencode run` spawn. Budget (min gap + max calls/hour) is enforced here so a
runaway loop can never hammer the model.

Paths, in preference order:
  1. HTTP  -> the running `opencode serve` on loopback (mrfluffy-serve.service),
              warm session, tools available. Fast path.
  2. sandboxed CLI -> if the server is down, a one-shot `opencode run` inside a
              systemd-run read-only-home sandbox while egress is firewalled to
              loopback + DNS + api.opencode.ai only (legacy containment).

Security note: with the server path the model can actually use tools (that's the
point — Mr.Fluffy will do many things), so containment is budget-bounded rather
than OS-bounded. The egress lockdown/sandbox still guards the CLI fallback.
"""
import json, os, shutil, signal, socket, subprocess, sys, time, urllib.request
from pathlib import Path

FLUFFY = Path.home() / "mrfluffy"
SETTINGS = FLUFFY / "config" / "fluffy_settings.json"
BUDGET = FLUFFY / "logs" / "fluffy_budget.json"
SESSION_FILE = FLUFFY / "logs" / "readout_session.id"
GUARD_PID = FLUFFY / "logs" / "guard.pid"
API_HOST = "api.opencode.ai"
OPENCODE_BIN = shutil.which("opencode") or str(Path.home() / ".opencode" / "bin" / "opencode")

EGRESS_TABLE = "inky_fluffy_guard"
_SANDBOX_PROPS = [
    "-p", "ProtectSystem=strict",
    "-p", "ProtectHome=read-only",
    "-p", "ReadWritePaths=/home/%s/.local/share/opencode" % os.getenv("USER", "a"),
    "-p", "PrivateTmp=yes",
    "-p", "PrivateDevices=yes",
    "-p", "NoNewPrivileges=yes",
]


def settings() -> dict:
    defaults = {"enabled": True, "min_gap_seconds": 120, "max_calls_per_hour": 12,
                "opencode_cmd": "opencode", "opencode_timeout_seconds": 300,
                "server_host": "127.0.0.1", "server_port": 4199,
                "serve_service": "mrfluffy-serve.service"}
    try:
        return {**defaults, **json.loads(SETTINGS.read_text())}
    except Exception:
        return defaults


def _budget() -> dict:
    try:
        b = json.loads(BUDGET.read_text())
        if not isinstance(b, dict):
            b = {}
    except Exception:
        b = {}
    b.setdefault("calls", [])
    return b


def _save_budget(b: dict):
    BUDGET.parent.mkdir(parents=True, exist_ok=True)
    try:
        BUDGET.write_text(json.dumps(b))
    except OSError:
        pass


def status() -> dict:
    s = settings()
    b = _budget()
    now = time.time()
    calls = [c for c in b.get("calls", []) if now - c < 3600]
    last = max(calls) if calls else 0
    gap_ok = (now - last) >= s.get("min_gap_seconds", 120)
    rate_ok = len(calls) < s.get("max_calls_per_hour", 12)
    return {
        "enabled": s.get("enabled", True),
        "calls_last_hour": len(calls),
        "max_calls_per_hour": s.get("max_calls_per_hour", 12),
        "min_gap_seconds": s.get("min_gap_seconds", 120),
        "seconds_until_next": max(0, int(s.get("min_gap_seconds", 120) - (now - last))) if last else 0,
        "allowed": bool(s.get("enabled", True)) and gap_ok and rate_ok,
    }


def _mark_call():
    b = _budget()
    now = time.time()
    b["calls"] = [c for c in b.get("calls", []) if now - c < 3600] + [now]
    _save_budget(b)


def reset():
    _save_budget({"calls": []})


def _online(max_age: float = 30.0) -> bool:
    """Cheap connectivity gate, cached ~30s. When offline we must NOT spawn
    opencode and hang to the timeout (the old failure mode)."""
    cache = getattr(_online, "_c", {"ts": 0.0, "ok": None})
    if cache["ok"] is not None and time.time() - cache["ts"] < max_age:
        return cache["ok"]
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=2):
            ok = True
    except OSError:
        ok = False
    cache.update(ts=time.time(), ok=ok)
    _online._c = cache
    return ok


# ---- warm session ------------------------------------------------------------

def session() -> str | None:
    try:
        s = SESSION_FILE.read_text().strip()
    except OSError:
        return None
    return s if s.startswith("ses_") else None


def set_session(sid: str):
    if not str(sid).startswith("ses_"):
        raise ValueError("session id must start with 'ses_'")
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(str(sid).strip())


def server_url() -> str:
    s = settings()
    return f"http://{s['server_host']}:{s['server_port']}"


def _http(method: str, path: str, payload: dict | None = None,
          timeout: float = 10) -> dict:
    url = server_url() + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def server_up() -> bool:
    try:
        _http("GET", "/api/session", timeout=2)
        return True
    except Exception:
        return False


def ensure_server() -> bool:
    """Start the serve unit if it's down. Returns True when up."""
    if server_up():
        return True
    try:
        subprocess.run(["systemctl", "--user", "start", settings()["serve_service"]],
                       capture_output=True, timeout=20)
    except Exception:
        pass
    for _ in range(30):  # up to ~60s for a cold opencode serve
        if server_up():
            return True
        time.sleep(2)
    return False


def start_server() -> bool:
    """Manual/long-lived start: launch `opencode serve` detached (no systemd)."""
    if server_up():
        return True
    try:
        s = settings()
        subprocess.Popen(
            [OPENCODE_BIN, "serve", "--port", str(s["server_port"]),
             "--hostname", s["server_host"]],
            cwd=str(FLUFFY), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return False
    for _ in range(30):
        if server_up():
            return True
        time.sleep(2)
    return False


def _ask_via_http(sess: str, prompt: str, timeout: int) -> str | None:
    """Fast path: POST a prompt into the warm session, poll for the reply."""
    try:
        post = _http("POST", f"/api/session/{sess}/prompt",
                     {"prompt": {"text": prompt}}, timeout=30)
    except Exception as e:
        return None if server_up() else f"(server error: {e})"
    admitted_ts = post.get("data", {}).get("timeCreated", 0)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msgs = _http("GET", f"/api/session/{sess}/message", timeout=30)
        except Exception:
            time.sleep(1)
            continue
        parts, done, err = [], False, None
        for m in msgs.get("data", []):
            if m.get("type") != "assistant":
                continue
            if (m.get("time", {}).get("created") or 0) <= admitted_ts:
                continue  # only the reply admitted by THIS prompt
            content = m.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                        parts.append(part["text"])
            elif isinstance(content, str) and content:
                parts.append(content)
            if m.get("finish") and m.get("finish") != "tool-calls":
                done = True
            if m.get("error"):
                err = json.dumps(m.get("error"))[:300]
        if parts or done or err:
            text = "\n".join(parts).strip()
            if err and not text:
                text = f"(brain error: {err})"
            return text or (f"(brain error: {err})" if err else None)
        time.sleep(1.0)
    return None


# ---- sandboxed CLI fallback (legacy containment) -----------------------------

def opencode_bin() -> str:
    return OPENCODE_BIN


def _nft(*args):
    return subprocess.run(["sudo", "-n", "nft", *args], capture_output=True, text=True)


def _api_addresses() -> tuple[list, list]:
    v4, v6 = [], []
    try:
        infos = socket.getaddrinfo(API_HOST, 443, type=socket.SOCK_STREAM)
    except Exception:
        infos = []
    for fam, *_rest, sockaddr in infos:
        ip = sockaddr[0]
        if ":" in ip:
            v6.append(ip)
        else:
            v4.append(ip)
    v4 += ["104.17.185.205"]
    v6 += ["2606:4700:78::90:0:140", "2606:4700:10::6814:2011", "2606:4700:10::ac42:ad95"]
    return sorted(set(v4)), sorted(set(v6))


def _lockdown_egress() -> tuple[list, list]:
    _release_egress()
    v4, v6 = _api_addresses()
    ruleset = [f"table inet {EGRESS_TABLE} {{",
               f"  set api_v4 {{ type ipv4_addr; flags interval; elements = {{ {', '.join(v4)} }} }}",
               f"  set api_v6 {{ type ipv6_addr; flags interval; elements = {{ {', '.join(v6)} }} }}",
               "  chain out { type filter hook output priority 0; policy drop;",
               "    ct state established,related accept", "    oif lo accept",
               "    udp dport 53 accept", "    tcp dport 53 accept",
               "    ip daddr @api_v4 accept", "    ip6 daddr @api_v6 accept }",
               "  chain in { type filter hook input priority 0; policy drop;",
               "    ct state established,related accept", "    iif lo accept }", "}"]
    r = subprocess.run(["sudo", "-n", "nft", "-f", "-"],
                       input="\n".join(ruleset) + "\n", capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"nft egress lockdown failed: {r.stderr.strip()}")
    GUARD_PID.write_text(str(os.getpid()))
    return v4, v6


def _release_egress():
    _nft("delete", "table", "inet", EGRESS_TABLE)
    try:
        GUARD_PID.unlink()
    except FileNotFoundError:
        pass


def clear_stale_guard() -> bool:
    """Heal a stranded egress lockdown left by a killed process."""
    if _nft("list", "table", "inet", EGRESS_TABLE).returncode != 0:
        return False
    try:
        pid = int(GUARD_PID.read_text().strip())
        alive = os.path.exists(f"/proc/{pid}")
    except Exception:
        pid, alive = None, False
    if alive:
        return False
    try:
        _release_egress()
    except Exception:
        return True
    return True


def _ask_via_sandbox(prompt: str, timeout: int) -> str | None:
    """Legacy one-shot path: sandboxed `opencode run` with egress lockdown."""
    if not shutil.which("systemd-run"):
        return None
    clear_stale_guard()
    try:
        _lockdown_egress()
    except Exception:
        return None
    try:
        try:
            r = subprocess.run(
                ["systemd-run", "--user", "--pipe", "--wait", "--collect", "--quiet",
                 *_SANDBOX_PROPS, "--", OPENCODE_BIN, "run", prompt],
                capture_output=True, text=True, cwd=str(FLUFFY), timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        finally:
            try:
                _release_egress()
            except Exception:
                pass
        if r.returncode != 0:
            return None
        return (r.stdout or "").strip() or None
    finally:
        try:
            _release_egress()
        except Exception:
            pass


# ---- ask ---------------------------------------------------------------------

def ask(prompt: str) -> dict:
    """Return {"text": str, "source": "http"|"sandbox"|"online"|"budget",
               "error": str|None}."""
    if not status()["allowed"]:
        return {"text": "", "source": "budget", "error": "budget: cooling down"}
    timeout = int(settings().get("opencode_timeout_seconds", 300))
    sess = session()

    if sess:
        if ensure_server():
            ans = _ask_via_http(sess, prompt, timeout)
            if isinstance(ans, str) and not ans.startswith("(server"):
                _mark_call()
                return {"text": ans, "source": "http", "error": None}
            if ans and ans.startswith("(server"):
                return {"text": "", "source": "http", "error": ans}
    elif server_up():
        return {"text": "", "source": "http", "error": "no session id provisioned"}

    # fallback: sandboxed one-shot (only when truly offline-safe to skip, else call)
    if not _online():
        return {"text": "", "source": "online",
                "error": "offline — skipped; will retry when back online"}
    ans = _ask_via_sandbox(prompt, timeout)
    if ans:
        _mark_call()
        return {"text": ans, "source": "sandbox", "error": None}
    return {"text": "", "source": "http", "error": "no answer from brain (server or sandbox)"}


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(json.dumps(status(), indent=2))
    elif "--reset" in sys.argv:
        reset(); print("budget reset")
    elif "--session" in sys.argv:
        print(json.dumps({"session": session(),
                          "server_url": server_url(),
                          "server_up": server_up()}))
    elif "--start" in sys.argv:
        print("server up:", start_server())
    else:
        p = sys.argv[1] if len(sys.argv) > 1 else "Say hi in one sentence."
        print(json.dumps(ask(p), indent=2))