#!/usr/bin/env python3
"""Mr.Fluffy GUI — news + wire, two separate panels.

The News tab shows the crypto reader's latest readout (grouped as-is). The Wire
tab is a totally separate panel: the network analyst's readout of who is on the
wire, what each talks to, crow verdicts, IDS alerts, lifeline health — with its
own history. Buttons control each channel independently. All model calls go
through brain.py (sandboxed + egress-locked, shared budget).
"""
import json, subprocess, sys, os, signal, time
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QComboBox, QSplitter, QFrame,
    QTabWidget, QMessageBox)

FLUFFY = Path.home() / "mrfluffy"
sys.path.insert(0, str(FLUFFY))
import news, readout, wireout, brain  # noqa: E402

try:
    import wiregame  # the playable wire (low-poly first-person)
except Exception as _wg_err:  # keep the app alive even without a GL stack
    wiregame = None
    _WIREGAME_ERR = str(_wg_err)
else:
    _WIREGAME_ERR = ""

LOGS = FLUFFY / "logs"
LATEST = LOGS / "news_readout_latest.json"
READOUTS = LOGS / "news_readouts.jsonl"
WIRE_LATEST = LOGS / "wire_readout_latest.json"
WIRE_READOUTS = LOGS / "wire_readouts.jsonl"
DAEMON_LOG = LOGS / "daemon.log"
PIDFILE = LOGS / "gui_daemon.pid"
THESIS = FLUFFY / "docs" / "NEWS_THESIS.md"
PROMOTIONS = LOGS / "promotions.jsonl"


def _mono(size=10):
    f = QFont("Monospace", size)
    return f


