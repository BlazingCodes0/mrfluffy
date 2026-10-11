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
import math, sys, time, hashlib

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QPainter, QPen, QSurfaceFormat, QCursor,
                         QRadialGradient)
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
from wiregate import MARKET_FLOOR_Y, MARKET_R, RETURN_GATE_POS

MARKET_GATE_POS = [6.0, 0.06, -14.0]   # the tall portal to BlackHorse, on the wire floor

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

    def add_gl(self, glw):
        self.glw = glw
        glw.setParent(self)
        glw.show()

    def add_panel(self, panel):
        self.panel = panel
        panel.setParent(self)

    def place_panel(self):
        p = self.panel
        if p is None:
            return
        w, h = self.width(), self.height()
        pw = max(250, min(400, int(w * 0.42)))
        p.setGeometry(w - pw - 14, 14, pw, max(200, min(h - 28, int(h * 0.88))))
        p.raise_()

    def resizeEvent(self, e):
        if self.glw is not None:
            self.glw.setGeometry(self.rect())
        self.place_panel()

class WireGLWidget(QOpenGLWidget):
    stratum_changed = pyqtSignal(int, str)     # index, focus label (may be "")
    request_rebuild = pyqtSignal()
    market_opened = pyqtSignal(object)         # the wiregate market snapshot
    market_closed = pyqtSignal()
    agent_selected = pyqtSignal(object)        # an agent dict (one platform)
    menu_toggle = pyqtSignal(bool)             # show/hide the market menu

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
        self.focus = ""
        self.show_real = False
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
        self._last_t = time.time()
        self._hud_msg = ""
        self._hud_until = 0.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._quad = gluNewQuadric()
        self._glyphs = []
        self._init_glyphs()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)

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
        self._draw_market_gate(t, y)

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
        if k == Qt.Key.Key_Escape:
            self._drag = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
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
            if self.market:
                self.refresh_market()
            else:
                self.request_rebuild.emit()
        elif k == Qt.Key.Key_T:
            self.show_real = not self.show_real
        elif k == Qt.Key.Key_H:
            self.menu_toggle.emit(True)
        elif k == Qt.Key.Key_Home:
            if self.market:
                self._leave_market()
            elif self.deep is not None:
                self._exit_deep(surface=True)
            else:
                self._go_surface()
        elif k == Qt.Key.Key_G:
            self._toggle_fly()
        else:
            self.keys.add(k)
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        self.keys.discard(e.key())
        super().keyReleaseEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = True
            self._last_xy = e.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.setFocus()

    def mouseReleaseEvent(self, e):
        self._drag = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseMoveEvent(self, e):
        if self._drag and self._last_xy is not None:
            p = e.position().toPoint()
            dx = p.x() - self._last_xy.x()
            dy = p.y() - self._last_xy.y()
            self.yaw += dx * 0.004
            self.pitch = max(-1.2, min(1.2, self.pitch - dy * 0.004))
            self._last_xy = p

    # ---- movement + interaction -------------------------------------------
    def _step(self, dt):
        if self.market:
            self._market_step(dt)
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
        fast = 2.2 if (Qt.Key.Key_Shift in k) else 1.0
        spd = 9.0 * fast * dt
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
        if self.deep is not None or self.transition is not None:
            return
        self.flying = not self.flying
        if not self.flying:
            self.pos[1] = self._floor_y() + EYE     # settle back onto the floor
            self._flash("landed on the wire")
        else:
            self._flash("flight on — Space up \u00b7 C down \u00b7 W/S/A/D glide")

    def _fly_step(self, dt, fast):
        k = self.keys
        spd = 13.0 * fast * dt
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
            self.pos[0] += dx / m * spd
            self.pos[1] += dy / m * spd
            self.pos[2] += dz / m * spd
        rr = math.hypot(self.pos[0], self.pos[2])
        if rr > PLATFORM_R - 1.5:
            self.pos[0] = self.pos[0] / rr * (PLATFORM_R - 1.5)
            self.pos[2] = self.pos[2] / rr * (PLATFORM_R - 1.5)
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
        fast = 2.2 if Qt.Key.Key_Shift in k else 1.0
        spd = 13.0 * fast * dt
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
        if m > 0 and not self._on_any_platform(ignore=0.0, pad_only=False):
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
        # landing: flying down onto a platform = stepping on it
        w = self.market_world
        if w:
            for a in w["agents"]:
                x, yy, z = a["pos"]
                d2 = math.hypot(self.pos[0] - x, self.pos[2] - z)
                if d2 <= a.get("radius", 4.2) + 1.0 and abs(self.pos[1] - yy) <= 3.4:
                    self.flying = False
                    self.pos[0], self.pos[1], self.pos[2] = x, yy + EYE, z
                    if self.selected_agent != a["id"]:
                        self.selected_agent = a["id"]
                        self.selected = a
                        self._flash(f"you are standing on {a['name']}'s platform "
                                    f"\u2014 [E] open its trading settings")
                    break

    def _on_any_platform(self, ignore=0.0, pad_only=True):
        w = self.market_world or {}
        for a in w.get("agents", []):
            x, yy, z = a["pos"]
            if math.hypot(self.pos[0] - x, self.pos[2] - z) <= a.get("radius", 4.2) + 1.0 \
                    and abs(self.pos[1] - yy) <= 3.4:
                return a
        return None

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
        # the platforms: one per trading agent, coloured by what it waits for
        for a in w.get("agents", []):
            self._platform_aesthetic(a, t)
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
        for p in self._peers:
            items.append((p["x"], p["y"] + 2.0, p["z"], f"\u25c8 {p['name']}",
                          self._peer_col(p["name"])))
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
        if self.market:
            return self._nearest_market()
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
        rx, ry, rz = RETURN_GATE_POS
        consider("leave_market", rx, rz, ry, 5.0)
        return best

    def _interact(self):
        n = self._nearest()
        if not n:
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
            elif n["kind"] == "leave_market":
                self._leave_market()
            return
        if self.flying and n["kind"] in ("gate", "well", "up", "electron", "ruin"):
            self._flash("land first (G) to use the well and the gates")
            return
        if n["kind"] == "gate":
            self._start_transition(1, focus=n["domain"])
            self._flash(f"following {n['domain']} ×{n['count']}")
        elif n["kind"] == "market":
            self._enter_market()
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
        else:
            self._glyph_rain(now)
        if self.market:
            self._draw_market(now)
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
        pr.drawText(14, h_ - 118,
                    "green = waiting to buy \u00b7 red = waiting to sell \u00b7 "
                    "pulsing red = an exit is firing \u00b7 dim = off")
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
        pr.drawText(14, h_ - 50, "it is always open \u00b7 step onto a platform to trade")
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
            elif n0["kind"] == "leave_market":
                prompt = "[E] leave the market \u2014 back to the wire"
            pr.setPen(QColor(255, 215, 120))
            tw = fm.horizontalAdvance(prompt)
            pr.drawText((w_ - tw) // 2, ccy + 46, prompt)
        if self._hud_msg and now < self._hud_until:
            pr.setPen(QColor(120, 230, 180))
            tw = fm.horizontalAdvance(self._hud_msg)
            pr.drawText((w_ - tw) // 2, h_ - 40, self._hud_msg)

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

        # ---- the market: blackhorse, reached through the gate on the wire ----
        if self.market:
            self._hud_market(pr, now)
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
        if prompt:
            pr.setPen(QColor(255, 235, 150))
            tw = pr.fontMetrics().horizontalAdvance(prompt)
            pr.drawText((w_ - tw) // 2, h_ - 96, prompt)
        # transient flash
        if self._hud_msg and now < self._hud_until:
            pr.setPen(QColor(120, 230, 180))
            fm = pr.fontMetrics()
            tw = fm.horizontalAdvance(self._hud_msg)
            pr.drawText((w_ - tw) // 2, 112, self._hud_msg)

    # ---- lifecycle ---------------------------------------------------------
    def shutdown(self):
        self._timer.stop()


class WireVisionTab(QWidget):
    """The 'Vision' tab: the playable wire + a live codex side panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.world = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        bar = QHBoxLayout()
        self.b_build = QPushButton("Build the wire")
        self.b_build.setToolTip("Read the local ground truth and rebuild the playable world (no network, no brain)")
        self.cb_real = QCheckBox("show real names")
        self.cb_real.setToolTip("Reveal the technical term for every place (level the field)")
        self.where = QLabel("not built yet — click 'Build the wire'")
        bar.addWidget(self.b_build)
        bar.addWidget(self.cb_real)
        bar.addWidget(self.where, 1)
        lay.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.deck = _GLDeck()
        self.deck.setMinimumSize(420, 320)
        self.gl = WireGLWidget()
        self.gl.setMinimumSize(420, 320)
        self.deck.add_gl(self.gl)
        split.addWidget(self.deck)

        right = QFrame(); rv = QVBoxLayout(right)
        rv.addWidget(QLabel("CODEX — the wire, translated"))
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
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        lay.addWidget(split, 1)

        self.b_build.clicked.connect(self.build)
        self.cb_real.stateChanged.connect(self._toggle_real)
        self.gl.stratum_changed.connect(self._on_stratum)
        self.gl.request_rebuild.connect(self.build)
        self.gl.market_opened.connect(self._on_market)
        self.gl.market_closed.connect(self._on_market_closed)
        self.gl.agent_selected.connect(self._open_editor)
        self.gl.menu_toggle.connect(self._toggle_menu)
        self.b_new_agent.clicked.connect(self._show_create)
        self.b_close_menu.clicked.connect(lambda: self._set_menu(False))
        self._render_codex()
        # first build on the next event-loop turn so the widget is realized
        QTimer.singleShot(300, self.build)

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
        base = prof.get("policy") or {}
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
        for k, w in self._ed_ov.items():
            if isinstance(w, QDoubleSpinBox):
                if w.specialValueText() and w.value() <= w.minimum():
                    overrides[k] = None
                else:
                    overrides[k] = w.value()
            else:
                overrides[k] = w.isChecked()
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
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
