"""wiregame.py — WIRE VISION, the low-poly first-person wire.

A QOpenGLWidget that renders wirevision.py's world model as a low-poly place you
can actually walk: WASD to move, drag / arrows to look, E to interact. You spawn
on the floor (your LAN) beside the heart; devices are low-poly dwellers, their
DNS names are gates, crows drift overhead, IDS alerts are rifts. Fall down the
central well and you ride the protocol stack — the talking place (application),
the sorting office (transport), the addressing plains (internet), the wire itself
(link) — down to the sparks: the last electron, the edge. Step past the edge and
you dive into the sea of information: it is unbounded and never bottoms out, but
below the edge it holds no named entity and carries no data — only the descent.

Everything you see is drawn from local ground truth (wirevision.py). This module
never touches the network and never calls the brain. Terminology is friendly by
default; the real term is one keypress away ('T'), so nobody is left behind.

Standalone:  python3 wiregame.py
"""
from __future__ import annotations
import math, os, random, sys, time, hashlib, html, re, collections, threading

from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPen, QSurfaceFormat,
                         QCursor, QRadialGradient, QShortcut, QKeySequence)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QSplitter, QTextBrowser, QVBoxLayout, QWidget)

import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

import wirevision
import wiregate
import wirenet
import machinevision
import birdguard
import wiresettings
import quran
import quranworld
import candlevision
from wiregate import MARKET_FLOOR_Y, MARKET_R, RETURN_GATE_POS

MARKET_GATE_POS = [23.0, 0.06, 0.0]   # the tall portal to BlackHorse — its own cleared plaza, due +x

# the OUTWARD GATE — the one place past the edge that really goes out. A pier
# runs off the floor, over the open sea, due −z, to a gate that dials the real
# net (wirenet: real DNS, real HTTP/HTTPS — no browser). Everywhere else the sea
# is a memory that carries no data; here, and only here, the wire is real.
NET_ANGLE = -math.pi * 0.5            # due −z, the far side, away from both plazas
NET_WEDGE_HALF = 0.17                 # radians of pier you can fly either side
NET_PIER_IN = 39.0                    # where the pier leaves the floor
NET_PIER_OUT = 55.0                   # how far out over the sea it reaches
NET_GATE_R = 52.0                     # the gate stands at the seaward end
NET_GATE_X = NET_GATE_R * math.cos(NET_ANGLE)
NET_GATE_Z = NET_GATE_R * math.sin(NET_ANGLE)
NET_PROBE_R = 10.0                    # close enough and the world starts a real probe
NET_HOST_ENV = "MRFLUFFY_NET_HOST"    # the real address to dial (unset = a neutral default)

# the room of the Word (Learn Islam): a calm hall on the far side, due −x.
# No image, nothing depicted — the room holds only scripture on light. From the
# hall you choose a chapter; each ayah then opens as its own world of abstract
# forms keyed to the images named in the verse (never the meaning, which is with
# Allah). The ayah is written on the sky, and gates lead on to the next world,
# back to the previous one, or back to the chapters.
WORD_GATE_POS = [-23.0, 0.06, 0.0]
WORD_FLOOR_Y = -66.0
WORD_R = 30.0
WORD_RETURN_POS = [0.0, WORD_FLOOR_Y + 6.0, WORD_R - 7.0]   # gate back to the wire
WORD_CLUSTER_R = 26.0        # the stars are scattered through a tall volume of sky
WORD_CLUSTER_TOP = WORD_FLOOR_Y + 56.0   # highest a chapter-star hangs
WORD_NEXT_ANGLE = 0.0        # gate to the next ayah, due +x
WORD_PREV_ANGLE = math.pi * 0.5   # gate to the previous ayah
WORD_BACK_ANGLE = math.pi    # gate back to the chapters

# the EXCHANGE — the hall the outward gate opens into: a room of gates. Each gate
# leads to a real service out on the net, and what a gate answers is real. For now
# there is one gate, and it is DuckDuckGo. The hall itself is dressing; the search
# is not. More gates will hang here later.
EXCHANGE_FLOOR_Y = -132.0
EXCHANGE_R = 30.0
EXCHANGE_GATE_R = 17.0        # the ring the service gates hang on
EXCHANGE_RETURN_POS = [0.0, EXCHANGE_FLOOR_Y + 6.0, EXCHANGE_R - 7.0]
EXCHANGE_CONSOLE_R = 6.5      # near a gate's console you type; away from it you fly
EXCHANGE_SERVER_R = 26.0      # where the far service hangs, out on the ring's edge
EXCHANGE_TABLET_R = 21.5      # where a search's result-tablets hang
EXCHANGE_GATES = (
    {"id": "ddg", "name": "DuckDuckGo", "angle": -math.pi * 0.5,
     "host": "lite.duckduckgo.com",
     "blurb": "the web, searched \u2014 real results, served here"},
)

# the MACHINE — the box under your feet, entered by a hatch on the wire floor
# due +z (the one free plaza wedge). LOCAL only: doors (listening sockets),
# roads (live connections), inhabitants (the processes holding them), and dark
# figures (intruders) drawn only from local defensive evidence. It never touches
# the net: everything here is read from /proc and raven's own logs (machinevision).
MACHINE_HATCH_POS = [0.0, 0.06, 23.0]     # the hatch, due +z
MACHINE_FLOOR_Y = -160.0                  # the machine sits below the Exchange
MACHINE_R = 30.0
MACHINE_DOOR_R = 15.0                     # the ring of doors (ways in)
MACHINE_WALL_R = 20.0                     # the shell's wall, between doors and figures
MACHINE_FIGURE_R = 25.0                   # dark figures stand in the field outside
MACHINE_RETURN_POS = [0.0, MACHINE_FLOOR_Y + 6.0, MACHINE_R - 7.0]  # up to the wire
MACHINE_COL = (0.35, 0.92, 0.58)          # terminal green — a machine readout
MACHINE_BIRD_R = 9.0                      # the birds circle the core
MACHINE_BIRD_Y = MACHINE_FLOOR_Y + 9.0
MACHINE_BIRD_NEAR = 5.5                   # close enough to speak to a bird
BIRD_COL = {"crow": (0.80, 0.82, 0.90), "finch": (0.45, 0.95, 0.85),
            "raven": (0.72, 0.62, 1.00)}

# the CANDLE ROOM — DOT/USD's tape read as a place, entered from the market's
# centre column. LOCAL files only (the candle dump + SignalBot's OWN saved rows),
# joined by bar index: it never runs the bot, never fetches, never invents a bar
# (see candlevision.py). One interval is chosen at the door; the room is a walk
# down the tape, one tower per candle, the newest glowing as it ticks.
CANDLES_FLOOR_Y = candlevision.FLOOR_Y
CANDLE_UP = candlevision.UP
CANDLE_DOWN = candlevision.DOWN
CANDLE_AMBER = candlevision.AMBER
CANDLE_GREY = candlevision.GREY

# index: 0 floor, 1..5 = protocol strata (top -> bottom)
STRATA_Y = [0.0, -10.0, -20.0, -30.0, -40.0, -50.0]
STRATA_KEY = ["floor", "app", "transport", "internet", "link", "physical"]
EYE = 1.7
PLATFORM_R = 46.0
WELL_R = 2.6
WALL_R = 30.0          # the wall between your segment (inside) and the old ruins
DOOR_HALF = 0.30       # half-width (radians) of a doorway gap in that wall

MARKET_STATE_COL = {
    "buy": (0.30, 0.96, 0.46),      # waiting to BUY  -> green
    "sell": (0.96, 0.30, 0.33),     # waiting to SELL -> red
    "selling": (1.00, 0.16, 0.22),  # an exit is firing
    "off": (0.40, 0.43, 0.50),      # disabled
}
MARKET_STATE_TXT = {
    "buy": "waiting to buy", "sell": "waiting to sell",
    "selling": "selling now", "off": "off",
}
# the SignalBot's LEAN — which way its own named fields point (green up / red down)
MARKET_LEAN_COL = {
    "up": (0.26, 0.96, 0.44),
    "down": (0.97, 0.28, 0.30),
    "flat": (0.98, 0.76, 0.22),
    "none": (0.46, 0.49, 0.56),
}
MARKET_LEAN_TXT = {"up": "LEAN UP", "down": "LEAN DOWN",
                   "flat": "FLAT", "none": "NO SIGNAL"}
MARKET_LEAN_GLYPH = {"up": "\u25b2", "down": "\u25bc",
                     "flat": "\u25ac", "none": "\u00b7"}

PAL = {
    "floor":     {"sky": (0.02, 0.07, 0.09), "a": (0.06, 0.16, 0.18), "b": (0.04, 0.11, 0.13), "accent": (0.98, 0.72, 0.22), "hill": (0.03, 0.09, 0.11)},
    "app":       {"sky": (0.10, 0.06, 0.16), "a": (0.16, 0.20, 0.34), "b": (0.12, 0.16, 0.28), "accent": (0.30, 0.78, 0.88), "hill": (0.10, 0.07, 0.18)},
    "transport": {"sky": (0.04, 0.11, 0.09), "a": (0.13, 0.24, 0.20), "b": (0.10, 0.19, 0.16), "accent": (0.38, 0.88, 0.48), "hill": (0.05, 0.12, 0.10)},
    "internet":  {"sky": (0.04, 0.07, 0.15), "a": (0.15, 0.19, 0.29), "b": (0.11, 0.15, 0.23), "accent": (0.38, 0.62, 0.98), "hill": (0.05, 0.08, 0.16)},
    "link":      {"sky": (0.11, 0.06, 0.04), "a": (0.27, 0.19, 0.11), "b": (0.21, 0.14, 0.09), "accent": (0.97, 0.66, 0.26), "hill": (0.13, 0.07, 0.05)},
    "physical":  {"sky": (0.02, 0.02, 0.03), "a": (0.08, 0.08, 0.11), "b": (0.05, 0.05, 0.08), "accent": (1.00, 0.85, 0.35), "hill": (0.02, 0.02, 0.03)},
}


def configure_gl():
    """Request a compatibility context so the low-poly immediate path works.
    Call this BEFORE QApplication is constructed (app.py main)."""
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)


def _norm(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / m, v[1] / m, v[2] / m)


class _GLDeck(QWidget):
    """The stage: the GL world fills the whole deck, and the market interface
    floats ABOVE it as an in-world panel — never a separate window that breaks
    the view. It is part of the world, not a widow cut into it."""

    def __init__(self):
        super().__init__()
        self.glw = None
        self.panel = None
        self.overlays = []          # (widget, anchor) floating over the world

    def add_gl(self, glw):
        self.glw = glw
        glw.setParent(self)
        glw.show()

    def add_panel(self, panel):
        self.panel = panel
        # parent to the GL widget so it is part of the GL composition tree and
        # appears at once when shown (siblings only compose on a resize)
        panel.setParent(self.glw if self.glw is not None else self)

    def add_overlay(self, widget, anchor="bottom-center"):
        # children of the QOpenGLWidget compose on top of it every frame; a mere
        # sibling only appears the next time the window is resized.
        widget.setParent(self.glw if self.glw is not None else self)
        self.overlays.append((widget, anchor))

    def place_panel(self):
        p = self.panel
        if p is None:
            return
        w, h = self.width(), self.height()
        pw = max(250, min(400, int(w * 0.42)))
        p.setGeometry(w - pw - 14, 14, pw, max(200, min(h - 28, int(h * 0.88))))
        p.raise_()

    def place_overlays(self):
        w, h = self.width(), self.height()
        for ov, anchor in self.overlays:
            sw, sh = ov.sizeHint().width(), ov.sizeHint().height()
            if anchor == "top-center":
                x, y = (w - sw) // 2, 12
            elif anchor == "top-left":
                x, y = 14, 14
            elif anchor == "top-right":
                x, y = w - sw - 14, 14
            elif anchor == "bottom-right":
                x, y = w - sw - 14, h - sh - 16
            elif anchor == "center":
                x, y = (w - sw) // 2, max(12, (h - sh) // 2)
            else:                                   # bottom-center
                x, y = (w - sw) // 2, h - sh - 16
            ov.setGeometry(x, y, sw, sh)
            ov.raise_()

    def resizeEvent(self, e):
        if self.glw is not None:
            self.glw.setGeometry(self.rect())
        self.place_panel()
        self.place_overlays()


class _GameMenu(QFrame):
    """The pause/popup menu, floating over the world. Esc or Tab closes it;
    while it is open it holds the keyboard, so the world does not also move."""

    escape = pyqtSignal()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Tab):
            self.escape.emit()
            return
        super().keyPressEvent(e)


def _clampf(v, lo, hi, fallback):
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return fallback


def _hbytes(n):
    """A plain, honest byte size — used only to label a number we actually read."""
    n = float(n or 0)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f}{u}" if u == "B" else f"{n:.1f}{u}"
        n /= 1024


class _PacketReader:
    """A bounded, read-only packet capture streamed into the room (heavy mode).

    Runs ONE `tshark` on the named interface, line-buffered, and keeps only the
    newest MAXQ packets as small dicts. It captures only — it never sends a
    packet, and it is the single place (with the knob at `capture`) that does
    real capture work. If it cannot start (no tshark, no permission), it reports
    why and the room falls back to the cheap delta mode.
    """
    MAXQ = 600

    def __init__(self, iface="any", max_pps=400):
        self.iface = iface or "any"
        self.max_pps = max_pps
        self.packets = collections.deque(maxlen=self.MAXQ)
        self.error = None
        self._stop = False
        self._proc = None
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _cmd(self):
        return ["tshark", "-i", self.iface, "-l", "-n", "-Q", "-T", "fields",
                "-e", "frame.time_epoch", "-e", "ip.src", "-e", "ip.dst",
                "-e", "_ws.col.Protocol", "-e", "frame.len",
                "-e", "tcp.srcport", "-e", "tcp.dstport",
                "-e", "udp.srcport", "-e", "udp.dstport"]

    def _run(self):
        import subprocess
        last = None
        for cmd in (["sudo", "-n"] + self._cmd(), self._cmd()):
            if self._stop:
                return
            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, bufsize=1)
            except FileNotFoundError:
                self.error = "tshark not found"
                return
            except Exception as e:
                last = str(e)
                continue
            if self._pump() == 0 and not self._stop:
                last = f"could not capture on {self.iface}"
                continue
            return
        self.error = last or "capture unavailable"

    def _pump(self):
        n = 0
        try:
            for line in self._proc.stdout:
                if self._stop:
                    break
                p = self.parse(line)
                if p:
                    self.packets.append(p)
                    n += 1
        except Exception:
            pass
        try:
            self._proc.wait(timeout=3)
        except Exception:
            pass
        return n

    @staticmethod
    def parse(line):
        f = line.rstrip("\n").split("\t")
        if len(f) < 5:
            return None
        try:
            ts = float(f[0])
        except Exception:
            ts = time.time()
        try:
            ln = int(f[4])
        except Exception:
            ln = 0
        sport = f[5] if len(f) > 5 and f[5] else (f[7] if len(f) > 7 else "")
        dport = f[6] if len(f) > 6 and f[6] else (f[8] if len(f) > 8 else "")
        return {"ts": ts, "src": f[1], "dst": f[2], "proto": f[3] or "?",
                "len": ln, "sport": sport, "dport": dport}

    def stop(self):
        self._stop = True
        try:
            if self._proc:
                self._proc.terminate()
        except Exception:
            pass


