#!/usr/bin/env python3
"""Mr.Fluffy — straight into the wire.

Mr.Fluffy opens the playable WIRE (the low-poly first-person read of the local
network and the rooms that hang off it) and gives it the whole screen. There is
no news channel any more and nothing is pulled in the background: the wire is
read from local files only, and Tab (or the ☰ button) opens the game menu with
Settings, Controls and a way to close the app. All model calls, where they
happen at all, still go through brain.py (sandboxed + egress-locked).
"""
import json, subprocess, sys, os
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QComboBox, QSplitter, QFrame,
    QTabWidget)

FLUFFY = Path.home() / "mrfluffy"
sys.path.insert(0, str(FLUFFY))
import wireout, brain  # noqa: E402

try:
    import wiregame  # the playable wire (low-poly first-person)
except Exception as _wg_err:  # keep the app alive even without a GL stack
    wiregame = None
    _WIREGAME_ERR = str(_wg_err)
else:
    _WIREGAME_ERR = ""

LOGS = FLUFFY / "logs"
WIRE_LATEST = LOGS / "wire_readout_latest.json"
WIRE_READOUTS = LOGS / "wire_readouts.jsonl"
DAEMON_LOG = LOGS / "daemon.log"


def _mono(size=10):
    return QFont("Monospace", size)