class Fluffy(QMainWindow):
    read_done = pyqtSignal()
    wire_read_done = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mr.Fluffy — news + wire")
        self.resize(1180, 760)
        self._daemon = None
        self._busy = False
        self._wire_busy = False

        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        title = QLabel("MR.FLUFFY"); title.setStyleSheet("font-size:20px;font-weight:bold;color:#c084fc")
        self._title = title
        outer.addWidget(title)

        split = QSplitter(Qt.Orientation.Horizontal)
        self._split = split

        # ---- left: controls + status (channel-agnostic) ----
        left = QWidget(); lv = QVBoxLayout(left)
        self._left = left
        self.status = QLabel("status: —"); self.status.setWordWrap(True)
        self.budget = QLabel("budget: —"); self.budget.setWordWrap(True)
        self.daemon_state = QLabel("daemon: stopped"); self.daemon_state.setWordWrap(True)
        for w in (self.status, self.budget, self.daemon_state):
            lv.addWidget(w)

        lv.addWidget(_sep())
        lv.addWidget(QLabel("News panel (the reader)"))
        self.b_read_now = QPushButton("Read news now")
        self.b_force = QPushButton("Force news re-read")
        self.b_news = QPushButton("Refresh news")
        self.b_promote = QPushButton("Promote thesis update")
        for b in (self.b_read_now, self.b_force, self.b_news, self.b_promote):
            lv.addWidget(b)

        lv.addWidget(_sep())
        lv.addWidget(QLabel("Wire panel (the vision)"))
        self.b_wire_read = QPushButton("Read wire now")
        self.b_wire_force = QPushButton("Force wire re-read")
        self.b_wire_store = QPushButton("Store wire read")
        lv.addWidget(self.b_wire_read)
        lv.addWidget(self.b_wire_force)
        lv.addWidget(self.b_wire_store)

        lv.addWidget(_sep())
        lv.addWidget(QLabel("Wire Vision (play the wire)"))
        self.b_vision = QPushButton("Open wire vision")
        self.b_vision.setToolTip("Walk the wire: the LAN floor, then fall the protocol stack to the last electron")
        lv.addWidget(self.b_vision)
        self.b_vision_fs = QPushButton("\u26f6 Wire vision full screen")
        self.b_vision_fs.setToolTip("Give Wire Vision the whole screen (F11) \u2014 hides the panels")
        lv.addWidget(self.b_vision_fs)

        lv.addWidget(_sep())
        self.b_daemon = QPushButton("Start daemon")
        lv.addWidget(self.b_daemon)

        lv.addWidget(_sep())
        lv.addWidget(QLabel("Daemon log"))
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFont(_mono(8))
        self.log.setMaximumBlockCount(400)
        lv.addWidget(self.log, 1)

        split.addWidget(left)

        # ---- right: two separate panels (tabs) ----
        self.tabs = QTabWidget()

        news_panel = QWidget(); nv = QVBoxLayout(news_panel)
        news_bar = QHBoxLayout()
        news_bar.addWidget(QLabel("News history"))
        self.history = QComboBox(); news_bar.addWidget(self.history, 1)
        nv.addLayout(news_bar)
        self.view = QTextEdit(); self.view.setReadOnly(True); self.view.setFont(_mono(10))
        nv.addWidget(self.view, 1)
        self.tabs.addTab(news_panel, "News")

        wire_panel = QWidget(); wv = QVBoxLayout(wire_panel)
        wire_bar = QHBoxLayout()
        wire_bar.addWidget(QLabel("Wire history"))
        self.wire_history = QComboBox(); wire_bar.addWidget(self.wire_history, 1)
        wv.addLayout(wire_bar)
        self.wire_view = QTextEdit(); self.wire_view.setReadOnly(True); self.wire_view.setFont(_mono(10))
        wv.addWidget(self.wire_view, 1)
        self.tabs.addTab(wire_panel, "Wire")

        # ---- third panel: the playable wire (low-poly first-person) ----
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

        footer = QLabel("Three panels: the News reader (tape), the Wire king (network), and Wire Vision (walk the wire). The game reads local ground truth only — no network, no brain calls.")
        footer.setStyleSheet("color:#9ca3af;font-size:10px")
        self._footer = footer
        outer.addWidget(footer)

        # ---- wiring ----
        self.b_read_now.clicked.connect(lambda: self.do_read(force=False))
        self.b_force.clicked.connect(lambda: self.do_read(force=True))
        self.b_news.clicked.connect(self.do_news)
        self.b_daemon.clicked.connect(self.toggle_daemon)
        self.b_promote.clicked.connect(self.do_promote)
        self.history.activated.connect(self.load_history)
        self.wire_history.activated.connect(self.load_wire_history)
        self.b_wire_read.clicked.connect(lambda: self.do_wire_read(force=False))
        self.b_wire_force.clicked.connect(lambda: self.do_wire_read(force=True))
        self.b_wire_store.clicked.connect(self.do_wire_store)
        self.b_vision.clicked.connect(self.open_vision)
        self.b_vision_fs.clicked.connect(self.open_vision_fullscreen)
        if self.vision is not None:
            self.vision.fullscreen_changed.connect(self._on_vision_fullscreen)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.read_done.connect(self._read_done)
        self.wire_read_done.connect(self._wire_read_done)

        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(15000)
        self._fs_shortcut = QShortcut(QKeySequence("F11"), self)
        self._fs_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._fs_shortcut.activated.connect(self._toggle_vision_fullscreen)
        self.refresh()

    def _toggle_vision_fullscreen(self):
        if self.vision is None:
            return
        self.tabs.setCurrentWidget(self.vision_panel)
        self.vision.toggle_fullscreen()

    # ---- data plumbing ----
    def refresh(self):
        self.refresh_status()
        self.refresh_log()
        self.load_latest()
        self.refresh_history()
        self.load_wire_latest()
        self.refresh_wire_history()
        if brain.clear_stale_guard():
            self.status.setText("healed a stale egress lockdown (a prior process died mid-call)")

    def refresh_status(self):
        st = readout._load_json(readout.STATE, {})
        wst = wireout._load_json(wireout.STATE, {})
        b = brain.status()
        last = st.get("last_readout_ts")
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(last)) if last else "never"
        wlast = wst.get("last_readout_ts")
        wwhen = time.strftime("%Y-%m-%d %H:%M", time.localtime(wlast)) if wlast else "never"
        self.status.setText(
            f"news  last    : {when}\n"
            f"headlines     : {st.get('headline_count','?')} · fp {str(st.get('fingerprint','?'))[:8]}\n"
            f"wire  last    : {wwhen} · devices {wst.get('devices_seen','?')} · fp {str(wst.get('fingerprint','?'))[:8]}")
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

    def load_latest(self):
        entry = readout._load_json(LATEST, {})
        ro = entry.get("readout")
        text = readout.render(ro) if ro else "(no readout yet — click 'Read now')"
        if self.history.currentData() != -1:
            return  # user is browsing history; don't yank the view
        if self.view.toPlainText() == text:
            return  # unchanged — keep scroll position
        self.view.setPlainText(text)

    def refresh_history(self):
        try:
            rows = READOUTS.read_text().splitlines()[-25:]
        except Exception:
            rows = []
        if self.history.count() == len(rows):
            return
        self.history.blockSignals(True)
        self.history.clear()
        self.history.addItem("(latest)", -1)
        for i, line in enumerate(rows):
            try:
                e = json.loads(line)
            except Exception:
                continue
            ts = time.strftime("%m-%d %H:%M", time.localtime(e.get("ts", 0)))
            self.history.addItem(f"{ts} · {str(e.get('readout',{}).get('one_liner',''))[:60]}", i)
        self.history.blockSignals(False)

    def load_history(self, idx):
        i = self.history.itemData(idx)
        if i is None or i < 0:
            self.load_latest(); return
        try:
            rows = READOUTS.read_text().splitlines()[-25:]
            e = json.loads(rows[i])
            self.view.setPlainText(readout.render(e.get("readout", {})))
        except Exception as ex:
            self.view.setPlainText(f"(could not load: {ex})")

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
    def do_read(self, force: bool):
        if self._busy:
            return
        self._busy = True
        self.b_read_now.setEnabled(False); self.b_force.setEnabled(False)
        self.status.setText("reading… (news → model → render)")
        import threading
        def _work():
            try:
                r = readout.run(force=force)
            except Exception as e:
                r = {"error": str(e)}
            self._last_read = r
            self.read_done.emit()
        threading.Thread(target=_work, daemon=True).start()

    def _read_done(self):
        self._busy = False
        self.b_read_now.setEnabled(True); self.b_force.setEnabled(True)
        r = getattr(self, "_last_read", {})
        if r.get("text"):
            self.view.setPlainText(r["text"])
        elif r.get("skipped"):
            self.view.setPlainText(f"(no readout — {r['skipped']})\n" + self.view.toPlainText())
        else:
            self.view.setPlainText(f"(read failed: {r.get('error','?')})")
        self.refresh_status(); self.refresh_history(); self.refresh_log()

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
            self.wire_read_done.emit()
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

    def open_vision(self):
        if self.vision is None:
            self.status.setText("wire vision unavailable (no OpenGL stack)")
            return
        self.tabs.setCurrentWidget(self.vision_panel)
        self.vision.build()
        self.status.setText("wire vision: built the playable wire — WASD to move, E to interact")

    def open_vision_fullscreen(self):
        if self.vision is None:
            self.status.setText("wire vision unavailable (no OpenGL stack)")
            return
        self.tabs.setCurrentWidget(self.vision_panel)
        self.vision.build()
        self.vision.toggle_fullscreen(True)
        self.status.setText("wire vision: full screen — press F11 or \u26f6 to exit")

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
            when = time.strftime("%H:%M", time.localtime(r["stored"]))
            self.status.setText(f"stored wire vision at {when} to history")
            self.refresh_wire_history()
        else:
            self.status.setText(r.get("error") or "nothing to store yet — read the wire first")

    def do_promote(self):
        """User confirms the latest readout's proposed thesis update into NEWS_THESIS.md."""
        entry = readout._load_json(LATEST, {})
        ro = entry.get("readout") or {}
        upd = (ro.get("thesis_update") or "").strip()
        if not upd:
            self.status.setText("nothing to promote — latest readout has no thesis_update")
            return
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime())
        ret = QMessageBox.question(
            self, "Promote thesis update?",
            f"User-confirm this thesis change into docs/NEWS_THESIS.md?\n\n{upd}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        block = f"\n## {ts} — user-promoted update\n\n{upd}\n"
        THESIS.parent.mkdir(parents=True, exist_ok=True)
        with THESIS.open("a") as fh:
            fh.write(block)
        PROMOTIONS.parent.mkdir(parents=True, exist_ok=True)
        with PROMOTIONS.open("a") as fh:
            fh.write(json.dumps({"ts": time.time(), "thesis_update": upd}) + "\n")
        self.status.setText(f"promoted thesis update ({ts}) into NEWS_THESIS.md")

    def do_news(self):
        self.status.setText("fetching news…")
        import threading
        def _work():
            ctx = news.get(0)
            self._news_sum = news.summary(ctx)
            QTimer.singleShot(0, lambda: self.status.setText("news: " + self._news_sum))
        threading.Thread(target=_work, daemon=True).start()

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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()