class WireGLWidget(QOpenGLWidget):
    stratum_changed = pyqtSignal(int, str)     # index, focus label (may be "")
    request_rebuild = pyqtSignal()
    market_opened = pyqtSignal(object)         # the wiregate market snapshot
    market_closed = pyqtSignal()
    agent_selected = pyqtSignal(object)        # an agent dict (one platform)
    menu_toggle = pyqtSignal(bool)             # show/hide the market menu
    fullscreen_request = pyqtSignal()          # F11 — the tab owns full screen
    escape_request = pyqtSignal()              # Esc — leave full screen (the tab decides)
    word_changed = pyqtSignal()                # entered/left the Word room, or moved ayah
    web_changed = pyqtSignal()                 # entered/left the Exchange, or a gate
    machine_changed = pyqtSignal()             # entered/left the machine room
    candles_changed = pyqtSignal()             # entered/left the candle room
    live_changed = pyqtSignal(str, str)        # live mode, effective mode
    menu_request = pyqtSignal()                # Tab — the tab opens the game menu

    def __init__(self, parent=None):
        super().__init__(parent)
        self.world = None
        self.active = 0
        self.pos = [0.0, EYE, 10.0]
        self.yaw = 0.0
        self.pitch = -0.05
        self.keys = set()
        self._drag = False
        self._last_xy = None
        self._looklocked = False    # mouse captured: move to look, click to grab
        self.focus = ""
        self.show_real = False
        self.move_mult = 1.9        # fly speed multiplier (the game knob)
        self.walk_mult = 1.0        # walk speed multiplier (the game knob)
        self.boost_mult = 2.2       # sprint / boost multiplier while Shift is held
        self.look_sens = 1.0        # mouse-look sensitivity (the game knob)
        self._speed_now = 0.0       # the speed you are actually carrying (units/s)
        self._speedlines = []       # streaking motion lines, built once
        self.transition = None
        self.deep = None            # the open sea below the edge: unbounded, no data
        self.flying = False         # free flight through the wire (G toggles)
        # the market — blackhorse, entered through the gate on the wire floor
        self.market = False
        self.market_world = None
        self.presence = None
        self.selected_agent = None
        self.selected = None
        self._peers = []
        self._online = False
        self._ghost_line = ""
        self._beat = 0.0
        # the room of the Word — Learn Islam, read in the wire (no imagery)
        self.word = False
        self.word_mode = "select"        # "select" (chapters) | "ayah" (a world)
        self.word_ref = None             # (surah number, ayah index) in a world
        self._word_reci = None           # the recipe of the current ayah world
        self._word_suras = []
        self._word_stars = None          # lazily-built decorative star field
        self._word_cluster = None        # lazily-built scatter of chapter-stars
        self._word_cluster_n = -1
        # the outward gate — the one place the wire is REAL (wirenet, no browser)
        self.net = None                  # lazily-started background dialer
        self._net_host = os.environ.get(NET_HOST_ENV) or "https://1.1.1.1/cdn-cgi/trace"
        self._net_job = None
        self._net_result = None
        self._net_probe_t = 0.0
        self._net_status = ""            # what the gate last really answered
        # the Exchange — the hall of gates the outward gate opens into
        self.exchange = False
        self.service = None              # the gate stepped into, or None
        self.web_query = ""              # what has been typed at the terminal
        self.web_job = None              # the search/read out on the worker
        self.web_answer = None           # the last real answer dict
        self.web_results = []
        self.web_status = ""
        self.web_page = None             # {title, url, lines} a served page
        self.web_scroll = 0
        self._web_caret = 0.0
        self.web_hist = []               # result pages we came from
        self.web_data = None             # the form fields of the current page
        self.web_next = None             # the fields that fetch the next page
        # the packet theatre: real phases, played as motes across the hall
        self.service_angle = 0.0         # where the live gate hangs on the ring
        self.web_net = None              # {host, ip, port} of the far service
        self.pkt = []                    # motes in flight
        self.pkt_rows = []               # the packet ledger (real ms/bytes)
        self._pkt_q = []                 # queued phase events
        self._pkt_i = 0
        self._pkt_t = 0.0
        self.web_tabs = []               # result-tablets you fly to
        self.web_mono = None             # the page, assembled as light
        # the machine — the box under your feet, entered by a hatch on the wire
        self.machine = False
        self.machine_world = None        # machinevision.build() — this host, live
        self.machine_xray = False        # see through the wall to a door a figure touched
        self.machine_birds_armed = False  # finch's hand is live (behind an explicit arm)
        self._machine_arm_until = 0.0
        self._machine_contain_confirm = None   # (ip, deadline) — the second E
        self._machine_release_until = 0.0
        self._machine_contained = {}     # ip -> {reason, at}, mirrored from birdguard
        self.machine_autoguard = False   # Phase 3: finch detects + contains on its own
        self._machine_auto_until = 0.0
        self._auto_attempts = {}         # ip -> last-attempt time (cooldown for refusals)
        # the candle room — DOT/USD's tape as a place, entered from the market column
        self.candles = False
        self.candles_world = None
        self.candles_select = False      # the interval chooser at the door
        self.candles_ivs = []            # the chooser's options
        self.candles_sel = None          # the bar whose panel is open
        self._candle_stars = None        # lazily-built decorative star field
        # live vision (the knob): off / delta / capture, or auto-detected
        self.live_mode = "auto"
        self.live_effective = "off"
        self._live_info = None           # the auto-detect read
        self._live = {}                  # newest real rates (delta mode)
        self._live_prev = None           # previous counter snapshot
        self._live_t = 0.0
        self._capture = None             # the packet-capture reader, when running
        self._last_t = time.time()
        self._hud_msg = ""
        self._hud_until = 0.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._quad = gluNewQuadric()
        self._glyphs = []
        self._init_glyphs()
        self._init_speedlines()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)
        self._auto_timer = QTimer(self)          # the auto-defend heartbeat
        self._auto_timer.timeout.connect(self._machine_autoguard_beat)
        self._auto_timer.start(3000)
        self._live_timer = QTimer(self)      # the live-vision sampler (delta mode)
        self._live_timer.timeout.connect(self._live_sample)
        self._apply_saved_live_mode()
        self.reload_game_settings()

    def reload_game_settings(self):
        """Read the player's own knobs (walk speed, fly speed, boost, look
        sensitivity) from wiresettings. Purely a preference — it changes nothing
        about the world."""
        try:
            st = wiresettings.load()
        except Exception:
            st = {}
        self.move_mult = _clampf(st.get("fly_speed"), 0.5, 4.0, 1.9)
        self.walk_mult = _clampf(st.get("walk_speed"), 0.5, 3.0, 1.0)
        self.boost_mult = _clampf(st.get("boost_mult"), 1.0, 6.0, 2.2)
        self.look_sens = _clampf(st.get("look_sensitivity"), 0.2, 3.0, 1.0)

    def _boost(self):
        """The speed boost you get while Shift is held — sprint on foot, burn in
        flight. One knob; the player owns it."""
        return self.boost_mult if Qt.Key.Key_Shift in self.keys else 1.0

    def _init_glyphs(self):
        """Deterministic columns of falling code — the sea of information.
        Sorted far -> near so a rising density simply reveals the closer columns,
        letting the rain thicken as you dive without ever inventing a datum."""
        import random
        rnd = random.Random(1995)
        cols = []
        for _ in range(420):
            a = rnd.random() * 2 * math.pi
            r = 14.0 + rnd.random() * 76.0          # 14 (near) .. 90 (far)
            cols.append((r, a, 6.0 + rnd.random() * 30.0,
                         0.6 + rnd.random() * 1.8, rnd.random()))
        cols.sort(key=lambda c: -c[0])              # far first
        self._glyphs = [(r * math.cos(a), r * math.sin(a), h, spd, ph)
                        for (r, a, h, spd, ph) in cols]
        # near-field motes for the open sea: they stream past the falling camera
        # to give parallax and scale. Atmosphere only — no data, no entity.
        rnd2 = random.Random(1995 + 7)
        self._motes = []
        for _ in range(240):
            a = rnd2.random() * 2 * math.pi
            r = 2.0 + rnd2.random() * 24.0
            self._motes.append((r * math.cos(a), r * math.sin(a),
                                rnd2.random() * 60.0, 4.0 + rnd2.random() * 12.0))

    def _init_speedlines(self):
        """The streaks that fly past when you are moving fast. Built once, with a
        fixed seed, so the same line always streaks from the same direction — the
        only thing that changes is how hard you are going. Atmosphere, nothing
        more: it carries no data and is tied to the speed you actually measure."""
        rnd = random.Random(1995 + 31)
        lines = []
        for _ in range(96):
            a = rnd.random() * 2 * math.pi
            rate = 0.8 + rnd.random() * 1.9      # how fast it flies outward
            ln = 0.10 + rnd.random() * 0.26      # length, as a fraction of the radius
            ph = rnd.random()                    # starting phase, 0..1
            w = 1.0 + rnd.random() * 1.7
            lines.append((a, rate, ln, ph, w))
        self._speedlines = lines

    def _rain_level(self):
        """How thick the sea is right now: 1.0 on the floor, deeper with each
        stratum, surging during a dive, and deepening without bound in the open
        sea below the edge. Atmosphere only — it carries no data."""
        lvl = 1.0 + 0.16 * self.active
        if self.transition:
            lvl += 0.6
        if self.deep is not None:
            lvl += min(3.0, self.deep["d"] / 34.0)
        return lvl

    # ---- world / camera plumbing ------------------------------------------
    def set_world(self, world: dict):
        self.world = world
        self.active = 0
        self.focus = ""
        self.transition = None
        self.deep = None
        self.flying = False
        self.market = False
        self.market_world = None
        self.selected_agent = None
        self.selected = None
        self.word = False
        self.word_mode = "select"
        self.word_ref = None
        self._word_reci = None
        self._word_suras = []
        self.exchange = False
        self.service = None
        self.web_query = ""
        self.web_job = None
        self.web_answer = None
        self.web_results = []
        self.web_status = ""
        self.web_page = None
        self.web_scroll = 0
        self.web_hist = []
        self.web_data = None
        self.web_next = None
        self.service_angle = 0.0
        self.web_net = None
        self.pkt = []
        self.pkt_rows = []
        self._pkt_q = []
        self._pkt_i = 0
        self._pkt_t = 0.0
        self.web_tabs = []
        self.web_mono = None
        self.machine = False
        self.machine_world = None
        self.machine_xray = False
        self.machine_birds_armed = False
        self._machine_arm_until = 0.0
        self._machine_contain_confirm = None
        self._machine_release_until = 0.0
        self._machine_contained = {}
        self.machine_autoguard = False
        self._machine_auto_until = 0.0
        self._auto_attempts = {}
        self.candles = False
        self.candles_world = None
        self.candles_select = False
        self.candles_ivs = []
        self.candles_sel = None
        self.pos = [0.0, EYE, 10.0]
        self.yaw = 0.0
        self.pitch = -0.05
        self.update()

    def _floor_y(self, idx=None):
        return STRATA_Y[idx if idx is not None else self.active]

    def _start_transition(self, idx: int, focus: str = ""):
        if not self.world or idx < 0 or idx >= len(STRATA_Y):
            return
        if self.transition:
            return
        self.focus = focus
        from_r = math.hypot(self.pos[0], self.pos[2])
        to_y = self._floor_y(idx) + EYE
        self.transition = {"to": idx, "t": 0.0,
                           "dur": 1.0 + abs(to_y - self.pos[1]) / 22.0,
                           "from_y": self.pos[1], "from_x": self.pos[0],
                           "from_z": self.pos[2], "from_pitch": self.pitch,
                           "from_yaw": self.yaw, "from_r": from_r,
                           "from_angle": math.atan2(self.pos[2], self.pos[0])}
        self.active = idx
        self.stratum_changed.emit(idx, focus)

    def _go_surface(self):
        self._start_transition(0)

    # ---- GL ----------------------------------------------------------------
    def initializeGL(self):
        glClearColor(*PAL["floor"]["sky"], 1.0)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)   # faceted, double-sided — low-poly, winding-agnostic
        glShadeModel(GL_FLAT)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def resizeGL(self, w, h):
        glViewport(0, 0, max(1, w), max(1, h))

    def _sky_and_hills(self, p):
        glClearColor(*p["sky"], 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        y0 = self._floor_y()
        seg = 28
        r = 120.0
        glBegin(GL_TRIANGLES)
        for i in range(seg):
            a0 = 2 * math.pi * i / seg
            a1 = 2 * math.pi * (i + 1) / seg
            h = 6.0 + 10.0 * (0.5 + 0.5 * math.sin(i * 1.7 + self.active))
            glColor3f(*p["hill"])
            glVertex3f(r * math.cos(a0), y0 - 2, r * math.sin(a0))
            glVertex3f(r * math.cos(a1), y0 - 2, r * math.sin(a1))
            glColor3f(min(p["hill"][0] * 1.6 + 0.02, 1), min(p["hill"][1] * 1.6 + 0.02, 1), min(p["hill"][2] * 1.6 + 0.02, 1))
            glVertex3f(r * math.cos((a0 + a1) / 2), y0 + h, r * math.sin((a0 + a1) / 2))
        glEnd()

    def _ground(self, p):
        y = self._floor_y()
        t = 5.0
        n = int(PLATFORM_R / t)
        for gx in range(-n, n):
            for gz in range(-n, n):
                cx, cz = (gx + 0.5) * t, (gz + 0.5) * t
                dc = math.hypot(cx, cz)
                if dc > PLATFORM_R - 1 or dc < WELL_R:
                    continue
                c = p["a"] if (gx + gz) % 2 == 0 else p["b"]
                glColor3f(*c)
                x0, x1 = gx * t, (gx + 1) * t
                z0, z1 = gz * t, (gz + 1) * t
                glBegin(GL_QUADS)
                glVertex3f(x0, y, z0); glVertex3f(x1, y, z0)
                glVertex3f(x1, y, z1); glVertex3f(x0, y, z1)
                glEnd()

    def _glyph_rain(self, t, spin=0.0, dim=1.0):
        """Phosphor code-green glyphs drifting down — the sea of information,
        shown obliquely. Atmosphere only; it carries no data. The sea thickens as
        you descend: deeper reads reveal more of the deterministic columns, and
        the near ones burn brighter and stream faster. `spin` slowly turns the
        whole field so the open sea reads as alive, never a still image."""
        lvl = self._rain_level()
        in_deep = self.deep is not None
        y0 = self._floor_y()
        n = min(len(self._glyphs), int(96 * lvl) + 12)
        if in_deep:
            y0 = self.pos[1] - 18.0 + ((self.deep["d"] * 0.6) % 30.0)
        speed = 1.0 + (0.35 * (lvl - 1.0))
        # teal-leaning green; the open sea reads a touch colder
        cr = 0.22
        cg = 0.95 if not in_deep else 0.92
        cb = 0.45 if not in_deep else 0.72
        segs = 4 if not in_deep else 7          # longer streaks down in the sea
        gap = 1.5 if not in_deep else 1.9
        cs, sn = math.cos(spin), math.sin(spin)
        glLineWidth(1.0)
        for i in range(n):
            x, z, h, spd, ph = self._glyphs[i]
            if spin:
                x, z = x * cs - z * sn, x * sn + z * cs
            near = i / max(1, n - 1)
            yoff = y0 + ((h + t * spd * speed) % 30.0) - 6.0
            a = (0.08 + 0.30 * near) * min(1.5, 0.75 * lvl) * dim
            glColor4f(cr, cg, cb, min(0.6, a))
            glBegin(GL_LINES)
            for k in range(segs):
                yy = yoff + k * gap
                glVertex3f(x, yy, z)
                glVertex3f(x, yy + 0.85, z)
            glEnd()

    def _deep_motes(self, t):
        """Fast near-field motes that rush upward past the descending camera —
        parallax and scale for the open sea. More appear the deeper you fall.
        Deterministic atmosphere; it is not an entity and carries no datum."""
        if not getattr(self, "_motes", None):
            return
        n = min(len(self._motes), 80 + int(self.deep["d"]))
        glLineWidth(1.0)
        for i in range(n):
            x, z, y0, spd = self._motes[i]
            yy = self.pos[1] + ((y0 + t * spd) % 60.0) - 30.0
            glColor4f(0.30, 0.92, 0.72, 0.42)
            glBegin(GL_LINES)
            glVertex3f(x, yy, z)
            glVertex3f(x, yy + 1.6, z)
            glEnd()

    def _well(self, t=0.0):
        y0 = self._floor_y()
        glColor3f(0.01, 0.02, 0.03)
        glBegin(GL_QUAD_STRIP)
        seg = 20
        for i in range(seg + 1):
            a = 2 * math.pi * i / seg
            x, z = WELL_R * math.cos(a), WELL_R * math.sin(a)
            glVertex3f(x, y0, z)
            glVertex3f(x, y0 - 8.0, z)
        glEnd()
        # the dive port: a wet-glass pool that doubles the light, rippling outward
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(0.10, 0.34, 0.40, 0.55)
        glVertex3f(0, y0 + 0.05, 0)
        for i in range(23):
            a = 2 * math.pi * i / 22
            glColor4f(0.06, 0.22, 0.30, 0.10)
            glVertex3f((WELL_R + 2.2) * math.cos(a), y0 + 0.05, (WELL_R + 2.2) * math.sin(a))
        glEnd()
        glLineWidth(2.0)
        for k in range(2):
            rr = WELL_R + 2.2 + ((t * 1.4 + k * 1.6) % 3.2)
            glColor4f(0.30, 0.85, 0.95, 0.5 * (1.0 - (rr - WELL_R - 2.2) / 3.2))
            glBegin(GL_LINE_LOOP)
            for i in range(24):
                a = 2 * math.pi * i / 24
                glVertex3f(rr * math.cos(a), y0 + 0.06, rr * math.sin(a))
            glEnd()
        glLineWidth(1.0)

    def _cube(self, x, y, z, sx, sy, sz, c):
        glColor3f(*c)
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        glBegin(GL_QUADS)
        # +x -x +y -y +z -z
        glVertex3f(x + hx, y - hy, z - hz); glVertex3f(x + hx, y - hy, z + hz); glVertex3f(x + hx, y + hy, z + hz); glVertex3f(x + hx, y + hy, z - hz)
        glVertex3f(x - hx, y - hy, z + hz); glVertex3f(x - hx, y - hy, z - hz); glVertex3f(x - hx, y + hy, z - hz); glVertex3f(x - hx, y + hy, z + hz)
        glVertex3f(x - hx, y + hy, z - hz); glVertex3f(x + hx, y + hy, z - hz); glVertex3f(x + hx, y + hy, z + hz); glVertex3f(x - hx, y + hy, z + hz)
        glVertex3f(x - hx, y - hy, z + hz); glVertex3f(x + hx, y - hy, z + hz); glVertex3f(x + hx, y - hy, z - hz); glVertex3f(x - hx, y - hy, z - hz)
        glVertex3f(x - hx, y - hy, z + hz); glVertex3f(x + hx, y - hy, z + hz); glVertex3f(x + hx, y + hy, z + hz); glVertex3f(x - hx, y + hy, z + hz)
        glVertex3f(x + hx, y - hy, z - hz); glVertex3f(x - hx, y - hy, z - hz); glVertex3f(x - hx, y + hy, z - hz); glVertex3f(x + hx, y + hy, z - hz)
        glEnd()

    def _octa(self, x, y, z, r, c, squash=1.0):
        glColor3f(*c)
        ys = r * squash
        glBegin(GL_TRIANGLES)
        for sx, sz in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            glVertex3f(x + sx * r, y, z + sz * r)
            glVertex3f(x + sz * r, y, z - sx * r)
            glVertex3f(x, y + ys, z)
            glVertex3f(x + sz * r, y, z - sx * r)
            glVertex3f(x + sx * r, y, z + sz * r)
            glVertex3f(x, y - ys, z)
        glEnd()

    def _prism(self, x, z, r0, r1, y0, y1, sides, c):
        glColor3f(*c)
        glBegin(GL_QUADS)
        for i in range(sides):
            a0 = 2 * math.pi * i / sides
            a1 = 2 * math.pi * (i + 1) / sides
            glVertex3f(x + r0 * math.cos(a0), y0, z + r0 * math.sin(a0))
            glVertex3f(x + r0 * math.cos(a1), y0, z + r0 * math.sin(a1))
            glVertex3f(x + r1 * math.cos(a1), y1, z + r1 * math.sin(a1))
            glVertex3f(x + r1 * math.cos(a0), y1, z + r1 * math.sin(a0))
        glEnd()
        glBegin(GL_POLYGON)
        for i in range(sides):
            a = 2 * math.pi * i / sides
            glVertex3f(x + r1 * math.cos(a), y1, z + r1 * math.sin(a))
        glEnd()

    def _cone(self, x, y, z, r, h, c):
        glColor3f(*c)
        glBegin(GL_TRIANGLES)
        seg = 6
        for i in range(seg):
            a0 = 2 * math.pi * i / seg
            a1 = 2 * math.pi * (i + 1) / seg
            glVertex3f(x, y + h, z)
            glVertex3f(x + r * math.cos(a0), y, z + r * math.sin(a0))
            glVertex3f(x + r * math.cos(a1), y, z + r * math.sin(a1))
        glEnd()

    def _arrow_head(self, x, y, z, r, h, c, up=True):
        """A solid arrowhead: apex points up (or down), base cap closed."""
        glColor3f(*c)
        seg = 8
        apex = y + (h if up else -h)
        glBegin(GL_TRIANGLES)
        for i in range(seg):
            a0 = 2 * math.pi * i / seg
            a1 = 2 * math.pi * (i + 1) / seg
            glVertex3f(x, apex, z)
            glVertex3f(x + r * math.cos(a0), y, z + r * math.sin(a0))
            glVertex3f(x + r * math.cos(a1), y, z + r * math.sin(a1))
        glEnd()
        glBegin(GL_POLYGON)
        for i in range(seg):
            a = 2 * math.pi * i / seg
            glVertex3f(x + r * math.cos(a), y, z + r * math.sin(a))
        glEnd()

    def _portal(self, x, z, y, radius, c, t):
        pulse = 1.0 + 0.12 * math.sin(t * 3.0)
        rr = radius * pulse
        glColor4f(c[0], c[1], c[2], 0.35)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(x, y + radius, z)
        seg = 22
        for i in range(seg + 1):
            a = 2 * math.pi * i / seg
            glVertex3f(x + rr * math.cos(a), y + radius + rr * math.sin(a), z)
        glEnd()
        glLineWidth(3.0)
        glColor4f(c[0], c[1], c[2], 0.95)
        glBegin(GL_LINE_LOOP)
        for i in range(seg):
            a = 2 * math.pi * i / seg
            glVertex3f(x + rr * math.cos(a), y + radius + rr * math.sin(a), z)
        glEnd()
        glLineWidth(1.0)

    def _vring(self, x, y, z, radius, c, t):
        """A ring standing upright in the Y-Z plane at a fixed x — a doorway seen
        head-on when you look down the candle tape (the flat _portal won't do)."""
        pulse = 1.0 + 0.10 * math.sin(t * 3.0)
        rr = radius * pulse
        seg = 22
        glColor4f(c[0], c[1], c[2], 0.30)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(x, y, z)
        for i in range(seg + 1):
            a = 2 * math.pi * i / seg
            glVertex3f(x, y + rr * math.cos(a), z + rr * math.sin(a))
        glEnd()
        glLineWidth(3.0)
        glColor4f(c[0], c[1], c[2], 0.95)
        glBegin(GL_LINE_LOOP)
        for i in range(seg):
            a = 2 * math.pi * i / seg
            glVertex3f(x, y + rr * math.cos(a), z + rr * math.sin(a))
        glEnd()
        glLineWidth(1.0)

    def _sphere(self, x, y, z, r, c):
        glColor3f(*c)
        glPushMatrix()
        glTranslatef(x, y, z)
        gluSphere(self._quad, r, 10, 8)
        glPopMatrix()

    # ---- scene content -----------------------------------------------------
    def _draw_floor_objects(self, t):
        w = self.world
        y = self._floor_y()
        p = PAL["floor"]
        # the heart — your host, a pulsing monolith
        h = w["heart"]
        beat = 1.0 + 0.20 * math.sin(t * (2.0 + (h.get("rtt") or 20) / 60.0))
        hc = (0.55, 0.30, 0.90) if h.get("up") else (0.75, 0.15, 0.20)
        self._prism(0, -8, 2.6 * beat, 1.4 * beat, y, y + 9.0, 6, hc)
        self._octa(0, y + 10.5, -8, 1.6 * beat, (0.85, 0.70, 1.0))
        # devices
        for d in w["devices"]:
            x, z = d["pos"]
            big = d["sni_total"] > 0
            if d.get("is_self"):
                col = (1.0, 0.82, 0.30)
            elif d.get("role") == "gateway":
                col = (0.45, 0.90, 1.0)
            elif d.get("identity") == "unknown":
                col = (0.42, 0.45, 0.55)
            else:
                col = (0.30, 0.85, 0.95) if big else (0.55, 0.58, 0.70)
            if not d.get("fresh", True):
                col = tuple(c * 0.5 for c in col)      # stale = dimmed memory
            size = 1.0 + min(1.4, math.log10(d["sni_total"] + 1)) if big else 0.8
            self._octa(x, y + 1.2 * size, z, 0.7 * size, col, squash=1.6)
            self._cube(x, y + 0.5, z, 0.9, 0.9, 0.9, (col[0] * 0.6, col[1] * 0.6, col[2] * 0.6))
            if d.get("is_self"):
                self._portal(x, z, y, 1.9, (1.0, 0.85, 0.35), t)
            if d.get("role") == "gateway":
                dim = tuple(c * 0.7 for c in col)
                self._cube(x - 1.1, y + 2.0, z, 0.5, 4.0, 0.5, dim)
                self._cube(x + 1.1, y + 2.0, z, 0.5, 4.0, 0.5, dim)
                self._cube(x, y + 4.2, z, 2.7, 0.5, 0.6, col)
        # gates
        for g in w["gates"]:
            x, z = g["pos"]
            self._portal(x, z, y, 1.3, p["accent"], t + g["count"] * 0.1)
        # media campfire
        for m in w["media"]:
            x, z = m["pos"]
            self._cone(x, y, z, 0.9, 1.6, (0.95, 0.55, 0.20))
            self._cone(x, y, z, 0.6, 1.1, (1.0, 0.80, 0.35))
        # rifts — IDS alerts
        for rf in w["rifts"]:
            x, z = rf["pos"]
            for k in range(4):
                a = k * 1.6
                self._cone(x + 0.4 * math.cos(a), y, z + 0.4 * math.sin(a), 0.35, 2.6 + 0.5 * k, (0.95, 0.20, 0.30))
        # crows
        for c in w["crows"]:
            x, z = c["pos"]
            bob = 0.5 * math.sin(t * 1.6 + x)
            self._crow(x, y + 4.0 + bob, z, t)
        # the gate to BlackHorse — the market, entered from the wire
        self._market_apron(t, y)
        self._draw_market_gate(t, y)
        # the room of the Word — Learn Islam, on the far side, due −x
        self._word_apron(t, y)
        self._draw_word_gate(t, y)
        # the OUTWARD GATE — a pier over the open sea; the one place the wire is real
        self._draw_net_gate(t, y)
        # the machine hatch — the box under your feet, its own wedge due +z
        self._machine_hatch(t, y)

    def _machine_hatch(self, t, y):
        """The hatch down into THIS machine: a lit hex rim on the floor with a
        dark shaft pulsing beneath — the way down, standing apart from the crowd.
        Dressing only; the room itself is read live from /proc."""
        hx, hy, hz = MACHINE_HATCH_POS
        r = 3.4
        glColor4f(0.02, 0.06, 0.045, 0.9)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(hx, y + 0.045, hz)
        for i in range(7):
            a = 2 * math.pi * i / 6
            glVertex3f(hx + r * math.cos(a), y + 0.05, hz + r * math.sin(a))
        glEnd()
        glColor4f(0.20, 0.55, 0.34, 0.55)
        glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        for i in range(6):
            a = 2 * math.pi * i / 6
            glVertex3f(hx + r * math.cos(a), y + 0.06, hz + r * math.sin(a))
        glEnd()
        self._portal(hx, hz, y + 0.2, 2.2, (0.35, 0.92, 0.58), t + 0.8)
        for k in range(3):
            glColor4f(0.30, 0.85, 0.52, 0.35 - 0.08 * k)
            glLineWidth(1.5)
            glBegin(GL_LINE_LOOP)
            aa = t * 0.5 + k * 0.5
            for i in range(24):
                a = 2 * math.pi * i / 24 + aa
                glVertex3f(hx + (1.2 + 0.6 * k) * math.cos(a), y + 0.07,
                           hz + (1.2 + 0.6 * k) * math.sin(a))
            glEnd()
        glLineWidth(1.0)

    def _market_apron(self, t, y):
        """Blackhorse's own arrival pad on the wire floor: a dark violet plaza
        with wiring rings and a slow sentry sweep, cleared of the LAN cluster so
        the gate stands apart from the well/devices/media crowd. Dressing only."""
        gx, gy, gz = MARKET_GATE_POS
        r = 5.6
        glColor4f(0.05, 0.03, 0.08, 0.55)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(gx, y + 0.04, gz)
        for i in range(33):
            a = 2 * math.pi * i / 32
            glVertex3f(gx + r * math.cos(a), y + 0.045, gz + r * math.sin(a))
        glEnd()
        for rr, alpha in ((5.6, 0.28), (3.9, 0.45), (2.4, 0.60)):
            glColor4f(0.55, 0.30, 0.75, alpha)
            glLineWidth(2.0 if rr < 5.6 else 1.0)
            glBegin(GL_LINE_LOOP)
            for i in range(40):
                a = 2 * math.pi * i / 40
                glVertex3f(gx + rr * math.cos(a), y + 0.05, gz + rr * math.sin(a))
            glEnd()
        # a slow sentry sweep around the plaza, watching the money
        rot = t * 0.4
        glColor4f(0.85, 0.55, 0.25, 0.45)
        glLineWidth(1.5)
        glBegin(GL_LINES)
        glVertex3f(gx, y + 0.06, gz)
        glVertex3f(gx + r * math.cos(rot), y + 0.06, gz + r * math.sin(rot))
        glEnd()
        # six small marker lights at the rim, evenly set like an approach path
        for k in range(6):
            a = k * 2 * math.pi / 6 + 0.2 * t
            self._octa(gx + 4.9 * math.cos(a), y + 1.15 + 0.15 * math.sin(t * 2 + k),
                       gz + 4.9 * math.sin(a), 0.16, (0.95, 0.60, 0.30), squash=1.4)
        glLineWidth(1.0)

    def _draw_market_gate(self, t, y):
        gx, gy, gz = MARKET_GATE_POS
        r = 2.1 + 0.18 * math.sin(t * 1.3)
        gc = (0.55, 0.30, 0.75)
        self._cube(gx, y + 3.2, gz, 0.9, 6.6, 0.9, (gc[0] * 0.5, gc[1] * 0.5, gc[2] * 0.5))
        glColor4f(gc[0] * 0.16, gc[1] * 0.16, gc[2] * 0.22, 0.9)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(gx, y + 3.2, gz)
        for i in range(33):
            a = 2 * math.pi * i / 32
            glVertex3f(gx + r * 0.95 * math.cos(a), y + 3.2 + r * 0.95 * math.sin(a), gz)
        glEnd()
        glLineWidth(2.0)
        glColor4f(0.95, 0.55, 0.20, 1.0)
        glBegin(GL_LINE_LOOP)
        for i in range(48):
            a = 2 * math.pi * i / 48
            glVertex3f(gx + r * math.cos(a), y + 3.2 + r * math.sin(a), gz)
        glEnd()
        glLineWidth(1.0)
        for i in range(22):
            a = 2 * math.pi * i / 22
            bx, by = gx + r * math.cos(a), y + 3.2 + r * math.sin(a)
            self._octa(bx, by, gz, 0.26, (0.85, 0.45, 0.15), squash=0.6)
        self._portal(gx, gz, gy, 2.6, (0.95, 0.55, 0.20), t)

    def _word_apron(self, t, y):
        """Learn Islam's arrival pad on the wire floor: a quiet ice-coloured
        disc with slow pale rings and a thin sweep of light. Words on light,
        nothing more — no figure is ever drawn here. Dressing only."""
        gx, gy, gz = WORD_GATE_POS
        r = 5.6
        glColor4f(0.02, 0.04, 0.07, 0.60)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(gx, y + 0.04, gz)
        for i in range(33):
            a = 2 * math.pi * i / 32
            glVertex3f(gx + r * math.cos(a), y + 0.045, gz + r * math.sin(a))
        glEnd()
        for rr, alpha in ((5.6, 0.22), (3.9, 0.36), (2.4, 0.50)):
            glColor4f(0.42, 0.62, 0.72, alpha)
            glLineWidth(2.0 if rr < 5.6 else 1.0)
            glBegin(GL_LINE_LOOP)
            for i in range(40):
                a = 2 * math.pi * i / 40
                glVertex3f(gx + rr * math.cos(a), y + 0.05, gz + rr * math.sin(a))
            glEnd()
        rot = t * 0.25
        glColor4f(0.72, 0.86, 0.90, 0.30)
        glLineWidth(1.5)
        glBegin(GL_LINES)
        glVertex3f(gx, y + 0.06, gz)
        glVertex3f(gx + r * math.cos(rot), y + 0.06, gz + r * math.sin(rot))
        glEnd()
        # six small reader-lights at the rim, calm and slow
        for k in range(6):
            a = k * 2 * math.pi / 6 - 0.05 * t
            self._octa(gx + 4.9 * math.cos(a), y + 1.05 + 0.1 * math.sin(t * 1.2 + k),
                       gz + 4.9 * math.sin(a), 0.14, (0.78, 0.92, 1.0), squash=1.4)
        glLineWidth(1.0)

    def _draw_word_gate(self, t, y):
        gx, gy, gz = WORD_GATE_POS
        r = 2.1 + 0.12 * math.sin(t * 0.9)
        gc = (0.42, 0.62, 0.72)
        self._cube(gx, y + 3.0, gz, 0.9, 6.2, 0.9, (gc[0] * 0.5, gc[1] * 0.5, gc[2] * 0.5))
        # a tall lens of light — a doorway, not a figure
        glColor4f(0.42, 0.72, 0.82, 0.85)
        glBegin(GL_QUADS)
        glVertex3f(gx - r, y + 0.5, gz)
        glVertex3f(gx + r, y + 0.5, gz)
        glVertex3f(gx + r * 0.7, y + 7.6, gz)
        glVertex3f(gx - r * 0.7, y + 7.6, gz)
        glEnd()
        glLineWidth(2.0)
        glColor4f(0.88, 0.96, 1.0, 0.9)
        glBegin(GL_LINE_LOOP)
        for i in range(48):
            a = 2 * math.pi * i / 48
            glVertex3f(gx + r * 0.96 * math.cos(a), y + 2.4 + r * 0.82 * math.sin(a), gz)
        glEnd()
        glLineWidth(1.0)
        self._portal(gx, gz, gy + 1.4, 2.6, (0.72, 0.88, 0.98), t)

    def _draw_net_gate(self, t, y):
        """The OUTWARD GATE — a pier run off the floor, out over the open sea, to
        the one gate that really dials the wire. The pier and the portal are
        dressing; the answer the gate gives is the network's, unedited."""
        ca, sa = math.cos(NET_ANGLE), math.sin(NET_ANGLE)
        px, pz = -sa, ca                      # perpendicular, across the pier
        w0, w1 = 2.2, 1.5

        def corner(r, off):
            return (r * ca + off * px, y + 0.06, r * sa + off * pz)

        quad = (corner(NET_PIER_IN, -w0), corner(NET_PIER_OUT, -w1),
                corner(NET_PIER_OUT, w1), corner(NET_PIER_IN, w0))
        glColor4f(0.08, 0.19, 0.18, 0.95)
        glBegin(GL_QUADS)
        for x, yy, z in quad:
            glVertex3f(x, yy, z)
        glEnd()
        glLineWidth(1.0)
        glColor4f(0.32, 0.82, 0.72, 0.65)
        glBegin(GL_LINE_LOOP)
        for x, yy, z in quad:
            glVertex3f(x, yy, z)
        glEnd()
        # pilings, dipping down into the dark sea
        for r in range(int(NET_PIER_IN), int(NET_PIER_OUT) + 1, 3):
            for off in (-w0 * 0.7, w0 * 0.7):
                x = r * ca + off * px
                z = r * sa + off * pz
                self._cube(x, y - 1.7, z, 0.34, 3.6, 0.34, (0.11, 0.15, 0.17))
        # the sign at the pier mouth
        mx, mz = NET_PIER_IN * ca, NET_PIER_IN * sa
        self._cube(mx, y + 1.1, mz, 1.1, 2.2, 0.5, (0.13, 0.33, 0.30))
        # the gate itself
        gx, gz = NET_GATE_X, NET_GATE_Z
        for off in (-1.6, 1.6):
            x = gx + off * px
            z = gz + off * pz
            self._cube(x, y + 3.2, z, 0.5, 6.4, 0.5, (0.20, 0.30, 0.30))
        self._cube(gx, y + 6.7, gz, 3.7, 0.5, 0.6, (0.35, 0.95, 0.80))
        rr = 2.0 + 0.15 * math.sin(t * 1.3)
        glColor4f(0.28, 0.95, 0.74, 0.80)
        glBegin(GL_QUADS)
        glVertex3f(gx - rr * px, y + 0.5, gz - rr * pz)
        glVertex3f(gx + rr * px, y + 0.5, gz + rr * pz)
        glVertex3f(gx + rr * 0.8 * px, y + 6.3, gz + rr * 0.8 * pz)
        glVertex3f(gx - rr * 0.8 * px, y + 6.3, gz - rr * 0.8 * pz)
        glEnd()
        self._portal(gx, gz, y + 3.0, 2.8, (0.40, 1.0, 0.80), t)

    # ---- the floor as ROOMS: your segment inside, old segments as ruins -----
    def _ruin_segments(self):
        return [s for s in (self.world or {}).get("segments", []) if not s.get("is_home")]

    def _in_door(self, a):
        for s in self._ruin_segments():
            da = abs((a - s["angle"] + math.pi) % (2 * math.pi) - math.pi)
            if da <= DOOR_HALF:
                return s
        return None

    def _wall(self, x, y, z, a, length, height, c):
        glPushMatrix()
        glTranslatef(x, y, z)
        glRotatef(-math.degrees(a), 0, 1, 0)
        self._cube(0, height / 2, 0, 0.6, height, length, c)
        glPopMatrix()

    def _draw_rooms(self, t):
        y = self._floor_y()
        # ruin ground: a desaturated pad on the outer ring behind the wall
        for s in self._ruin_segments():
            base = s["angle"]
            glColor4f(0.20, 0.15, 0.21, 0.55)
            glBegin(GL_TRIANGLE_STRIP)
            for k in range(21):
                a = base - 0.6 + 1.2 * k / 20
                xo, zo = (PLATFORM_R - 2) * math.cos(a), (PLATFORM_R - 2) * math.sin(a)
                xi, zi = 32.5 * math.cos(a), 32.5 * math.sin(a)
                glVertex3f(xi, y + 0.04, zi)
                glVertex3f(xo, y + 0.04, zo)
            glEnd()
        # the wall ring, omitted wherever there is a doorway
        step = 0.10
        a = 0.0
        while a < 2 * math.pi:
            if self._in_door(a) is None:
                x, z = WALL_R * math.cos(a), WALL_R * math.sin(a)
                self._wall(x, y, z, a, step * WALL_R * 1.2, 4.2, (0.30, 0.27, 0.35))
            a += step
        # doorway frames — a warm gate you can walk through into a memory
        for s in self._ruin_segments():
            a = s["angle"]
            for sa in (-1, 1):
                aa = a + sa * DOOR_HALF * 0.95
                xx, zz = WALL_R * math.cos(aa), WALL_R * math.sin(aa)
                self._cube(xx, y + 2.4, zz, 0.5, 5.0, 0.5, (0.95, 0.60, 0.30))
            x, z = WALL_R * math.cos(a), WALL_R * math.sin(a)
            self._portal(x, z, y, 1.7, (0.95, 0.65, 0.35), t + a)

    def _crow(self, x, y, z, t):
        flap = 0.35 + 0.35 * abs(math.sin(t * 4.0 + x))
        glColor3f(0.05, 0.05, 0.07)
        glBegin(GL_TRIANGLES)
        # body
        glVertex3f(x, y, z - 0.6); glVertex3f(x, y, z + 0.6); glVertex3f(x, y + 0.5, z)
        # wings
        glVertex3f(x, y + 0.2, z); glVertex3f(x - 1.6, y + flap, z); glVertex3f(x, y + 0.2, z + 0.5)
        glVertex3f(x, y + 0.2, z); glVertex3f(x + 1.6, y + flap, z); glVertex3f(x, y + 0.2, z + 0.5)
        glEnd()

    def _draw_stratum_objects(self, t):
        st = self.world["strata"][self.active - 1]
        key = st["key"]
        p = PAL[key]
        y = self._floor_y()
        for a in st["artifacts"]:
            x, z = a["pos"]
            if a["kind"] == "electron":
                pulse = 1.0 + 0.35 * math.sin(t * 5.0)
                self._sphere(x, y + 2.2, z, 0.9 * pulse, (1.0, 0.85, 0.35))
                for k in range(3):
                    ang = t * 1.2 + k * 2.09
                    self._sphere(x + 2.4 * math.cos(ang), y + 2.2 + 0.6 * math.sin(ang * 2), z + 2.4 * math.sin(ang), 0.18, (0.6, 0.75, 1.0))
                continue
            try:
                n = max(1.0, float(a.get("weight") or 1))
            except (TypeError, ValueError):
                n = 1.0
            height = 2.0 + 3.2 * (math.log10(n + 1) / 3.0)
            col = p["accent"] if a["kind"] in ("domain",) else (
                (0.35, 0.85, 0.55) if a["kind"] == "port" else
                (0.40, 0.62, 0.98) if a["kind"] == "ip" else (0.95, 0.66, 0.26))
            self._prism(x, z, 1.0, 0.35, y, y + height, 4, col)
            if self.focus and a["label"] == self.focus:
                self._cone(x, y + height, z, 0.5, 3.0, (1.0, 1.0, 1.0))

    def _labels(self):
        """Screen-space labels for the active scene. Returns list of (sx,sy,txt,color)."""
        out = []
        if self.machine:
            return self._machine_labels()
        if self.market:
            return self._market_labels()
        if not self.world:
            return out
        y = self._floor_y()
        vp = glGetIntegerv(GL_VIEWPORT)
        items = []
        if self.active == 0:
            for d in self.world["devices"]:
                x, z = d["pos"]
                if d.get("is_self"):
                    txt, col = "\u25c8 this machine (you)", (1.0, 0.85, 0.35)
                elif d.get("role") == "gateway":
                    txt, col = "the way out (gateway)", (0.60, 0.95, 1.0)
                elif d.get("identity") == "unknown":
                    txt, col = d["label"] + "  (identity unknown)", (0.55, 0.58, 0.68)
                elif d.get("identity") == "announced":
                    txt, col = d["label"] + "  (announced name)", (0.70, 0.80, 0.95)
                else:
                    txt, col = d["label"], (0.85, 0.9, 1.0)
                extra = []
                if d.get("last_seen"):
                    extra.append("seen " + d["last_seen"])
                if str(d.get("ghost", "")).startswith("cyberbrain"):
                    extra.append("cyberbrain")
                elif d.get("identity") == "unknown":
                    extra.append("no ghost readable")
                extra += [f for f in d.get("flags", []) if f != "the way out"]
                if extra:
                    txt += "  · " + " · ".join(extra)
                items.append((x, y + 2.2, z, txt, col))
            for g in self.world["gates"]:
                x, z = g["pos"]
                items.append((x, y + 2.0, z, f"{g['domain']} ×{g['count']}", (0.8, 0.7, 1.0)))
            h = self.world["heart"]
            rtt = "?" if h.get("rtt") is None else f"{round(float(h['rtt']), 1)}ms"
            items.append((0, y + 12.0, -8,
                          f"THE HEART (your host) · rtt {rtt} · strikes {h.get('strikes')}",
                          (0.9, 0.8, 1.0)))
            for c in self.world["crows"]:
                x, z = c["pos"]
                v = (c.get("verdict") or "")[:44]
                txt = c["name"] + (" · " + c["role"] if c.get("role") else "")
                if v:
                    txt += "  —  " + v
                items.append((x, y + 5.6, z, txt, (0.85, 0.85, 0.9)))
            segs = self.world.get("segments", [])
            home = next((s for s in segs if s.get("is_home")), None)
            if home:
                items.append((0, y + 8.5, 18,
                              f"YOUR SEGMENT {home['subnet']} \u2014 the lit room "
                              f"({home['count']} device(s))", (0.80, 0.95, 1.0)))
            for s in self._ruin_segments():
                rx, rz = 39 * math.cos(s["angle"]), 39 * math.sin(s["angle"])
                items.append((rx, y + 7.0, rz,
                              f"RUIN \u00b7 old segment {s['subnet']} \u00b7 {s['count']} device(s) "
                              f"\u00b7 last seen {s.get('newest')}", (0.88, 0.63, 0.45)))
                dx, dz = WALL_R * math.cos(s["angle"]), WALL_R * math.sin(s["angle"])
                items.append((dx, y + 5.8, dz, f"door \u2192 {s['subnet']} (a memory)",
                              (0.95, 0.70, 0.40)))
            gx, gy, gz = MARKET_GATE_POS
            items.append((gx, y + 6.8, gz,
                          "the gate to BlackHorse \u2014 the market [E], "
                          "reached from the wire floor", (0.95, 0.55, 0.20)))
            wx, wz = WORD_GATE_POS[0], WORD_GATE_POS[2]
            items.append((wx, y + 6.6, wz,
                          "LEARN ISLAM \u2014 the room of the Word [E] \u00b7 "
                          "the Qur'an read in the wire, words on light",
                          (0.72, 0.90, 1.0)))
            hx, hy, hz = MACHINE_HATCH_POS
            items.append((hx, y + 4.4, hz,
                          "THE MACHINE \u2014 down into this host [E] \u00b7 "
                          "the box under your feet, read live",
                          (0.62, 1.0, 0.72)))
        else:
            st = self.world["strata"][self.active - 1]
            for a in st["artifacts"]:
                x, z = a["pos"]
                sub = f"  ({a['sub']})" if a["kind"] != "electron" and a.get("sub") else ""
                items.append((x, y + 6.5, z, a["label"] + sub, (0.9, 0.95, 1.0)))
        for (x, yy, z, txt, col) in items:
            try:
                sx, sy, sz = gluProject(x, yy, z)
            except Exception:
                continue
            if sz < 0 or sz > 1:
                continue
            out.append((sx, vp[3] - sy, txt, col))
        return out

    def _real_or_friendly(self, friendly, kind, obj):
        if not self.show_real:
            return friendly
        return friendly

    # ---- input -------------------------------------------------------------
    def keyPressEvent(self, e):
        k = e.key()
        if self.service is not None:
            if (k in (Qt.Key.Key_Escape, Qt.Key.Key_Home,
                      Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight,
                      Qt.Key.Key_PageUp, Qt.Key.Key_PageDown)
                    or Qt.Key.Key_0 <= k <= Qt.Key.Key_9
                    or self.web_mono is not None or self._at_console()):
                self._web_key(e)
                return
        if self.candles_select:
            # the interval chooser at the candle room's door: number keys pick,
            # Esc cancels. Movement is held while you choose.
            if k == Qt.Key.Key_Escape:
                self.candles_select = False
                self.candles_ivs = []
                self._flash("candle room \u2014 cancelled")
            elif Qt.Key.Key_1 <= k <= Qt.Key.Key_9:
                i = k - Qt.Key.Key_1
                if 0 <= i < len(self.candles_ivs):
                    self._enter_candles(self.candles_ivs[i]["interval"])
            super().keyPressEvent(e)
            return
        if k == Qt.Key.Key_Escape:
            self._drag = False
            if self._looklocked:
                self.set_look_lock(False)      # free the mouse first; press again to leave full screen
                super().keyPressEvent(e)
                return
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.escape_request.emit()       # the tab drops full screen if it is on
            if self.market and self.selected_agent:
                self.selected_agent = None
                self.selected = None
                self._flash("closed the trading panel")
        elif k == Qt.Key.Key_E:
            if self.deep is not None:
                self._exit_deep()          # rise back to the edge
            else:
                self._interact()
        elif k == Qt.Key.Key_B:
            if self.candles:
                self.refresh_candles()
            elif self.machine:
                self.refresh_machine()
            elif self.market:
                self.refresh_market()
            elif not self.word:
                self.request_rebuild.emit()
        elif k == Qt.Key.Key_X:
            if self.machine:
                self.machine_xray = not self.machine_xray
                if self.machine_xray:
                    self._flash("x-ray on \u2014 see through the shell's wall to the "
                                "door a dark figure has touched")
                else:
                    self._flash("x-ray off")
        elif k == Qt.Key.Key_K:
            if self.machine:
                self._machine_arm_toggle()
        elif k == Qt.Key.Key_L:
            if self.machine:
                self._machine_release_toggle()
        elif k == Qt.Key.Key_M:
            if self.machine:
                self._machine_autoguard_toggle()
        elif k == Qt.Key.Key_BracketLeft:
            self._word_move(-1)
        elif k == Qt.Key.Key_BracketRight:
            self._word_move(1)
        elif k == Qt.Key.Key_T:
            self.show_real = not self.show_real
        elif k == Qt.Key.Key_R:
            if self.word:
                if self.word_mode == "select":
                    self._word_random()
                else:
                    self._word_to_select()
        elif k == Qt.Key.Key_H:
            self.menu_toggle.emit(True)
        elif k == Qt.Key.Key_Home:
            if self.candles:
                self._leave_candles()
            elif self.market:
                self._leave_market()
            elif self.word:
                self._leave_word()
            elif self.exchange:
                self._leave_exchange()
            elif self.machine:
                self._leave_machine()
            elif self.deep is not None:
                self._exit_deep(surface=True)
            else:
                self._go_surface()
        elif k == Qt.Key.Key_G:
            self._toggle_fly()
        elif k == Qt.Key.Key_Tab:
            self.menu_request.emit()          # open the game menu (Tab toggles)
        elif k == Qt.Key.Key_F11:
            self.fullscreen_request.emit()
        else:
            self.keys.add(k)
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        self.keys.discard(e.key())
        super().keyReleaseEvent(e)

    def focusNextPrevChild(self, _next):
        # Tab opens the game menu — it must never be swallowed by focus travel.
        return False

    def wheelEvent(self, e):
        # the wheel no longer travels the ayah — use the next/prev buttons, the
        # [ ] keys, or the gates. Scrolling stays out of the reading.
        super().wheelEvent(e)

    def _look_center(self):
        c = self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2))
        QCursor.setPos(c)
        self._last_xy = QPoint(self.width() // 2, self.height() // 2)

    def set_look_lock(self, on):
        """Capture the mouse (hide + pin it to the middle) so moving the mouse
        turns the view smoothly in any direction while you keep walking or
        flying — no need to stop, no edge to run into. Esc or right-click frees
        it again so you can reach the panels."""
        on = bool(on)
        if on == self._looklocked:
            return
        self._looklocked = on
        if on:
            self._drag = False
            self.setCursor(Qt.CursorShape.BlankCursor)
            self.setMouseTracking(True)
            self._look_center()
        else:
            self.unsetCursor()
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def focusOutEvent(self, e):
        if self._looklocked:
            self.set_look_lock(False)
        super().focusOutEvent(e)

    def mousePressEvent(self, e):
        self.setFocus()
        if e.button() == Qt.MouseButton.RightButton:
            if self._looklocked:
                self.set_look_lock(False)      # release the mouse back to the panels
            return
        if e.button() == Qt.MouseButton.LeftButton:
            if not self._looklocked:
                self.set_look_lock(True)       # click the world to grab the mouse
            else:
                self._drag = True              # (fallback) legacy drag while locked
                self._last_xy = e.position().toPoint()

    def mouseReleaseEvent(self, e):
        self._drag = False

    def mouseMoveEvent(self, e):
        if self._looklocked:
            p = e.position().toPoint()
            cx, cy = self.width() // 2, self.height() // 2
            dx, dy = p.x() - cx, p.y() - cy
            if dx or dy:
                s = 0.004 * self.look_sens
                self.yaw += dx * s
                self.pitch = max(-1.35, min(1.35, self.pitch - dy * s))
                self._look_center()
        elif self._drag and self._last_xy is not None:
            p = e.position().toPoint()
            dx = p.x() - self._last_xy.x()
            dy = p.y() - self._last_xy.y()
            s = 0.004 * self.look_sens
            self.yaw += dx * s
            self.pitch = max(-1.2, min(1.2, self.pitch - dy * s))
            self._last_xy = p

    # ---- movement + interaction -------------------------------------------
    def _step(self, dt):
        self._net_tick()
        self._speed_now = 0.0
        if self.candles:
            self._candles_step(dt)
            return
        if self.exchange:
            if self.service is None or not self._at_console():
                self._exchange_step(dt)
            self._packet_step(dt)
            self._web_tick()
            return
        if self.market:
            self._market_step(dt)
            return
        if self.word:
            self._word_step(dt)
            return
        if self.machine:
            self._machine_step(dt)
            return
        if self.deep is not None:
            d = self.deep
            d["vy"] = min(22.0, d["vy"] + 16.0 * dt)     # fall, then terminal drift
            d["d"] += d["vy"] * dt
            ang = d["d"] * 0.045
            self.pos[0] = 1.4 * math.sin(ang)
            self.pos[2] = 1.4 * math.cos(ang * 0.71)
            self.pos[1] = self._floor_y(5) + EYE - d["d"]
            self.pitch = max(-1.15, self.pitch - 0.20 * dt)   # settle into the fall
            return
        if self.transition:
            tr = self.transition
            tr["t"] += dt
            u = min(1.0, tr["t"] / tr["dur"])
            ease = u * u * (3 - 2 * u)
            ty = self._floor_y(tr["to"]) + EYE
            # horizontal: draw to the well mouth, drop through the shaft, step out
            if u < 0.32:
                ke = (u / 0.32) ** 2 * (3 - 2 * (u / 0.32))
                r = tr["from_r"] * (1 - ke)
                self.pos[0] = r * math.cos(tr["from_angle"])
                self.pos[2] = r * math.sin(tr["from_angle"])
            elif u < 0.72:
                self.pos[0] = self.pos[2] = 0.0
            else:
                ke = ((u - 0.72) / 0.28) ** 2 * (3 - 2 * ((u - 0.72) / 0.28))
                self.pos[0] = 0.0
                self.pos[2] = 7.0 * ke
            # vertical: the whole fall is one eased drop
            self.pos[1] = tr["from_y"] + (ty - tr["from_y"]) * ease
            # pitch dips to look down the shaft, then levels out at the floor
            if u < 0.35:
                self.pitch = tr["from_pitch"] * (1 - u / 0.35) + (-1.15) * (u / 0.35)
            elif u < 0.70:
                self.pitch = -1.15
            else:
                ke = ((u - 0.70) / 0.30) ** 2 * (3 - 2 * ((u - 0.70) / 0.30))
                self.pitch = -1.15 * (1 - ke) + (-0.05) * ke
            self.yaw = tr["from_yaw"]
            if u >= 1.0:
                self.transition = None
                self.pitch = -0.05
            return
        k = self.keys
        fast = self._boost()
        spd = 9.0 * self.walk_mult * fast * dt
        yaw_spd = 1.8 * dt
        if Qt.Key.Key_Left in k or Qt.Key.Key_Q in k:
            self.yaw -= yaw_spd
        if Qt.Key.Key_Right in k:
            self.yaw += yaw_spd
        if Qt.Key.Key_Up in k or Qt.Key.Key_R in k:
            self.pitch = min(1.2, self.pitch + yaw_spd)
        if Qt.Key.Key_Down in k or Qt.Key.Key_F in k:
            self.pitch = max(-1.2, self.pitch - yaw_spd)
        if self.flying:
            self._fly_step(dt, fast)
            return
        fx, fz = math.sin(self.yaw), -math.cos(self.yaw)
        rx, rz = math.cos(self.yaw), math.sin(self.yaw)
        dx = dz = 0.0
        if Qt.Key.Key_W in k:
            dx += fx; dz += fz
        if Qt.Key.Key_S in k:
            dx -= fx; dz -= fz
        if Qt.Key.Key_A in k:
            dx -= rx; dz -= rz
        if Qt.Key.Key_D in k:
            dx += rx; dz += rz
        m = math.hypot(dx, dz)
        if m > 0:
            self._speed_now = 9.0 * self.walk_mult * fast
            dx, dz = dx / m * spd, dz / m * spd
            nx, nz = self.pos[0] + dx, self.pos[2] + dz
            rr = math.hypot(nx, nz)
            if rr > PLATFORM_R - 1.5:
                nx, nz = nx / rr * (PLATFORM_R - 1.5), nz / rr * (PLATFORM_R - 1.5)
            # the wall between your segment and the ruins: you cross only at a door
            if self.active == 0:
                r_old = math.hypot(self.pos[0], self.pos[2])
                r_new = rr
                if (r_old - WALL_R) * (r_new - WALL_R) < 0 and r_new > 1e-6:
                    if self._in_door(math.atan2(nz, nx)) is None:
                        side = WALL_R - 0.7 if r_old < WALL_R else WALL_R + 0.7
                        nx, nz = nx / r_new * side, nz / r_new * side
            self.pos[0], self.pos[2] = nx, nz
        # gentle step height for the eye
        self.pos[1] = self._floor_y() + EYE

    # ---- flight: move freely through the wire (G) -------------------------
    def _toggle_fly(self):
        if self.deep is not None or self.transition is not None or self.machine \
                or self.candles:
            return
        self.flying = not self.flying
        if not self.flying:
            self.pos[1] = self._floor_y() + EYE     # settle back onto the floor
            self._flash("landed on the wire")
        else:
            self._flash("flight on — Space up \u00b7 C down \u00b7 W/S/A/D glide")

    def _fly_step(self, dt, fast):
        k = self.keys
        spd = 13.0 * self.move_mult * fast * dt
        cp = math.cos(self.pitch)
        fx, fy, fz = cp * math.sin(self.yaw), math.sin(self.pitch), -cp * math.cos(self.yaw)
        rx, rz = math.cos(self.yaw), math.sin(self.yaw)
        dx = dy = dz = 0.0
        if Qt.Key.Key_W in k:
            dx += fx; dy += fy; dz += fz
        if Qt.Key.Key_S in k:
            dx -= fx; dy -= fy; dz -= fz
        if Qt.Key.Key_A in k:
            dx -= rx; dz -= rz
        if Qt.Key.Key_D in k:
            dx += rx; dz += rz
        if Qt.Key.Key_Space in k:
            dy += 1.0
        if Qt.Key.Key_C in k:
            dy -= 1.0
        m = math.sqrt(dx * dx + dy * dy + dz * dz)
        if m > 0:
            self._speed_now = 13.0 * self.move_mult * fast
            self.pos[0] += dx / m * spd
            self.pos[1] += dy / m * spd
            self.pos[2] += dz / m * spd
        rr = math.hypot(self.pos[0], self.pos[2])
        # the floor ends at PLATFORM_R — except the pier, which runs out over the
        # open sea to the outward gate. There, and only there, you may go past it.
        ang = math.atan2(self.pos[2], self.pos[0])
        on_pier = abs((ang - NET_ANGLE + math.pi) % (2 * math.pi) - math.pi) <= NET_WEDGE_HALF
        cap = (NET_PIER_OUT - 1.0) if on_pier else (PLATFORM_R - 1.5)
        if rr > cap:
            self.pos[0] = self.pos[0] / rr * cap
            self.pos[2] = self.pos[2] / rr * cap
        # the nearest stratum is the layer you see: glide up and down the stack,
        # and past the edge into the open sea (still just atmosphere, no entity).
        self.active = min(range(len(STRATA_Y)),
                          key=lambda i: abs((STRATA_Y[i] + EYE) - self.pos[1]))
        hi = EYE + 36.0
        lo = STRATA_Y[-1] + EYE - 60.0
        self.pos[1] = max(lo, min(hi, self.pos[1]))

    # ---- the market: blackhorse, entered from the wire ---------------------
    def _market_floor(self):
        if self.market_world:
            return float(self.market_world.get("floor_y", MARKET_FLOOR_Y))
        return MARKET_FLOOR_Y

    def _enter_market(self):
        try:
            self.market_world = wiregate.snapshot()
        except Exception as e:
            self._flash(f"could not open the market: {e}")
            return
        if self.presence is None:
            self.presence = wiregate.Presence()
            self.presence.start()
        self._ghost_line = self.presence.describe()
        self.market = True
        self.transition = None
        self.deep = None
        self.flying = True
        self.active = 0
        self.selected_agent = None
        self.selected = None
        self._beat = 0.0
        self._peers = self.presence.peers() if self.presence else []
        floor = self._market_floor()
        self.pos = [0.0, floor + EYE, 30.0]
        self.yaw = 0.0
        self.pitch = -0.05
        acc = self.market_world.get("account", {})
        self._flash(f"blackhorse \u2014 the market \u00b7 {acc.get('mode')} "
                    f"\u00b7 cash {acc.get('cash')} {acc.get('currency')}")
        self.market_opened.emit(self.market_world)

    def _leave_market(self):
        was = self.market
        self.market = False
        self.market_world = None
        self.selected_agent = None
        self.selected = None
        self.flying = False
        if self.presence is not None:
            try:
                self.presence.leave()
            except Exception:
                pass
        self.pos = [16.0, EYE, -8.0]
        self.yaw = math.pi
        self.pitch = -0.05
        self.active = 0
        if was:
            self._flash("back on the wire \u2014 the market is closed")
            self.market_closed.emit()

    def refresh_market(self):
        """Re-read blackhorse's files and rebuild the market floor (B inside)."""
        if not self.market:
            return
        try:
            self.market_world = wiregate.snapshot()
        except Exception as e:
            self._flash(f"market rebuild failed: {e}")
            return
        if self.market_world:
            self._flash(f"market rebuilt \u00b7 fp {self.market_world.get('fingerprint')}")
            self.market_opened.emit(self.market_world)
            self.update()

    def _market_step(self, dt):
        k = self.keys
        fast = self._boost()
        spd = 13.0 * self.move_mult * fast * dt
        cp = math.cos(self.pitch)
        fx, fy, fz = cp * math.sin(self.yaw), math.sin(self.pitch), -cp * math.cos(self.yaw)
        rx, rz = math.cos(self.yaw), math.sin(self.yaw)
        dx = dy = dz = 0.0
        if Qt.Key.Key_W in k:
            dx += fx; dy += fy; dz += fz
        if Qt.Key.Key_S in k:
            dx -= fx; dy -= fy; dz -= fz
        if Qt.Key.Key_A in k:
            dx -= rx; dz -= rz
        if Qt.Key.Key_D in k:
            dx += rx; dz += rz
        if Qt.Key.Key_Space in k:
            dy += 1.0
        if Qt.Key.Key_C in k:
            dy -= 1.0
        m = math.sqrt(dx * dx + dy * dy + dz * dz)
        descending = dy < -0.01
        if m > 0:
            self._speed_now = 13.0 * self.move_mult * fast
            if self._on_any_platform() is not None and not descending:
                self.flying = True          # step off the pad / take a lift
            self.pos[0] += dx / m * spd
            self.pos[1] += dy / m * spd
            self.pos[2] += dz / m * spd
        rr = math.hypot(self.pos[0], self.pos[2])
        if rr > MARKET_R - 1.5:
            self.pos[0] = self.pos[0] / rr * (MARKET_R - 1.5)
            self.pos[2] = self.pos[2] / rr * (MARKET_R - 1.5)
        floor = self._market_floor()
        self.pos[1] = max(floor + EYE * 0.4, min(floor + 64.0, self.pos[1]))
        # announce to the relay on a beat, then read who else is here
        self._beat += dt
        if self.presence and self._beat >= 1.2:
            self._beat = 0.0
            ok = self.presence.announce({"x": self.pos[0], "y": self.pos[1], "z": self.pos[2]})
            self._peers = self.presence.peers()
            self._online = ok
            self._ghost_line = self.presence.describe()
        # landing: you only come to rest on a pad when you descend onto it from
        # above while flying — a single, deliberate touch. Stepping off is always
        # free, and a pad never grabs you back after you leave its deck.
        w = self.market_world
        if w:
            for a in w["agents"]:
                x, yy, z = a["pos"]
                d2 = math.hypot(self.pos[0] - x, self.pos[2] - z)
                prev_above = getattr(self, "_land_prev_y", None) is None or \
                    self._land_prev_y > yy + EYE + 0.2
                if (self.flying and descending and prev_above
                        and d2 <= a.get("radius", 4.2) + 1.0
                        and self.pos[1] <= yy + EYE + 3.4):
                    self.flying = False
                    self.pos[0], self.pos[1], self.pos[2] = x, yy + EYE, z
                    if self.selected_agent != a["id"]:
                        self.selected_agent = a["id"]
                        self.selected = a
                        self._flash(f"you are standing on {a['name']}'s platform "
                                    f"\u2014 [E] open its trading settings")
                    break
        self._land_prev_y = self.pos[1]

    def _on_any_platform(self, ignore=0.0, pad_only=True):
        w = self.market_world or {}
        for a in w.get("agents", []):
            x, yy, z = a["pos"]
            if math.hypot(self.pos[0] - x, self.pos[2] - z) <= a.get("radius", 4.2) + 1.0 \
                    and abs(self.pos[1] - yy) <= 3.4:
                return a
        return None

    # ---- the room of the Word: chapters hall + a world for each ayah --------
    def _word_gate_xy(self, angle):
        rr = WORD_R - 6.0
        return (rr * math.cos(angle), rr * math.sin(angle))

    def _word_surah_by_number(self, n):
        for s in self._word_suras:
            if s["number"] == n:
                return s
        return None

    def _word_chapter_points(self, n):
        """Scatter the n chapter-stars through a tall cylinder of sky with a
        best-candidate (blue-noise) spread — the same sky every time, but wide
        and far apart, so you fly a little adventure between chapters."""
        if self._word_cluster is None or self._word_cluster_n != n:
            rnd = random.Random(20261011)
            y0, y1 = WORD_FLOOR_Y + 5.0, WORD_CLUSTER_TOP
            pts = []
            for _ in range(n):
                best, bd = None, -1.0
                for _ in range(40):
                    a = rnd.uniform(0.0, 2.0 * math.pi)
                    r = WORD_CLUSTER_R * math.sqrt(0.12 + 0.88 * rnd.random())
                    p = (r * math.cos(a), rnd.uniform(y0, y1), r * math.sin(a))
                    d = min((math.dist(p, q) for q in pts), default=1e9)
                    if d > bd:
                        bd, best = d, p
                pts.append(best)
            self._word_cluster = pts
            self._word_cluster_n = n
        return self._word_cluster

    def _word_chapter_pos(self, i, n):
        """Where chapter i hangs among the stars (a fixed scatter, cached)."""
        pts = self._word_chapter_points(n)
        return pts[i % len(pts)]

    def _word_random_pos(self):
        return (0.0, WORD_FLOOR_Y + 20.0, 0.0)

    def _word_star_points(self):
        """A fixed field of small stars to fly through — atmosphere, nothing more."""
        if self._word_stars is None:
            rnd = random.Random(20261011)
            pts = []
            for _ in range(360):
                a = rnd.random() * 2 * math.pi
                rr = (WORD_R - 2.0) * math.sqrt(rnd.random())
                y = WORD_FLOOR_Y + 1.5 + rnd.random() * 58.0
                pts.append((rr * math.cos(a), y, rr * math.sin(a),
                            rnd.random() * 6.283, 0.6 + rnd.random() * 1.6))
            self._word_stars = pts
        return self._word_stars

    def _word_to_select(self, start=False, quiet=False):
        """Open (or return to) the hall of chapters."""
        self.word_mode = "select"
        self.word_ref = None
        self._word_reci = None
        self.pos = [0.0, WORD_FLOOR_Y + EYE, WORD_R - 11.0]
        self.yaw = 0.0
        self.pitch = -0.04
        if start:
            self._flash("LEARN ISLAM \u2014 a cluster of chapters, hung like stars. "
                        "Fly to a star and press E \u00b7 R opens a random chapter")
        elif not quiet:
            self._flash("back to the cluster of chapters \u2014 fly to another star, "
                        "or leave by the far gate")
        self.word_changed.emit()
        self.update()

    def _word_enter_ayah(self, surah, idx):
        """Step into the world of one ayah — its text written on the sky."""
        ay = surah["ayahs"]
        idx = max(0, min(idx, len(ay) - 1))
        self.word_mode = "ayah"
        self.word_ref = (surah["number"], idx)
        self._word_reci = quranworld.recipe(surah, ay[idx])
        self.pos = [0.0, WORD_FLOOR_Y + EYE, WORD_R - 11.0]
        self.yaw = 0.0
        self.pitch = 0.05
        self._flash(f"{surah['number']}:{ay[idx]['n']}  \u00b7  {surah['name']}  "
                    f"\u00b7  [ ] travel the ayah \u00b7 R the chapters")
        self.word_changed.emit()

    def _word_move(self, d):
        """[ ] — travel ayah by ayah; the end returns to the chapters."""
        if not self.word or self.word_mode != "ayah" or not self.word_ref:
            return
        num, idx = self.word_ref
        surah = self._word_surah_by_number(num)
        if surah is None:
            return
        nxt = idx + d
        if nxt < 0:
            self._flash("this is the first ayah of the chapter")
            return
        if nxt >= len(surah["ayahs"]):
            self._flash("the chapter is complete \u2014 back to the chapters")
            self._word_to_select(quiet=True)
            return
        self._word_enter_ayah(surah, nxt)

    # -- the same moves, for the on-screen buttons (a reader who does not fly) --
    def word_next(self):
        self._word_move(1)

    def word_prev(self):
        self._word_move(-1)

    def word_back_to_chapters(self):
        self._word_to_select()

    def word_lucky(self):
        self._word_random()

    def word_leave_room(self):
        self._leave_word()

    def word_open_surah(self, number):
        """Open any chapter by its mushaf number (from the codex list)."""
        if not self.word:
            self._enter_word()
        s = self._word_surah_by_number(number)
        if s is not None:
            self._word_enter_ayah(s, 0)

    def _word_random(self):
        """A random chapter, opening at its first ayah — travel on from there."""
        if not self._word_suras:
            self._word_suras = quran.all_suras()
        s = random.choice(self._word_suras)
        self._word_enter_ayah(s, 0)
        self._flash(f"a random chapter \u2014 {s['number']} {s['name']} "
                    f"({s['translation']}) \u00b7 [ ] travel on \u00b7 R the chapters")

    def _word_has_prev(self):
        return bool(self.word_ref) and self.word_ref[1] > 0

    def _word_at_end(self):
        if not self.word_ref:
            return False
        surah = self._word_surah_by_number(self.word_ref[0])
        return bool(surah) and self.word_ref[1] >= len(surah["ayahs"]) - 1

    def _enter_word(self):
        if self.presence is None:
            self.presence = wiregate.Presence()
            self.presence.start()
        self._ghost_line = self.presence.describe()
        self.word = True
        self.market = False
        self.market_world = None
        self.transition = None
        self.deep = None
        self.flying = True
        self.active = 0
        self._beat = 0.0
        self._peers = self.presence.peers() if self.presence else []
        self._word_suras = quran.all_suras()
        self._word_to_select(start=True)

    def _leave_word(self):
        was = self.word
        self.word = False
        self.word_mode = "select"
        self.word_ref = None
        self._word_reci = None
        self._word_suras = []
        self.selected_agent = None
        self.selected = None
        self.flying = False
        if self.presence is not None:
            try:
                self.presence.leave()
            except Exception:
                pass
        self.pos = [-16.0, EYE, 0.0]
        self.yaw = -math.pi / 2
        self.pitch = -0.05
        self.active = 0
        if was:
            self._flash("back on the wire \u2014 the room of the Word is still "
                        "there, whenever you turn back to it")
        self.word_changed.emit()

    def _word_step(self, dt):
        k = self.keys
        fast = self._boost()
        spd = 13.0 * self.move_mult * fast * dt
        cp = math.cos(self.pitch)
        fx, fy, fz = cp * math.sin(self.yaw), math.sin(self.pitch), -cp * math.cos(self.yaw)
        rx, rz = math.cos(self.yaw), math.sin(self.yaw)
        dx = dy = dz = 0.0
        if Qt.Key.Key_W in k:
            dx += fx; dy += fy; dz += fz
        if Qt.Key.Key_S in k:
            dx -= fx; dy -= fy; dz -= fz
        if Qt.Key.Key_A in k:
            dx -= rx; dz -= rz
        if Qt.Key.Key_D in k:
            dx += rx; dz += rz
        if Qt.Key.Key_Space in k:
            dy += 1.0
        if Qt.Key.Key_C in k:
            dy -= 1.0
        m = math.sqrt(dx * dx + dy * dy + dz * dz)
        if m > 0:
            self._speed_now = 13.0 * self.move_mult * fast
            self.pos[0] += dx / m * spd
            self.pos[1] += dy / m * spd
            self.pos[2] += dz / m * spd
        rr = math.hypot(self.pos[0], self.pos[2])
        if rr > WORD_R - 1.5:
            self.pos[0] = self.pos[0] / rr * (WORD_R - 1.5)
            self.pos[2] = self.pos[2] / rr * (WORD_R - 1.5)
        self.pos[1] = max(WORD_FLOOR_Y + EYE * 0.4,
                          min(WORD_FLOOR_Y + 64.0, self.pos[1]))
        self._beat += dt
        if self.presence and self._beat >= 1.2:
            self._beat = 0.0
            ok = self.presence.announce({"x": self.pos[0], "y": self.pos[1],
                                         "z": self.pos[2]})
            self._peers = self.presence.peers()
            self._online = ok
            self._ghost_line = self.presence.describe()

    # ---- the machine: the box under your feet --------------------------------
    def _machine_door_pos(self, i, n):
        a = 2 * math.pi * i / max(1, n) - math.pi * 0.5
        return (MACHINE_DOOR_R * math.cos(a), MACHINE_FLOOR_Y,
                MACHINE_DOOR_R * math.sin(a))

    def _machine_figure_pos(self, i, n):
        a = 2 * math.pi * i / max(1, n) + 0.35
        return (MACHINE_FIGURE_R * math.cos(a), MACHINE_FLOOR_Y,
                MACHINE_FIGURE_R * math.sin(a))

    def _machine_road_end(self, i, n):
        a = 2 * math.pi * i / max(1, n) + 0.9
        r = MACHINE_R - 3.0
        return (r * math.cos(a), r * math.sin(a))

    def _machine_at_door(self, a, n):
        for i in range(max(1, n)):
            da = 2 * math.pi * i / max(1, n) - math.pi * 0.5
            if abs((a - da + math.pi) % (2 * math.pi) - math.pi) <= 0.16:
                return True
        return False

    def _machine_door_index(self, door):
        doors = (self.machine_world or {}).get("doors", [])
        try:
            return doors.index(door), max(1, len(doors))
        except ValueError:
            return 0, max(1, len(doors))

    def _machine_door_for_figure(self, fig):
        """Resolve a figure's 'touched' door against the doors we actually have,
        for the x-ray line only — never a guess: only a port we can truly see."""
        for d in (self.machine_world or {}).get("doors", []):
            if f":{d['lport']}" in (fig.get("touched") or ""):
                i, n = self._machine_door_index(d)
                return self._machine_door_pos(i, n)
        return None

    def _enter_machine(self):
        """Step down the hatch into THIS machine — a local, defensive model."""
        try:
            self.machine_world = machinevision.build()
        except Exception as e:
            self._flash(f"could not read the machine: {e}")
            return
        self.machine = True
        self.market = False
        self.word = False
        self.exchange = False
        self.market_world = None
        self.deep = None
        self.transition = None
        self.service = None
        self.machine_xray = False
        self.machine_birds_armed = False
        self._machine_arm_until = 0.0
        self._machine_contain_confirm = None
        self._machine_release_until = 0.0
        self.machine_autoguard = False
        self._machine_auto_until = 0.0
        self._auto_attempts = {}
        try:
            self._machine_contained = birdguard.contained()
        except Exception:
            self._machine_contained = {}
        self.flying = True
        self.active = 0
        self.pos = [0.0, MACHINE_FLOOR_Y + EYE, 11.0]
        self.yaw = 0.0
        self.pitch = -0.03
        h = self.machine_world.get("host", {})
        c = self.machine_world.get("counts", {})
        b = self.machine_world.get("birds", [])
        held = f" \u00b7 {len(self._machine_contained)} held" if self._machine_contained else ""
        self._flash(f"the machine \u00b7 {h.get('name', '?')} \u2014 {c.get('doors', 0)} doors "
                    f"\u00b7 {c.get('roads', 0)} roads \u00b7 {c.get('inhabitants', 0)} "
                    f"inhabitants \u00b7 {c.get('figures', 0)} dark figures \u00b7 "
                    f"{len(b)} birds (read-only{held})")
        if self.live_effective == "capture":
            self._start_capture()
        self.machine_changed.emit()

    def _leave_machine(self):
        was = self.machine
        self.machine = False
        self.machine_world = None
        self._stop_capture()            # never capture while you are elsewhere
        self.machine_xray = False
        self.machine_birds_armed = False
        self._machine_arm_until = 0.0
        self._machine_contain_confirm = None
        self._machine_release_until = 0.0
        self.machine_autoguard = False
        self._machine_auto_until = 0.0
        self._auto_attempts = {}
        self.flying = False
        self.pos = [0.0, EYE, 19.0]
        self.yaw = math.pi
        self.pitch = -0.05
        self.active = 0
        if was:
            self._flash("back on the wire \u2014 the machine is still under your feet")
        self.machine_changed.emit()

    def refresh_machine(self):
        """Re-read THIS host from /proc and rebuild the machine room (B inside)."""
        if not self.machine:
            return
        try:
            self.machine_world = machinevision.build()
        except Exception as e:
            self._flash(f"machine rebuild failed: {e}")
            return
        h = self.machine_world.get("host", {})
        c = self.machine_world.get("counts", {})
        self._flash(f"machine rebuilt \u00b7 {h.get('name', '?')} \u00b7 "
                    f"{c.get('doors', 0)} doors \u00b7 {c.get('figures', 0)} dark figures")
        self.update()

    def _machine_step(self, dt):
        k = self.keys
        fast = self._boost()
        spd = 13.0 * self.move_mult * fast * dt
        cp = math.cos(self.pitch)
        fx, fy, fz = cp * math.sin(self.yaw), math.sin(self.pitch), -cp * math.cos(self.yaw)
        rx, rz = math.cos(self.yaw), math.sin(self.yaw)
        dx = dy = dz = 0.0
        if Qt.Key.Key_W in k:
            dx += fx; dy += fy; dz += fz
        if Qt.Key.Key_S in k:
            dx -= fx; dy -= fy; dz -= fz
        if Qt.Key.Key_A in k:
            dx -= rx; dz -= rz
        if Qt.Key.Key_D in k:
            dx += rx; dz += rz
        if Qt.Key.Key_Space in k:
            dy += 1.0
        if Qt.Key.Key_C in k:
            dy -= 1.0
        m = math.sqrt(dx * dx + dy * dy + dz * dz)
        if m > 0:
            self._speed_now = 13.0 * self.move_mult * fast
            self.pos[0] += dx / m * spd
            self.pos[1] += dy / m * spd
            self.pos[2] += dz / m * spd
        rr = math.hypot(self.pos[0], self.pos[2])
        if rr > MACHINE_R - 1.5:
            self.pos[0] = self.pos[0] / rr * (MACHINE_R - 1.5)
            self.pos[2] = self.pos[2] / rr * (MACHINE_R - 1.5)
        self.pos[1] = max(MACHINE_FLOOR_Y + EYE * 0.4,
                          min(MACHINE_FLOOR_Y + 46.0, self.pos[1]))

    def _machine_sky(self):
        glClearColor(0.006, 0.014, 0.011, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        y = MACHINE_FLOOR_Y
        glLineWidth(1.0)
        glColor4f(0.10, 0.24, 0.16, 1.0)
        glBegin(GL_LINE_LOOP)
        for i in range(64):
            a = 2 * math.pi * i / 64
            glVertex3f((MACHINE_R - 1.0) * math.cos(a), y + 0.02,
                       (MACHINE_R - 1.0) * math.sin(a))
        glEnd()

    def _draw_machine(self, t):
        w = self.machine_world or {}
        y = MACHINE_FLOOR_Y
        g = MACHINE_COL
        # the floor: a slab of dark steel with a diagnostic ring grid
        glColor4f(0.010, 0.026, 0.020, 1.0)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, y, 0)
        for i in range(49):
            a = 2 * math.pi * i / 48
            glVertex3f(MACHINE_R * math.cos(a), y, MACHINE_R * math.sin(a))
        glEnd()
        for r in (7, 14, 21, MACHINE_WALL_R):
            glColor4f(0.05, 0.16, 0.11, 1.0)
            glBegin(GL_LINE_LOOP)
            for i in range(64):
                a = 2 * math.pi * i / 64
                glVertex3f(r * math.cos(a), y + 0.03, r * math.sin(a))
            glEnd()

        # the shell's wall: a hard ring outside the doors, broken at each door
        doors = w.get("doors", [])
        nd = max(1, len(doors))
        step = 0.09
        a = 0.0
        while a < 2 * math.pi:
            if not self._machine_at_door(a, nd):
                xx, zz = MACHINE_WALL_R * math.cos(a), MACHINE_WALL_R * math.sin(a)
                self._cube(xx, y + 1.6, zz, 0.5, 3.2, step * MACHINE_WALL_R * 1.2,
                           (0.06, 0.20, 0.13))
            a += step

        # the roads: live connections, paths already drawn on the wire
        roads = w.get("roads", [])
        nr = max(1, len(roads))
        for i, r in enumerate(roads):
            ex, ez = self._machine_road_end(i, nr)
            if r.get("inbound"):
                col = (0.95, 0.45, 0.30)
            elif r.get("external"):
                col = (0.30, 0.70, 0.98)
            else:
                col = (0.35, 0.80, 0.85)
            glColor4f(col[0] * 0.6, col[1] * 0.6, col[2] * 0.6, 0.35)
            glLineWidth(1.0)
            glBegin(GL_LINES)
            glVertex3f(0, y + 0.06, 0)
            glVertex3f(ex, y + 0.06, ez)
            glEnd()
            q = (t * 0.4 + i * 0.37) % 1.0
            qq = (1.0 - q) if r.get("inbound") else q
            mx, mz = ex * qq, ez * qq
            glColor4f(col[0], col[1], col[2], 0.9)
            glBegin(GL_LINES)
            glVertex3f(mx, y + 0.07, mz)
            glVertex3f(mx, y + 0.5, mz)
            glEnd()

        # the shell core: THIS host — a hex monolith breathing like the box
        beat = 1.0 + 0.10 * math.sin(t * 1.4)
        self._prism(0, 0, 2.4 * beat, 1.5 * beat, y, y + 11.0, 6, (0.07, 0.30, 0.20))
        self._prism(0, 0, 1.6 * beat, 2.9 * beat, y + 11.0, y + 13.0, 6, (0.10, 0.40, 0.27))
        self._octa(0, y + 14.4, 0, 1.5 * beat, (0.55, 1.0, 0.72))
        rot = t * 0.5
        glColor4f(g[0], g[1], g[2], 0.5)
        glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        for i in range(48):
            aa = 2 * math.pi * i / 48 + rot
            glVertex3f(3.6 * math.cos(aa), y + 0.08, 3.6 * math.sin(aa))
        glEnd()
        glLineWidth(1.0)

        # the doors: a way in, each with the program that owns it standing at it
        for i, d in enumerate(doors):
            self._machine_door(*self._machine_door_pos(i, nd), d, t)
        # inhabitants that hold no door (a road only) stand beside the core
        self._machine_extra_inhabitants(w, t)

        # the dark figures: intruders in the field, only from local evidence
        figs = w.get("figures", [])
        nf = max(1, len(figs))
        for i, f in enumerate(figs):
            self._machine_figure(*self._machine_figure_pos(i, nf), y, f, t, i)

        # the birds: crow / finch / raven, perched above the core in a slow orbit
        self._machine_birds(w, t)

        # live vision: the motion a real read just measured (the knob)
        self._live_render(w, t)

        # x-ray: the line through the wall to the door a figure touched
        if self.machine_xray and figs:
            glLineWidth(2.0)
            glColor4f(1.0, 0.75, 0.25, 0.85)
            for i, f in enumerate(figs):
                hit = self._machine_door_for_figure(f)
                if hit is None:
                    continue
                fx, _, fz = self._machine_figure_pos(i, nf)
                glBegin(GL_LINES)
                glVertex3f(fx, y + 2.0, fz)
                glVertex3f(hit[0], y + 2.0, hit[2])
                glEnd()
                self._octa(hit[0], y + 3.0, hit[2], 0.5, (1.0, 0.8, 0.3), squash=1.4)
            glLineWidth(1.0)

        # the way back up: the hatch you came down
        rx, ry, rz = MACHINE_RETURN_POS
        self._portal(rx, rz, ry - 0.5, 3.0, (0.45, 0.85, 1.0), t + 0.4)
        self._portal(rx, rz, ry + 2.5, 2.0, (0.28, 0.55, 0.80), t + 1.4)

    def _machine_door(self, x, y, z, d, t):
        col = (0.30, 0.88, 0.58) if d.get("proc") else (0.35, 0.55, 0.45)
        self._cube(x, y + 1.4, z, 1.1, 2.8, 0.4,
                   (col[0] * 0.3, col[1] * 0.35, col[2] * 0.3))
        self._portal(x, z, y + 1.0, 1.5, col, t + x * 0.3)
        if d.get("proc"):
            h = int(hashlib.md5((d.get("proc") or "?").encode()).hexdigest()[:8], 16)
            pc = (0.45 + 0.55 * ((h >> 16) & 255) / 255,
                  0.45 + 0.55 * ((h >> 8) & 255) / 255,
                  0.45 + 0.55 * (h & 255) / 255)
            ix, iz = x * 0.86, z * 0.86
            self._octa(ix, y + 2.6, iz, 0.5, pc, squash=1.2)
            self._cube(ix, y + 1.0, iz, 0.7, 1.2, 0.7,
                       (pc[0] * 0.55, pc[1] * 0.55, pc[2] * 0.55))

    def _machine_extra_inhabitants(self, w, t):
        y = MACHINE_FLOOR_Y
        door_pids = {d.get("pid") for d in w.get("doors", []) if d.get("pid")}
        extra = [p for p in w.get("inhabitants", [])
                 if p.get("pid") not in door_pids and p.get("roads")]
        ne = max(1, len(extra))
        for i, p in enumerate(extra):
            a = 2 * math.pi * i / ne + 1.3
            x, z = 5.5 * math.cos(a), 5.5 * math.sin(a)
            h = int(hashlib.md5((p.get("name") or "?").encode()).hexdigest()[:8], 16)
            pc = (0.45 + 0.55 * ((h >> 16) & 255) / 255,
                  0.45 + 0.55 * ((h >> 8) & 255) / 255,
                  0.45 + 0.55 * (h & 255) / 255)
            self._octa(x, y + 2.0 + 0.25 * math.sin(t * 2 + i), z, 0.5, pc, squash=1.2)
            self._cube(x, y + 1.0, z, 0.7, 1.2, 0.7,
                       (pc[0] * 0.55, pc[1] * 0.55, pc[2] * 0.55))

    def _machine_figure(self, x, y, z, f, t, i):
        sev = int(f.get("severity") or 2)
        k = 0.85 + 0.22 * sev
        col = (0.80, 0.10, 0.14) if sev >= 3 else (0.62, 0.16, 0.24)
        if f.get("confidence") == "inferred":
            col = tuple(c * 0.7 for c in col)
        bob = 0.3 * math.sin(t * 1.6 + i)
        self._octa(x, y + 2.4 * k + bob, z, 0.7 * k, col, squash=1.9)
        self._cube(x, y + 1.0, z, 1.0 * k, 1.6 * k, 1.0 * k,
                   (col[0] * 0.4, col[1] * 0.4, col[2] * 0.45))
        glColor4f(col[0] * 0.5, col[1] * 0.5, col[2] * 0.6, 0.35)
        glLineWidth(1.5)
        glBegin(GL_LINE_LOOP)
        for j in range(20):
            aa = 2 * math.pi * j / 20
            glVertex3f(x + 2.2 * math.cos(aa), y + 0.06, z + 2.2 * math.sin(aa))
        glEnd()
        glLineWidth(1.0)

    def _machine_bird_pos(self, i):
        a = 2 * math.pi * i / 3 - math.pi * 0.5
        return (MACHINE_BIRD_R * math.cos(a), MACHINE_BIRD_Y,
                MACHINE_BIRD_R * math.sin(a))

    def _machine_birds(self, w, t):
        for i, b in enumerate(w.get("birds", [])):
            x, y, z = self._machine_bird_pos(i)
            self._machine_bird(x, y, z, b, t, i)
        # the armed halo: one ring over the whole perch when finch's hand is live
        if self.machine_birds_armed:
            glColor4f(1.0, 0.35, 0.30, 0.5)
            glLineWidth(2.0)
            glBegin(GL_LINE_LOOP)
            for i in range(48):
                a = 2 * math.pi * i / 48 + t * 0.4
                glVertex3f((MACHINE_BIRD_R + 1.6) * math.cos(a), MACHINE_BIRD_Y + 2.6,
                           (MACHINE_BIRD_R + 1.6) * math.sin(a))
            glEnd()
            glLineWidth(1.0)

    def _machine_bird(self, x, y, z, b, t, i):
        kind = b.get("kind", "crow")
        col = BIRD_COL.get(kind, (0.8, 0.8, 0.9))
        bob = 0.4 * math.sin(t * 1.8 + i)
        yy = y + bob
        if kind == "raven":
            k = 1.3
        elif kind == "finch":
            k = 0.8
        else:
            k = 1.0
        # a small low-poly bird: body + two wings that beat
        flap = 0.4 + 0.5 * abs(math.sin(t * 3.2 + i * 1.7))
        glColor4f(col[0] * 0.5, col[1] * 0.5, col[2] * 0.5, 1.0)
        glBegin(GL_TRIANGLES)
        glVertex3f(x, yy, z - 0.6 * k); glVertex3f(x, yy, z + 0.6 * k)
        glVertex3f(x, yy + 0.5 * k, z)
        glVertex3f(x, yy + 0.2 * k, z)
        glVertex3f(x - 1.6 * k, yy + flap * k, z)
        glVertex3f(x, yy + 0.2 * k, z + 0.5 * k)
        glVertex3f(x, yy + 0.2 * k, z)
        glVertex3f(x + 1.6 * k, yy + flap * k, z)
        glVertex3f(x, yy + 0.2 * k, z + 0.5 * k)
        glEnd()
        # an eye/reticle: green when it has nothing to say, red when armed+held
        if kind == "finch" and self.machine_birds_armed:
            ec = (1.0, 0.35, 0.30)
        else:
            ec = (0.75, 1.0, 0.85)
        self._octa(x, yy + 0.15 * k, z, 0.18 * k, ec, squash=1.0)

    def _machine_labels(self):
        out = []
        vp = glGetIntegerv(GL_VIEWPORT)
        items = []
        w = self.machine_world or {}
        y = MACHINE_FLOOR_Y
        doors = w.get("doors", [])
        n = max(1, len(doors))
        px, pz = self.pos[0], self.pos[2]
        ranked = []
        for i, d in enumerate(doors):
            dx, _, dz = self._machine_door_pos(i, n)
            ranked.append(((px - dx) ** 2 + (pz - dz) ** 2, dx, dz, d))
        ranked.sort(key=lambda c: c[0])
        for (_dd, dx, dz, d) in ranked[:6]:
            name = machinevision.SERVICE_NAMES.get(d["lport"], "?")
            who = d.get("proc") or "?"
            items.append((dx, y + 4.2, dz,
                          f"door {d['proto']} :{d['lport']} {name} \u2014 {who} [E]",
                          (0.62, 1.0, 0.72)))
        figs = w.get("figures", [])
        nf = max(1, len(figs))
        for i, f in enumerate(figs):
            fx, _, fz = self._machine_figure_pos(i, nf)
            held = str(f.get("src")) in self._machine_contained
            tag = " \u2014 HELD [L to release]" if held else " [E]"
            items.append((fx, y + 5.4, fz,
                          f"dark figure \u00b7 {f['kind']} {f['src']} \u00b7 {f['confidence']}{tag}",
                          (0.55, 0.95, 0.65) if held else (1.0, 0.45, 0.42)))
        for i, b in enumerate(w.get("birds", [])):
            bx, by, bz = self._machine_bird_pos(i)
            short = b.get("role", "")
            items.append((bx, by + 2.4, bz,
                          f"{b['kind']} \u00b7 {short} [E]" +
                          (" \u00b7 ARMED" if self.machine_birds_armed and b["kind"] == "finch" else ""),
                          BIRD_COL.get(b.get("kind"), (0.8, 0.8, 0.9))))
        items.append((0, y + 16.4, 0,
                      f"THIS MACHINE \u00b7 {w.get('host', {}).get('name', '?')} "
                      f"\u2014 the box under your feet", (0.62, 1.0, 0.72)))
        rx, ry, rz = MACHINE_RETURN_POS
        items.append((rx, ry + 2.6, rz, "up the hatch [E] \u2014 back to the wire",
                      (0.70, 0.90, 1.0)))
        for (x, yy, z, txt, col) in items:
            try:
                sx, sy, sz = gluProject(x, yy, z)
            except Exception:
                continue
            if sz < 0 or sz > 1:
                continue
            out.append((sx, vp[3] - sy, txt, col))
        return out

    def _nearest_machine(self):
        px, pz = self.pos[0], self.pos[2]
        best = None

        def consider(kind, x, z, radius, **kw):
            nonlocal best
            d = math.hypot(px - x, pz - z)
            if d <= radius and (best is None or d < best["d"]):
                best = {"kind": kind, "d": d, **kw}

        w = self.machine_world or {}
        doors = w.get("doors", [])
        n = max(1, len(doors))
        for i, d in enumerate(doors):
            x, _, z = self._machine_door_pos(i, n)
            consider("machine_door", x, z, 3.4, door=d)
        figs = w.get("figures", [])
        nf = max(1, len(figs))
        for i, f in enumerate(figs):
            x, _, z = self._machine_figure_pos(i, nf)
            consider("machine_figure", x, z, 4.2, fig=f)
        for i, b in enumerate(w.get("birds", [])):
            x, _, z = self._machine_bird_pos(i)
            consider("machine_bird", x, z, MACHINE_BIRD_NEAR, bird=b)
        consider("machine_leave", MACHINE_RETURN_POS[0], MACHINE_RETURN_POS[2], 5.5)
        return best

    def _machine_figure_talk(self, f):
        """Read a figure; if the birds are armed, finch may contain it (2-press)."""
        ev = (f.get("evidence") or [""])[0]
        ip = str(f.get("src") or "")
        if not self.machine_birds_armed:
            held = " \u2014 HELD (L to release)" if ip in self._machine_contained else ""
            self._flash(f"dark figure \u00b7 {f['kind']} {f['src']} \u2014 touched "
                        f"{f['touched']} \u00b7 {f['confidence']} \u00b7 {ev}{held} "
                        f"\u2014 press K to arm the birds", 6.0)
            return
        ok, why = birdguard.usable(ip)
        if not ok:
            self._flash(f"finch can't contain {ip or 'that'} \u2014 {why}", 5.0)
            return
        now = time.time()
        conf = self._machine_contain_confirm
        if conf and conf[0] == ip and now < conf[1]:
            res = birdguard.contain(ip, reason=f"dark figure {f['kind']} {f['src']} \u2014 {ev}")
            self._machine_contain_confirm = None
            if res.get("ok"):
                self._machine_contained = birdguard.contained()
                extra = " (dry run)" if res.get("dry") else ""
                self._flash(f"finch contained {ip}{extra} \u2014 host-local DROP in "
                            f"{birdguard.CHAIN}; press L to release", 6.0)
            else:
                self._flash(f"finch could not contain {ip}: "
                            f"{res.get('refused') or res.get('error')}", 6.0)
            return
        self._machine_contain_confirm = (ip, now + 5.0)
        self._flash(f"press E again to CONTAIN {ip} \u2014 a host-local DROP at THIS NIC, "
                    f"never aimed at anyone else", 5.0)

    def _machine_bird_talk(self, b):
        k = b.get("kind")
        armed = self.machine_birds_armed
        if k == "crow":
            msg = (f"crow \u00b7 recon / eyes \u2014 read-only \u00b7 {b.get('age', '?')} \u00b7 "
                   f"{b.get('verdict') or b.get('returned') or 'no report yet'}")
        elif k == "finch":
            msg = (f"finch \u00b7 quarantine / contain (host-local) \u2014 "
                   f"{'ARMED' if armed else 'read-only (K to arm)'} \u00b7 baseline "
                   f"{b.get('baseline_age')} \u00b7 trusted {b.get('trusted_ssid')} \u00b7 "
                   f"{b.get('quarantine_files')} file(s) held")
        else:
            msg = (f"raven \u00b7 scope gate \u2014 read-only \u00b7 up={b.get('up')} "
                   f"gw={b.get('gw')} guard={b.get('guard_mode')} strikes={b.get('strikes')} "
                   f"survival={b.get('survival')}")
        self._flash(msg, 7.0)

    def _machine_arm_toggle(self):
        now = time.time()
        if self.machine_birds_armed:
            self.machine_birds_armed = False
            self.machine_autoguard = False     # auto cannot run unarmed
            self._machine_contain_confirm = None
            self._flash("birds stood down \u2014 read-only again")
            return
        if now < self._machine_arm_until:
            self.machine_birds_armed = True
            self._machine_arm_until = 0.0
            self._flash("birds ARMED \u2014 only finch acts, and only on THIS machine "
                        "(host-local DROP); K to stand down, L to release", 7.0)
            return
        self._machine_arm_until = now + 4.0
        self._flash("press K again to ARM the birds \u2014 finch's hand becomes live, "
                    "host-local only; nothing is ever aimed at another host", 6.0)

    def _machine_release_toggle(self):
        now = time.time()
        if not self._machine_contained:
            self._flash("nothing is held \u2014 the firewall is clean")
            return
        n = len(self._machine_contained)
        if now < self._machine_release_until:
            birdguard.release_all()
            self._machine_contained = {}
            self._machine_release_until = 0.0
            self._machine_contain_confirm = None
            self._flash(f"released {n} held source(s) \u2014 firewall clean")
            return
        self._machine_release_until = now + 4.0
        self._flash(f"press L again to RELEASE all {n} held source(s)")

    def _machine_autoguard_toggle(self):
        """Phase 3: finch detects and contains on its own. Needs the birds armed."""
        now = time.time()
        if self.machine_autoguard:
            self.machine_autoguard = False
            self._machine_auto_until = 0.0
            self._flash("auto-defend OFF \u2014 finch waits for your E again")
            return
        if not self.machine_birds_armed:
            self._flash("auto-defend needs the birds armed first (K)", 5.0)
            return
        if now < self._machine_auto_until:
            self.machine_autoguard = True
            self._machine_auto_until = 0.0
            self._flash("AUTO-DEFEND ON \u2014 finch now finds & contains dark figures by "
                        "itself, host-local only, defensively; L still releases", 8.0)
            return
        self._machine_auto_until = now + 5.0
        self._flash("press M again to switch AUTO-DEFEND ON \u2014 finch acts without E, "
                    "still never aimed at anyone else", 6.0)

    def _machine_autoguard_beat(self):
        """The auto-defend loop: live-detect, then contain on THIS host only.
        Only observed figures (never the inferred road figures), with all of
        birdguard's guardrails, one action per beat, cooldowned per source."""
        if not self.machine or not self.machine_autoguard or not self.machine_birds_armed:
            return
        now = time.time()
        try:
            figs = machinevision.build().get("figures", [])
        except Exception:
            return
        for f in figs:
            if f.get("confidence") == "inferred":
                continue                      # a live road is a pointer, not a crime
            ip = str(f.get("src") or "")
            if not ip or ip in self._machine_contained:
                continue
            if now - self._auto_attempts.get(ip, 0.0) < 30:
                continue                      # cooldown: don't re-bark at a refusal
            self._auto_attempts[ip] = now
            ok, why = birdguard.usable(ip)
            if not ok:
                continue                      # self/gateway/reserved — never touched
            ev = (f.get("evidence") or [""])[0]
            res = birdguard.contain(ip, reason="[auto] " + " \u00b7 ".join(
                str(x) for x in (f.get("kind"), f.get("touched") or "", ev) if x))
            if res.get("ok"):
                try:
                    self.machine_world = machinevision.build()   # room now reflects it
                    self._machine_contained = birdguard.contained()
                except Exception:
                    pass
                dry = " (dry run)" if res.get("dry") else ""
                self._flash(f"AUTO \u00b7 finch contained {ip} \u2014 {f.get('kind')}{dry} "
                            f"\u00b7 host-local DROP at THIS NIC, L to release", 8.0)
                self.update()
            self.machine_changed.emit()
            return

    # ---- live vision (the knob: off / delta / capture / auto) ---------------
    def _apply_saved_live_mode(self):
        try:
            mode = wiresettings.load().get("live_mode", "auto")
        except Exception:
            mode = "off"
        self.set_live_mode(mode, save=False)

    def set_live_mode(self, mode, save=True):
        """Turn the live-vision knob. Returns the auto-detect read, if any."""
        if mode not in wiresettings.MODES:
            mode = "off"
        self.live_mode = mode
        try:
            eff, info = wiresettings.resolve(mode)
        except Exception:
            eff, info = "off", None
        self.live_effective = eff
        self._live_info = info
        self._live_prev = None
        self._live = {}
        self._live_t = 0.0
        self._live_timer.stop()
        self._stop_capture()
        if eff == "delta":
            self._live_timer.start(1000)
            self._live_sample()
        elif eff == "capture":
            self._live_timer.start(2000)     # still read cpu/disk/io for the HUD
            self._live_sample()
            self._start_capture()
        if save:
            try:
                st = wiresettings.load()
                st["live_mode"] = mode
                st["live_effective"] = eff
                wiresettings.save(st)
            except Exception:
                pass
        self.live_changed.emit(self.live_mode, self.live_effective)
        self.update()
        return info

    def _start_capture(self):
        if self._capture is not None or not self.machine:
            return
        iface = "any"
        try:
            iface = ((self.machine_world or {}).get("lifeline", {})
                     .get("iface")) or "any"
        except Exception:
            iface = "any"
        try:
            max_pps = wiresettings.load().get("capture_max_pps", 400)
        except Exception:
            max_pps = 400
        self._capture = _PacketReader(iface, max_pps)
        self._capture.start()

    def _stop_capture(self):
        c, self._capture = self._capture, None
        if c is not None:
            try:
                c.stop()
            except Exception:
                pass

    @staticmethod
    def _rd(path):
        try:
            with open(path) as f:
                return f.read()
        except Exception:
            return ""

    def _read_dev(self):
        out = {}
        for line in self._rd("/proc/net/dev").splitlines():
            if ":" not in line:
                continue
            name, rest = line.split(":", 1)
            f = rest.split()
            if len(f) < 16:
                continue
            try:
                out[name.strip()] = (int(f[0]), int(f[8]), int(f[1]), int(f[9]))
            except Exception:
                pass
        return out

    def _read_stat(self):
        try:
            f = self._rd("/proc/stat").splitlines()[0].split()[1:]
            v = [int(x) for x in f]
            idle = v[3] + (v[4] if len(v) > 4 else 0)
            return (sum(v), idle)
        except Exception:
            return None

    def _read_disk(self):
        rd = wr = 0
        for line in self._rd("/proc/diskstats").splitlines():
            f = line.split()
            if len(f) < 14:
                continue
            try:
                rd += int(f[5]); wr += int(f[9])
            except Exception:
                pass
        return (rd, wr)

    def _read_pio(self, pid):
        try:
            d = {}
            for ln in self._rd(f"/proc/{pid}/io").splitlines():
                k, _, v = ln.partition(":")
                d[k.strip()] = int(v.strip())
            return (d.get("rchar", 0), d.get("wchar", 0),
                    d.get("read_bytes", 0), d.get("write_bytes", 0))
        except Exception:
            return None

    def _live_sample(self):
        now = time.time()
        dev = self._read_dev()
        stat = self._read_stat()
        disk = self._read_disk()
        w = self.machine_world or {}
        pio = {}
        for p in w.get("inhabitants", []):
            pid = p.get("pid")
            if not pid:
                continue
            r = self._read_pio(pid)
            if r is not None:
                pio[pid] = r
        prev = self._live_prev
        live = {"t": now, "dev": {}, "cpu": None, "disk": None, "proc": {}}
        if prev is not None:
            dt = max(0.2, now - prev["t"])
            for name, cur in dev.items():
                p = prev["dev"].get(name)
                if not p:
                    continue
                live["dev"][name] = {
                    "rx_bps": max(0.0, (cur[0] - p[0]) / dt),
                    "tx_bps": max(0.0, (cur[1] - p[1]) / dt),
                    "rx_pps": max(0.0, (cur[2] - p[2]) / dt),
                    "tx_pps": max(0.0, (cur[3] - p[3]) / dt)}
            if stat and prev["stat"]:
                dtot = stat[0] - prev["stat"][0]
                didle = stat[1] - prev["stat"][1]
                if dtot > 0:
                    live["cpu"] = max(0.0, min(1.0, 1.0 - didle / dtot))
            if disk and prev["disk"]:
                live["disk"] = {
                    "r_bps": max(0.0, (disk[0] - prev["disk"][0]) * 512 / dt),
                    "w_bps": max(0.0, (disk[1] - prev["disk"][1]) * 512 / dt)}
            for pid, cur in pio.items():
                p = prev["pio"].get(pid)
                if not p:
                    continue
                live["proc"][pid] = {
                    "rd_bps": max(0.0, (cur[0] - p[0]) / dt),
                    "wr_bps": max(0.0, (cur[1] - p[1]) / dt)}
        self._live_prev = {"t": now, "dev": dev, "stat": stat,
                           "disk": disk, "pio": pio}
        a = 0.5
        if self._live:
            for name, cur in live["dev"].items():
                old = (self._live.get("dev") or {}).get(name)
                if old:
                    for k in ("rx_bps", "tx_bps", "rx_pps", "tx_pps"):
                        cur[k] = old[k] * (1 - a) + cur[k] * a
            if live["cpu"] is not None and self._live.get("cpu") is not None:
                live["cpu"] = self._live["cpu"] * (1 - a) + live["cpu"] * a
        self._live = live
        if self.machine:
            self.update()

    def _live_totals(self):
        rx = tx = pps = 0.0
        for name, r in (self._live.get("dev") or {}).items():
            if name == "lo":
                continue
            rx += r["rx_bps"]; tx += r["tx_bps"]
            pps += r["rx_pps"] + r["tx_pps"]
        return rx, tx, pps

    def _top_writer(self):
        proc = self._live.get("proc") or {}
        if not proc:
            return None
        names = {p.get("pid"): (p.get("name") or str(p.get("pid")))
                 for p in (self.machine_world or {}).get("inhabitants", [])}
        pid, best = None, 0.0
        for p, r in proc.items():
            if r.get("wr_bps", 0.0) > best:
                pid, best = p, r["wr_bps"]
        if pid is None or best < 200_000:
            return None
        return (names.get(pid, f"pid {pid}"), best)

    def _live_render(self, w, t):
        """Draw the motion that a real read just measured — never invented."""
        if self.live_effective == "off":
            return
        y = MACHINE_FLOOR_Y
        cpu = self._live.get("cpu")
        rx, tx, pps = self._live_totals()
        if cpu is not None:
            glColor4f(0.40, 1.0, 0.70, 0.10 + 0.45 * cpu)
            glLineWidth(3.0)
            glBegin(GL_LINE_LOOP)
            for i in range(64):
                aa = 2 * math.pi * i / 64
                r = 3.9 + 0.6 * cpu
                glVertex3f(r * math.cos(aa), y + 0.10, r * math.sin(aa))
            glEnd()
            glLineWidth(1.0)
        n = int(min(48, 3 + pps * 0.05))
        speed = 0.15 + min(1.8, (rx + tx) / 2_000_000.0)
        for i in range(max(0, n)):
            a = (i * (2 * math.pi / max(1, n)) + t * speed) % (2 * math.pi)
            rr = MACHINE_WALL_R - 1.5
            self._octa(rr * math.cos(a), y + 1.6, rr * math.sin(a), 0.16,
                       (0.5, 1.0, 0.75))
        d = self._live.get("disk") or {}
        io = d.get("w_bps", 0.0) + d.get("r_bps", 0.0)
        if io:
            h = min(7.0, 0.4 + io / 3_000_000.0)
            glColor4f(0.92, 0.76, 0.30, 0.6)
            glLineWidth(2.0)
            glBegin(GL_LINES)
            glVertex3f(5.2, y + 0.05, 3.4)
            glVertex3f(5.2, y + 0.05 + h, 3.4)
            glEnd()
            glLineWidth(1.0)
        if self.live_effective == "capture" and self._capture is not None:
            now = time.time()
            for j, p in enumerate(list(self._capture.packets)[-120:]):
                q = max(0.0, min(1.0, (now - p.get("ts", now)) / 2.0))
                a = (j * 2.399) % (2 * math.pi)
                r = MACHINE_WALL_R * (1.0 - q)
                self._octa(r * math.cos(a), y + 1.0 + 2.6 * (1.0 - q),
                           r * math.sin(a), 0.12, (1.0, 0.55, 0.42))

    def _live_line(self):
        eff = self.live_effective
        if eff == "off":
            return "LIVE [knob] off \u2014 a snapshot (press B to rebuild)"
        cpu = self._live.get("cpu")
        rx, tx, pps = self._live_totals()
        cpu_s = "\u2014" if cpu is None else f"{int(cpu * 100)}%"
        s = (f"LIVE [knob] {eff} \u00b7 cpu {cpu_s} \u00b7 net "
             f"\u2193{_hbytes(rx)}/s \u2191{_hbytes(tx)}/s \u00b7 {int(pps)} pkt/s")
        if eff == "capture" and self._capture is not None:
            s += f" \u00b7 captured {len(self._capture.packets)}"
            if self._capture.error:
                s += f" (capture failed: {self._capture.error})"
        top = self._top_writer()
        if top:
            s += f" \u00b7 writing: {top[0]} {_hbytes(top[1])}/s"
        return s

    def _word_sky(self):
        if self.word_mode == "ayah" and self._word_reci:
            sky = self._word_reci["sky"]
            glClearColor(sky[0], sky[1], sky[2], 1.0)
        else:
            glClearColor(0.006, 0.012, 0.020, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        y = WORD_FLOOR_Y
        glLineWidth(1.0)
        glColor4f(0.06, 0.10, 0.14, 1.0)
        glBegin(GL_LINE_LOOP)
        for i in range(64):
            a = 2 * math.pi * i / 64
            glVertex3f((WORD_R - 1.0) * math.cos(a), y + 0.02,
                       (WORD_R - 1.0) * math.sin(a))
        glEnd()
        glLineWidth(1.0)

    def _word_floor(self, ground):
        y = WORD_FLOOR_Y
        glColor4f(ground[0], ground[1], ground[2], 1.0)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, y, 0)
        for i in range(49):
            a = 2 * math.pi * i / 48
            glVertex3f(WORD_R * math.cos(a), y, WORD_R * math.sin(a))
        glEnd()

    def _draw_word(self, t):
        if self.word_mode == "ayah" and self._word_reci:
            self._draw_word_ayah(t)
        else:
            self._draw_word_select(t)

    def _draw_word_select(self, t):
        y = WORD_FLOOR_Y
        self._word_floor((0.008, 0.014, 0.024))
        glLineWidth(1.0)
        for r in (9, 17, 25):
            glColor4f(0.05, 0.10, 0.15, 1.0)
            glBegin(GL_LINE_LOOP)
            for i in range(48):
                a = 2 * math.pi * i / 48
                glVertex3f(r * math.cos(a), y + 0.03, r * math.sin(a))
            glEnd()
        glLineWidth(1.0)
        # the cluster: a field of small stars you fly through
        glPointSize(2.0)
        glBegin(GL_POINTS)
        for (x, yy, z, ph, sz) in self._word_star_points():
            tw = 0.55 + 0.45 * math.sin(t * 1.4 + ph)
            glColor4f(0.15 + 0.55 * tw, 0.12 + 0.62 * tw, 0.10 + 0.80 * tw, 0.9)
            glVertex3f(x, yy, z)
        glEnd()
        glPointSize(1.0)
        # the beacon you launch from: a still column with the lucky-dip star on top
        breathe = 1.0 + 0.08 * math.sin(t * 1.0)
        self._prism(0, 0, 1.4 * breathe, 0.5, y, y + 20.0, 6, (0.07, 0.24, 0.30))
        rx, ry, rz = self._word_random_pos()
        glow = 1.0 + 0.14 * math.sin(t * 1.6)
        self._octa(rx, ry, rz, 3.0 * glow, (0.30, 0.62, 0.52), squash=0.5)
        self._sphere(rx, ry, rz, 1.6 * glow, (0.62, 0.90, 0.72))
        self._portal(rx, rz, ry - 2.8, 2.6, (0.60, 0.88, 0.72), t + 0.4)
        # the chapters, each a bright star in the cluster. The whole Book is here
        # (114 stars); draw the few nearest in full, the rest as small stars, so
        # the sky stays smooth to fly through.
        n = max(1, len(self._word_suras))
        px, py, pz = self.pos
        stars = []
        for i, s in enumerate(self._word_suras):
            x, yy, z = self._word_chapter_pos(i, n)
            d2 = (px - x) ** 2 + (py - yy) ** 2 + (pz - z) ** 2
            stars.append((d2, i, s, x, yy, z))
        stars.sort(key=lambda c: c[0])
        near = stars[:12]
        near_idx = {c[1] for c in near}
        glPointSize(3.0)
        glBegin(GL_POINTS)
        for (d2, i, s, x, yy, z) in stars:
            if i in near_idx:
                continue
            tw = 0.6 + 0.4 * math.sin(t * 1.8 + i)
            glColor4f(0.20 + 0.45 * tw, 0.24 + 0.60 * tw, 0.40 + 0.95 * tw, 0.9)
            glVertex3f(x, yy, z)
        glEnd()
        glPointSize(1.0)
        for (d2, i, s, x, yy, z) in near:
            tw = 1.0 + 0.16 * math.sin(t * 1.8 + i)
            self._octa(x, yy, z, 2.8 * tw, (0.24, 0.48, 0.60), squash=0.45)
            self._sphere(x, yy, z, 1.4 * tw, (0.72, 0.86, 0.98))
            self._portal(x, z, yy - 2.6, 2.4, (0.48, 0.78, 0.86), t + i * 0.9)
        # other readers, announced over the relay — learning together
        for p in self._peers:
            self._draw_peer(p, t)
        # the gate back to the wire
        rx, ry, rz = WORD_RETURN_POS
        self._portal(rx, rz, ry - 0.5, 2.8, (0.52, 0.78, 0.90), t + 0.7)
        self._portal(rx, rz, ry + 2.0, 1.8, (0.32, 0.56, 0.70), t + 1.6)
        glLineWidth(1.0)

    def _draw_word_ayah(self, t):
        y = WORD_FLOOR_Y
        r = self._word_reci
        self._word_floor(r["ground"])
        glLineWidth(1.0)
        for pr in r["props"]:
            self._motif_form(pr["kind"], pr["x"], y, pr["z"], pr["s"], pr["col"],
                             t, pr["ph"], pr.get("central", False))
        for p in self._peers:
            self._draw_peer(p, t)
        # gates: next ayah (+x), previous ayah (+z), back to the chapters (−x)
        nx, nz = self._word_gate_xy(WORD_NEXT_ANGLE)
        bx, bz = self._word_gate_xy(WORD_BACK_ANGLE)
        self._portal(nx, nz, y + 0.5, 2.6, r["ring"], t + 0.3)
        if self._word_has_prev():
            px, pz = self._word_gate_xy(WORD_PREV_ANGLE)
            self._portal(px, pz, y + 0.5, 2.4, (0.50, 0.60, 0.80), t + 1.1)
        self._portal(bx, bz, y + 0.5, 2.8, (0.55, 0.80, 0.70), t + 1.9)
        glLineWidth(1.0)

    def _motif_form(self, kind, x, y, z, s, c, t, ph, central=False):
        """One abstract form from the motif vocabulary. Nothing here is a figure."""
        if kind == "ring":
            glColor4f(c[0], c[1], c[2], 0.85)
            glBegin(GL_LINE_LOOP)
            for i in range(64):
                a = 2 * math.pi * i / 64
                glVertex3f(x + s * math.cos(a), y + 0.04, z + s * math.sin(a))
            glEnd()
        elif kind == "column":
            h = 16.0 * s
            self._prism(x, z, 1.1 * s, 0.7 * s, y, y + h, 6,
                        (c[0] * 0.35, c[1] * 0.35, c[2] * 0.45))
            self._octa(x, y + h * 0.5, z, 1.5 * s, c, squash=1.6)
            self._octa(x, y + h + 0.6 * s, z, 1.0 * s, c, squash=1.2)
        elif kind == "beam":
            h = 20.0 * s
            glColor4f(c[0], c[1], c[2], 0.32)
            glBegin(GL_TRIANGLE_STRIP)
            for dy in (0.0, h):
                wdt = 2.4 * s * (1.0 - dy / h * 0.6)
                glVertex3f(x - wdt, y + dy, z)
                glVertex3f(x + wdt, y + dy, z)
            glEnd()
            self._octa(x, y + 3.0 * s, z, 1.3 * s, c, squash=1.1)
        elif kind == "canopy":
            for k in range(3):
                rr = (5.0 + k * 3.0) * s
                glColor4f(c[0], c[1], c[2], 0.5 - k * 0.12)
                glBegin(GL_LINE_LOOP)
                for i in range(48):
                    a = math.pi * i / 47
                    glVertex3f(x + rr * math.cos(a + ph), y + 8.0 * s + k * 1.2,
                               z + rr * math.sin(a + ph) * 0.6)
                glEnd()
            self._octa(x, y + 2.0 * s, z, 1.2 * s, c, squash=1.0)
        elif kind == "orb":
            self._sphere(x, y + 6.0 * s + 0.6 * math.sin(t + ph), z, 2.2 * s, c)
            if central:
                for k in range(3):
                    a = t * 0.4 + ph + k * 2.09
                    self._sphere(x + 5.0 * s * math.cos(a),
                                 y + 6.0 * s + 1.4 * math.sin(a),
                                 z + 5.0 * s * math.sin(a), 0.7 * s,
                                 (c[0] * 0.8, c[1] * 0.8, c[2] * 0.9))
        elif kind == "orbs":
            for k in range(6):
                a = ph + k * 1.05
                rr = (3.0 + 1.4 * k) * s
                self._sphere(x + rr * math.cos(a),
                             y + 3.0 + 2.0 * k * s + 0.5 * math.sin(t + k),
                             z + rr * math.sin(a), 0.6 * s, c)
        elif kind == "path":
            for k in range(7):
                fr = k / 6.0
                zz = z + (fr - 0.5) * 18.0 * s
                self._octa(x, y + 0.4, zz, (0.9 - 0.4 * fr) * s,
                           (c[0] * (0.5 + fr), c[1] * (0.5 + fr),
                            c[2] * (0.5 + fr)), squash=0.4)
        elif kind == "hourglass":
            self._cone(x, y + 6.0 * s, z, 2.2 * s, 5.0 * s, c)
            glPushMatrix()
            glTranslatef(x, y + 11.0 * s, z)
            glScalef(1.0, -1.0, 1.0)
            self._cone(0, 0, 0, 2.2 * s, 5.0 * s, c)
            glPopMatrix()
            glPointSize(2.0)
            glColor4f(c[0], c[1], c[2], 0.9)
            glBegin(GL_POINTS)
            for k in range(10):
                fy = (t * 3.0 + k * 0.7) % 6.0
                glVertex3f(x + 0.3 * math.sin(k), y + 11.0 * s - fy, z)
            glEnd()
            glPointSize(1.0)
        elif kind == "faded":
            for k in range(4):
                h = (2.0 + k * 1.5) * s
                glColor4f(c[0], c[1], c[2], 0.14 + 0.12 * k)
                self._prism(x + (k - 1.5) * 2.0 * s, z + (k - 1.5) * 1.5 * s,
                            0.6 * s, 0.3 * s, y, y + h, 5,
                            (c[0] * 0.6, c[1] * 0.6, c[2] * 0.6))
        elif kind == "ripple":
            for k in range(3):
                rr = ((t * 2.5 + k * 4.0 + ph) % 12.0) * s
                glColor4f(c[0], c[1], c[2], max(0.0, 0.6 - rr * 0.04))
                glBegin(GL_LINE_LOOP)
                for i in range(48):
                    a = 2 * math.pi * i / 48
                    glVertex3f(x + rr * math.cos(a), y + 0.05, z + rr * math.sin(a))
                glEnd()
            self._octa(x, y + 1.5 * s, z, 1.0 * s, c, squash=1.0)
        elif kind == "arc":
            glColor4f(c[0], c[1], c[2], 0.7)
            glLineWidth(2.0)
            glBegin(GL_LINE_STRIP)
            for i in range(33):
                a = math.pi * i / 32
                glVertex3f(x + 6.0 * s * math.cos(a + ph),
                           y + 5.0 * s * math.sin(a) + 0.5, z)
            glEnd()
            glLineWidth(1.0)
        elif kind == "dim":
            self._sphere(x, y + 4.0 * s + 0.3 * math.sin(t * 0.6 + ph), z, 2.0 * s,
                         (c[0] * 0.6, c[1] * 0.6, c[2] * 0.7))
        elif kind == "motes":
            glPointSize(2.0)
            glColor4f(c[0], c[1], c[2], 0.8)
            glBegin(GL_POINTS)
            for k in range(24):
                a = ph + k * 0.9
                rr = (2.0 + (k % 6) * 1.3) * s
                yy2 = y + 2.0 + ((t * 1.5 + k * 0.6) % 12.0)
                glVertex3f(x + rr * math.cos(a), yy2, z + rr * math.sin(a))
            glEnd()
            glPointSize(1.0)
        elif kind == "ember":
            self._cone(x, y + 2.0 * s, z, 1.4 * s, 4.0 * s, c)
            glPointSize(2.0)
            glColor4f(c[0], c[1] * 0.8, c[2] * 0.7, 0.9)
            glBegin(GL_POINTS)
            for k in range(16):
                fy = (t * 4.0 + k * 0.9) % 8.0
                glVertex3f(x + 0.8 * math.sin(k * 1.7), y + 2.0 + fy,
                           z + 0.8 * math.cos(k))
            glEnd()
            glPointSize(1.0)
        elif kind == "pool":
            glColor4f(c[0], c[1], c[2], 0.35)
            glBegin(GL_TRIANGLE_FAN)
            glVertex3f(x, y + 0.06, z)
            for i in range(33):
                a = 2 * math.pi * i / 32
                glVertex3f(x + 3.0 * s * math.cos(a), y + 0.06,
                           z + 3.0 * s * math.sin(a))
            glEnd()
            glColor4f(c[0], c[1], c[2], 0.8)
            glBegin(GL_LINE_LOOP)
            for i in range(40):
                a = 2 * math.pi * i / 40
                glVertex3f(x + 3.0 * s * math.cos(a), y + 0.08,
                           z + 3.0 * s * math.sin(a))
            glEnd()
            self._octa(x, y + 1.4 * s, z, 0.9 * s, c, squash=1.0)
        elif kind == "heart":
            pulse = 1.0 + 0.18 * math.sin(t * 2.2 + ph)
            self._octa(x, y + 5.0 * s, z, 1.8 * s * pulse, c, squash=1.3)
            self._prism(x, z, 0.7 * s, 0.4 * s, y, y + 3.0 * s, 5,
                        (c[0] * 0.4, c[1] * 0.4, c[2] * 0.5))
        else:
            self._octa(x, y + 2.0 * s, z, 1.0 * s, c, squash=1.0)

    def _word_labels(self):
        out = []
        vp = glGetIntegerv(GL_VIEWPORT)
        items = []
        if self.word_mode == "ayah" and self.word_ref:
            nx, nz = self._word_gate_xy(WORD_NEXT_ANGLE)
            bx, bz = self._word_gate_xy(WORD_BACK_ANGLE)
            nxt = ("the chapter ends \u2014 back to the chapters [E]"
                   if self._word_at_end() else "travel to the next ayah [E]")
            items.append((nx, WORD_FLOOR_Y + 6.2, nz, nxt, (0.85, 0.95, 1.0)))
            if self._word_has_prev():
                px, pz = self._word_gate_xy(WORD_PREV_ANGLE)
                items.append((px, WORD_FLOOR_Y + 6.2, pz,
                              "back to the previous ayah [E]", (0.72, 0.82, 0.95)))
            items.append((bx, WORD_FLOOR_Y + 6.2, bz,
                          "back to the chapters [E]", (0.70, 0.92, 0.80)))
        else:
            n = max(1, len(self._word_suras))
            px, py, pz = self.pos
            chapters = []
            for i, s in enumerate(self._word_suras):
                x, yy, z = self._word_chapter_pos(i, n)
                d = (px - x) ** 2 + (py - yy) ** 2 + (pz - z) ** 2
                chapters.append((d, x, yy, z, s))
            chapters.sort(key=lambda c: c[0])
            # of the whole sky of chapters, name only the few nearest you — so a
            # cluster of 114 stars stays readable as you fly through it
            for (_d, x, yy, z, s) in chapters[:7]:
                items.append((x, yy + 2.6, z,
                              f"{s['number']} \u00b7 {s['name']} \u2014 "
                              f"{s['translation']} ({len(s['ayahs'])} verses) [E]",
                              (0.72, 0.92, 1.0)))
            rx, ry, rz = self._word_random_pos()
            items.append((rx, ry + 3.0, rz,
                          "a random chapter [E]", (0.72, 1.0, 0.82)))
            lx, ly, lz = WORD_RETURN_POS
            items.append((lx, ly + 2.4, lz,
                          "leave the room of the Word [E] \u2014 back to the wire",
                          (0.72, 0.92, 1.0)))
        for p in self._peers:
            items.append((p["x"], p["y"] + 2.0, p["z"], f"\u25c8 {p['name']}",
                          self._peer_col(p["name"])))
        for (x, yy, z, txt, col) in items:
            try:
                sx, sy, sz = gluProject(x, yy, z)
            except Exception:
                continue
            if sz < 0 or sz > 1:
                continue
            out.append((sx, vp[3] - sy, txt, col))
        return out

    def _peer_col(self, name):
        h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
        return (0.4 + 0.6 * ((h >> 16) & 255) / 255,
                0.4 + 0.6 * ((h >> 8) & 255) / 255,
                0.4 + 0.6 * (h & 255) / 255)

    def _draw_peer(self, p, t):
        x, z = p["x"], p["z"]
        yy = p["y"]
        bob = 0.4 * math.sin(t * 2.4 + x)
        col = self._peer_col(p["name"])
        self._octa(x, yy + bob, z, 0.7, col, squash=1.1)
        self._cube(x, yy + bob - 1.3, z, 0.9, 1.1, 0.9,
                   (col[0] * 0.55, col[1] * 0.55, col[2] * 0.55))

    # ---- the market scene ---------------------------------------------------
    def _market_sky(self):
        glClearColor(0.012, 0.016, 0.024, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        y = self._market_floor()
        glLineWidth(1.0)
        glColor4f(0.10, 0.16, 0.22, 1.0)
        glBegin(GL_LINE_LOOP)
        for i in range(48):
            a = 2 * math.pi * i / 48
            glVertex3f((MARKET_R - 1.0) * math.cos(a), y + 0.02,
                       (MARKET_R - 1.0) * math.sin(a))
        glEnd()
        glLineWidth(1.0)

    def _draw_market(self, t):
        w = self.market_world
        if not w:
            return
        y = self._market_floor()
        # the floor: a dark disc with a grid of wiring rings
        glColor4f(0.045, 0.070, 0.095, 1.0)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, y, 0)
        for i in range(33):
            a = 2 * math.pi * i / 32
            glVertex3f(MARKET_R * math.cos(a), y, MARKET_R * math.sin(a))
        glEnd()
        glLineWidth(1.0)
        for r in (10, 20, 30, 40, 50):
            glColor4f(0.09, 0.16, 0.18, 1.0)
            glBegin(GL_LINE_LOOP)
            for i in range(40):
                a = 2 * math.pi * i / 40
                glVertex3f(r * math.cos(a), y + 0.03, r * math.sin(a))
            glEnd()
        # the centre column: your account, breathing with the loop heartbeat
        loop = w.get("loop", {})
        ok = loop.get("heartbeat") == "ok"
        beat = 1.0 + 0.15 * math.sin(t * (1.3 if ok else 0.35))
        col = (0.55, 0.85, 0.75) if ok else (0.85, 0.25, 0.22)
        self._prism(0, 0, 2.6 * beat, 1.7 * beat, y, y + 14.0, 6,
                    (col[0], col[1], col[2]))
        col2 = (col[0] * 0.7, col[1] * 0.7, col[2] * 0.7)
        self._prism(0, 0, 1.7 * beat, 3.1 * beat, y + 14.0, y + 16.5, 4, col2)
        # rank of candle-lights round the column top: the way down into the
        # candle room (DOT/USD's tape). Strictly dressing — a signpost, no datum.
        for j in range(9):
            ca = 2 * math.pi * j / 9 + t * 0.25
            cxx, czz = 2.7 * math.cos(ca), 2.7 * math.sin(ca)
            cc = CANDLE_UP if j % 2 else CANDLE_AMBER
            self._cube(cxx, y + 17.6 + 0.35 * math.sin(t * 2.0 + j), czz,
                       0.26, 0.9 + 0.2 * math.sin(t * 2.0 + j), 0.26, cc)
        # the platforms: one per trading agent, coloured by what it waits for
        for i, a in enumerate(w.get("agents", [])):
            self._platform_aesthetic(a, t)
            # the SignalBot's lean, drawn big above the platform so it reads
            # from across the floor (green points up, red points down)
            sig = a.get("signal") or {}
            lean = sig.get("lean") if sig.get("available") else None
            enabled = a.get("state") != "off"
            self._signal_arrow(a["pos"][0], a["pos"][1] + 6.9, a["pos"][2],
                               lean, t + i * 0.7, enabled=enabled)
        # the loop's own wiring: each platform is reached from the centre column,
        # and a pulse of light rides the link (the account hardware talking)
        glLineWidth(1.0)
        for i, a in enumerate(w.get("agents", [])):
            x, z = a["pos"][0], a["pos"][2]
            st = a["state"]
            base = MARKET_STATE_COL.get(st, MARKET_STATE_COL["off"])
            glColor4f(base[0] * 0.8, base[1] * 0.8, base[2] * 0.8, 0.12)
            glBegin(GL_LINES)
            glVertex3f(0, y + 0.06, 0)
            glVertex3f(x, y + 0.06, z)
            glEnd()
            q = (t * 0.45 + i * 0.37) % 1.0
            gx, gz = x * q, z * q
            glColor4f(base[0], base[1], base[2], 0.9)
            glBegin(GL_LINES)
            glVertex3f(gx, y + 0.07, gz)
            glVertex3f(gx, y + 0.55, gz)
            glEnd()
        # other users, announced over the relay
        for p in self._peers:
            self._draw_peer(p, t)
        # the return gate back to the wire
        rx, ry, rz = RETURN_GATE_POS
        self._portal(rx, rz, ry - 0.5, 3.4, (0.85, 0.45, 0.95), t + 1.0)
        self._portal(rx, rz, ry + 2.5, 2.2, (0.60, 0.30, 0.75), t + 2.0)
        glLineWidth(1.0)

    def _signal_arrow(self, x, y0, z, lean, t, enabled=True, scale=1.9):
        """The SignalBot's lean as one bold arrow in the sky over the platform:
        green pointing up, red pointing down, amber flat, grey when the bot has
        no read. Dressing only — the direction is a vote over the bot's own
        fields (wiregate computes it); this just points it."""
        d = (lean or {}).get("dir", "none")
        base = MARKET_LEAN_COL.get(d, MARKET_LEAN_COL["none"])
        col = base if enabled else tuple(c * 0.55 for c in base)
        live = enabled and d in ("up", "down")
        pulse = 1.0 + (0.16 * math.sin(t * 3.1) if live else 0.05 * math.sin(t * 1.4))
        r = scale * 0.70 * pulse
        shaft = scale * 1.0
        head = scale * 1.35
        # a soft column of light, so the arrow carries at a distance
        glColor4f(col[0], col[1], col[2], 0.12 if live else 0.05)
        glBegin(GL_TRIANGLE_STRIP)
        for i in range(13):
            aa = 2 * math.pi * i / 12
            glVertex3f(x + scale * 0.55 * math.cos(aa), y0 - shaft * 0.6,
                       z + scale * 0.55 * math.sin(aa))
            glVertex3f(x + scale * 0.16 * math.cos(aa), y0 + shaft + head,
                       z + scale * 0.16 * math.sin(aa))
        glEnd()
        if d == "up":
            self._prism(x, z, 0.22 * scale, 0.22 * scale, y0 - shaft, y0, 6,
                        tuple(c * 0.82 for c in col))
            self._arrow_head(x, y0, z, r, head, col, up=True)
        elif d == "down":
            self._prism(x, z, 0.22 * scale, 0.22 * scale, y0, y0 + shaft, 6,
                        tuple(c * 0.82 for c in col))
            self._arrow_head(x, y0, z, r, head, col, up=False)
        else:
            # flat / no signal: a still amber bar, clearly not a direction
            self._cube(x, y0, z, scale * 0.28, scale * 0.28, scale * 2.4, col)
            self._octa(x, y0, z, scale * 0.5, col, squash=0.4)
        # a bright ring at the shaft's foot to anchor it to the pad
        glColor4f(col[0], col[1], col[2], 0.7 if live else 0.4)
        glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        for i in range(20):
            aa = 2 * math.pi * i / 20
            glVertex3f(x + scale * 0.7 * math.cos(aa), y0 - shaft * 0.6,
                       z + scale * 0.7 * math.sin(aa))
        glEnd()
        glLineWidth(1.0)

    def _platform_aesthetic(self, a, t):
        """A trading platform, brought up to the wire home's standard of beauty:
        a halo on the floor, a lit plinth, a scalloped hex sigil that breathes, a
        beacon of light and twin orbiting gems. Strictly dressing — the labels
        and colours still carry the real snapshot, none of this is a datum."""
        x, z = a["pos"][0], a["pos"][2]
        yy = a["pos"][1]
        y = self._market_floor()
        st = a["state"]
        base = MARKET_STATE_COL.get(st, MARKET_STATE_COL["off"])
        r0 = float(a.get("radius", 4.2))
        enabled = bool(a.get("enabled")) and st != "off"
        pulse = 1.0 + 0.16 * math.sin(t * 2.2 + x * 0.5) if enabled else 1.0
        heat = tuple(min(1.0, c * pulse) for c in base)
        lit = tuple(min(1.0, c * 0.92) for c in base)
        deep = tuple(c * 0.40 for c in base)

        if self.selected_agent == a["id"]:
            self._portal(x, z, yy, r0 + 0.7, (1.0, 1.0, 1.0), t)
        # halo it casts on the floor
        glColor4f(base[0] * 0.9, base[1] * 0.9, base[2] * 0.9, 0.10)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(x, y + 0.03, z)
        for i in range(33):
            aa = 2 * math.pi * i / 32
            glVertex3f(x + (r0 + 1.3) * math.cos(aa), y + 0.03,
                       z + (r0 + 1.3) * math.sin(aa))
        glEnd()
        glColor4f(lit[0], lit[1], lit[2], 0.22)
        glLineWidth(1.0)
        glBegin(GL_LINE_LOOP)
        for i in range(32):
            aa = 2 * math.pi * i / 32
            glVertex3f(x + (r0 + 1.1) * math.cos(aa), y + 0.03,
                       z + (r0 + 1.1) * math.sin(aa))
        glEnd()
        # the plinth: a tiered hex lattice with lit struts
        self._prism(x, z, 0.95, 0.62, y - 0.2, yy, 6, deep)
        self._prism(x, z, 0.34, 0.26, y - 0.2, yy, 6,
                    tuple(min(1.0, c * 1.7) for c in lit))
        glLineWidth(2.0)
        glColor4f(lit[0], lit[1], lit[2], 0.85)
        glBegin(GL_LINES)
        for i in range(6):
            aa = 2 * math.pi * i / 6
            glVertex3f(x + 0.92 * math.cos(aa), y - 0.15, z + 0.92 * math.sin(aa))
            glVertex3f(x + 0.60 * math.cos(aa), yy, z + 0.60 * math.sin(aa))
        glEnd()
        glLineWidth(1.0)
        # the pad: a scalloped hex sigil, bright centre breathing with the market
        glShadeModel(GL_SMOOTH)
        glBegin(GL_POLYGON)
        glColor4f(heat[0], heat[1], heat[2], 1.0)
        glVertex3f(x, yy + 0.16, z)
        for i in range(13):
            edge = i % 2 == 0
            glColor3f(*(lit if edge else heat))
            aa = 2 * math.pi * i / 12
            rr = r0 if edge else r0 * 0.90
            glVertex3f(x + rr * math.cos(aa), yy + 0.16, z + rr * math.sin(aa))
        glEnd()
        glShadeModel(GL_FLAT)
        glColor4f(lit[0], lit[1], lit[2], 0.95)
        glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        for i in range(48):
            aa = 2 * math.pi * i / 48
            glVertex3f(x + r0 * math.cos(aa), yy + 0.17, z + r0 * math.sin(aa))
        glEnd()
        glLineWidth(1.0)
        # a rune ring and a radar sweep cross the pad
        rot = t * 0.6
        glColor4f(heat[0], heat[1], heat[2], 0.9)
        glBegin(GL_LINE_LOOP)
        for i in range(24):
            aa = 2 * math.pi * i / 24 + rot
            glVertex3f(x + r0 * 0.55 * math.cos(aa), yy + 0.18, z + r0 * 0.55 * math.sin(aa))
        glEnd()
        glBegin(GL_LINES)
        aa = rot * 1.8
        glVertex3f(x, yy + 0.19, z)
        glVertex3f(x + r0 * 0.98 * math.cos(aa), yy + 0.19, z + r0 * 0.98 * math.sin(aa))
        glEnd()
        # pulse rings ripple out while the order waits (enabled + live)
        if enabled:
            for k in range(2):
                q = (t * 0.35 + k * 0.5) % 1.0
                rr = 0.3 + q * (r0 + 0.4)
                glColor4f(heat[0], heat[1], heat[2], 0.50 * (1.0 - q))
                glBegin(GL_LINE_LOOP)
                for i in range(18):
                    aa = 2 * math.pi * i / 18
                    glVertex3f(x + rr * math.cos(aa), yy + 0.20, z + rr * math.sin(aa))
                glEnd()
        # the beacon of light standing on the pad — brighter when live
        bh = 2.6 if not enabled else 6.5
        glColor4f(heat[0], heat[1], heat[2], 0.10)
        glBegin(GL_TRIANGLE_STRIP)
        for i in range(13):
            aa = 2 * math.pi * i / 12
            glVertex3f(x + r0 * 0.30 * math.cos(aa), yy + 0.2, z + r0 * 0.30 * math.sin(aa))
            glVertex3f(x + r0 * 0.06 * math.cos(aa), yy + bh, z + r0 * 0.06 * math.sin(aa))
        glEnd()
        glColor4f(lit[0], lit[1], lit[2], 0.55)
        glBegin(GL_LINES)
        glVertex3f(x, yy + 0.2, z)
        glVertex3f(x, yy + bh + (1.2 if enabled else 0.0), z)
        glEnd()
        # twin gems above the pad — the trading mind and its ghost
        bob = yy + 2.4 + (0.30 if enabled else 0.15) * math.sin(t * 1.8 + x)
        self._octa(x, bob, z, 0.55, heat, squash=1.3)
        self._octa(x, bob + 1.1, z, 0.28,
                   tuple(min(1.0, c * 1.7) for c in lit), squash=0.7)
        glLineWidth(1.0)

    def _market_labels(self):
        out = []
        vp = glGetIntegerv(GL_VIEWPORT)
        items = []
        w = self.market_world or {}
        for a in w.get("agents", []):
            x, z = a["pos"][0], a["pos"][2]
            yy = a["pos"][1]
            txt = f"{a['name']} \u00b7 {MARKET_STATE_TXT.get(a['state'], a['state'])}" \
                  f" \u00b7 {(a.get('capital') or 0):g} {a.get('mode', '?')}"
            if a.get("net_pct") is not None:
                txt += f" \u00b7 net {a['net_pct']}%"
            col = MARKET_STATE_COL.get(a["state"], (0.6, 0.6, 0.65))
            items.append((x, yy + 3.5, z, txt, col))
            sig = a.get("signal") or {}
            if sig.get("available"):
                ld = (sig.get("lean") or {}).get("dir", "none")
                glyph = MARKET_LEAN_GLYPH.get(ld, "\u00b7")
                txt2 = f"{glyph} {sig.get('summary') or ''}"
                items.append((x, yy + 5.4, z, txt2,
                              MARKET_LEAN_COL.get(ld, (0.6, 0.6, 0.65))))
        for p in self._peers:
            items.append((p["x"], p["y"] + 2.0, p["z"], f"\u25c8 {p['name']}",
                          self._peer_col(p["name"])))
        items.append((0.0, self._market_floor() + 18.5, 0.0,
                      "the candle room [E] \u2014 down into DOT/USD's tape",
                      (0.95, 0.72, 0.98)))
        rx, ry, rz = RETURN_GATE_POS
        items.append((rx, ry + 2.6, rz, "leave the market [E] \u2014 back to the wire",
                      (0.90, 0.72, 0.98)))
        for (x, yy, z, txt, col) in items:
            try:
                sx, sy, sz = gluProject(x, yy, z)
            except Exception:
                continue
            if sz < 0 or sz > 1:
                continue
            out.append((sx, vp[3] - sy, txt, col))
        return out

    def _nearest(self):
        if self.candles:
            return self._nearest_candles()
        if self.market:
            return self._nearest_market()
        if self.word:
            return self._nearest_word()
        if self.exchange:
            return self._nearest_exchange()
        if self.machine:
            return self._nearest_machine()
        if not self.world or self.deep is not None:
            return None
        px, pz = self.pos[0], self.pos[2]
        best = None
        def consider(kind, x, z, radius, **kw):
            nonlocal best
            d = math.hypot(px - x, pz - z)
            if d <= radius and (best is None or d < best["d"]):
                best = {"kind": kind, "d": d, **kw}
        if self.active == 0:
            for g in self.world["gates"]:
                consider("gate", g["pos"][0], g["pos"][1], 3.0, domain=g["domain"], count=g["count"])
            consider("heart", 0, -8, 4.5)
            consider("market", MARKET_GATE_POS[0], MARKET_GATE_POS[2], 4.6)
            consider("word", WORD_GATE_POS[0], WORD_GATE_POS[2], 4.6)
            consider("net", NET_GATE_X, NET_GATE_Z, 6.0)
            consider("machine", MACHINE_HATCH_POS[0], MACHINE_HATCH_POS[2], 4.6)
            for s in self._ruin_segments():
                dx = WALL_R * math.cos(s["angle"])
                dz = WALL_R * math.sin(s["angle"])
                consider("ruin", dx, dz, 4.5, subnet=s["subnet"],
                         newest=s.get("newest"), angle=s["angle"])
            consider("well", 0, 0, WELL_R + 1.6, to=self.active + 1)
        elif self.active < len(STRATA_Y) - 1:
            consider("well", 0, 0, WELL_R + 1.6, to=self.active + 1)
            consider("up", 0, -42, 4.0, to=self.active - 1)
        else:
            consider("electron", 0, 0, WELL_R + 3.0)
        return best

    def _nearest_market(self):
        px, py, pz = self.pos
        best = None
        def consider(kind, x, z, yy, radius, **kw):
            nonlocal best
            d = math.hypot(px - x, pz - z)
            dy = abs(py - yy)
            if d <= radius and dy <= 10.0 and (best is None or d < best["d"]):
                best = {"kind": kind, "d": d, **kw}
        for a in (self.market_world or {}).get("agents", []):
            x, yy, z = a["pos"]
            consider("platform", x, z, yy, a.get("radius", 4.2) + 1.5, agent=a)
        # the centre column: the way down into the candle room (DOT/USD's tape)
        consider("candles", 0.0, 0.0, self._market_floor() + 8.0, 5.5)
        rx, ry, rz = RETURN_GATE_POS
        consider("leave_market", rx, rz, ry, 5.0)
        return best

    def _nearest_word(self):
        px, py, pz = self.pos
        best = None

        def consider(kind, x, y, z, radius, **kw):
            nonlocal best
            d = math.sqrt((px - x) ** 2 + (py - y) ** 2 + (pz - z) ** 2)
            if d <= radius and (best is None or d < best["d"]):
                best = {"kind": kind, "d": d, **kw}

        if self.word_mode == "ayah" and self.word_ref:
            fy = WORD_FLOOR_Y
            nx, nz = self._word_gate_xy(WORD_NEXT_ANGLE)
            bx, bz = self._word_gate_xy(WORD_BACK_ANGLE)
            consider("word_next", nx, fy, nz, 5.5)
            if self._word_has_prev():
                px2, pz2 = self._word_gate_xy(WORD_PREV_ANGLE)
                consider("word_prev", px2, fy, pz2, 5.5)
            consider("word_chapters", bx, fy, bz, 5.5)
            return best
        # the cluster of chapters
        n = max(1, len(self._word_suras))
        for i, s in enumerate(self._word_suras):
            x, y, z = self._word_chapter_pos(i, n)
            consider("word_surah", x, y, z, 6.0, surah=s)
        x, y, z = self._word_random_pos()
        consider("word_random", x, y, z, 6.0)
        consider("word_leave", WORD_RETURN_POS[0], WORD_RETURN_POS[1],
                 WORD_RETURN_POS[2], 5.5)
        return best

    def _interact(self):
        n = self._nearest()
        if not n:
            return
        if self.candles:
            if n["kind"] == "candle":
                b = n["bar"]
                self.candles_sel = b["i"]
                m = b.get("mood") or {}
                self._flash(f"bar {b['i']} \u00b7 {b['tstr']} \u00b7 C {b['c']:g}"
                            + (f" \u00b7 {m.get('word')}" if m.get("word") else ""))
            elif n["kind"] == "candles_leave":
                self._leave_candles()
            return
        if self.machine:
            if n["kind"] == "machine_door":
                d = n["door"]
                name = machinevision.SERVICE_NAMES.get(d["lport"], "?")
                who = d.get("proc") or "?"
                usr = f" ({d['user']})" if d.get("user") else ""
                self._flash(f"door \u00b7 {d['proto']} :{d['lport']} {name} \u2014 "
                            f"{who}{usr} listening on {d['laddr']} \u00b7 [{d['state']}]", 5.0)
            elif n["kind"] == "machine_figure":
                self._machine_figure_talk(n["fig"])
            elif n["kind"] == "machine_bird":
                self._machine_bird_talk(n["bird"])
            elif n["kind"] == "machine_leave":
                self._leave_machine()
            return
        if self.market:
            if n["kind"] == "platform":
                a = n["agent"]
                if self.selected_agent != a["id"]:
                    self.selected_agent = a["id"]
                    self.selected = a
                    self._flash(f"{a['name']} \u2014 {MARKET_STATE_TXT.get(a['state'], a['state'])} "
                                f"\u00b7 {a.get('mode', '?')} \u00b7 capital {a.get('capital')}")
                self.agent_selected.emit(a)
            elif n["kind"] == "candles":
                self._candles_enter_select()
            elif n["kind"] == "leave_market":
                self._leave_market()
            return
        if self.word:
            if n["kind"] == "word_surah":
                self._word_enter_ayah(n["surah"], 0)
            elif n["kind"] == "word_random":
                self._word_random()
            elif n["kind"] == "word_next":
                self._word_move(1)
            elif n["kind"] == "word_prev":
                self._word_move(-1)
            elif n["kind"] == "word_chapters":
                self._word_to_select()
            elif n["kind"] == "word_leave":
                self._leave_word()
            return
        if self.exchange:
            if n["kind"] == "web_tablet":
                self._web_open_tablet(n["index"])
            elif n["kind"] == "service":
                self._open_service(n["gate"]["id"])
            elif n["kind"] == "leave_exchange":
                self._leave_exchange()
            return
        if self.flying and n["kind"] in ("gate", "well", "up", "electron", "ruin"):
            self._flash("land first (G) to use the well and the gates")
            return
        if n["kind"] == "gate":
            self._start_transition(1, focus=n["domain"])
            self._flash(f"following {n['domain']} ×{n['count']}")
        elif n["kind"] == "market":
            self._enter_market()
        elif n["kind"] == "word":
            self._enter_word()
        elif n["kind"] == "machine":
            self._enter_machine()
        elif n["kind"] == "net":
            self._net_go()
        elif n["kind"] == "heart":
            h = self.world["heart"]
            rtt = "?" if h.get("rtt") is None else f"{round(float(h['rtt']), 1)}ms"
            self._flash(f"the heart: up={h.get('up')} {h.get('iface')} gw={h.get('gw')} rtt={rtt} guard={h.get('mode')}")
        elif n["kind"] == "ruin":
            a = n["angle"]
            self.pos[0] = 36.5 * math.cos(a)
            self.pos[2] = 36.5 * math.sin(a)
            self._flash(f"the ruin of {n['subnet']} — a memory, last seen {n.get('newest')}. "
                        f"Nothing here is live: these devices were recorded on a network you left.")
        elif n["kind"] == "well":
            self._start_transition(n["to"])
        elif n["kind"] == "up":
            self._start_transition(n["to"])
        elif n["kind"] == "electron":
            self._enter_deep()

    def _enter_deep(self):
        """Step off the edge into the sea of information. It is vast and infinite
        and it has no bottom — but below the edge there are no named entities,
        only the descent itself. Ground truth stops; the sea carries no data."""
        self.deep = {"d": 0.0, "vy": 0.0}
        self.focus = ""
        self._flash("past the last electron — the sea has no bottom")

    def _exit_deep(self, surface=False):
        self.deep = None
        if surface:
            self._start_transition(0)
        else:
            self.active = 5
            self.pos = [0.0, self._floor_y(5) + EYE, 10.0]
            self.pitch = -0.05
            self.yaw = 0.0

    def _flash(self, msg, secs=3.0):
        self._hud_msg = msg
        self._hud_until = time.time() + secs

    # ---- the outward gate: real DNS + real HTTP(S), off the main thread ----
    def _net_tick(self):
        """The gate's heartbeat: once you are near it, ask the real net on the
        background worker and keep the last real answer to show. Never blocks."""
        if self._net_job is not None and self.net is not None:
            got = self.net.poll(self._net_job)
            if got is not None:
                self._net_result = got
                self._net_status = self._net_describe(got)
                self._net_job = None
        if self.word or self.market or self.exchange or self.machine or \
                self.deep is not None or not self.world:
            return
        if self.active != 0:
            return
        near = math.hypot(self.pos[0] - NET_GATE_X, self.pos[2] - NET_GATE_Z) <= NET_PROBE_R
        if near and self._net_job is None and time.time() - self._net_probe_t > 6.0:
            self._net_probe_t = time.time()
            if self.net is None:
                self.net = wirenet.Net()
            self._net_job = self.net.ask("fetch", self._net_host, max_bytes=2048)

    def _net_describe(self, r):
        """Say what the net really answered — or the real reason it did not."""
        if not r or r.get("state") == "out":
            return "reaching out\u2026"
        if r.get("kind") == "whoami" and r.get("ok"):
            return (f"you are {r.get('ip')} on the net \u00b7 colo {r.get('colo')} "
                    f"\u00b7 {r.get('ms'):.0f}ms")
        if r.get("ok"):
            return (f"real answer \u00b7 {r.get('status')} in {r.get('ms'):.0f}ms "
                    f"\u00b7 {r.get('ip')} \u00b7 {r.get('bytes')}b")
        return f"no answer: {r.get('error')}"

    def _net_go(self):
        """Step through the outward gate: it opens into the Exchange, the hall of
        gates, where each gate leads to a real service out on the net."""
        if self.net is None:
            self.net = wirenet.Net()
        relay = os.environ.get("MRFLUFFY_GATE_URL")
        if relay and self.presence is None:
            self._join_relay(relay)
        self._net_probe_t = time.time()
        self._enter_exchange()

    def _join_relay(self, url):
        """Point our presence at a real relay out on the net, so the market crowd
        becomes real other users rather than just this machine's loopback."""
        try:
            if self.presence is not None:
                self.presence.stop()
            self.presence = wiregate.Presence(base_url=url)
            self.presence.start()
            self._ghost_line = self.presence.describe()
            self._flash(f"joined the net relay at {url}")
        except Exception as e:
            self._flash(f"could not join {url}: {e}")

    # ---- the Exchange: the hall of gates out on the net --------------------
    def _exchange_gate_xz(self, angle, radius=None):
        r = EXCHANGE_GATE_R if radius is None else radius
        return r * math.cos(angle), r * math.sin(angle)

    def _enter_exchange(self):
        """Step through the outward gate into the hall of gates."""
        self.exchange = True
        self.market = False
        self.word = False
        self.market_world = None
        self.deep = None
        self.transition = None
        self.selected_agent = None
        self.selected = None
        self.service = None
        self.web_tabs = []
        self.web_mono = None
        self.pkt = []
        self.pkt_rows = []
        self._pkt_q = []
        self._pkt_i = 0
        self.web_net = None
        self.flying = True
        self.active = 0
        self.pos = [0.0, EXCHANGE_FLOOR_Y + EYE, 14.0]
        self.yaw = 0.0
        self.pitch = -0.02
        if self.net is None:
            self.net = wirenet.Net()
        self._flash("the Exchange \u2014 gates stand on the ring; step into one to go out")
        self.web_changed.emit()

    def _leave_exchange(self):
        self.exchange = False
        self.service = None
        self.web_page = None
        self.web_results = []
        self.web_query = ""
        self.web_scroll = 0
        self.web_job = None
        self.web_hist = []
        self.web_data = None
        self.web_next = None
        self.web_net = None
        self.pkt = []
        self.pkt_rows = []
        self._pkt_q = []
        self._pkt_i = 0
        self.web_tabs = []
        self.web_mono = None
        self.flying = False
        self.pos = [NET_GATE_X, EYE, NET_GATE_Z - 2.0]
        self.yaw = NET_ANGLE
        self.pitch = -0.05
        self.active = 0
        self._flash("back on the pier \u2014 the Exchange is still out there")
        self.web_changed.emit()

    def _exchange_step(self, dt):
        k = self.keys
        fast = self._boost()
        spd = 13.0 * self.move_mult * fast * dt
        cp = math.cos(self.pitch)
        fx, fy, fz = cp * math.sin(self.yaw), math.sin(self.pitch), -cp * math.cos(self.yaw)
        rx, rz = math.cos(self.yaw), math.sin(self.yaw)
        dx = dy = dz = 0.0
        if Qt.Key.Key_W in k:
            dx += fx; dy += fy; dz += fz
        if Qt.Key.Key_S in k:
            dx -= fx; dy -= fy; dz -= fz
        if Qt.Key.Key_A in k:
            dx -= rx; dz -= rz
        if Qt.Key.Key_D in k:
            dx += rx; dz += rz
        if Qt.Key.Key_Space in k:
            dy += 1.0
        if Qt.Key.Key_C in k:
            dy -= 1.0
        m = math.sqrt(dx * dx + dy * dy + dz * dz)
        if m > 0:
            self._speed_now = 13.0 * self.move_mult * fast
            self.pos[0] += dx / m * spd
            self.pos[1] += dy / m * spd
            self.pos[2] += dz / m * spd
        rr = math.hypot(self.pos[0], self.pos[2])
        if rr > EXCHANGE_R - 1.5:
            self.pos[0] = self.pos[0] / rr * (EXCHANGE_R - 1.5)
            self.pos[2] = self.pos[2] / rr * (EXCHANGE_R - 1.5)
        self.pos[1] = max(EXCHANGE_FLOOR_Y + EYE * 0.4,
                          min(EXCHANGE_FLOOR_Y + 46.0, self.pos[1]))

    def _exchange_sky(self):
        glClearColor(0.010, 0.015, 0.030, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        y = EXCHANGE_FLOOR_Y
        glLineWidth(1.0)
        glColor4f(0.07, 0.12, 0.18, 1.0)
        glBegin(GL_LINE_LOOP)
        for i in range(64):
            a = 2 * math.pi * i / 64
            glVertex3f((EXCHANGE_R - 1.0) * math.cos(a), y + 0.02,
                       (EXCHANGE_R - 1.0) * math.sin(a))
        glEnd()

    def _draw_exchange(self, t):
        y = EXCHANGE_FLOOR_Y
        glColor4f(0.008, 0.014, 0.026, 1.0)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, y, 0)
        for i in range(49):
            a = 2 * math.pi * i / 48
            glVertex3f(EXCHANGE_R * math.cos(a), y, EXCHANGE_R * math.sin(a))
        glEnd()
        for r in (9, 17, 25):
            glColor4f(0.05, 0.10, 0.16, 1.0)
            glBegin(GL_LINE_LOOP)
            for i in range(48):
                a = 2 * math.pi * i / 48
                glVertex3f(r * math.cos(a), y + 0.03, r * math.sin(a))
            glEnd()
        # a slow field of pale data-motes drifting in the hall (dressing)
        glPointSize(2.0)
        glBegin(GL_POINTS)
        for i in range(150):
            a = (i * 2.39996) % (2 * math.pi)
            rr = EXCHANGE_R * (0.18 + 0.78 * ((i * 0.618) % 1.0))
            hh = 2.0 + 34.0 * ((i * 0.271) % 1.0)
            tw = 0.5 + 0.5 * math.sin(t * 1.1 + i)
            glColor4f(0.10 + 0.35 * tw, 0.42 + 0.40 * tw, 0.70 + 0.30 * tw, 0.7)
            glVertex3f(rr * math.cos(a), y + hh, rr * math.sin(a))
        glEnd()
        glPointSize(1.0)
        # the beacon you arrive by
        self._prism(0, 0, 1.2, 0.4, y, y + 18.0, 6, (0.05, 0.18, 0.30))
        # the service gates on the ring
        for g in EXCHANGE_GATES:
            self._draw_exchange_gate(g, t)
        # the return gate back to the pier, due +z
        rx, _, rz = EXCHANGE_RETURN_POS
        rr = 2.1 + 0.12 * math.sin(t * 0.9)
        self._cube(rx, y + 3.0, rz, 0.9, 6.2, 0.9, (0.30, 0.22, 0.10))
        glColor4f(0.95, 0.72, 0.25, 0.85)
        glBegin(GL_QUADS)
        glVertex3f(rx - rr, y + 0.5, rz)
        glVertex3f(rx + rr, y + 0.5, rz)
        glVertex3f(rx + rr * 0.7, y + 7.6, rz)
        glVertex3f(rx - rr * 0.7, y + 7.6, rz)
        glEnd()
        self._portal(rx, rz, y + 1.4, 2.6, (0.95, 0.72, 0.25), t)
        # the live link to the far service, and its packets, when a gate is open
        if self.service is not None:
            self._draw_packets(t)

    def _draw_exchange_gate(self, g, t):
        x, z = self._exchange_gate_xz(g["angle"])
        y = EXCHANGE_FLOOR_Y
        near = math.hypot(self.pos[0] - x, self.pos[2] - z) <= 9.0
        col = (0.30, 0.80, 0.98) if near else (0.20, 0.52, 0.70)
        self._cube(x, y + 1.2, z, 1.3, 2.4, 1.3, (col[0] * 0.3, col[1] * 0.3, col[2] * 0.3))
        r = 2.2 + 0.14 * math.sin(t * 1.4)
        # a tall lens of light: a doorway, not a figure
        glColor4f(col[0], col[1], col[2], 0.42)
        glBegin(GL_QUADS)
        glVertex3f(x - r, y - 2.6, z)
        glVertex3f(x + r, y - 2.6, z)
        glVertex3f(x + r * 0.72, y + 4.6, z)
        glVertex3f(x - r * 0.72, y + 4.6, z)
        glEnd()
        glLineWidth(2.0)
        glColor4f(min(1.0, col[0] * 1.5), min(1.0, col[1] * 1.4), col[2], 0.95)
        glBegin(GL_LINE_LOOP)
        for i in range(40):
            a = 2 * math.pi * i / 40
            glVertex3f(x + r * math.cos(a), y + 1.0 + r * 0.9 * math.sin(a), z)
        glEnd()
        glLineWidth(1.0)
        for k in range(6):
            a = k * 2 * math.pi / 6 + 0.3 * t
            self._octa(x + 3.0 * math.cos(a), y - 1.6 + 0.3 * math.sin(t + k),
                       z + 3.0 * math.sin(a), 0.14, col, squash=1.4)
        self._portal(x, z, y - 3.0, 2.4, col, t)

    def _nearest_exchange(self):
        px, pz = self.pos[0], self.pos[2]
        best = None

        def consider(kind, x, z, radius, **kw):
            nonlocal best
            d = math.hypot(px - x, pz - z)
            if d <= radius and (best is None or d < best["d"]):
                best = {"kind": kind, "d": d, **kw}

        for g in EXCHANGE_GATES:
            x, z = self._exchange_gate_xz(g["angle"])
            consider("service", x, z, 6.0, gate=g)
        if self.service is not None:
            for i, tab in enumerate(self.web_tabs):
                consider("web_tablet", tab["x"], tab["z"], 5.5, index=i)
        consider("leave_exchange", EXCHANGE_RETURN_POS[0], EXCHANGE_RETURN_POS[2], 5.5)
        return best

    # ---- the gates themselves: real services (for now, DuckDuckGo) ----------
    def _open_service(self, gid):
        g = next((x for x in EXCHANGE_GATES if x["id"] == gid), None)
        if g is None:
            return
        self.service = gid
        self.service_angle = g["angle"]
        self.web_query = ""
        self.web_results = []
        self.web_answer = None
        self.web_page = None
        self.web_scroll = 0
        self.web_job = None
        self.web_hist = []
        self.web_data = None
        self.web_next = None
        self.web_net = None
        self.pkt = []
        self.pkt_rows = []
        self._pkt_q = []
        self._pkt_i = 0
        self.web_tabs = []
        self.web_mono = None
        self.web_status = f"{g['name']} \u2014 type a search and press Enter"
        # stand before the console, looking out along the wire to the far service
        a = g["angle"]
        r0 = EXCHANGE_GATE_R - 4.5
        self.pos = [r0 * math.cos(a), EXCHANGE_FLOOR_Y + EYE, r0 * math.sin(a)]
        self.yaw = a + math.pi / 2
        self.pitch = -0.05
        self.flying = True
        if self.net is None:
            self.net = wirenet.Net()
        self._flash(f"you step into {g['name']} \u2014 watch the packets leave the console")
        self.web_changed.emit()

    def _close_service(self):
        self.service = None
        self.web_page = None
        self.web_results = []
        self.web_query = ""
        self.web_scroll = 0
        self.web_hist = []
        self.web_data = None
        self.web_next = None
        self.web_net = None
        self.pkt = []
        self.pkt_rows = []
        self._pkt_q = []
        self._pkt_i = 0
        self.web_tabs = []
        self.web_mono = None
        a = self.service_angle
        self.pos = [(EXCHANGE_GATE_R + 4.0) * math.cos(a), EXCHANGE_FLOOR_Y + EYE,
                    (EXCHANGE_GATE_R + 4.0) * math.sin(a)]
        self.web_changed.emit()

    def _web_key(self, e):
        """Keys at a gate's console. Typing happens only while you stand at it."""
        k = e.key()
        if k == Qt.Key.Key_Escape:
            if self.web_mono is not None:
                self.web_mono = None
                self.web_changed.emit()
            else:
                self._close_service()
            return True
        if k == Qt.Key.Key_Home:
            self._leave_exchange()
            return True
        if self.web_mono is not None:                       # reading a real page
            if k in (Qt.Key.Key_BracketLeft, Qt.Key.Key_PageUp, Qt.Key.Key_Up):
                self.web_mono["scroll"] = max(0, self.web_mono["scroll"] - 70)
            elif k in (Qt.Key.Key_BracketRight, Qt.Key.Key_PageDown, Qt.Key.Key_Down):
                self.web_mono["scroll"] += 70
            elif k == Qt.Key.Key_End:
                self.web_mono["scroll"] += 100000
            return True
        if k in (Qt.Key.Key_BracketLeft, Qt.Key.Key_PageUp):   # turn result pages
            self._web_more(-1)
            return True
        if k in (Qt.Key.Key_BracketRight, Qt.Key.Key_PageDown):
            self._web_more(1)
            return True
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):      # the search terminal
            self._web_search()
        elif k == Qt.Key.Key_Backspace:
            self.web_query = self.web_query[:-1]
        elif Qt.Key.Key_1 <= k <= Qt.Key.Key_9:
            self._web_open_result(k - Qt.Key.Key_1)
        elif k == Qt.Key.Key_0:
            self._web_open_result(9)
        else:
            ch = e.text()
            if ch and ch.isprintable() and len(self.web_query) < 140:
                self.web_query += ch
        return True

    def _web_search(self):
        q = self.web_query.strip()
        if not q:
            self.web_status = "nothing typed yet \u2014 write a search first"
            return
        if self.net is None:
            self.net = wirenet.Net()
        self.web_results = []
        self.web_mono = None
        self.web_tabs = []
        self.pkt = []
        self.pkt_rows = []
        self._pkt_q = []
        self._pkt_i = 0
        self.web_hist = []
        self.web_next = None
        self.web_data = {"q": q, "kl": "us-en"}
        self.web_status = f"asking DuckDuckGo for \u201c{q}\u201d\u2026"
        self.web_job = self.net.ask("search", q, data=self.web_data)

    def _web_more(self, direction):
        """Turn to the next page of real results — or back to the one before."""
        if direction > 0:
            if not self.web_next:
                self.web_status = "no further results from DuckDuckGo"
                return
            self.web_hist.append(self.web_data)
            self.web_data = self.web_next
        else:
            if not self.web_hist:
                self.web_status = "that is the first page"
                return
            self.web_data = self.web_hist.pop()
        self.web_results = []
        self.web_mono = None
        self.web_tabs = []
        self.pkt = []
        self.pkt_rows = []
        self._pkt_q = []
        self._pkt_i = 0
        self.web_status = "next page\u2026" if direction > 0 else "back a page\u2026"
        if self.net is None:
            self.net = wirenet.Net()
        self.web_job = self.net.ask("search", "", data=self.web_data)

    def _web_open_result(self, i):
        if i < 0 or i >= len(self.web_results):
            return
        self._web_read(self.web_results[i])

    def _web_open_tablet(self, i):
        if 0 <= i < len(self.web_results):
            self._web_read(self.web_results[i])

    def _web_read(self, hit):
        """Reach out for one real page — the packets will cross the hall."""
        if self.net is None:
            self.net = wirenet.Net()
        self.web_mono = {"title": hit["title"], "url": hit["url"], "lines": None,
                         "status": "reaching\u2026", "scroll": 0}
        self.pkt = []
        self.pkt_rows = []
        self._pkt_q = []
        self._pkt_i = 0
        self.web_job = self.net.ask("read", hit["url"], max_bytes=400000, timeout=10)
        self.web_changed.emit()

    def _web_tick(self):
        """Collect the real answer the worker brought back — search or page."""
        if self.web_job is None or self.net is None:
            return
        got = self.net.poll(self.web_job)
        if got is None:
            return
        self.web_job = None
        if got.get("kind") == "search":
            self.web_answer = got
            if got.get("ok"):
                res = got.get("results", [])
                self.web_results = res
                self.web_next = got.get("next")
                self._place_tablets(res)
                self._load_phases(got.get("phases", []))
                self.web_net = {"host": (got.get("url") or "").split("//")[-1].split("/")[0],
                                "ip": got.get("ip")}
                n = len(res)
                page = len(self.web_hist) + 1
                self.web_status = (
                    f"duckduckgo \u00b7 page {page} \u00b7 {n} result{'' if n == 1 else 's'} \u00b7 "
                    f"{got.get('ms', 0):.0f}ms \u00b7 {got.get('ip')} \u2014 fly to a tablet and press E"
                    if n else f"duckduckgo \u00b7 page {page} \u00b7 no results here")
            else:
                self.web_results = []
                self.web_next = None
                self.web_status = f"no answer: {got.get('error')}"
        elif got.get("kind") == "read" and self.web_mono is not None:
            if got.get("ok"):
                text = self._web_extract(got.get("text", ""))
                self.web_mono["lines"] = text or "(this page served no readable text \u2014 it may be script-only)"
                self.web_mono["status"] = (f"{got.get('status')} \u00b7 "
                                           f"{got.get('ms', 0):.0f}ms \u00b7 "
                                           f"{got.get('bytes')}b \u00b7 {got.get('ip')}")
                self._load_phases(got.get("phases", []))
                self.web_net = {"host": (got.get("url") or "").split("//")[-1].split("/")[0],
                                "ip": got.get("ip")}
            else:
                self.web_mono["lines"] = f"(could not read it: {got.get('error')})"
                self.web_mono["status"] = "no answer"
            self.web_changed.emit()

    # ---- the packet theatre -------------------------------------------------
    def _service_geom(self):
        """Where the console stands and where the far service hangs, in the hall."""
        a = self.service_angle
        cx = EXCHANGE_GATE_R * math.cos(a)
        cz = EXCHANGE_GATE_R * math.sin(a)
        sx = EXCHANGE_SERVER_R * math.cos(a)
        sz = EXCHANGE_SERVER_R * math.sin(a)
        y = EXCHANGE_FLOOR_Y
        return (cx, y + 3.2, cz), (sx, y + 9.0, sz)

    def _at_console(self):
        if self.service is None:
            return True
        a = self.service_angle
        cx = EXCHANGE_GATE_R * math.cos(a)
        cz = EXCHANGE_GATE_R * math.sin(a)
        return math.hypot(self.pos[0] - cx, self.pos[2] - cz) <= EXCHANGE_CONSOLE_R

    def _place_tablets(self, results):
        """Hang each result as a tablet on the ring of the hall, yours to fly to."""
        self.web_tabs = []
        a0 = self.service_angle
        for i, hit in enumerate(results[:10]):
            col = i % 5
            row = i // 5
            a = a0 + (col - 2) * 0.30
            r = EXCHANGE_TABLET_R + row * 5.0
            x, z = r * math.cos(a), r * math.sin(a)
            self.web_tabs.append({"index": i, "angle": a, "x": x, "z": z,
                                  "title": hit.get("title", ""), "url": hit.get("url", ""),
                                  "col": (0.35, 0.85, 1.0)})

    def _load_phases(self, phases):
        """Turn the real, measured phases into a stream of packets to fly."""
        q = []
        for ph in phases or []:
            nm = ph.get("phase")
            ms = ph.get("ms", 0.0)
            by = ph.get("bytes", 0)
            if nm == "dns":
                q.append({"dir": "out", "label": "DNS " + str(ph.get("host", "")),
                          "col": (0.40, 0.62, 1.0), "burst": 1,
                          "row": f"dns query \u00b7 {ph.get('host','')}",
                          "rcol": (0.55, 0.72, 1.0)})
                q.append({"dir": "back", "label": "DNS \u2192 " + str(ph.get("ip", "")),
                          "col": (0.55, 0.92, 1.0), "burst": 1, "row": "",
                          "rcol": (0.55, 0.92, 1.0)})
            elif nm == "tcp":
                q.append({"dir": "out", "label": "SYN", "col": (1.0, 0.85, 0.35), "burst": 1,
                          "row": f"tcp connect \u00b7 {ph.get('ip','')}:{ph.get('port','')}",
                          "rcol": (1.0, 0.85, 0.45)})
                q.append({"dir": "back", "label": "SYN/ACK", "col": (1.0, 0.92, 0.55), "burst": 1,
                          "row": f"  handshake \u00b7 {ms:.1f} ms", "rcol": (0.8, 0.8, 0.6)})
                q.append({"dir": "out", "label": "ACK", "col": (1.0, 0.85, 0.35), "burst": 1,
                          "row": "", "rcol": (1.0, 0.85, 0.45)})
            elif nm == "tls":
                q.append({"dir": "out", "label": "ClientHello", "col": (0.5, 1.0, 0.62), "burst": 2,
                          "row": f"tls {ph.get('version','')} \u00b7 {ph.get('cipher','')} \u00b7 {ms:.1f} ms",
                          "rcol": (0.55, 0.95, 0.7)})
                q.append({"dir": "back", "label": "ServerHello", "col": (0.62, 1.0, 0.72), "burst": 2,
                          "row": "", "rcol": (0.62, 1.0, 0.72)})
            elif nm == "request":
                lbl = f"{ph.get('method','GET')} {ph.get('path','/')}"
                q.append({"dir": "out", "label": lbl, "col": (1.0, 0.60, 0.30),
                          "burst": 1 + by // 700,
                          "row": f"{lbl} \u00b7 {by}b", "rcol": (1.0, 0.65, 0.4)})
            elif nm == "response":
                q.append({"dir": "back", "label": f"{ph.get('status','')} \u00b7 {by}b",
                          "col": (0.55, 1.0, 0.62), "burst": 1 + by // 9000,
                          "row": f"response \u00b7 http {ph.get('status','')} \u00b7 {ms:.1f} ms \u00b7 {by}b",
                          "rcol": (0.6, 1.0, 0.7)})
        self._pkt_q = q
        self._pkt_i = 0
        self._pkt_t = 0.0

    def _packet_step(self, dt):
        if self.service is None:
            self.pkt = []
            return
        if self._pkt_i < len(self._pkt_q):
            self._pkt_t += dt
            if self._pkt_t >= 0.14:
                self._pkt_t = 0.0
                ev = self._pkt_q[self._pkt_i]
                self._pkt_i += 1
                for k in range(max(1, ev.get("burst", 1))):
                    self.pkt.append({"ev": ev, "t0": time.time() - k * 0.035, "dur": 0.55})
                if ev.get("row"):
                    self.pkt_rows.append({"txt": ev["row"],
                                          "col": ev.get("rcol", (0.7, 0.9, 1.0))})
                    if len(self.pkt_rows) > 16:
                        self.pkt_rows = self.pkt_rows[-16:]
        now = time.time()
        self.pkt = [p for p in self.pkt if now - p["t0"] < p["dur"]]

    def _draw_packets(self, t):
        """The link itself: console \u2192 far service, with the packets mid-flight."""
        if self.service is None:
            return
        (cx, cy, cz), (sx, sy, sz) = self._service_geom()
        # the wire drawn between them
        glLineWidth(1.0)
        glColor4f(0.25, 0.55, 0.70, 0.45)
        glBegin(GL_LINES)
        glVertex3f(cx, cy, cz)
        glVertex3f(sx, sy, sz)
        glEnd()
        # the far service: a monolith of light on the ring's edge
        pulse = 0.5 + 0.5 * math.sin(t * 1.6)
        self._cube(sx, sy, sz, 1.6, 3.4, 1.6, (0.10, 0.30, 0.42))
        glColor4f(0.35, 0.85 + 0.10 * pulse, 1.0, 0.30)
        glBegin(GL_QUADS)
        glVertex3f(sx - 1.9, sy + 3.4, sz)
        glVertex3f(sx + 1.9, sy + 3.4, sz)
        glVertex3f(sx + 1.9, sy + 9.5, sz)
        glVertex3f(sx - 1.9, sy + 9.5, sz)
        glEnd()
        # the console: a low bench you stand at
        self._cube(cx, cy - 2.0, cz, 1.5, 1.2, 1.5, (0.12, 0.22, 0.28))
        # every packet, again, at the place it truly is along the wire
        now = time.time()
        for p in self.pkt:
            ev = p["ev"]
            u = (now - p["t0"]) / p["dur"]
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            if ev.get("dir") == "out":
                x = cx + (sx - cx) * u
                yv = cy + (sy - cy) * u
                z = cz + (sz - cz) * u
            else:
                x = sx + (cx - sx) * u
                yv = sy + (cy - sy) * u
                z = sz + (cz - sz) * u
            fade = 1.0 - 0.5 * u
            c = ev.get("col", (0.8, 0.9, 1.0))
            self._octa(x, yv, z, 0.20, (c[0] * fade, c[1] * fade, c[2] * fade), squash=1.0)


    def _web_extract(self, raw, limit=40000):
        """The readable text of a real page: scripts and markup stripped, nothing
        invented. If a page carries no text we say so rather than dress it up."""
        t = re.sub(r"(?is)<!--.*?-->", " ", raw or "")
        t = re.sub(r"(?is)<(script|style|noscript|svg|head|template)[^>]*>.*?</\1>", " ", t)
        t = re.sub(r"(?is)<br\s*/?>", "\n", t)
        t = re.sub(r"(?is)</(p|div|li|h[1-6]|tr|section|article|header|footer)>", "\n", t)
        t = re.sub(r"(?is)<[^>]+>", " ", t)
        t = html.unescape(t)
        for _ in range(3):                       # any style block left unclosed
            t = re.sub(r"\{[^{}]*\}", " ", t)
        t = re.sub(r"[ \t\r\f\v\u00a0]+", " ", t)
        t = re.sub(r"\n[ \t]*", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()[:limit]

    def _hud_exchange(self, pr: QPainter, now):
        w_, h_ = self.width(), self.height()
        pr.setFont(QFont("Monospace", 9))
        pr.setPen(QColor(120, 235, 220))
        pr.drawText(14, 22, "SECTION 9  //  WIRE VISION  \u2014  THE EXCHANGE")
        pr.setPen(QColor(90, 150, 160))
        pr.drawText(14, 36, "the hall past the outward gate  \u00b7  each gate leads to a real service")
        if self.service is not None:
            self._hud_ddg(pr, now)
            return
        n = self._nearest_exchange()
        pr.setPen(QColor(180, 200, 220))
        pr.drawText(14, 52, "you are in the Exchange   [on the net, for real]")
        if n and n["kind"] == "service":
            g = n["gate"]
            pr.setPen(QColor(150, 235, 255))
            pr.drawText(14, h_ - 96, f"[E] step into {g['name']} \u2014 {g['blurb']}")
        elif n and n["kind"] == "leave_exchange":
            pr.setPen(QColor(255, 235, 150))
            pr.drawText(14, h_ - 96, "[E] back to the wire")
        pr.setPen(QColor(150, 190, 180))
        pr.drawText(14, h_ - 118, "one gate hangs here for now \u2014 more will follow")
        pr.setPen(QColor(120, 235, 220))
        pr.drawText(14, h_ - 66, "WASD fly  \u00b7  Space/C up/down  \u00b7  E step in  \u00b7  Home leave the Exchange")
        if self._hud_msg and now < self._hud_until:
            pr.setPen(QColor(140, 245, 210))
            pr.drawText(14, h_ - 44, self._hud_msg[:118])

    def _hud_ddg(self, pr: QPainter, now):
        w_, h_ = self.width(), self.height()
        at = self._at_console()
        # the world stays visible under a light film — the packets are the show
        pr.fillRect(0, 0, w_, h_, QColor(0, 0, 0, 96))
        pr.setFont(QFont("Monospace", 9))
        pr.setPen(QColor(150, 235, 255))
        pr.drawText(14, 22, "THE EXCHANGE  //  DUCKDUCKGO  \u2014  watch the packets leave the console")
        # the live packet ledger, down the right
        lx = w_ - 316
        ly = 44
        pr.fillRect(lx, ly, 300, h_ - ly - 96, QColor(4, 10, 16, 200))
        pr.setPen(QColor(40, 70, 80))
        pr.drawRect(lx, ly, 300, h_ - ly - 96)
        pr.setPen(QColor(120, 220, 240))
        pr.drawText(lx + 12, ly + 20, "PACKET LEDGER  \u00b7  as measured")
        yy = ly + 42
        if not self.pkt_rows:
            pr.setPen(QColor(90, 130, 140))
            pr.drawText(lx + 12, yy, "\u2014 no packets in flight \u2014")
        for row in self.pkt_rows:
            if yy > h_ - 118:
                break
            c = row.get("col", (0.7, 0.9, 1.0))
            pr.setPen(QColor(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)))
            pr.drawText(lx + 12, yy, row["txt"][:44])
            yy += 15
        if self.web_net:
            pr.setPen(QColor(120, 180, 190))
            pr.drawText(lx + 12, h_ - 118,
                        f"far service: {self.web_net.get('host','?')}")
            pr.drawText(lx + 12, h_ - 104, f"{self.web_net.get('ip','')}")
        # what is left to fly: the result-tablets, named where they hang
        self._hud_tablets(pr, now, w_, h_)
        if self.web_mono is not None:
            self._hud_mono(pr, now, w_, h_)
            return
        # the console line — only while you actually stand at it
        if at:
            caret = "\u2588" if int(now * 2) % 2 == 0 else " "
            pr.setFont(QFont("Monospace", 13))
            pr.setPen(QColor(205, 240, 255))
            pr.drawText(20, h_ - 74, "\u25b8 " + self.web_query + caret)
        else:
            pr.setPen(QColor(150, 200, 210))
            pr.drawText(20, h_ - 74, "fly back to the console to type a new search")
        pr.setFont(QFont("Monospace", 9))
        pr.setPen(QColor(140, 200, 210))
        pr.drawText(20, h_ - 54, self.web_status[:118])
        pr.setPen(QColor(120, 235, 220))
        pr.drawText(14, h_ - 34,
                    "at the console: type + Enter  \u00b7  fly to a tablet + E to open  "
                    "\u00b7  [ ] page  \u00b7  Esc  \u00b7  Home leave")

    def _hud_tablets(self, pr, now, w_, h_):
        if not self.web_tabs:
            return
        try:
            vp = glGetIntegerv(GL_VIEWPORT)
        except Exception:
            return
        pr.setFont(QFont("Monospace", 9))
        far = None
        for i, tab in enumerate(self.web_tabs):
            try:
                sx, sy, sz = gluProject(tab["x"], EXCHANGE_FLOOR_Y + 4.0, tab["z"])
            except Exception:
                continue
            if sz < 0 or sz > 1:
                continue
            sxx, syy = int(sx), int(vp[3] - sy)
            if not (0 <= sxx <= w_ and 0 <= syy <= h_):
                continue
            d = math.hypot(self.pos[0] - tab["x"], self.pos[2] - tab["z"])
            near = d <= 5.5
            pr.setPen(QColor(255, 220, 120) if near else QColor(120, 200, 235))
            pr.drawText(sxx + 6, syy, f"[{i + 1 if i < 9 else 0}] " + tab["title"][:60])
            if near:
                far = i
        return far

    def _hud_mono(self, pr, now, w_, h_):
        mo = self.web_mono
        m, top = 40, 40
        ww, hh = w_ - 380, h_ - 150
        pr.fillRect(m, top, ww, hh, QColor(3, 12, 18, 226))
        pr.setPen(QColor(70, 160, 190))
        pr.drawRect(m, top, ww, hh)
        pr.setFont(QFont("Monospace", 11))
        pr.setPen(QColor(160, 245, 255))
        pr.drawText(m + 16, top + 28, mo["title"][:96])
        pr.setFont(QFont("Monospace", 9))
        pr.setPen(QColor(120, 175, 190))
        pr.drawText(m + 16, top + 46, mo["url"][:118])
        pr.setPen(QColor(150, 205, 205))
        pr.drawText(m + 16, top + 62, "served \u00b7 " + (mo.get("status") or ""))
        body = mo.get("lines")
        rect = QRect(m + 16, top + 76, ww - 32, hh - 76 - 26)
        pr.setClipRect(rect)
        pr.setPen(QColor(205, 228, 228))
        tr = QRect(rect.x(), rect.y() - mo.get("scroll", 0), rect.width(), 100000)
        pr.drawText(tr, int(Qt.TextFlag.TextWordWrap), body or "(reaching\u2026)")
        pr.setClipping(False)
        pr.setPen(QColor(120, 235, 220))
        pr.drawText(m + 16, top + hh - 10,
                    "[ ] scroll  \u00b7  Esc back  \u00b7  Home leave the Exchange")

    # ---- paint -------------------------------------------------------------
    def paintGL(self):
        now = time.time()
        dt = min(0.1, now - self._last_t)
        self._last_t = now
        self._step(dt)

        key = STRATA_KEY[self.active]
        p = PAL[key]
        if self.market:
            self._market_sky()
        elif self.word:
            self._word_sky()
        elif self.exchange:
            self._exchange_sky()
        elif self.machine:
            self._machine_sky()
        elif self.candles:
            self._candles_sky()
        else:
            self._sky_and_hills(p)

        # camera
        w_, h_ = max(1, self.width()), max(1, self.height())
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(70.0, w_ / h_, 0.1, 400.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        cp = math.cos(self.pitch)
        look = (cp * math.sin(self.yaw), math.sin(self.pitch), -cp * math.cos(self.yaw))
        gluLookAt(self.pos[0], self.pos[1], self.pos[2],
                  self.pos[0] + look[0], self.pos[1] + look[1], self.pos[2] + look[2],
                  0, 1, 0)

        if self.deep is not None:
            sp = self.deep["d"] * 0.05          # the sea turns as you fall
            self._glyph_rain(now, spin=sp, dim=1.0)
            self._glyph_rain(now, spin=sp + 1.1, dim=0.62)
            self._deep_motes(now)
        elif not self.word and not self.exchange and not self.machine \
                and not self.candles:
            self._glyph_rain(now)
        if self.market:
            self._draw_market(now)
        elif self.word:
            self._draw_word(now)
        elif self.exchange:
            self._draw_exchange(now)
        elif self.machine:
            self._draw_machine(now)
        elif self.candles:
            self._draw_candles(now)
        elif self.world and self.deep is None:
            self._ground(p)
            self._well(now)
            if self.active == 0:
                self._draw_rooms(now)
                self._draw_floor_objects(now)
            else:
                self._draw_stratum_objects(now)

        # ---- HUD via QPainter ----
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            self._hud(painter, now, key)
        finally:
            painter.end()

    def _hud_market(self, pr: QPainter, now):
        w_, h_ = self.width(), self.height()
        f = QFont("Monospace", 9)
        pr.setFont(f)
        fm = pr.fontMetrics()
        mw = self.market_world or {}
        acc = mw.get("account", {})
        mode = acc.get("mode", "?")
        cash = acc.get("cash")
        alloc = acc.get("allocated")
        cur = acc.get("currency", "")
        loop = mw.get("loop", {})
        ok = loop.get("heartbeat") == "ok"
        line1 = "SECTION 9  //  WIRE VISION  \u2014  THE MARKET (BLACKHORSE)"
        pr.setPen(QColor(120, 235, 220))
        pr.drawText(14, 22, line1)
        pr.setPen(QColor(90, 150, 160))
        pr.drawText(14, 36, "blackhorse \u00b7 the trading floor, reached through the gate on the wire")
        pr.setPen(QColor(180, 200, 220))
        pr.drawText(14, 52, "you are in the market   [blackhorse]")
        # account block (real files, honest values)
        pr.setPen(QColor(0, 0, 0, 40))
        px = w_ - 320
        pr.fillRect(px, 30, 306, 92, QColor(10, 18, 24, 190))
        yy = 46
        pr.setPen(QColor(210, 235, 230))
        pr.drawText(px + 10, yy, f"BLACKHORSE \u00b7 {mode}")
        pr.setPen(QColor(150, 200, 195))
        s = f"cash {cash:g} {cur} \u00b7 allocated {alloc:g}" if cash is not None else f"mode {mode}"
        pr.drawText(px + 10, yy + 16, s)
        if loop:
            pr.setPen(QColor(120, 230, 160) if ok else QColor(235, 90, 70))
            reason = loop.get("reason") or loop.get("decision") or "?"
            pr.drawText(px + 10, yy + 32, f"loop {reason}"[:80])
        n = len(self._peers)
        online = self._online or n > 0
        pr.setPen(QColor(160, 190, 210))
        if online:
            msg = f"relay online \u00b7 {n} other user{'' if n == 1 else 's'} on the floor"
        else:
            msg = "alone here \u00b7 no other user on the relay"
        pr.drawText(px + 10, yy + 48, msg)
        # legend + honesty
        pr.setPen(QColor(150, 190, 180))
        pr.drawText(14, h_ - 134,
                    "pad green = waiting to buy \u00b7 pad red = waiting to sell \u00b7 "
                    "pulsing red = an exit is firing \u00b7 dim = off")
        pr.setPen(QColor(170, 220, 175))
        pr.drawText(14, h_ - 118,
                    "the floating arrow = the SignalBot's LEAN \u2014 green points up, "
                    "red points down, amber = flat \u00b7 fly close to read the full interval")
        pr.setPen(QColor(130, 165, 175))
        pr.drawText(14, h_ - 102,
                    "platforms are YOUR trading agents (real config); "
                    "bodies are other users on the relay (real); the floor is dressing")
        ghost = self._ghost_line or "ghost layer: open \u00b7 set MRFLUFFY_WIRE_KEY on relay + players"
        pr.setPen(QColor(160, 190, 210) if "hardened" in ghost else QColor(200, 170, 90))
        pr.drawText(14, h_ - 86, ghost[:116])
        pr.setPen(QColor(120, 235, 220))
        pr.drawText(14, h_ - 66,
                    "WASD fly \u00b7 Space/C up/down \u00b7 E step / settings \u00b7 "
                    "B rebuild \u00b7 H menu \u00b7 Home leave")
        # fallback control hint when instructions are off
        pr.setPen(QColor(180, 200, 220))
        pr.drawText(14, h_ - 50, "it is always open \u00b7 step onto a platform = fly down to it (C) \u00b7 "
                                 "press any key to step off")
        n0 = self._nearest()
        ccx, ccy = w_ // 2, h_ // 2
        if n0:
            pr.setPen(QPen(QColor(255, 185, 40, 235), 2))
        else:
            pr.setPen(QPen(QColor(120, 230, 180, 190), 2))
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            pr.drawLine(ccx + dx * 18, ccy + dy * 18, ccx + dx * 18 + dx * 12, ccy + dy * 18)
            pr.drawLine(ccx + dx * 18, ccy + dy * 18, ccx + dx * 18, ccy + dy * 18 + dy * 12)
        if n0:
            if n0["kind"] == "platform":
                a = n0["agent"]
                prompt = f"[E] step onto {a['name']}'s platform \u2014 open its trading settings"
            elif n0["kind"] == "candles":
                prompt = "[E] enter the candle room \u2014 DOT/USD's tape, read as a place"
            elif n0["kind"] == "leave_market":
                prompt = "[E] leave the market \u2014 back to the wire"
            pr.setPen(QColor(255, 215, 120))
            tw = fm.horizontalAdvance(prompt)
            pr.drawText((w_ - tw) // 2, ccy + 46, prompt)
        # ---- in-world labels (platform names + the SignalBot lean tag) ----
        for (sx, sy, txt, col) in self._market_labels():
            if not (0 <= sx <= w_ and 0 <= sy <= h_):
                continue
            pr.setPen(QColor(int(col[0] * 255), int(col[1] * 255),
                             int(col[2] * 255), 230))
            pr.drawText(int(sx) + 6, int(sy), txt)
        # ---- the full SignalBot read, floating in the world by each platform -
        # no menu: fly near a platform and its interval's whole read is laid out
        # beside it, exactly as the "Run SignalBot now" pane shows it.
        self._market_signal_panels(pr)
        if self.candles_select:
            self._candles_chooser(pr)
        if self._hud_msg and now < self._hud_until:
            pr.setPen(QColor(120, 230, 180))
            tw = fm.horizontalAdvance(self._hud_msg)
            pr.drawText((w_ - tw) // 2, h_ - 40, self._hud_msg)

    def _market_signal_panels(self, pr):
        """The full per-interval SignalBot read as floating panels in the world,
        anchored to each platform you are near or standing on. Dressing only —
        every line is the bot's own snapshot (see wiregate._signal_lines)."""
        w_, h_ = self.width(), self.height()
        vp = glGetIntegerv(GL_VIEWPORT)
        sel = self.selected_agent
        near_dist = 24.0
        for a in (self.market_world or {}).get("agents", []):
            sig = a.get("signal") or {}
            if not sig.get("available"):
                continue
            x, yy, z = a["pos"]
            try:
                sx, sy, sz = gluProject(x, yy + 7.6, z)
            except Exception:
                continue
            if sz < 0 or sz > 1:
                continue
            dist = math.dist((x, yy, z), tuple(self.pos))
            if not (dist <= near_dist or a["id"] == sel):
                continue
            sxx, syy = sx, vp[3] - sy
            lean = sig.get("lean") or {}
            ld = lean.get("dir", "none")
            rows = [("hdr", f"{a['name']}  \u2014  SignalBot \u00b7 "
                            f"{sig.get('pair', '?')} @ {sig.get('exchange', '?')} \u00b7 "
                            f"{sig.get('strategy', '?')} \u00b7 read {sig.get('age', '?')}")]
            rows.append(("lean", f"LEAN {MARKET_LEAN_TXT.get(ld, ld)}"
                                 f"  (score {lean.get('score')}: {lean.get('basis')})"))
            for r in sig.get("reads", []):
                for ln in r.get("lines", []):
                    rows.append(("gate" if "strength gate" in ln else "body", ln))
            pr.setFont(QFont("Monospace", 8))
            fm = pr.fontMetrics()
            lh = fm.height() + 1
            wmax = max((fm.horizontalAdvance(t) for _, t in rows), default=220)
            wbox = min(640, wmax + 22)
            hbox = lh * len(rows) + 16
            bx = min(max(8, int(sxx) + 20), w_ - wbox - 8)
            by = min(max(8, int(syy) - hbox // 2), h_ - hbox - 8)
            pr.setPen(Qt.PenStyle.NoPen)
            pr.setBrush(QColor(8, 16, 22, 208))
            pr.drawRoundedRect(bx, by, wbox, hbox, 6, 6)
            pr.setBrush(Qt.BrushStyle.NoBrush)
            pr.setPen(QPen(QColor(90, 150, 160, 170), 1))
            pr.drawRoundedRect(bx, by, wbox, hbox, 6, 6)
            ty = by + 8 + fm.ascent()
            for kind, t in rows:
                if kind == "hdr":
                    pr.setPen(QColor(140, 235, 220))
                elif kind == "lean":
                    pr.setPen(QColor(*(int(c * 255) for c in
                                       MARKET_LEAN_COL.get(ld, MARKET_LEAN_COL["none"]))))
                elif kind == "gate":
                    pr.setPen(QColor(255, 205, 120))
                else:
                    pr.setPen(QColor(190, 210, 220))
                pr.drawText(bx + 10, ty, t)
                ty += lh
            pr.setFont(QFont("Monospace", 9))

    # ---- the candle room: DOT/USD's tape read as a place --------------------
    # Entered from the market's centre column. One interval is chosen at the
    # door; the room is a walk down the tape — one tower per candle, the newest
    # glowing as it ticks, the market's "feel" painted from SignalBot's own
    # per-candle rows. Everything is local ground truth (candlevision.py): the
    # bars are real OHLCV, the read is the bot's own saved row, the room is dressing.
    def _candles_enter_select(self):
        opts = candlevision.available()
        if not opts:
            self._flash("no candle history on file \u2014 nothing to read yet")
            return
        self.candles_select = True
        self.candles_ivs = opts
        labels = "  ".join(f"[{i + 1}] {o['interval']}" for i, o in enumerate(opts))
        self._flash(f"choose an interval for the candle room:  {labels}")

    def _enter_candles(self, iv):
        try:
            w = candlevision.build(iv)
        except Exception as e:
            self._flash(f"could not open the candle room: {e}")
            self.candles_select = False
            self.candles_ivs = []
            return
        self.candles_world = w
        self.candles = True
        self.candles_select = False
        self.candles_ivs = []
        self.candles_sel = None
        self.market = False
        self.market_world = None
        self.word = False
        self.exchange = False
        self.machine = False
        self.service = None
        self.deep = None
        self.transition = None
        self.selected_agent = None
        self.selected = None
        self.flying = True
        self.active = 0
        g = w["geometry"]
        self.pos = [g["x1"] + 2.0, g["base_y"] + 8.0, 0.0]
        self.yaw = -math.pi / 2.0        # stand at the newest bar, look back in time
        self.pitch = -0.05
        nowr = w.get("now") or {}
        tail = f" \u00b7 SignalBot read {nowr.get('age')}" if nowr.get("age") else ""
        self._flash(f"the candle room \u00b7 {w['pair']} @ {iv} \u00b7 {w['n']} bars "
                    f"\u00b7 {w['rows_joined']} carry a bot read{tail}")
        self.candles_changed.emit()

    def _leave_candles(self):
        was = self.candles
        self.candles = False
        self.candles_world = None
        self.candles_sel = None
        self.candles_select = False
        self.candles_ivs = []
        self.flying = False
        # back up the column into the market you came from
        self._enter_market()
        if self.market:
            self.pos = [0.0, self._market_floor() + EYE, 9.0]
            self.yaw = 0.0
            self.pitch = -0.05
        if was:
            self._flash("back in the market \u2014 the candle room is closed")
        self.candles_changed.emit()

    def refresh_candles(self):
        """Re-read the candle + row files and rebuild the tape (B inside)."""
        if not self.candles or not self.candles_world:
            return
        iv = self.candles_world.get("interval")
        try:
            self.candles_world = candlevision.build(iv)
        except Exception as e:
            self._flash(f"candle room rebuild failed: {e}")
            return
        w = self.candles_world
        self._flash(f"candle room rebuilt \u00b7 {w['interval']} \u00b7 {w['n']} bars "
                    f"\u00b7 fp {w.get('fingerprint')}")
        self.update()

    def _candles_step(self, dt):
        k = self.keys
        fast = self._boost()
        spd = 13.0 * self.move_mult * fast * dt
        cp = math.cos(self.pitch)
        fx, fy, fz = cp * math.sin(self.yaw), math.sin(self.pitch), -cp * math.cos(self.yaw)
        rx, rz = math.cos(self.yaw), math.sin(self.yaw)
        dx = dy = dz = 0.0
        if Qt.Key.Key_W in k:
            dx += fx; dy += fy; dz += fz
        if Qt.Key.Key_S in k:
            dx -= fx; dy -= fy; dz -= fz
        if Qt.Key.Key_A in k:
            dx -= rx; dz -= rz
        if Qt.Key.Key_D in k:
            dx += rx; dz += rz
        if Qt.Key.Key_Space in k:
            dy += 1.0
        if Qt.Key.Key_C in k:
            dy -= 1.0
        m = math.sqrt(dx * dx + dy * dy + dz * dz)
        if m > 0:
            self._speed_now = 13.0 * self.move_mult * fast
            self.pos[0] += dx / m * spd
            self.pos[1] += dy / m * spd
            self.pos[2] += dz / m * spd
        g = (self.candles_world or {}).get("geometry") or {}
        x0 = g.get("x0", 0.0); xe = g.get("entry_x", g.get("x1", 0.0) + 8.0)
        floor = g.get("floor_y", CANDLES_FLOOR_Y)
        self.pos[0] = max(x0 - 16.0, min(xe + 2.0, self.pos[0]))
        self.pos[2] = max(-15.0, min(15.0, self.pos[2]))
        self.pos[1] = max(floor + 1.5, min(floor + 72.0, self.pos[1]))

    def _candles_sky(self):
        glClearColor(0.020, 0.012, 0.030, 1.0)          # a dark violet hall
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        g = (self.candles_world or {}).get("geometry") or {}
        base = g.get("base_y", CANDLES_FLOOR_Y + 3.0)
        if self._candle_stars is None:
            rnd = random.Random(1995 + 11)
            self._candle_stars = [(rnd.uniform(-20.0, 380.0), base + rnd.uniform(6.0, 96.0),
                                   rnd.uniform(-70.0, 70.0)) for _ in range(240)]
        glPointSize(1.0)
        glColor4f(0.58, 0.64, 0.86, 0.5)
        glBegin(GL_POINTS)
        for (sx, sy, sz) in self._candle_stars:
            glVertex3f(sx, sy, sz)
        glEnd()

    def _draw_candles(self, t):
        w = self.candles_world
        if not w or not w.get("bars"):
            return
        g = w["geometry"]
        y0 = g["floor_y"]; base = g["base_y"]; top = g["top_y"]
        x0, x1 = g["x0"], g["x1"]
        # the floor: a long dark slab, faint rails running with the tape
        glColor4f(0.045, 0.030, 0.062, 1.0)
        glBegin(GL_QUADS)
        glVertex3f(x0 - 12, y0, -18); glVertex3f(x1 + 16, y0, -18)
        glVertex3f(x1 + 16, y0, 18); glVertex3f(x0 - 12, y0, 18)
        glEnd()
        glLineWidth(1.0)
        for rr in (-10.0, -5.0, 5.0, 10.0):
            glColor4f(0.10, 0.07, 0.145, 1.0)
            glBegin(GL_LINES)
            glVertex3f(x0 - 12, y0 + 0.03, rr); glVertex3f(x1 + 16, y0 + 0.03, rr)
            glEnd()
        # the floor and roof of the range
        for yy in (base, top):
            glColor4f(0.15, 0.16, 0.32, 1.0)
            glBegin(GL_LINES)
            glVertex3f(x0, yy, 0.0); glVertex3f(x1, yy, 0.0)
            glEnd()
        # the bars: one tower per candle, wick to the true high/low, mood at its foot
        for b in w["bars"]:
            up = b["c"] >= b["o"]
            base_col = CANDLE_UP if up else CANDLE_DOWN
            hasrow = b.get("row") is not None
            col = base_col if hasrow else tuple(c * 0.60 for c in base_col)
            lo, hi = min(b["y_open"], b["y_close"]), max(b["y_open"], b["y_close"])
            if hi - lo < 0.05:
                hi = lo + 0.05
            self._cube(b["x"], (lo + hi) / 2.0, 0.0, 0.30, hi - lo, 0.42, col)
            glColor4f(min(1.0, col[0] * 1.08), min(1.0, col[1] * 1.08),
                      min(1.0, col[2] * 1.08), 1.0)
            glLineWidth(1.3)
            glBegin(GL_LINES)
            glVertex3f(b["x"], b["y_low"], 0.0); glVertex3f(b["x"], b["y_high"], 0.0)
            glEnd()
            m = b.get("mood")
            if m:
                mc = m["col"]
                glColor4f(mc[0], mc[1], mc[2], 0.55 if hasrow else 0.26)
                glBegin(GL_QUADS)
                glVertex3f(b["x"] - 0.20, y0 + 0.05, -0.20)
                glVertex3f(b["x"] + 0.20, y0 + 0.05, -0.20)
                glVertex3f(b["x"] + 0.20, y0 + 0.05, 0.20)
                glVertex3f(b["x"] - 0.20, y0 + 0.05, 0.20)
                glEnd()
        glLineWidth(1.0)
        # the close line: one polyline through every close
        glColor4f(0.86, 0.86, 1.0, 0.32)
        glBegin(GL_LINE_STRIP)
        for b in w["bars"]:
            glVertex3f(b["x"], b["y_close"], 0.0)
        glEnd()
        # the newest bar: the live one, breathing a halo of light
        nb = w["bars"][-1]
        pulse = 1.0 + 0.25 * math.sin(t * 4.0)
        mid = (nb["y_open"] + nb["y_close"]) / 2.0
        glColor4f(0.98, 0.82, 0.38, 0.18)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(nb["x"], mid, 0.0)
        for i in range(25):
            aa = 2 * math.pi * i / 24
            glVertex3f(nb["x"] + 1.3 * pulse * math.cos(aa),
                       mid + 2.6 * pulse * math.sin(aa), 0.0)
        glEnd()
        self._octa(nb["x"], top + 3.0, 0.0, 0.5, CANDLE_AMBER)
        # the selected bar, ringed
        if self.candles_sel is not None and 0 <= self.candles_sel < len(w["bars"]):
            b = w["bars"][self.candles_sel]
            bm = (min(b["y_open"], b["y_close"]) + max(b["y_open"], b["y_close"])) / 2.0
            self._vring(b["x"], bm, 0.0, 1.9, (1.0, 1.0, 1.0), t)
        # lights strung along the tape's spine (dressing)
        for j in range(int(x0), int(x1) + 1, 12):
            lum = 0.4 + 0.25 * math.sin(t * 1.6 + j * 0.3)
            glColor4f(lum, 0.55 * lum, 0.30 * lum, 0.5)
            self._octa(float(j), top + 6.0, 0.0, 0.22, (lum, 0.55 * lum, 0.30 * lum))
        # the way back: the entrance portal at the newest end
        self._vring(g["entry_x"], base + 3.4, 0.0, 3.2, (0.85, 0.45, 0.95), t + 0.6)
        self._vring(g["entry_x"], base + 3.4, 0.0, 2.1, (0.60, 0.30, 0.75), t + 1.6)

    def _nearest_candles(self):
        w = self.candles_world
        if not w or not w.get("bars"):
            return None
        px, py, pz = self.pos
        g = w["geometry"]
        best = None
        dl = math.hypot(px - g["entry_x"], pz)
        if dl <= 5.5:
            best = {"kind": "candles_leave", "d": dl}
        for b in w["bars"]:
            dx = abs(px - b["x"])
            if dx > 2.4 or abs(pz) > 12.0:
                continue
            if abs(py - (b["y_high"] + b["y_low"]) / 2.0) > 16.0:
                continue
            if best is None or dx < best["d"]:
                best = {"kind": "candle", "d": dx, "bar": b, "index": b["i"]}
        return best

    def _candles_labels(self):
        out = []
        w = self.candles_world
        if not w or not w.get("bars"):
            return out
        vp = glGetIntegerv(GL_VIEWPORT)
        px = self.pos[0]
        g = w["geometry"]
        near = sorted(w["bars"], key=lambda b: abs(b["x"] - px))[:28]
        for b in near:
            if abs(b["x"] - px) > 30.0:
                continue
            try:
                sx, sy, sz = gluProject(b["x"], b["y_high"] + 1.3, 0.0)
            except Exception:
                continue
            if sz < 0 or sz > 1:
                continue
            m = b.get("mood") or {}
            glyph = "\u25b2" if b["c"] >= b["o"] else "\u25bc"
            out.append((sx, vp[3] - sy, f"{b['tstr'][5:16]} \u00b7 {glyph}{b['c']:g}",
                        m.get("col", CANDLE_GREY)))
        try:
            sx, sy, sz = gluProject(g["entry_x"], g["base_y"] + 4.2, 0.0)
            if 0 <= sz <= 1:
                out.append((sx, vp[3] - sy, "leave the candle room [E] \u2014 back to the market",
                            (0.90, 0.72, 0.98)))
        except Exception:
            pass
        return out

    def _candles_panel(self, pr):
        """The full read of one bar, floating beside it in the world — the bar's
        real OHLCV and, where the bot left one, its own row for that candle."""
        w = self.candles_world
        if not w or not w.get("bars"):
            return
        idx = self.candles_sel
        if idx is None:
            n = self._nearest_candles()
            if not n or n["kind"] != "candle":
                return
            idx = n["index"]
        if not (0 <= idx < len(w["bars"])):
            return
        b = w["bars"][idx]
        vp = glGetIntegerv(GL_VIEWPORT)
        ymid = (min(b["y_open"], b["y_close"]) + max(b["y_open"], b["y_close"])) / 2.0
        try:
            sx, sy, sz = gluProject(b["x"], ymid, 0.0)
        except Exception:
            return
        if sz < 0 or sz > 1:
            return
        m = b.get("mood") or {}
        r = b.get("row")

        def _p(x):
            return "\u2014" if x is None else f"{x:+.2f}%"
        rows = [("hdr", f"bar {b['i']} \u00b7 {b['tstr']} \u00b7 {w['pair']} @ {w['interval']}"),
                ("ohlc", f"O {b['o']:g}  H {b['h']:g}  L {b['l']:g}  C {b['c']:g}  "
                         f"V {b['v']:,.0f}"),
                ("mood", f"the feel: {m.get('word', '?')}  ({m.get('after', '')})")]
        if r:
            rows.append(("bot", f"bot read: range {r.get('rangeSignal')} \u00b7 zone "
                                f"{r.get('zone')} \u00b7 strength "
                                f"{round(r.get('strength') or 0, 3)} "
                                f"{r.get('strengthDirection')}"))
            rows.append(("bot", f"MAs short {r.get('shortMA')} long {r.get('longMA')} "
                                f"\u00b7 spread {r.get('maSpreadPct')}% \u00b7 trend {r.get('trend')}"))
            rows.append(("bot", f"band lower {r.get('lowerBand')} upper {r.get('upperBand')} "
                                f"\u00b7 support {r.get('nearestSupportPct')}% "
                                f"({r.get('supportTouches')} touches)"))
            rows.append(("next", f"what happened next: 1 {_p(r.get('return1'))} \u00b7 "
                                 f"3 {_p(r.get('return3'))} \u00b7 5 {_p(r.get('return5'))} \u00b7 "
                                 f"10 {_p(r.get('return10'))} \u00b7 20 {_p(r.get('return20'))}"))
            rows.append(("next", f"excursion 5: mfe {_p(r.get('mfe5'))} mae {_p(r.get('mae5'))}"))
        else:
            rows.append(("dim", "no bot row joined to this bar (lookback warmup, or an older dump)"))
        rows.append(("dim", "bar = observed (real OHLCV) \u00b7 feel = the bot's own row, "
                            "or the bar's shape"))

        pr.setFont(QFont("Monospace", 8))
        fm = pr.fontMetrics()
        lh = fm.height() + 1
        wmax = max((fm.horizontalAdvance(t) for _, t in rows), default=220)
        wbox = min(self.width() - 16, wmax + 22)
        hbox = lh * len(rows) + 16
        sxx, syy = sx, vp[3] - sy
        bx = min(max(8, int(sxx) + 20), self.width() - wbox - 8)
        by = min(max(8, int(syy) - hbox // 2), self.height() - hbox - 8)
        pr.setPen(Qt.PenStyle.NoPen)
        pr.setBrush(QColor(24, 14, 26, 212))
        pr.drawRoundedRect(bx, by, wbox, hbox, 6, 6)
        pr.setBrush(Qt.BrushStyle.NoBrush)
        pr.setPen(QPen(QColor(170, 120, 150, 170), 1))
        pr.drawRoundedRect(bx, by, wbox, hbox, 6, 6)
        ty = by + 8 + fm.ascent()
        for kind, txt in rows:
            if kind == "hdr":
                pr.setPen(QColor(245, 205, 150))
            elif kind == "ohlc":
                pr.setPen(QColor(210, 205, 225))
            elif kind == "mood":
                pr.setPen(QColor(*(int(c * 255) for c in m.get("col", CANDLE_GREY))))
            elif kind == "bot":
                pr.setPen(QColor(170, 220, 200))
            elif kind == "next":
                pr.setPen(QColor(200, 190, 235))
            else:
                pr.setPen(QColor(150, 140, 165))
            pr.drawText(bx + 10, ty, txt)
            ty += lh
        pr.setFont(QFont("Monospace", 9))

    def _candles_chooser(self, pr):
        """The interval chooser at the candle room's door: one number per tape."""
        w_, h_ = self.width(), self.height()
        fm = pr.fontMetrics()
        rows = ["ENTER THE CANDLE ROOM",
                "choose an interval for DOT/USD \u2014 blackhorse's own tape:",
                ""]
        for i, o in enumerate(self.candles_ivs):
            rows.append(f"   [{i + 1}]   {o['interval']:>5}    {o['bars']} bars  \u00b7  "
                        f"{o['rows']} bot rows  \u00b7  dumped {o['age']}")
        rows.append("")
        rows.append(f"press 1\u2013{len(self.candles_ivs)} to enter  \u00b7  Esc to cancel")
        lh = fm.height() + 2
        wbox = min(w_ - 60, 560)
        hbox = lh * len(rows) + 26
        bx = (w_ - wbox) // 2
        by = (h_ - hbox) // 2
        pr.setPen(Qt.PenStyle.NoPen)
        pr.setBrush(QColor(20, 12, 24, 230))
        pr.drawRoundedRect(bx, by, wbox, hbox, 10, 10)
        pr.setBrush(Qt.BrushStyle.NoBrush)
        pr.setPen(QPen(QColor(200, 150, 120, 200), 1))
        pr.drawRoundedRect(bx, by, wbox, hbox, 10, 10)
        ty = by + 14 + fm.ascent()
        for i, line in enumerate(rows):
            if i == 0:
                pr.setPen(QColor(255, 210, 150))
            elif i == 1:
                pr.setPen(QColor(190, 170, 190))
            elif line.startswith("press"):
                pr.setPen(QColor(160, 220, 180))
            else:
                pr.setPen(QColor(220, 205, 220))
            pr.drawText(bx + 16, ty, line)
            ty += lh

    def _hud_candles(self, pr, now):
        w_, h_ = self.width(), self.height()
        f = QFont("Monospace", 9)
        pr.setFont(f)
        fm = pr.fontMetrics()
        w = self.candles_world or {}
        pr.setPen(QColor(235, 190, 140))
        pr.drawText(14, 22, "SECTION 9  //  WIRE VISION  \u2014  THE CANDLE ROOM")
        pr.setPen(QColor(150, 120, 145))
        pr.drawText(14, 36, "the tape read as a place \u00b7 DOT/USD, drawn from "
                            "blackhorse's own candle + SignalBot files")
        pr.setPen(QColor(210, 200, 220))
        pr.drawText(14, 52, f"you are in the candle room   [{w.get('interval', '?')}]")
        # the current SignalBot read (the "now" at the newest bar)
        nowr = w.get("now") or {}
        if nowr:
            px = w_ - 330
            pr.setPen(Qt.PenStyle.NoPen)
            pr.setBrush(QColor(26, 16, 28, 200))
            pr.drawRoundedRect(px, 30, 320, 86, 6, 6)
            pr.setBrush(Qt.BrushStyle.NoBrush)
            pr.setPen(QColor(240, 205, 160))
            pr.drawText(px + 10, 46, f"SIGNALBOT NOW \u00b7 {nowr.get('channel', '?')} "
                                      f"\u00b7 {nowr.get('interval', '?')}")
            pr.setPen(QColor(205, 195, 215))
            pr.drawText(px + 10, 62, f"{nowr.get('action')}  conf={nowr.get('confidence')}  "
                                     f"str={round(nowr.get('strength') or 0, 3)} "
                                     f"{nowr.get('strength_direction')}")
            pr.drawText(px + 10, 78, f"trend {nowr.get('trend')} \u00b7 RSI {nowr.get('rsi')} "
                                     f"\u00b7 range {nowr.get('range_signal')}")
            pr.setPen(QColor(165, 150, 180))
            pr.drawText(px + 10, 94, f"read {nowr.get('age')} \u00b7 {nowr.get('pair')} "
                                     f"@ {nowr.get('exchange')}")
        # legend + honesty
        pr.setPen(QColor(220, 180, 150))
        pr.drawText(14, h_ - 118, "green bar = close above open \u00b7 red = close below "
                                  "\u00b7 the wick spans the true high/low")
        pr.setPen(QColor(180, 170, 200))
        pr.drawText(14, h_ - 102, "the light under a bar = SignalBot's own read of it: "
                                  "its strength, its range signal, what happened next")
        hs = candlevision.honesty()
        pr.setPen(QColor(140, 135, 160))
        pr.drawText(14, h_ - 86, hs["real"][:158])
        pr.drawText(14, h_ - 70, hs["feels"][:158])
        pr.setPen(QColor(235, 190, 140))
        pr.drawText(14, h_ - 50, "WASD fly \u00b7 Space/C up/down \u00b7 E read a bar "
                                 "\u00b7 B rebuild \u00b7 Home leave the room")
        # crosshair
        n0 = self._nearest()
        ccx, ccy = w_ // 2, h_ // 2
        pr.setPen(QPen(QColor(255, 185, 40, 235) if n0 else QColor(220, 150, 180, 190), 2))
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            pr.drawLine(ccx + dx * 18, ccy + dy * 18, ccx + dx * 18 + dx * 12, ccy + dy * 18)
            pr.drawLine(ccx + dx * 18, ccy + dy * 18, ccx + dx * 18, ccy + dy * 18 + dy * 12)
        prompt = ""
        if n0 and n0["kind"] == "candle":
            prompt = f"[E] read bar {n0['index']} \u00b7 {n0['bar']['tstr']}"
        elif n0 and n0["kind"] == "candles_leave":
            prompt = "[E] leave the candle room \u2014 back to the market"
        if prompt:
            pr.setPen(QColor(255, 225, 160))
            tw = fm.horizontalAdvance(prompt)
            pr.drawText((w_ - tw) // 2, ccy + 46, prompt)
        # in-world labels + the bar panel
        for (sx, sy, txt, col) in self._candles_labels():
            if not (0 <= sx <= w_ and 0 <= sy <= h_):
                continue
            pr.setPen(QColor(int(col[0] * 255), int(col[1] * 255), int(col[2] * 255), 230))
            pr.drawText(int(sx) + 6, int(sy), txt)
        self._candles_panel(pr)
        if self._hud_msg and now < self._hud_until:
            pr.setPen(QColor(235, 190, 140))
            tw = fm.horizontalAdvance(self._hud_msg)
            pr.drawText((w_ - tw) // 2, h_ - 40, self._hud_msg)

    def _hud_machine(self, pr: QPainter, now):
        w_, h_ = self.width(), self.height()
        mono = QFont("Monospace", 9)
        pr.setFont(mono)
        fm = pr.fontMetrics()
        w = self.machine_world or {}
        h = w.get("host", {})
        c = w.get("counts", {})
        # ---- header: the machine, and what it is (and is not) ----
        pr.setPen(QColor(140, 235, 170))
        pr.drawText(14, 22, f"SECTION 16  //  WIRE VISION  \u2014  THE MACHINE  \u00b7  "
                            f"{h.get('name', '?')}")
        pr.setPen(QColor(105, 170, 135))
        pr.drawText(14, 36, "this is THIS machine, read live from /proc and the local "
                            "logs \u2014 not the network, not a scan, a memory of nothing")
        pr.drawText(14, 50, "observed: a pid, a socket, a port, a path \u00b7 "
                            "inferred: the program's meaning, a dark figure's intent")
        # counts (top-right)
        xr = "on" if self.machine_xray else "off"
        pr.setPen(QColor(150, 200, 170))
        msg = (f"doors {c.get('doors', 0)} \u00b7 roads {c.get('roads', 0)} \u00b7 "
               f"inhabitants {c.get('inhabitants', 0)} \u00b7 dark figures {c.get('figures', 0)}")
        pr.drawText(w_ - fm.horizontalAdvance(msg) - 14, 22, msg)
        tail = (f"kernel {h.get('kernel', '?')} \u00b7 up {h.get('uptime', '?')} \u00b7 "
                f"x-ray [X] {xr}")
        pr.setPen(QColor(150, 200, 170))
        pr.drawText(w_ - fm.horizontalAdvance(tail[:118]) - 14, 38, tail[:118])

        if not c.get("figures"):
            pr.setPen(QColor(120, 200, 150))
            pr.drawText(14, 68, "no dark figures in this field \u2014 nothing local reads "
                                "as an intruder in the files (the wire is quiet)")

        # ---- the birds: read-only, or armed (finch's hand live) ----
        armed = self.machine_birds_armed
        birds = w.get("birds", [])
        pr.setPen(QColor(255, 150, 120) if armed else QColor(140, 200, 230))
        state = "ARMED \u2014 finch may contain (host-local only)" if armed else \
                "read-only \u00b7 press K to arm"
        held = f" \u00b7 {len(self._machine_contained)} held [L]" if self._machine_contained else ""
        pr.drawText(14, 84, f"BIRDS \u00b7 crow / finch / raven \u2014 {state}{held}")
        bx = 14
        for b in birds:
            k = b.get("kind")
            if k == "crow":
                s = f"crow: {b.get('age', '?')}"
            elif k == "finch":
                s = (f"finch: {b.get('quarantine_files')} held"
                     + (" \u2588" if armed else ""))
            else:
                s = f"raven: up={b.get('up')}"
            pr.setPen(QColor(*[int(v * 255) for v in BIRD_COL.get(k, (0.8, 0.8, 0.9))]))
            pr.drawText(bx, 98, s)
            bx += fm.horizontalAdvance(s) + 22

        # ---- auto-defend (Phase 3): finch detects & contains on its own ----
        auto = self.machine_autoguard
        pr.setPen(QColor(255, 190, 90) if auto else QColor(120, 140, 160))
        a_on = "ON \u2014 finch finds & contains by itself (host-local, observed figures only)"
        pr.drawText(14, 112, f"AUTO-DEFEND [M] \u00b7 {a_on if auto else 'off \u2014 finch waits for E'}")

        # ---- live vision (the knob): what the counters actually say right now ----
        live = self._live_line()
        pr.setPen(QColor(140, 220, 190) if self.live_effective != "off"
                  else QColor(110, 130, 150))
        pr.drawText(14, 126, live)

        # ---- in-world labels over the doors, figures and the core ----
        pr.setFont(mono)
        for (sx, sy, txt, col) in self._machine_labels():
            if not (0 <= sx <= w_ and 0 <= sy <= h_):
                continue
            pr.setPen(QColor(int(col[0] * 255), int(col[1] * 255),
                             int(col[2] * 255), 225))
            pr.drawText(int(sx) + 6, int(sy), txt)

        # ---- prompt at whatever you are standing in ----
        n0 = self._nearest()
        fm = pr.fontMetrics()
        if n0:
            kind = n0["kind"]
            if kind == "machine_door":
                d = n0["door"]
                name = machinevision.SERVICE_NAMES.get(d["lport"], "?")
                prompt = (f"[E] {d['proto']} :{d['lport']} {name} \u2014 "
                          f"{d.get('proc') or 'unknown program'}")
            elif kind == "machine_figure":
                f = n0["fig"]
                ip = str(f.get("src") or "")
                conf = self._machine_contain_confirm
                if self.machine_birds_armed and ip in self._machine_contained:
                    prompt = f"[E] dark figure \u00b7 {f['kind']} \u00b7 {ip} \u2014 HELD (L releases)"
                elif self.machine_birds_armed and conf and conf[0] == ip and now < conf[1]:
                    prompt = f"[E] CONFIRM \u2014 finch contains {ip} (host-local DROP)"
                elif self.machine_birds_armed:
                    ok, why = birdguard.usable(ip)
                    prompt = (f"[E] finch: contain {ip}" if ok else f"finch can't contain {ip} \u2014 {why}")
                else:
                    prompt = f"[E] dark figure \u00b7 {f['kind']} \u00b7 {ip} \u00b7 {f['confidence']}"
            elif kind == "machine_bird":
                b = n0["bird"]
                prompt = f"[E] {b['kind']} \u00b7 {b.get('role', '')} \u2014 read what it found"
            elif kind == "machine_leave":
                prompt = "[E] up the hatch \u2014 back to the wire"
            else:
                prompt = ""
            if prompt:
                pr.setPen(QColor(255, 215, 120))
                tw = fm.horizontalAdvance(prompt)
                pr.drawText((w_ - tw) // 2, h_ - 46, prompt)
        if self._hud_msg and now < self._hud_until:
            pr.setPen(QColor(120, 230, 180))
            tw = fm.horizontalAdvance(self._hud_msg)
            pr.drawText((w_ - tw) // 2, h_ - 30, self._hud_msg)

    def _hud_word(self, pr: QPainter, now):
        w_, h_ = self.width(), self.height()
        mono = QFont("Monospace", 9)
        pr.setFont(mono)
        fm = pr.fontMetrics()
        # ---- header: the room of the Word, and its rule ----
        pr.setPen(QColor(150, 235, 225))
        pr.drawText(14, 22, "SECTION 9  //  WIRE VISION  \u2014  LEARN ISLAM")
        pr.setPen(QColor(105, 165, 175))
        pr.drawText(14, 36, "nothing is depicted here \u2014 not Allah, not the prophets, "
                            "not the companions; only the words, on light")
        pr.drawText(14, 50, "each ayah is a world of abstract forms keyed to the images "
                            "named in the verse, and the words are written on the sky")
        # reader count + ghost layer (top-right)
        n = len(self._peers)
        online = self._online or n > 0
        pr.setPen(QColor(160, 190, 210))
        msg = (f"relay online \u00b7 {n} other reader{'' if n == 1 else 's'} in the room"
               if online else "alone in the room \u00b7 no other reader on the relay")
        pr.drawText(w_ - fm.horizontalAdvance(msg) - 14, 22, msg)
        ghost = self._ghost_line or "ghost layer: open \u00b7 set MRFLUFFY_WIRE_KEY on relay + players"
        pr.setPen(QColor(160, 190, 210) if "hardened" in ghost else QColor(200, 170, 90))
        pr.drawText(w_ - fm.horizontalAdvance(ghost[:116]) - 14, 38, ghost[:116])

        if self.word_mode == "ayah" and self.word_ref:
            surah = self._word_surah_by_number(self.word_ref[0])
            if surah:
                ay = surah["ayahs"][self.word_ref[1]]
                self._hud_word_ayah(pr, now, w_, h_, surah, ay)
        else:
            self._hud_word_select(pr, now, w_, h_)

        # ---- in-world labels over the gates and portals ----
        pr.setFont(mono)
        for (sx, sy, txt, col) in self._word_labels():
            if not (0 <= sx <= w_ and 0 <= sy <= h_):
                continue
            pr.setPen(QColor(int(col[0] * 255), int(col[1] * 255),
                             int(col[2] * 255), 225))
            pr.drawText(int(sx) + 6, int(sy), txt)

        # ---- prompt at whatever you are standing in. No centre reticle here:
        #      the Word room is for reading, and the words must not be boxed in. ----
        n0 = self._nearest()
        pr.setFont(mono)
        fm = pr.fontMetrics()
        if n0:
            kind = n0["kind"]
            if kind == "word_surah":
                prompt = f"[E] open {n0['surah']['number']} {n0['surah']['name']}"
            elif kind == "word_random":
                prompt = "[E] open a random chapter (its first ayah)"
            elif kind == "word_next":
                prompt = ("[E] the chapter ends \u2014 back to the chapters"
                          if self._word_at_end() else "[E] travel to the next ayah")
            elif kind == "word_prev":
                prompt = "[E] back to the previous ayah"
            elif kind == "word_chapters":
                prompt = "[E] back to the chapters"
            elif kind == "word_leave":
                prompt = "[E] leave the room of the Word \u2014 back to the wire"
            else:
                prompt = ""
            if prompt:
                pr.setPen(QColor(255, 215, 120))
                if self.word_mode == "ayah":
                    pr.drawText(14, h_ - 134, prompt)      # out of the reading column
                else:
                    tw = fm.horizontalAdvance(prompt)
                    pr.drawText((w_ - tw) // 2, h_ // 2 + 46, prompt)
        if self._hud_msg and now < self._hud_until:
            pr.setPen(QColor(120, 230, 180))
            tw = fm.horizontalAdvance(self._hud_msg)
            pr.drawText((w_ - tw) // 2, h_ - 40, self._hud_msg)

    def _hud_word_ayah(self, pr, now, w_, h_, surah, ay):
        """The ayah, written on the sky — Arabic, transliteration, a translation."""
        txt = quranworld.sky_text(surah, ay)
        x0, x1 = int(w_ * 0.11), int(w_ - w_ * 0.11)
        # a soft panel so the words stay legible over the world — taller for the
        # whole ayah to fit, whatever its length (some verses are very long)
        bottom_cap = h_ - 132
        band_h = max(170, min(bottom_cap - 60, int(h_ * 0.62)))
        pr.fillRect(x0, 60, x1 - x0, band_h, QColor(4, 10, 16, 190))
        pr.setPen(QColor(70, 120, 132))
        pr.drawRect(x0, 60, x1 - x0, band_h)
        # reference line
        pr.setFont(QFont("Monospace", 11, QFont.Weight.Bold))
        pr.setPen(QColor(140, 225, 215))
        ref = (f"{txt['ref']}   \u00b7   "
               f"{'MECCAN' if surah.get('meccan') else 'MEDINAN'}   \u00b7   "
               f"ayah {ay['n']} of {len(surah['ayahs'])}")
        fm = pr.fontMetrics()
        pr.drawText((w_ - fm.horizontalAdvance(ref)) // 2, 82, ref)
        # the Arabic, centred — the Qur'an itself. Size it down until it fits, so
        # even the Book's longest verse (2:282) is shown whole, never clipped.
        ar_w = x1 - x0 - 40
        ar_top = 92
        tr_space = 40
        en_space = max(60, int(band_h * 0.26))
        ar_max_h = max(40, band_h - (ar_top - 60) - tr_space - en_space)
        size = max(16, int(h_ * 0.075))
        while size > 10:
            m = QFontMetrics(QFont("Sans Serif", size))
            br = m.boundingRect(QRect(0, 0, ar_w, 100000),
                                int(Qt.TextFlag.TextWordWrap), txt["arabic"])
            if br.height() <= ar_max_h:
                break
            size -= 1
        pr.setFont(QFont("Sans Serif", size))
        pr.setPen(QColor(235, 240, 245))
        pr.drawText(QRect(x0 + 20, ar_top, ar_w, ar_max_h),
                    int(Qt.AlignmentFlag.AlignHCenter) | int(Qt.AlignmentFlag.AlignTop)
                    | int(Qt.TextFlag.TextWordWrap), txt["arabic"])
        # transliteration + translation beneath it
        ty = 60 + band_h - en_space - tr_space + 4
        tr_f = QFont("Monospace", max(9, int(h_ * 0.017)))
        tr_f.setItalic(True)
        pr.setFont(tr_f)
        pr.setPen(QColor(160, 185, 195))
        pr.drawText(QRect(x0 + 30, ty, x1 - x0 - 60, tr_space - 6),
                    int(Qt.AlignmentFlag.AlignHCenter) | int(Qt.AlignmentFlag.AlignTop)
                    | int(Qt.TextFlag.TextWordWrap), txt["transliteration"])
        ey = ty + tr_space
        en_f = QFont("Serif", max(11, int(h_ * 0.020)))
        pr.setFont(en_f)
        pr.setPen(QColor(216, 226, 231))
        pr.drawText(QRect(x0 + 30, ey, x1 - x0 - 60, en_space),
                    int(Qt.AlignmentFlag.AlignHCenter) | int(Qt.AlignmentFlag.AlignTop)
                    | int(Qt.TextFlag.TextWordWrap), txt["translation"])
        # the world, described honestly (what image, not what meaning)
        pr.setFont(QFont("Monospace", 9))
        pr.setPen(QColor(150, 190, 185))
        desc = quranworld.describe(self._word_reci)
        pr.drawText(14, h_ - 118, f"this world is {desc} \u2014 a reverent impression, "
                                  f"NOT the meaning (which is with Allah)")
        pr.setPen(QColor(130, 165, 175))
        pr.drawText(14, h_ - 102,
                    "faithful local copy of a published mushaf \u2014 quran-uthmani "
                    "(Hafs) \u00b7 en.sahih (Saheeh International), via alquran.cloud")
        pr.setPen(QColor(120, 190, 180))
        pr.drawText(14, h_ - 86,
                    "a translation opens a door; it is not the Book \u2014 the Arabic is "
                    "the Qur'an. Seek a teacher, and the tafsir, for understanding.")
        pr.setPen(QColor(140, 175, 190))
        pr.drawText(14, h_ - 66,
                    "WASD fly \u00b7 Space/C up/down \u00b7 [ ] travel the ayah "
                    "\u00b7 or the next / prev buttons \u00b7 E at a gate "
                    "\u00b7 R the chapters \u00b7 Home leave the room")

    def _hud_word_select(self, pr, now, w_, h_):
        """The cluster of chapters: the whole Book, hung like stars to fly to."""
        total = sum(len(s["ayahs"]) for s in self._word_suras)
        # title
        pr.setFont(QFont("Monospace", 14, QFont.Weight.Bold))
        fm = pr.fontMetrics()
        title = "THE CHAPTERS, HUNG LIKE STARS"
        pr.setPen(QColor(150, 240, 228))
        pr.drawText((w_ - fm.horizontalAdvance(title)) // 2, h_ // 2 - 24, title)
        pr.setFont(QFont("Monospace", 10))
        fm = pr.fontMetrics()
        sub = (f"the whole Book is here \u2014 {len(self._word_suras)} chapters, "
               f"{total} ayahs")
        pr.setPen(QColor(140, 210, 205))
        pr.drawText((w_ - fm.horizontalAdvance(sub)) // 2, h_ // 2 - 2, sub)
        hint = ("fly to a star and press E to open that chapter \u00b7 or press R for a "
                "random chapter \u00b7 or pick any chapter from the list at right")
        pr.setPen(QColor(150, 190, 200))
        fm = pr.fontMetrics()
        pr.drawText((w_ - fm.horizontalAdvance(hint)) // 2, h_ // 2 + 20, hint)
        # a small codex of the chapters nearest you — the sky is too full to name all
        n = max(1, len(self._word_suras))
        px, py, pz = self.pos
        near = []
        for i, s in enumerate(self._word_suras):
            x, yy, z = self._word_chapter_pos(i, n)
            near.append(((px - x) ** 2 + (py - yy) ** 2 + (pz - z) ** 2, s))
        near.sort(key=lambda c: c[0])
        rows = near[:10]
        px0 = 14
        py0 = 66
        pr.fillRect(px0, py0, 300, 40 + 16 * len(rows), QColor(6, 14, 20, 180))
        pr.setPen(QColor(130, 210, 200))
        pr.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        pr.drawText(px0 + 10, py0 + 18, "NEAREST CHAPTERS TO YOU")
        pr.setFont(QFont("Monospace", 9))
        yy = py0 + 40
        for (_d, s) in rows:
            pr.setPen(QColor(180, 200, 220))
            pr.drawText(px0 + 10, yy, f"{s['number']:>3}  {s['name']} \u2014 "
                                      f"{s['translation']}")
            pr.setPen(QColor(120, 160, 170))
            pr.drawText(px0 + 250, yy, f"{len(s['ayahs'])}v")
            yy += 16
        pr.setPen(QColor(150, 190, 185))
        pr.drawText(px0 + 10, yy + 4, "R  \u2014  a random chapter \u00b7 first ayah")
        # honesty + controls
        pr.setPen(QColor(130, 165, 175))
        pr.drawText(14, h_ - 118,
                    "faithful local copy of a published mushaf \u2014 quran-uthmani "
                    "(Hafs) \u00b7 en.sahih (Saheeh International), via alquran.cloud")
        pr.setPen(QColor(120, 190, 180))
        pr.drawText(14, h_ - 102,
                    "a translation opens a door; it is not the Book \u2014 the Arabic is "
                    "the Qur'an. Seek a teacher, and the tafsir, for understanding.")
        pr.setPen(QColor(140, 175, 190))
        pr.drawText(14, h_ - 66,
                    "WASD fly \u00b7 Space/C up/down \u00b7 fly to a star, E to open "
                    "\u00b7 R a random chapter \u00b7 Home leave the room")

    def _speed_lines(self, pr: QPainter, now, w_, h_):
        """Radial motion lines that streak past the camera the faster you move —
        sprint on the floor, boost in flight. Thresholded on the speed you are
        actually carrying, so they only ever appear when you are really moving.
        Atmosphere only."""
        v = self._speed_now
        v0, v1 = 18.0, 62.0
        if v <= v0 or not self._speedlines:
            return
        inten = min(1.0, (v - v0) / (v1 - v0))
        cx, cy = w_ * 0.5, h_ * 0.5
        rmax = math.hypot(cx, cy)
        rmin = min(w_, h_) * 0.15
        span = rmax - rmin
        n = int(len(self._speedlines) * (0.22 + 0.78 * inten))
        for i in range(n):
            a, rate, ln, ph, lw = self._speedlines[i]
            t = (now * rate * (1.1 + 1.4 * inten) + ph) % 1.0
            r0 = rmin + t * span
            r1 = r0 + ln * span * (0.55 + 0.9 * inten)
            ca, sa = math.cos(a), math.sin(a)
            alpha = int(215 * inten * (1.0 - 0.5 * t))
            if alpha <= 4:
                continue
            pen = QPen(QColor(206, 248, 255, min(255, alpha)))
            pen.setWidthF(lw)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pr.setPen(pen)
            pr.drawLine(int(cx + ca * r0), int(cy + sa * r0),
                        int(cx + ca * r1), int(cy + sa * r1))

    def _hud(self, pr: QPainter, now, key):
        w_, h_ = self.width(), self.height()
        f = QFont("Monospace", 9)
        pr.setFont(f)
        codex = (self.world or {}).get("codex", {})
        cx = codex.get(key, {})
        # ---- GitS diagnostic overlay: drained vignette + scanlines (atmosphere) ----
        grad = QRadialGradient(w_ / 2.0, h_ / 2.0, max(w_, h_) * 0.7)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.55, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, 150))
        pr.fillRect(0, 0, w_, h_, grad)
        pr.setPen(QColor(0, 0, 0, 24))
        for yy in range(0, h_, 3):
            pr.drawLine(0, yy, w_, yy)

        # ---- the streaks of speed: only when you are really moving ----
        self._speed_lines(pr, now, w_, h_)
        if self._speed_now > 1.0:
            tag = f"{self._speed_now:4.0f} u/s"
            if self._boost() > 1.0:
                tag += f"   \u26a1 \u00d7{self.boost_mult:g}"
            pr.setPen(QColor(150, 225, 245, 225))
            pr.drawText(14, h_ - 14, tag)
        if not self._looklocked:
            hint = ("click to look around  \u00b7  move the mouse to turn  \u00b7  "
                    "Esc or right-click frees it")
            pr.setPen(QColor(150, 205, 220, 195))
            tw = QFontMetrics(f).horizontalAdvance(hint)
            pr.drawText(max(14, (w_ - tw) // 2), h_ - 34, hint)

        # ---- the market: blackhorse, reached through the gate on the wire ----
        if self.market:
            self._hud_market(pr, now)
            return

        # ---- the room of the Word: Learn Islam, scripture on light ----
        if self.word:
            self._hud_word(pr, now)
            return

        # ---- the Exchange: the hall of gates out on the net ----
        if self.exchange:
            self._hud_exchange(pr, now)
            return

        # ---- the machine: the box under your feet, read live from /proc ----
        if self.machine:
            self._hud_machine(pr, now)
            return

        # ---- the candle room: DOT/USD's tape, read as a place ----
        if self.candles:
            self._hud_candles(pr, now)
            return

        # ---- the open sea below the edge: unbounded, honest, carrying no data ----
        if self.deep is not None:
            pr.setPen(QColor(120, 245, 200))
            pr.drawText(14, 22, "SECTION 9  //  WIRE VISION  \u2014  THE DIVE")
            pr.setPen(QColor(90, 150, 160))
            pr.drawText(14, 36, "the sea of information  \u00b7  unbounded  \u00b7  carries no data")
            big = "THE SEA OF INFORMATION"
            pr.setFont(QFont("Monospace", 16))
            fm = pr.fontMetrics()
            pr.setPen(QColor(150, 255, 210, 235))
            pr.drawText((w_ - fm.horizontalAdvance(big)) // 2, h_ // 2 - 8, big)
            pr.setFont(f)
            fm = pr.fontMetrics()
            line = (f"depth {int(self.deep['d'])}  \u00b7  no named entity lives below "
                    f"the edge \u2014 every shell is above you now")
            pr.setPen(QColor(150, 205, 195, 225))
            pr.drawText((w_ - fm.horizontalAdvance(line)) // 2, h_ // 2 + 14, line)
            pr.setPen(QColor(255, 235, 150))
            p2 = "[E] rise to the edge \u00b7 [Home] surface"
            pr.drawText((w_ - fm.horizontalAdvance(p2)) // 2, h_ // 2 + 34, p2)
            if self._hud_msg and now < self._hud_until:
                pr.setPen(QColor(120, 230, 180))
                tw = fm.horizontalAdvance(self._hud_msg)
                pr.drawText((w_ - tw) // 2, h_ - 40, self._hud_msg)
            return

        # crosshair / amber acquisition reticle
        n0 = self._nearest()
        amber = QColor(255, 185, 40, 235)
        pr.setPen(QPen(amber if n0 else QColor(120, 230, 180, 190), 2))
        ccx, ccy = w_ // 2, h_ // 2
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            pr.drawLine(ccx + dx * 18, ccy + dy * 18, ccx + dx * 18 + dx * 12, ccy + dy * 18)
            pr.drawLine(ccx + dx * 18, ccy + dy * 18, ccx + dx * 18, ccy + dy * 18 + dy * 12)
        if n0:
            pr.setPen(QColor(255, 185, 40, 220))
            pr.drawText(ccx + 22, ccy - 18, "ACQ")
        # title bar — Section 9 diagnostic header
        pr.setPen(QColor(120, 235, 220))
        pr.drawText(14, 22, "SECTION 9  //  WIRE VISION")
        pr.setPen(QColor(90, 150, 160))
        pr.drawText(14, 36, "ghost-line \u00b7 the wire read as a place")
        pr.setPen(QColor(180, 200, 220))
        place = cx.get("friendly", key)
        real = cx.get("real", "")
        if self.active == 0 and self.world:
            segs = self.world.get("segments", [])
            home = next((s for s in segs if s.get("is_home")), None)
            nruin = len([s for s in segs if not s.get("is_home")])
            if home:
                place = (f"the floor \u00b7 your segment {home['subnet']} "
                         f"(with {nruin} ruin{'' if nruin == 1 else 's'} outside)")
        pr.drawText(14, 54, f"you are in {place.upper()}   [{self.active}/5]")
        if self.show_real and real:
            pr.setPen(QColor(120, 230, 180))
            pr.drawText(14, 70, f"= {real}")
        mem = (self.world or {}).get("memory")
        if mem:
            pr.setPen(QColor(235, 170, 90))
            pr.drawText(14, 88, "\u25f7 " + str(mem.get("note", ""))
                                + f"  (last observed {mem.get('newest', '?')})")
        # ---- ghost-line readout (top-right) ----
        if self.world:
            fm = pr.fontMetrics()
            fp = self.world.get("fingerprint")
            devs0 = self.world.get("devices", [])
            cyb = sum(1 for d in devs0 if d.get("sni_total", 0) > 0)
            cx_list = self.world.get("complexes", [])
            sac = cx_list[0]["domain"] if cx_list else "none"
            ro = [f"GHOST-LINE  {fp}",
                  f"shells {len(devs0)}   cyberbrains {cyb}",
                  f"stand-alone complex: {sac}"]
            pr.setPen(QColor(120, 230, 180, 215))
            for i, s in enumerate(ro):
                pr.drawText(w_ - fm.horizontalAdvance(s) - 14, 22 + i * 16, s)
        if self.world:
            src = self.world["source"]
            devs = self.world["devices"]
            unnamed = sum(1 for d in devs if d.get("identity") == "unknown")
            stale = sum(1 for d in devs if not d.get("fresh"))
            pr.setPen(QColor(150, 165, 185))
            pr.drawText(14, h_ - 74, f"devices {src['devices']} ({unnamed} unnamed · {stale} stale) · "
                                    f"gates {src['gates']} · crows {src['crows']} · rifts {src['rifts']}")
        # controls
        pr.setPen(QColor(140, 150, 170))
        if self.flying:
            pr.drawText(14, h_ - 56, "FLIGHT · WASD glide (W/S follow your gaze) · Space up · C down · drag/arrows look · G land")
        else:
            pr.drawText(14, h_ - 56, "WASD move · drag / arrows look · E interact · G fly · Home surface · B rebuild · T real names")
        if self.show_real:
            pr.setPen(QColor(120, 230, 180)); pr.drawText(14, h_ - 40, "REAL NAMES: on")
        if self.flying:
            pr.setPen(QColor(150, 235, 210))
            pr.drawText(w_ - 190, 88, "FLIGHT: on")
        # labels
        for (sx, sy, txt, col) in self._labels():
            if not (0 <= sx <= w_ and 0 <= sy <= h_):
                continue
            pr.setPen(QColor(int(col[0] * 255), int(col[1] * 255), int(col[2] * 255), 230))
            pr.drawText(int(sx) + 6, int(sy), txt)
        # prompt
        n = self._nearest()
        prompt = ""
        if n:
            if n["kind"] == "gate":
                prompt = f"[E] follow {n['domain']} ×{n['count']} down the stack"
            elif n["kind"] == "market":
                prompt = "[E] enter the market (Blackhorse)"
            elif n["kind"] == "word":
                prompt = "[E] enter the room of the Word \u2014 Learn Islam"
            elif n["kind"] == "heart":
                prompt = "[E] read the heart (your host)"
            elif n["kind"] == "ruin":
                prompt = f"[E] step through the door into the ruin of {n['subnet']} (a memory)"
            elif n["kind"] == "well":
                nx = STRATA_KEY[n["to"]] if n["to"] < len(STRATA_KEY) else ""
                prompt = f"[E] dive into the net \u2192 {codex.get(nx, {}).get('friendly', nx)}"
            elif n["kind"] == "up":
                prompt = f"[E] ride up to {codex.get(STRATA_KEY[n['to']], {}).get('friendly','')}"
            elif n["kind"] == "electron":
                prompt = "[E] touch the last electron"
            elif n["kind"] == "net":
                prompt = "[E] go out to the net \u2014 really dial it"
        if prompt:
            pr.setPen(QColor(255, 235, 150))
            tw = pr.fontMetrics().horizontalAdvance(prompt)
            pr.drawText((w_ - tw) // 2, h_ - 96, prompt)
        # the outward gate's real answer, shown while you stand near it
        if (self.active == 0 and self.world and not self.market and not self.word
                and self.deep is None
                and math.hypot(self.pos[0] - NET_GATE_X, self.pos[2] - NET_GATE_Z) <= NET_PROBE_R):
            fmx = pr.fontMetrics()
            pr.setPen(QColor(150, 255, 210))
            line = self._net_status or "reaching out to the real net\u2026"
            tw = fmx.horizontalAdvance(line)
            pr.drawText((w_ - tw) // 2, h_ - 122, line)
            pr.setPen(QColor(150, 205, 225))
            tw = fmx.horizontalAdvance(self._net_host)
            pr.drawText((w_ - tw) // 2, h_ - 106, self._net_host)
        # transient flash
        if self._hud_msg and now < self._hud_until:
            pr.setPen(QColor(120, 230, 180))
            fm = pr.fontMetrics()
            tw = fm.horizontalAdvance(self._hud_msg)
            pr.drawText((w_ - tw) // 2, 112, self._hud_msg)

    # ---- lifecycle ---------------------------------------------------------
    def shutdown(self):
        self._timer.stop()
        try:
            self._live_timer.stop()
            self._auto_timer.stop()
            self._stop_capture()
        except Exception:
            pass


class WireVisionTab(QWidget):
    """The 'Vision' tab: the playable wire + a live codex side panel."""

    fullscreen_changed = pyqtSignal(bool)      # so the host window can hide its chrome
    close_requested = pyqtSignal()             # the menu's "Close Mr.Fluffy"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.world = None
        self._fs = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        bar = QHBoxLayout()
        self.b_build = QPushButton("Build the wire")
        self.b_build.setToolTip("Read the local ground truth and rebuild the playable world (no network, no brain)")
        self.b_machine = QPushButton("\u29c9 the machine")
        self.b_machine.setToolTip("Step down into THIS host \u2014 its doors, roads and "
                                  "inhabitants read live from /proc and the local logs "
                                  "(also: the hatch on the wire floor, due +z)")
        self.cb_real = QCheckBox("show real names")
        self.cb_real.setToolTip("Reveal the technical term for every place (level the field)")
        self.cb_live = QComboBox()
        for _m, _lab in (("auto", "live: auto"), ("off", "live: off (snapshot)"),
                         ("delta", "live: delta (cheap)"),
                         ("capture", "live: capture (heavy)")):
            self.cb_live.addItem(_lab, _m)
        self.cb_live.setToolTip("How live the machine room is. 'auto' benchmarks THIS "
                                "host once and picks off / delta / capture for it.")
        self.b_full = QPushButton("\u26f6 full screen")
        self.b_full.setToolTip("Give Wire Vision the whole screen (F11) \u2014 hides the "
                               "panels, keeps the world")
        self.where = QLabel("not built yet — click 'Build the wire'")
        bar.addWidget(self.b_build)
        bar.addWidget(self.b_machine)
        bar.addWidget(self.cb_live)
        bar.addWidget(self.cb_real)
        bar.addWidget(self.b_full)
        bar.addWidget(self.where, 1)
        self.bar = bar
        self.bar_widget = QWidget()
        self.bar_widget.setLayout(bar)
        lay.addWidget(self.bar_widget)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.deck = _GLDeck()
        self.deck.setMinimumSize(420, 320)
        self.gl = WireGLWidget()
        self.gl.setMinimumSize(420, 320)
        self.deck.add_gl(self.gl)
        split.addWidget(self.deck)

        right = QFrame(); rv = QVBoxLayout(right)
        self.right = right
        rv.addWidget(QLabel("CODEX — the wire, translated"))
        # A direct way into the Word for a reader who does not want to fly: every
        # chapter of the Qur'an, listed — pick one, open its first ayah.
        self.surah_box = QWidget()
        sb = QVBoxLayout(self.surah_box); sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(4)
        self.surah_head = QLabel("THE WHOLE QUR'AN \u2014 all 114 chapters")
        self.surah_head.setStyleSheet("color:#8be0ff;font-weight:bold;")
        sb.addWidget(self.surah_head)
        self.surah_list = QListWidget()
        self.surah_list.setStyleSheet(
            "QListWidget{background:#0a1216;border:1px solid #2a4a55;color:#cfe3dd;}"
            "QListWidget::item:selected{background:#12303a;color:#8be0ff;}")
        for _s in quran.all_suras():
            _it = QListWidgetItem(f"{_s['number']:>3}   {_s['name']} \u2014 "
                                  f"{_s['translation']}  ({len(_s['ayahs'])}v)")
            _it.setData(Qt.ItemDataRole.UserRole, _s["number"])
            self.surah_list.addItem(_it)
        self.b_open_surah = QPushButton("Open the first ayah of the selected chapter")
        sb.addWidget(self.surah_list, 1)
        sb.addWidget(self.b_open_surah)
        self.surah_box.setVisible(False)
        rv.addWidget(self.surah_box)
        self.codex = QTextBrowser(); self.codex.setOpenExternalLinks(False)
        rv.addWidget(self.codex, 1)
        self.market_panel = QFrame(); self.market_panel.setVisible(False)
        self.market_panel.setStyleSheet(
            "QFrame#marketPanel{border:1px solid #2a4a55;border-radius:8px;"
            "background:rgba(10,18,22,236);}"
            "QLabel{color:#cfe3dd;background:transparent;}"
            "QPushButton{background:#12303a;border:1px solid #2a4a55;border-radius:4px;padding:3px;}"
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}")
        self.market_panel.setObjectName("marketPanel")
        mpl = QVBoxLayout(self.market_panel)
        mpl.setContentsMargins(10, 8, 10, 8)
        mpl.setSpacing(5)
        header = QHBoxLayout()
        self.market_title = QLabel("BLACKHORSE \u2014 the market")
        self.market_title.setStyleSheet("color:#8be0ff;font-weight:bold;")
        b_x = QPushButton("\u2715")
        b_x.setFixedWidth(28)
        b_x.setToolTip("Close the market panel (also: H)")
        b_x.setStyleSheet("background:transparent;color:#8be0ff;border:1px solid #2a4a55;"
                          "border-radius:4px;font-weight:bold;")
        b_x.clicked.connect(lambda: self._set_menu(False))
        header.addWidget(self.market_title)
        header.addStretch(1)
        header.addWidget(b_x)
        mpl.addLayout(header)
        self.market_balance = QLabel("balance: \u2014")
        self.market_balance.setWordWrap(True)
        self.market_status = QLabel("")
        self.market_status.setWordWrap(True)
        self.market_ghost = QLabel("")
        self.market_ghost.setWordWrap(True)
        self.market_form = QWidget()
        self._mform = QVBoxLayout(self.market_form)
        self._mform.setContentsMargins(0, 0, 0, 0)
        self.market_scroll = QScrollArea()
        self.market_scroll.setWidgetResizable(True)
        self.market_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.market_scroll.setWidget(self.market_form)
        self.form_buttons = QHBoxLayout()
        self.b_new_agent = QPushButton("New agent\u2026")
        self.b_close_menu = QPushButton("Hide menu")
        self.form_buttons.addWidget(self.b_new_agent)
        self.form_buttons.addWidget(self.b_close_menu)
        mpl.addWidget(self.market_balance)
        mpl.addWidget(self.market_status)
        mpl.addWidget(self.market_ghost)
        mpl.addWidget(self.market_scroll, 1)
        mpl.addLayout(self.form_buttons)
        self._menu_visible = False
        self.deck.add_panel(self.market_panel)
        self.deck.place_panel()

        # ---- overlays that float over the world ----
        # an always-available way out of full screen (the panel bars are hidden there)
        self.fs_exit = QPushButton("\u2715 exit full screen")
        self.fs_exit.setToolTip("Leave full screen and bring the panels back (Esc or F11)")
        self.fs_exit.setStyleSheet(
            "QPushButton{background:rgba(20,34,40,225);color:#8be0ff;"
            "border:1px solid #2a4a55;border-radius:4px;padding:6px 12px;}"
            "QPushButton:hover{background:rgba(32,56,66,240);}")
        self.fs_exit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fs_exit.setVisible(False)
        self.fs_exit.clicked.connect(lambda: self.toggle_fullscreen(False))
        self.deck.add_overlay(self.fs_exit, "top-center")

        # the game menu — one popup with Settings, Controls, Resume and a way out
        self.menu_btn = QPushButton("\u2630 menu")
        self.menu_btn.setToolTip("The game menu \u2014 settings, controls, and a way out (Tab)")
        self.menu_btn.setStyleSheet(
            "QPushButton{background:rgba(20,34,40,225);color:#8be0ff;"
            "border:1px solid #2a4a55;border-radius:4px;padding:6px 12px;}"
            "QPushButton:hover{background:rgba(32,56,66,240);}")
        self.menu_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu_btn.clicked.connect(self._open_game_menu)
        self.deck.add_overlay(self.menu_btn, "top-left")

        self.game_menu = _GameMenu()
        self.game_menu.setObjectName("gameMenu")
        self.game_menu.setFixedWidth(470)
        self.game_menu.setStyleSheet(
            "QFrame#gameMenu{border:1px solid #2a4a55;border-radius:10px;"
            "background:rgba(8,16,20,245);}"
            "QFrame#gameMenu QLabel{color:#cfe3dd;background:transparent;}"
            "QFrame#gameMenu QPushButton{background:#12303a;border:1px solid #2a4a55;"
            "border-radius:4px;padding:6px 10px;color:#cfe3dd;}"
            "QFrame#gameMenu QPushButton:hover{background:#1b4652;}"
            "QFrame#gameMenu QDoubleSpinBox,QFrame#gameMenu QComboBox{"
            "background:#0a1216;color:#cfe3dd;border:1px solid #2a4a55;"
            "border-radius:4px;padding:2px;}")
        self.game_menu.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.game_menu.setVisible(False)
        self._gm_body = QVBoxLayout(self.game_menu)
        self._gm_body.setContentsMargins(14, 12, 14, 12)
        self._gm_body.setSpacing(8)
        self.game_menu.escape.connect(self._close_game_menu)
        self.deck.add_overlay(self.game_menu, "center")

        # quick travel + actions for a reader who does not want to fly to a gate
        self.word_bar = QWidget()
        wbl = QHBoxLayout(self.word_bar)
        wbl.setContentsMargins(0, 0, 0, 0); wbl.setSpacing(6)
        _wbs = ("QPushButton{background:rgba(20,34,40,225);color:#cfe3dd;"
                "border:1px solid #2a4a55;border-radius:4px;padding:6px 10px;}"
                "QPushButton:hover{background:rgba(32,56,66,240);}"
                "QPushButton:disabled{color:#4a6470;}")
        self.bw_prev = QPushButton("\u25c0 prev ayah")
        self.bw_next = QPushButton("next ayah \u25b6")
        self.bw_chapters = QPushButton("\u2637 chapters")
        self.bw_rand = QPushButton("\u2726 random chapter")
        self.bw_leave = QPushButton("\u2190 leave the room")
        for _b in (self.bw_prev, self.bw_next, self.bw_chapters,
                   self.bw_rand, self.bw_leave):
            _b.setStyleSheet(_wbs)
            _b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            wbl.addWidget(_b)
        self.word_bar.setVisible(False)
        self.deck.add_overlay(self.word_bar, "bottom-center")

        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        lay.addWidget(split, 1)

        self.b_build.clicked.connect(self.build)
        self.cb_real.stateChanged.connect(self._toggle_real)
        self.b_full.clicked.connect(lambda: self.toggle_fullscreen())
        self.gl.stratum_changed.connect(self._on_stratum)
        self.gl.request_rebuild.connect(self.build)
        self.gl.market_opened.connect(self._on_market)
        self.gl.market_closed.connect(self._on_market_closed)
        self.gl.agent_selected.connect(self._open_editor)
        self.gl.menu_toggle.connect(self._toggle_menu)
        self.gl.fullscreen_request.connect(self.toggle_fullscreen)
        self.gl.escape_request.connect(self._escape_fullscreen)
        self.gl.menu_request.connect(self._toggle_game_menu)
        self.gl.word_changed.connect(self._refresh_word_ui)
        self.gl.web_changed.connect(self._refresh_word_ui)
        self.gl.machine_changed.connect(self._refresh_machine_ui)
        self.gl.live_changed.connect(self._refresh_live_ui)
        self.cb_live.currentIndexChanged.connect(self._on_live_change)
        self._refresh_live_ui(self.gl.live_mode, self.gl.live_effective)
        self.b_machine.clicked.connect(self._machine_btn)
        self.bw_prev.clicked.connect(lambda: self._word_btn(self.gl.word_prev))
        self.bw_next.clicked.connect(lambda: self._word_btn(self.gl.word_next))
        self.bw_chapters.clicked.connect(lambda: self._word_btn(self.gl.word_back_to_chapters))
        self.bw_rand.clicked.connect(lambda: self._word_btn(self.gl.word_lucky))
        self.bw_leave.clicked.connect(lambda: self._word_btn(self.gl.word_leave_room))
        self.b_open_surah.clicked.connect(lambda: self._open_selected_surah())
        self.surah_list.itemDoubleClicked.connect(lambda _it: self._open_selected_surah())
        self.surah_list.itemActivated.connect(lambda _it: self._open_selected_surah())
        self.b_new_agent.clicked.connect(self._show_create)
        self.b_close_menu.clicked.connect(lambda: self._set_menu(False))
        self._fs_sc = QShortcut(QKeySequence("F11"), self)
        self._fs_sc.setContext(Qt.ShortcutContext.WindowShortcut)
        self._fs_sc.activated.connect(self.toggle_fullscreen)
        self._render_codex()
        # first build on the next event-loop turn so the widget is realized
        QTimer.singleShot(300, self.build)

    def toggle_fullscreen(self, want=None):
        """Give the world the whole screen: hide this tab's bar + codex, ask the
        host window to hide its own chrome, and go full screen. Reversible — the
        exit button floats over the world while it is on."""
        self._fs = (not self._fs) if want is None else bool(want)
        self.bar_widget.setVisible(not self._fs)
        self.right.setVisible(not self._fs)
        self.b_full.setText("\u2715 exit full screen" if self._fs
                            else "\u26f6 full screen")
        self.fs_exit.setVisible(self._fs)
        win = self.window()
        if win is not None:
            if self._fs:
                win.showFullScreen()
            else:
                win.showNormal()
        self.fullscreen_changed.emit(self._fs)
        self._reflow_overlays()
        self.gl.setFocus()

    def _escape_fullscreen(self):
        """Esc always gets you out of full screen — never stuck."""
        if self._fs:
            self.toggle_fullscreen(False)

    # ---- the game menu: Settings / Controls / Resume / Close ----------------
    def _open_game_menu(self):
        if self.game_menu.isVisible():
            self._close_game_menu()
            return
        self._gm_home()
        self.game_menu.setVisible(True)
        try:
            self.gl.keys.clear()      # stop any held movement while the menu is up
            self.gl.set_look_lock(False)    # free the mouse so the widgets are usable
        except Exception:
            pass
        self._reflow_overlays()
        self.game_menu.setFocus()

    def _close_game_menu(self):
        if not self.game_menu.isVisible():
            return
        self.game_menu.setVisible(False)
        self._reflow_overlays()
        self.gl.setFocus()
        try:
            self.gl.set_look_lock(True)     # back to smooth look as you resume
        except Exception:
            pass

    def _toggle_game_menu(self):
        if self.game_menu.isVisible():
            self._close_game_menu()
        else:
            self._open_game_menu()

    def _reflow_overlays(self):
        """An overlay floats over a QOpenGLWidget. After showing, hiding, or
        resizing one, nudge the whole stack so it composes at once \u2014 otherwise the
        new content only appears the next time the window is resized."""
        lay = self.game_menu.layout()
        if lay is not None:
            lay.activate()          # settle the frame's height before we place it
        self.deck.place_overlays()
        self.game_menu.update()
        self.menu_btn.update()
        self.deck.update()
        self.gl.update()
        win = self.window()
        if win is not None:
            win.update()
        # child size hints are only final once they are polished, which happens on
        # the next event-loop turn — re-place then so a freshly-switched menu page
        # is sized right at once (no resize nudge needed).
        QTimer.singleShot(0, self.deck.place_overlays)

    def _gm_clear(self):
        self._gm_clear_layout(self._gm_body)

    def _gm_clear_layout(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
            else:
                sub = it.layout()
                if sub is not None:
                    self._gm_clear_layout(sub)

    def _gm_row(self, label, widget):
        row = QHBoxLayout()
        lab = QLabel(label)
        lab.setMinimumWidth(150)
        row.addWidget(lab)
        row.addWidget(widget, 1)
        self._gm_body.addLayout(row)

    def _gm_title(self, text, sub=""):
        t = QLabel(text)
        t.setStyleSheet("color:#8be0ff;font-weight:bold;")
        self._gm_body.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setWordWrap(True)
            s.setStyleSheet("color:#9aa;")
            self._gm_body.addWidget(s)

    def _gm_home(self):
        self._gm_clear()
        self._gm_title("MR.FLUFFY \u2014 the wire",
                       "You are in the wire. Fly it, read it, live it.")
        for label, slot in (("Resume \u2014 back to the wire", self._close_game_menu),
                            ("\u2699  Settings", self._gm_settings),
                            ("\u2328  Controls \u2014 every key", self._gm_controls),
                            ("\u26f6  Toggle full screen", self.toggle_fullscreen)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, s=slot: s())
            self._gm_body.addWidget(b)
        close = QPushButton("\u2716  Close Mr.Fluffy")
        close.setStyleSheet(
            "QFrame#gameMenu QPushButton{background:#3a1622;border:1px solid #6a2a3a;"
            "border-radius:4px;padding:6px 10px;color:#ffb4c4;}"
            "QFrame#gameMenu QPushButton:hover{background:#4a1c2c;}")
        close.clicked.connect(self.close_requested.emit)
        self._gm_body.addWidget(close)
        self._reflow_overlays()

    def _gm_settings(self):
        self._gm_clear()
        self._gm_title("\u2699  SETTINGS", "Your own preferences \u2014 they change "
                       "nothing about the ground truth the wire is built from.")
        wk = QDoubleSpinBox()
        wk.setRange(0.5, 3.0); wk.setSingleStep(0.1); wk.setDecimals(1)
        wk.setSuffix("  \u00d7")
        wk.setValue(float(self.gl.walk_mult))
        wk.valueChanged.connect(self._gm_set_walk)
        self._gm_row("Walk speed", wk)

        sp = QDoubleSpinBox()
        sp.setRange(0.5, 4.0); sp.setSingleStep(0.1); sp.setDecimals(1)
        sp.setSuffix("  \u00d7")
        sp.setValue(float(self.gl.move_mult))
        sp.setToolTip("How fast you fly. Esc or Tab closes this menu.")
        sp.valueChanged.connect(self._gm_set_speed)
        self._gm_row("Fly speed", sp)

        bt = QDoubleSpinBox()
        bt.setRange(1.0, 6.0); bt.setSingleStep(0.1); bt.setDecimals(1)
        bt.setSuffix("  \u00d7")
        bt.setValue(float(self.gl.boost_mult))
        bt.setToolTip("Hold Shift to sprint on foot and boost in flight.")
        bt.valueChanged.connect(self._gm_set_boost)
        self._gm_row("Boost (hold Shift)", bt)

        ls = QDoubleSpinBox()
        ls.setRange(0.2, 3.0); ls.setSingleStep(0.1); ls.setDecimals(1)
        ls.setSuffix("  \u00d7")
        ls.setValue(float(self.gl.look_sens))
        ls.valueChanged.connect(self._gm_set_look)
        self._gm_row("Look sensitivity", ls)

        cb = QComboBox()
        for _m, _lab in (("auto", "auto (benchmark this host)"),
                         ("off", "off (snapshot \u00b7 rebuild with B)"),
                         ("delta", "delta \u00b7 1 Hz kernel deltas (cheap)"),
                         ("capture", "capture \u00b7 real packets (heavy)")):
            cb.addItem(_lab, _m)
        i = cb.findData(self.gl.live_mode)
        if i >= 0:
            cb.setCurrentIndex(i)
        cb.currentIndexChanged.connect(lambda _i: self._gm_set_live(cb.currentData()))
        self._gm_row("Live vision", cb)

        rn = QCheckBox("Show real names (the technical term for every place)")
        rn.setChecked(bool(self.gl.show_real))
        rn.toggled.connect(self._gm_set_real)
        self._gm_body.addWidget(rn)
        self._gm_back()

    def _gm_controls(self):
        self._gm_clear()
        self._gm_title("\u2328  CONTROLS \u2014 every key")
        rows = [
            ("Move", "\u2191 \u2193 \u2190 \u2192  or  W A S D"),
            ("Sprint / boost", "hold Shift \u2014 speed lines fly when you move fast"),
            ("Up / down (in flight)", "Space  up  \u00b7  C  down"),
            ("Look", "move the mouse \u00b7 click to capture \u00b7 Esc or right-click frees it"),
            ("Fly on / off", "G"),
            ("Interact \u00b7 enter a gate / room", "E"),
            ("Rebuild from the files", "B"),
            ("Back to the surface \u00b7 leave a room", "Home"),
            ("Real names on / off", "T"),
            ("This menu", "Tab"),
            ("Full screen on / off", "F11"),
            ("Leave full screen", "Esc"),
            ("BlackHorse market", "H  (menu)  \u00b7  E on a platform"),
            ("Candle room (at the column)", "E  then  1-4  \u00b7  Esc cancels"),
            ("The Word (Qur'an)", "[  prev ayah  \u00b7  ]  next  \u00b7  R  random"),
            ("The machine (this host)", "X x-ray  \u00b7  K arm  \u00b7  L release  \u00b7  M auto"),
        ]
        html = ["<table cellspacing='0' cellpadding='3' width='100%'>"]
        for k, v in rows:
            html.append(
                f"<tr><td style='color:#8be0ff' nowrap>{k}</td>"
                f"<td style='color:#cfe3dd'>{v}</td></tr>")
        html.append("</table>")
        lab = QLabel("".join(html))
        lab.setTextFormat(Qt.TextFormat.RichText)
        lab.setWordWrap(True)
        self._gm_body.addWidget(lab)
        self._gm_back()

    def _gm_back(self):
        b = QPushButton("\u25c0  back")
        b.clicked.connect(self._gm_home)
        self._gm_body.addWidget(b)
        self._reflow_overlays()

    def _gm_save(self):
        try:
            st = wiresettings.load()
            st["fly_speed"] = float(self.gl.move_mult)
            st["walk_speed"] = float(self.gl.walk_mult)
            st["boost_mult"] = float(self.gl.boost_mult)
            st["look_sensitivity"] = float(self.gl.look_sens)
            wiresettings.save(st)
        except Exception:
            pass

    def _gm_set_speed(self, v):
        self.gl.move_mult = _clampf(v, 0.5, 4.0, 1.9)
        self._gm_save()

    def _gm_set_walk(self, v):
        self.gl.walk_mult = _clampf(v, 0.5, 3.0, 1.0)
        self._gm_save()

    def _gm_set_boost(self, v):
        self.gl.boost_mult = _clampf(v, 1.0, 6.0, 2.2)
        self._gm_save()

    def _gm_set_look(self, v):
        self.gl.look_sens = _clampf(v, 0.2, 3.0, 1.0)
        self._gm_save()

    def _gm_set_real(self, on):
        self.gl.show_real = bool(on)
        self.cb_real.setChecked(bool(on))
        self.gl.update()

    def _gm_set_live(self, mode):
        if mode is None:
            return
        info = self.gl.set_live_mode(mode)
        self._refresh_live_ui(self.gl.live_mode, self.gl.live_effective, info)
        self._reflow_overlays()

    def _word_btn(self, action):
        action()
        self.gl.setFocus()
        self._refresh_word_ui()

    def _open_selected_surah(self):
        it = self.surah_list.currentItem()
        if it is None:
            return
        self.gl.word_open_surah(int(it.data(Qt.ItemDataRole.UserRole)))
        self.gl.setFocus()

    def _refresh_word_ui(self):
        """Show the in-world quick buttons + the chapter list only in the Word."""
        on = bool(self.gl.word)
        self.word_bar.setVisible(on)
        self.surah_box.setVisible(on)
        if on:
            select = self.gl.word_mode == "select"
            self.bw_rand.setVisible(select)
            self.bw_leave.setVisible(True)
            self.bw_chapters.setVisible(not select)
            self.bw_prev.setVisible(not select)
            self.bw_next.setVisible(not select)
            self.bw_prev.setEnabled(self.gl._word_has_prev())
            self.bw_next.setText("finish \u2794 chapters" if self.gl._word_at_end()
                                 else "next ayah \u25b6")
        self._reflow_overlays()

    def _machine_btn(self):
        if self.gl.machine:
            self.gl._leave_machine()
        else:
            self.gl._enter_machine()
        self.gl.setFocus()

    def _refresh_machine_ui(self):
        """The tab button mirrors the room; no floating bar (the room is flown)."""
        on = bool(self.gl.machine)
        self.b_machine.setText("\u21a9 leave the machine" if on else "\u29c9 the machine")
        self._reflow_overlays()

    def _on_live_change(self, _idx=None):
        mode = self.cb_live.currentData() or "auto"
        info = self.gl.set_live_mode(mode)
        self._refresh_live_ui(self.gl.live_mode, self.gl.live_effective, info)

    def _refresh_live_ui(self, mode, effective, info=None):
        if info is None:
            info = self.gl._live_info
        i = self.cb_live.findData(mode)
        if i >= 0 and self.cb_live.currentIndex() != i:
            self.cb_live.blockSignals(True)
            self.cb_live.setCurrentIndex(i)
            self.cb_live.blockSignals(False)
        self.cb_live.setToolTip("Live vision: " + wiresettings.describe(mode, effective, info)
                                + "\n'auto' benchmarks THIS host once (cores, load, a tiny "
                                  "timed loop) — no network, no tool.")
        self._reflow_overlays()

    def build(self):
        try:
            self.world = wirevision.build()
        except Exception as e:
            self.where.setText(f"build failed: {e}")
            return
        self.gl.show_real = self.cb_real.isChecked()
        self.gl.set_world(self.world)
        self.where.setText(f"built · fp {self.world.get('fingerprint')} · "
                           f"{self.world['source']['devices']} devices")
        self._render_codex(self.world)

    def _toggle_real(self, _state):
        self.gl.show_real = self.cb_real.isChecked()
        self.gl.update()

    def _on_stratum(self, idx, focus):
        key = STRATA_KEY[idx]
        cx = (self.world or {}).get("codex", {}).get(key, {})
        extra = f" · following {focus}" if focus else ""
        self.where.setText(f"you are in {cx.get('friendly', key).upper()}{extra}")

    def _render_codex(self, world=None):
        world = world or self.world or {"codex": wirevision.CODEX}
        codex = world.get("codex", {})
        order = codex.get("_order", ["floor", "app", "transport", "internet", "link", "physical"])
        rows = ["<b>WHAT WE ACTUALLY KNOW</b> (fact vs. guess)<br>"]
        truth = world.get("truth")
        if truth:
            rows.append("<span style='color:#7fd7a0'>observed (fact)</span><br>")
            for o in truth["observed"]:
                rows.append(f"&nbsp;• {o}<br>")
            rows.append("<span style='color:#e0b060'>inferred (a story)</span><br>")
            for o in truth["inferred"]:
                rows.append(f"&nbsp;• {o}<br>")
            rows.append("<br>")
            for nt in truth["notes"]:
                rows.append(f"<span style='color:#9aa'>{nt}</span><br>")
            rows.append("<br>")
        mem = world.get("memory")
        if mem:
            rows.append(f"<span style='color:#e0a070'>\u25f7 {mem.get('note','')} "
                        f"(last observed {mem.get('newest','?')})</span><br>")
            rows.append(f"<span style='color:#9aa'>{mem.get('counts_note','')}</span><br><br>")
        segs = world.get("segments")
        if segs:
            rows.append("<b>the floor is ROOMS</b><br>")
            for s in segs:
                if s.get("is_home"):
                    rows.append(f"&nbsp;• <span style='color:#7fd7ff'>your segment {s['subnet']}</span> "
                                f"\u2014 the lit room ({s['count']} device(s))<br>")
                else:
                    rows.append(f"&nbsp;• <span style='color:#e0a070'>ruin \u00b7 old segment {s['subnet']}</span> "
                                f"\u2014 {s['count']} device(s), last seen {s.get('newest')} "
                                f"(walk through the door)<br>")
            rows.append("<br>")
        srcs = world.get("sources")
        if srcs:
            rows.append("<b>SOURCES \u2014 what feeds this world (how to 'look again')</b><br>")
            for s in srcs:
                col = "#e07070" if s.get("stale") else "#7fd7a0"
                mark = "STALE" if s.get("stale") else "fresh"
                rows.append(f"&nbsp;• <span style='color:{col}'>[{mark}] {s.get('name')}</span> "
                            f"\u2014 last written {s.get('age')}<br>"
                            f"&nbsp;&nbsp;&nbsp;<span style='color:#9aa'>\u2192 {s.get('hint')}</span><br>")
            rows.append("<br>")
        cxs = world.get("complexes")
        if cxs:
            rows.append("<b>stand-alone complexes</b> "
                        "(a name two or more shells both reach \u2014 no single origin)<br>")
            for c in cxs:
                rows.append(f"&nbsp;• <span style='color:#7fd7a0'>{c['domain']}</span> "
                            f"\u2190 {', '.join(c['devices'])}<br>")
            rows.append("<br>")
        if world.get("heart"):
            h = world["heart"]
            rtt = "?" if h.get("rtt") is None else f"{round(float(h['rtt']),1)}ms"
            rows.insert(0, f"<b>the heart</b> · up={h.get('up')} {h.get('iface')} gw={h.get('gw')} "
                           f"rtt={rtt} guard={h.get('mode')}<br>"
                           f"<span style='color:#9aa'>{h.get('what','')}</span><br><br>")
        if world.get("crow_report"):
            cr = world["crow_report"]
            rows.insert(0, f"<b>newest crow</b> · {cr.get('name')} {cr.get('role')} on {cr.get('target')}<br>"
                           f"<span style='color:#e0a'>⚠ {cr.get('verdict')}</span><br><br>")
        rows.append("<b>Every place, friendly name = real term</b><br><br>")
        for k in order:
            c = codex.get(k, {})
            rows.append(f"<b>{c.get('friendly','')}</b> = <i>{c.get('real','')}</i><br>"
                        f"<span style='color:#9aa'>{c.get('blurb','')}</span><br><br>")
        self.codex.setHtml("".join(rows))

    def _on_market(self, w):
        self._set_menu(True)
        acc = (w or {}).get("account", {}) or {}
        cash = acc.get("cash")
        alloc = acc.get("allocated")
        cur = acc.get("currency", "")
        bal = f"cash {cash:g} {cur} \u00b7 allocated {alloc:g} \u00b7 equity~{acc.get('equity_est')}"
        self.market_balance.setText("BLACKHORSE live balance:\n" + bal)
        self.market_ghost.setText(self.gl._ghost_line)
        agent = None
        if self.gl.selected_agent and w:
            agent = next((a for a in w.get("agents", [])
                          if a["id"] == self.gl.selected_agent), None)
        if agent is not None:
            self._open_editor(agent)
        else:
            self._menu_root(w)

    def _on_market_closed(self):
        self.market_panel.setVisible(False)
        self._menu_visible = False
        self._clear_form()
        self.market_balance.setText("balance: \u2014")

    def _toggle_menu(self, _flag):
        if not self.gl.market:
            return
        self._set_menu(not self._menu_visible)

    def _set_menu(self, on):
        self._menu_visible = on
        self.market_panel.setVisible(on and self.gl.market)

    def _clear_form(self):
        lay = self._mform
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _menu_root(self, w=None):
        self._clear_form()
        w = w or self.gl.market_world or {}
        acc = w.get("account", {}) or {}
        rows = [f"account \u00b7 {acc.get('mode', '?')} \u2014 "
                f"{'LIVE' if acc.get('live') else 'paper'} (autonomous {acc.get('autonomous')})"]
        rows.append(f"cash {acc.get('cash')} {acc.get('currency')} \u00b7 "
                    f"allocated {acc.get('allocated')} \u00b7 "
                    f"open positions {acc.get('open_positions')}")
        rp = acc.get('realized_pnl')
        if rp is not None:
            rows.append(f"realized pnl {rp:g} \u00b7 closed {acc.get('closed')} "
                        f"(w {acc.get('wins')} / l {acc.get('losses')})")
        agents = w.get("agents", [])
        rows.append("platforms (your trading agents):")
        for a in agents:
            st = MARKET_STATE_TXT.get(a["state"], a["state"])
            net = f" \u00b7 net {a['net_pct']}%" if a.get("net_pct") is not None else ""
            rows.append(f"  \u2022 {a['name']} [{st}]{net}")
        if not agents:
            rows.append("  (none yet \u2014 create one below)")
        lbl = QLabel("<br>".join(rows))
        lbl.setWordWrap(True)
        self._mform.addWidget(lbl)

    def _agent_doc(self, aid):
        try:
            doc = wiregate._load_json(wiregate.AGENTS_JSON, {"agents": {}})
            return doc.get("agents", {}).get(aid), doc
        except Exception:
            return None, {}

    def _open_editor(self, a):
        self._set_menu(True)
        self._clear_form()
        aid = a["id"]
        cur_agent, doc = self._agent_doc(aid)
        profs = dict(wiregate.PROFILES or {})
        prof_name = (cur_agent or {}).get("profile") or a.get("profile") or "slow"
        prof = profs.get(prof_name) or {}
        ov = dict(((cur_agent or {}).get("policy_overrides") or {}))
        self._ctx = {"aid": aid, "ov": ov, "cur": cur_agent or {}}
        t = QLabel(f"EDIT \u2014 {a['name']} <span style='color:#8be0ff'>({aid})</span> "
                   f"<span style='color:#9aa'>\u00b7 {a.get('mode', '?')}</span>")
        t.setWordWrap(True)
        self._mform.addWidget(t)
        self._ed_enabled = QCheckBox("enabled (will trade with live capital)")
        self._ed_enabled.setChecked(bool((cur_agent or {}).get("enabled", a.get("enabled"))))
        self._mform.addWidget(self._ed_enabled)
        row = QHBoxLayout()
        row.addWidget(QLabel("capital"))
        self._ed_capital = QDoubleSpinBox()
        self._ed_capital.setRange(0, 100000); self._ed_capital.setDecimals(1)
        self._ed_capital.setValue(float((cur_agent or {}).get("capital", a.get("capital") or 0)))
        row.addWidget(self._ed_capital, 1)
        self._mform.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("profile"))
        self._ed_profile = QComboBox()
        for k, v in profs.items():
            self._ed_profile.addItem(v.get("label") or k, k)
        idx = self._ed_profile.findData(prof_name)
        if idx >= 0:
            self._ed_profile.setCurrentIndex(idx)
        row.addWidget(self._ed_profile, 1)
        self._mform.addLayout(row)
        d = QLabel(prof.get("description") or "")
        d.setWordWrap(True); d.setStyleSheet("color:#9aa;")
        self._mform.addWidget(d)
        row = QHBoxLayout()
        row.addWidget(QLabel("pairs"))
        self._ed_pairs = QListWidget(); self._ed_pairs.setMaximumHeight(72)
        have = set((cur_agent or {}).get("pairs", a.get("pairs") or []))
        for p in wiregate.PAIRS:
            item = QListWidgetItem(p)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if p in have
                               else Qt.CheckState.Unchecked)
            self._ed_pairs.addItem(item)
        row.addWidget(self._ed_pairs, 1)
        self._mform.addLayout(row)
        over_row = QLabel("<b>policy overrides</b> (blank values = use the profile)")
        over_row.setStyleSheet("color:#cbb;")
        self._mform.addWidget(over_row)
        self._ed_ov = {}
        # the effective profile policy: blackhorse's decider defaults with the
        # profile's own cfg on top (agents.policy_for's base, minus the agent's
        # overrides). So a blank field shows the value blackhorse shows, not "?".
        base = dict(wiregate.PROFILE_DEFAULTS or {})
        base.update(prof.get("cfg") or prof.get("policy") or {})
        self._ed_base = base
        for k, (kind, lo, hi) in (wiregate.EDITABLE or {}).items():
            if k == "channels":
                continue
            if kind == "num":
                row = QHBoxLayout()
                row.addWidget(QLabel(k))
                sb = QDoubleSpinBox()
                sb.setRange(lo, hi)
                sb.setDecimals(2 if hi <= 10 else 1)
                v = ov.get(k) if k in ov else None
                val = float(v) if v is not None else float(base.get(k, lo))
                sb.setValue(val)
                if k not in ov:
                    sb.setSpecialValueText(f"profile ({base.get(k, '?')})")
                    sb.setMinimum(min(lo, float(base.get(k, lo)) if base.get(k) is not None else lo))
                row.addWidget(sb, 1)
                self._mform.addLayout(row)
                self._ed_ov[k] = sb
            else:
                cb = QCheckBox(k)
                v = ov.get(k) if k in ov else None
                cb.setChecked(bool(v) if v is not None else bool(base.get(k)))
                self._ed_ov[k] = cb
                self._mform.addWidget(cb)
        save = QPushButton("Save settings")
        save.clicked.connect(self._do_save)
        back = QPushButton("Back to market")
        back.clicked.connect(lambda: self._menu_root(self.gl.market_world))
        hb = QHBoxLayout()
        hb.addWidget(save); hb.addWidget(back)
        self._mform.addLayout(hb)

    def _do_save(self):
        ctx = getattr(self, "_ctx", {})
        aid = ctx.get("aid")
        if not aid or not hasattr(self, "_ed_ov"):
            return
        overrides = {}
        base = getattr(self, "_ed_base", {}) or {}
        had = ctx.get("ov") or {}
        for k, w in self._ed_ov.items():
            if isinstance(w, QDoubleSpinBox):
                val = w.value()
                if k not in had and k in base:
                    try:
                        if abs(val - float(base[k])) < 1e-9:
                            continue          # still the profile's own value
                    except (TypeError, ValueError):
                        pass
                if w.specialValueText() and val <= w.minimum():
                    overrides[k] = None
                else:
                    overrides[k] = val
            else:
                on = w.isChecked()
                if k not in had and k in base and bool(base[k]) == on:
                    continue                  # still the profile's own value
                overrides[k] = on
        overrides = {k: v for k, v in overrides.items() if v is not None}
        pairs = [self._ed_pairs.item(i).text() for i in range(self._ed_pairs.count())
                 if self._ed_pairs.item(i).checkState() == Qt.CheckState.Checked]
        res = wiregate.apply_settings(
            aid,
            enabled=self._ed_enabled.isChecked(),
            capital=self._ed_capital.value(),
            profile=self._ed_profile.currentData(),
            pairs=pairs,
            overrides=overrides)
        self._after_write(res)

    def _show_create(self):
        self._clear_form()
        t = QLabel("NEW AGENT \u2014 a platform appears on the floor")
        self._mform.addWidget(t)
        row = QHBoxLayout()
        row.addWidget(QLabel("name (optional)"))
        self._cr_name = QLineEdit()
        row.addWidget(self._cr_name, 1)
        self._mform.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("profile"))
        self._cr_profile = QComboBox()
        for k, v in (wiregate.PROFILES or {}).items():
            self._cr_profile.addItem(v.get("label") or k, k)
        row.addWidget(self._cr_profile, 1)
        self._mform.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("capital"))
        self._cr_capital = QDoubleSpinBox()
        self._cr_capital.setRange(0, 100000); self._cr_capital.setDecimals(1)
        row.addWidget(self._cr_capital, 1)
        self._mform.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("pairs"))
        self._cr_pairs = QListWidget(); self._cr_pairs.setMaximumHeight(72)
        for p in wiregate.PAIRS:
            item = QListWidgetItem(p)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if p == "DOT/USD"
                               else Qt.CheckState.Unchecked)
            self._cr_pairs.addItem(item)
        row.addWidget(self._cr_pairs, 1)
        self._mform.addLayout(row)
        make = QPushButton("Create agent")
        make.clicked.connect(self._do_create)
        back = QPushButton("Back to market")
        back.clicked.connect(lambda: self._menu_root(self.gl.market_world))
        hb = QHBoxLayout()
        hb.addWidget(make); hb.addWidget(back)
        self._mform.addLayout(hb)

    def _do_create(self):
        pairs = [self._cr_pairs.item(i).text() for i in range(self._cr_pairs.count())
                 if self._cr_pairs.item(i).checkState() == Qt.CheckState.Checked]
        res = wiregate.create_agent(
            self._cr_profile.currentData(),
            self._cr_capital.value(),
            name=self._cr_name.text().strip(),
            pairs=pairs)
        self._after_write(res)

    def _after_write(self, res):
        if not res.get("ok"):
            self.market_status.setText(f"\u2716 {res.get('error')}")
            self.gl._flash(f"not saved \u2014 {res.get('error')}", 5.0)
            return
        self.market_status.setText(
            f"\u2713 saved \u00b7 {res.get('name')} ({res.get('agent')})")
        self.gl._flash(f"saved \u00b7 {res.get('name')} {res.get('capital')} "
                       f"enabled={bool(res.get('enabled'))}", 3.0)
        self.gl.refresh_market()

    def shutdown(self):
        self.gl.shutdown()


def main():
    from PyQt6.QtWidgets import QApplication
    configure_gl()
    app = QApplication(sys.argv)
    w = WireVisionTab()
    w.resize(1200, 760)
    w.close_requested.connect(w.close)
    w.show()
    QTimer.singleShot(0, lambda: w.toggle_fullscreen(True))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