class Fluffy(QMainWindow):
    """The wire, full screen. The small side controls only appear when you step
    back out of full screen, so opening Mr.Fluffy drops you straight in."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mr.Fluffy — the wire")
        self.resize(1180, 760)
        self._daemon = None
        self._wire_busy = False

        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        title = QLabel("MR.FLUFFY"); title.setStyleSheet("font-size:20px;font-weight:bold;color:#c084fc")
        self._title = title
        outer.addWidget(title)

        split = QSplitter(Qt.Orientation.Horizontal)
        self._split = split

        # ---- left: wire controls + status (hidden while the wire is full screen) ----
        left = QWidget(); lv = QVBoxLayout(left)
        self._left = left
        self.status = QLabel("status: —"); self.status.setWordWrap(True)
        self.budget = QLabel("budget: —"); self.budget.setWordWrap(True)
        self.daemon_state = QLabel("daemon: stopped"); self.daemon_state.setWordWrap(True)
        for w in (self.status, self.budget, self.daemon_state):
            lv.addWidget(w)

        lv.addWidget(_sep())
        lv.addWidget(QLabel("Wire panel (the network analyst)"))
        self.b_wire_read = QPushButton("Read wire now")
        self.b_wire_force = QPushButton("Force wire re-read")
        self.b_wire_store = QPushButton("Store wire read")
        for b in (self.b_wire_read, self.b_wire_force, self.b_wire_store):
            lv.addWidget(b)

        lv.addWidget(_sep())
        self.b_daemon = QPushButton("Start daemon")
        lv.addWidget(self.b_daemon)

        lv.addWidget(_sep())
        lv.addWidget(QLabel("Daemon log"))
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFont(_mono(8))
        self.log.setMaximumBlockCount(400)
        lv.addWidget(self.log, 1)

        split.addWidget(left)

        # ---- right: the wire readout + the playable wire (the Vision tab) ----
        self.tabs = QTabWidget()

        wire_panel = QWidget(); wv = QVBoxLayout(wire_panel)
        wire_bar = QHBoxLayout()
        wire_bar.addWidget(QLabel("Wire history"))
        self.wire_history = QComboBox(); wire_bar.addWidget(self.wire_history, 1)
        wv.addLayout(wire_bar)
        self.wire_view = QTextEdit(); self.wire_view.setReadOnly(True); self.wire_view.setFont(_mono(10))
        wv.addWidget(self.wire_view, 1)
        self.tabs.addTab(wire_panel, "Wire")

        # the playable wire (low-poly first-person) — the default surface
        self.vision_panel = QWidget(); vv = QVBoxLayout(self.vision_panel)
        vv.setContentsMargins(0, 0, 0, 0)
        self.vision = None
        if wiregame is not None:
            self.vision = wiregame.WireVisionTab()
            vv.addWidget(self.vision)
        else:
            msg = QLabel(f"Wire Vision unavailable — no OpenGL stack here.\n({_WIREGAME_ERR})")
            msg.setWordWrap(True)
            vv.addWidget(msg)
        self.tabs.addTab(self.vision_panel, "Vision")

        split.addWidget(self.tabs)
        split.setStretchFactor(1, 3)
        outer.addWidget(split, 1)

        footer = QLabel("Mr.Fluffy is the wire: the LAN floor, the rooms that hang "
                        "off it, and the sea of information below. Local ground truth "
                        "only — no network pulled in the background.")
        footer.setStyleSheet("color:#9ca3af;font-size:10px")
        self._footer = footer
        outer.addWidget(footer)

        # ---- wiring ----
        self.b_wire_read.clicked.connect(lambda: self.do_wire_read(force=False))
        self.b_wire_force.clicked.connect(lambda: self.do_wire_read(force=True))
        self.b_wire_store.clicked.connect(self.do_wire_store)
        self.b_daemon.clicked.connect(self.toggle_daemon)
        self.wire_history.activated.connect(self.load_wire_history)
        if self.vision is not None:
            self.vision.fullscreen_changed.connect(self._on_vision_fullscreen)
            self.vision.close_requested.connect(self.close)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # only local file reads — nothing is fetched in the background
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(15000)
        self._fs_shortcut = QShortcut(QKeySequence("F11"), self)
        self._fs_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._fs_shortcut.activated.connect(self._toggle_vision_fullscreen)
        self.refresh()

    def start_wire(self):
        """The moment Mr.Fluffy opens: build the wire and give it the whole screen."""
        if self.vision is None:
            return
        self.tabs.setCurrentWidget(self.vision_panel)
        self.vision.build()
        self.vision.toggle_fullscreen(True)

    def _toggle_vision_fullscreen(self):
        if self.vision is None:
            return
        self.tabs.setCurrentWidget(self.vision_panel)
        self.vision.toggle_fullscreen()

    # ---- data plumbing ----
    def refresh(self):
        self.refresh_status()
        self.refresh_log()
        self.load_wire_latest()
        self.refresh_wire_history()
        if brain.clear_stale_guard():
            self.status.setText("healed a stale egress lockdown (a prior process died mid-call)")

    def refresh_status(self):
        wst = wireout._load_json(wireout.STATE, {})
        b = brain.status()
        wlast = wst.get("last_readout_ts")
        wwhen = __import__("time").strftime(
            "%Y-%m-%d %H:%M", __import__("time").localtime(wlast)) if wlast else "never"
        self.status.setText(
            f"wire  last    : {wwhen} · devices {wst.get('devices_seen','?')} "
            f"· fp {str(wst.get('fingerprint','?'))[:8]}")
        if b["allowed"]:
            self.budget.setText(f"budget: ready · {b['calls_last_hour']}/{b['max_calls_per_hour']} this hour")
            self.budget.setStyleSheet("color:#22c55e")
        else:
            self.budget.setText(f"budget: cooling · next in {b['seconds_until_next']}s · "
                                f"{b['calls_last_hour']}/{b['max_calls_per_hour']}")
            self.budget.setStyleSheet("color:#f59e0b")

    def refresh_log(self):
        try:
            lines = DAEMON_LOG.read_text().splitlines()[-40:]
        except Exception:
            lines = ["(no daemon log yet)"]
        self.log.setPlainText("\n".join(lines))

    def load_wire_latest(self):
        entry = wireout._load_json(WIRE_LATEST, {})
        ro = entry.get("readout")
        text = wireout.render(ro) if ro else "(no wire vision yet — click 'Read wire now'; use 'Store wire read' to keep one)"
        if self.wire_history.currentData() != -1:
            return
        if self.wire_view.toPlainText() == text:
            return
        self.wire_view.setPlainText(text)

    def refresh_wire_history(self):
        try:
            rows = WIRE_READOUTS.read_text().splitlines()[-25:]
        except Exception:
            rows = []
        if self.wire_history.count() == len(rows):
            return
        self.wire_history.blockSignals(True)
        self.wire_history.clear()
        self.wire_history.addItem("(latest)", -1)
        import time
        for i, line in enumerate(rows):
            try:
                e = json.loads(line)
            except Exception:
                continue
            ts = time.strftime("%m-%d %H:%M", time.localtime(e.get("ts", 0)))
            self.wire_history.addItem(f"{ts} · {str(e.get('readout',{}).get('one_liner',''))[:60]}", i)
        self.wire_history.blockSignals(False)

    def load_wire_history(self, idx):
        i = self.wire_history.itemData(idx)
        if i is None or i < 0:
            self.load_wire_latest(); return
        try:
            rows = WIRE_READOUTS.read_text().splitlines()[-25:]
            e = json.loads(rows[i])
            self.wire_view.setPlainText(wireout.render(e.get("readout", {})))
        except Exception as ex:
            self.wire_view.setPlainText(f"(could not load: {ex})")

    # ---- actions ----
    def do_wire_read(self, force: bool):
        if self._wire_busy:
            return
        self._wire_busy = True
        self.b_wire_read.setEnabled(False); self.b_wire_force.setEnabled(False)
        self.status.setText("reading wire… (network → model → render)")
        import threading
        def _work():
            try:
                r = wireout.run(force=force)
            except Exception as e:
                r = {"error": str(e)}
            self._last_wire_read = r
            QTimer.singleShot(0, self._wire_read_done)
        threading.Thread(target=_work, daemon=True).start()

    def _wire_read_done(self):
        self._wire_busy = False
        self.b_wire_read.setEnabled(True); self.b_wire_force.setEnabled(True)
        r = getattr(self, "_last_wire_read", {})
        if r.get("text"):
            self.wire_view.setPlainText(r["text"])
        elif r.get("skipped"):
            self.wire_view.setPlainText(f"(no wire vision change — {r['skipped']})\n" + self.wire_view.toPlainText())
        else:
            self.wire_view.setPlainText(f"(wire read failed: {r.get('error','?')})")
        self.refresh_status(); self.refresh_wire_history(); self.refresh_log()

    def _on_vision_fullscreen(self, on):
        """Wire Vision asked for the whole screen: hide the app chrome around it."""
        for w in (self._title, self._left, self._footer):
            w.setVisible(not on)
        self.tabs.tabBar().setVisible(not on)
        self._split.setStretchFactor(0, 0 if on else 1)
        self._split.setStretchFactor(1, 1)
        if on:
            self.status.setText("wire vision: full screen — F11 or \u26f6 to exit")
        else:
            self.status.setText("wire vision: panels restored")

    def _on_tab_changed(self, _idx):
        # leaving the Vision tab always drops full screen, so the app is never stuck
        if self.vision is not None and getattr(self.vision, "_fs", False):
            if self.tabs.currentWidget() is not self.vision_panel:
                self.vision.toggle_fullscreen(False)

    def do_wire_store(self):
        r = wireout.store()
        if r.get("stored"):
            import time
            when = time.strftime("%H:%M", time.localtime(r["stored"]))
            self.status.setText(f"stored wire vision at {when} to history")
            self.refresh_wire_history()
        else:
            self.status.setText(r.get("error") or "nothing to store yet — read the wire first")

    def _daemon_running(self) -> bool:
        if self._daemon and self._daemon.poll() is None:
            return True
        return False

    def toggle_daemon(self):
        if self._daemon_running():
            self._daemon.terminate()
            self._daemon = None
            self.daemon_state.setText("daemon: stopped")
            self.b_daemon.setText("Start daemon")
            return
        self._daemon = subprocess.Popen(
            [sys.executable, str(FLUFFY / "daemon.py")],
            cwd=str(FLUFFY), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.daemon_state.setText(f"daemon: running (pid {self._daemon.pid})")
        self.b_daemon.setText("Stop daemon")

    def closeEvent(self, ev):
        if self.vision is not None and getattr(self.vision, "_fs", False):
            self.vision.toggle_fullscreen(False)
        if self._daemon_running():
            try:
                self._daemon.terminate()
            except Exception:
                pass
        if self.vision is not None:
            try:
                self.vision.shutdown()
            except Exception:
                pass
        ev.accept()


def _sep():
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine); f.setStyleSheet("color:#374151")
    return f


def main():
    if wiregame is not None:
        try:
            wiregame.configure_gl()   # compatibility context, before QApplication
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Mr.Fluffy")
    w = Fluffy()
    w.show()
    QTimer.singleShot(0, w.start_wire)   # straight into the wire, full screen
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
