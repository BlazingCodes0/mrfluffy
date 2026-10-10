#!/usr/bin/env python3
"""Mr.Fluffy GUI — the reader's window.

Shows the latest readout, the readout history, live budget/daemon status, and the
daemon log. Buttons let you refresh news, take a readout now, or force a re-read.
All model calls go through brain.py (sandboxed + egress-locked).
"""
import json, subprocess, sys, os, signal, time
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QComboBox, QSplitter, QFrame, QMessageBox)

FLUFFY = Path.home() / "mrfluffy"
sys.path.insert(0, str(FLUFFY))
import news, readout, brain  # noqa: E402

LOGS = FLUFFY / "logs"
LATEST = LOGS / "news_readout_latest.json"
READOUTS = LOGS / "news_readouts.jsonl"
DAEMON_LOG = LOGS / "daemon.log"
PIDFILE = LOGS / "gui_daemon.pid"


def _mono(size=10):
    f = QFont("Monospace", size)
    return f


class Fluffy(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mr.Fluffy — the reader")
        self.resize(1180, 760)
        self._daemon = None
        self._busy = False

        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        title = QLabel("MR.FLUFFY"); title.setStyleSheet("font-size:20px;font-weight:bold;color:#c084fc")
        outer.addWidget(title)

        split = QSplitter(Qt.Orientation.Horizontal)

        # ---- left: controls + status ----
        left = QWidget(); lv = QVBoxLayout(left)
        self.status = QLabel("status: —"); self.status.setWordWrap(True)
        self.budget = QLabel("budget: —"); self.budget.setWordWrap(True)
        self.daemon_state = QLabel("daemon: stopped"); self.daemon_state.setWordWrap(True)
        for w in (self.status, self.budget, self.daemon_state):
            lv.addWidget(w)

        lv.addWidget(_sep())
        self.b_read_now = QPushButton("Read now")
        self.b_force = QPushButton("Force re-read")
        self.b_news = QPushButton("Refresh news")
        self.b_daemon = QPushButton("Start daemon")
        for b in (self.b_read_now, self.b_force, self.b_news):
            lv.addWidget(b)
        lv.addWidget(_sep())
        lv.addWidget(self.b_daemon)

        lv.addWidget(_sep())
        lv.addWidget(QLabel("History"))
        self.history = QComboBox(); lv.addWidget(self.history)

        lv.addWidget(_sep())
        lv.addWidget(QLabel("Daemon log"))
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFont(_mono(8))
        self.log.setMaximumBlockCount(400)
        lv.addWidget(self.log, 1)

        split.addWidget(left)

        # ---- right: readout ----
        self.view = QTextEdit(); self.view.setReadOnly(True); self.view.setFont(_mono(10))
        split.addWidget(self.view)
        split.setStretchFactor(1, 3)
        outer.addWidget(split, 1)

        footer = QLabel("BlackHorse is the trading horse; Mr.Fluffy only reads. Calls are sandboxed + egress-locked.")
        footer.setStyleSheet("color:#9ca3af;font-size:10px")
        outer.addWidget(footer)

        # ---- wiring ----
        self.b_read_now.clicked.connect(lambda: self.do_read(force=False))
        self.b_force.clicked.connect(lambda: self.do_read(force=True))
        self.b_news.clicked.connect(self.do_news)
        self.b_daemon.clicked.connect(self.toggle_daemon)
        self.history.activated.connect(self.load_history)

        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(15000)
        self.refresh()

    # ---- data plumbing ----
    def refresh(self):
        self.refresh_status()
        self.refresh_log()
        self.load_latest()
        self.refresh_history()
        if brain.clear_stale_guard():
            self.status.setText("healed a stale egress lockdown (a prior process died mid-call)")

    def refresh_status(self):
        st = readout._load_json(readout.STATE, {})
        b = brain.status()
        last = st.get("last_readout_ts")
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(last)) if last else "never"
        self.status.setText(
            f"last readout : {when}\n"
            f"headlines    : {st.get('headline_count','?')}\n"
            f"fingerprint  : {st.get('fingerprint','?')}")
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
        if ro:
            self.view.setPlainText(readout.render(ro))
        else:
            self.view.setPlainText("(no readout yet — click 'Read now')")

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

    # ---- actions ----
    def do_read(self, force: bool):
        if self._busy:
            return
        self._busy = True
        self.b_read_now.setEnabled(False); self.b_force.setEnabled(False)
        self.status.setText("reading… (news → model → render)")
        import threading
        def _work():
            r = readout.run(force=force)
            self._last_read = r
            QTimer.singleShot(0, self._read_done)
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
        if self._daemon_running():
            try:
                self._daemon.terminate()
            except Exception:
                pass
        ev.accept()


def _sep():
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine); f.setStyleSheet("color:#374151")
    return f


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Mr.Fluffy")
    w = Fluffy()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()