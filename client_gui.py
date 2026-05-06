# client_gui.py - Member 4
import sys
import threading
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFrame)
from PyQt5.QtCore    import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui     import QFont, QColor, QPalette, QLinearGradient, QPainter, QBrush

from client_network import NetworkReceiver
from client_audio   import AudioPlayer
from config         import MCAST_GRP, MCAST_PORT

# ── Signals (thread-safe bridge from worker → GUI) ────────────────────────────
class _Signals(QObject):
    stats_updated = pyqtSignal(int)   # lost_packets
    error         = pyqtSignal(str)

# ── Radio worker (runs in background thread) ──────────────────────────────────
class RadioWorker:
    def __init__(self, signals: _Signals):
        self._signals  = signals
        self._running  = False
        self._thread   = None
        self._network  = None
        self._audio    = None
        self._lock     = threading.Lock()

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
        if self._network:
            try:
                self._network.sock.close()   # unblocks recvfrom immediately
            except Exception:
                pass

    def _loop(self):
        try:
            self._network = NetworkReceiver()
            self._network.sock.settimeout(1.0)
            self._audio   = AudioPlayer()
        except Exception as e:
            self._signals.error.emit(f"Setup error: {e}")
            self._running = False
            return

        while True:
            with self._lock:
                if not self._running:
                    break
            try:
                payload, loss = self._network.receive_packet()
                self._audio.play(payload)
                self._signals.stats_updated.emit(loss)
            except OSError:
                continue    # socket timeout — re-check _running
            except Exception as e:
                self._signals.error.emit(str(e))
                break

        if self._audio:
            self._audio.close()
        self._running = False

# ── Main window ───────────────────────────────────────────────────────────────
class RadioWindow(QWidget):
    # Colour palette
    BG        = "#0a0b10"
    CARD      = "#181b2a"
    ACCENT    = "#7c3aed"
    ACCENT2   = "#06b6d4"
    GREEN     = "#22c55e"
    RED       = "#ef4444"
    MUTED     = "#64748b"
    TEXT      = "#e2e8f0"

    def __init__(self):
        super().__init__()
        self._signals = _Signals()
        self._worker  = RadioWorker(self._signals)
        self._running = False
        self._loss    = 0

        self._signals.stats_updated.connect(self._on_stats)
        self._signals.error.connect(self._on_error)

        self._build_ui()

        # Visualizer animation timer
        self._viz_timer = QTimer(self)
        self._viz_timer.timeout.connect(self._animate_bars)

    # ── UI construction ────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle("IP Multicast Radio")
        self.setFixedSize(400, 480)
        self.setStyleSheet(f"background-color: {self.BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(16)

        # ── Header ────────────────────────────────────────────────
        hdr = QHBoxLayout()
        icon = QLabel("📻")
        icon.setFont(QFont("Arial", 26))
        hdr.addWidget(icon)

        titles = QVBoxLayout()
        t1 = QLabel("IP Multicast Radio")
        t1.setFont(QFont("Arial", 15, QFont.Bold))
        t1.setStyleSheet(f"color: {self.ACCENT};")
        t2 = QLabel("Multimedia over IP — UDP Receiver")
        t2.setFont(QFont("Arial", 10))
        t2.setStyleSheet(f"color: {self.MUTED};")
        titles.addWidget(t1)
        titles.addWidget(t2)
        hdr.addLayout(titles)
        hdr.addStretch()
        root.addLayout(hdr)

        # ── Visualizer bars ────────────────────────────────────────
        self._bars = []
        bar_row = QHBoxLayout()
        bar_row.setSpacing(4)
        bar_row.setContentsMargins(0, 0, 0, 0)
        for _ in range(24):
            b = QFrame()
            b.setFixedWidth(8)
            b.setFixedHeight(8)
            b.setStyleSheet(f"background-color: {self.ACCENT}; border-radius: 3px;")
            bar_row.addWidget(b)
            self._bars.append(b)
        bar_container = QWidget()
        bar_container.setLayout(bar_row)
        bar_container.setFixedHeight(60)
        bar_container.setStyleSheet(f"background: {self.CARD}; border-radius: 10px;")
        root.addWidget(bar_container)

        # ── Status row ─────────────────────────────────────────────
        status_frame = QFrame()
        status_frame.setStyleSheet(
            f"background:{self.CARD}; border-radius:10px; padding:4px;")
        sf_layout = QHBoxLayout(status_frame)
        self._dot = QLabel("●")
        self._dot.setFont(QFont("Arial", 12))
        self._dot.setStyleSheet(f"color: {self.MUTED};")
        self._status_lbl = QLabel("Ready to tune in…")
        self._status_lbl.setFont(QFont("Arial", 11, QFont.Medium))
        self._status_lbl.setStyleSheet(f"color: {self.MUTED};")
        sf_layout.addWidget(self._dot)
        sf_layout.addWidget(self._status_lbl)
        sf_layout.addStretch()
        root.addWidget(status_frame)

        # ── Stats grid ─────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self._loss_box  = self._stat_box("Packet Loss",     "0",          "packets dropped")
        self._mcast_box = self._stat_box("Multicast Group", MCAST_GRP,    f"Port {MCAST_PORT}")
        stats_row.addWidget(self._loss_box[0])
        stats_row.addWidget(self._mcast_box[0])
        root.addLayout(stats_row)

        # ── Tune In / Tune Out button ──────────────────────────────
        self._btn = QPushButton("📡  Tune In")
        self._btn.setFixedHeight(52)
        self._btn.setFont(QFont("Arial", 13, QFont.Bold))
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self._toggle)
        self._set_btn_style(False)
        root.addWidget(self._btn)

        # ── Footer ─────────────────────────────────────────────────
        footer = QLabel(f"Server: {MCAST_GRP}:{MCAST_PORT}  ·  Codec: PCM 44.1 kHz")
        footer.setAlignment(Qt.AlignCenter)
        footer.setFont(QFont("Arial", 9))
        footer.setStyleSheet(f"color: {self.MUTED};")
        root.addWidget(footer)

    def _stat_box(self, label_text, value_text, unit_text):
        frame = QFrame()
        frame.setStyleSheet(
            f"background:{self.CARD}; border-radius:12px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)

        lbl = QLabel(label_text.upper())
        lbl.setFont(QFont("Arial", 8, QFont.Bold))
        lbl.setStyleSheet(f"color:{self.MUTED}; letter-spacing:1px;")

        val = QLabel(value_text)
        val.setFont(QFont("Arial", 20, QFont.Bold))
        val.setStyleSheet(f"color:{self.ACCENT};")

        unit = QLabel(unit_text)
        unit.setFont(QFont("Arial", 9))
        unit.setStyleSheet(f"color:{self.MUTED};")

        layout.addWidget(lbl)
        layout.addWidget(val)
        layout.addWidget(unit)
        return frame, val

    def _set_btn_style(self, running: bool):
        if running:
            self._btn.setStyleSheet(
                f"QPushButton {{background: {self.RED}; color: white; "
                f"border-radius: 13px; border: none;}}"
                f"QPushButton:hover {{background: #dc2626;}}"
                f"QPushButton:pressed {{background: #b91c1c;}}")
        else:
            self._btn.setStyleSheet(
                f"QPushButton {{background: {self.ACCENT}; color: white; "
                f"border-radius: 13px; border: none;}}"
                f"QPushButton:hover {{background: #6d28d9;}}"
                f"QPushButton:pressed {{background: #5b21b6;}}")

    # ── Slots ──────────────────────────────────────────────────────
    def _toggle(self):
        if not self._running:
            self._running = True
            self._worker.start()
            self._btn.setText("⏹  Tune Out")
            self._set_btn_style(True)
            self._status_lbl.setText("Streaming Live")
            self._status_lbl.setStyleSheet(f"color: {self.GREEN};")
            self._dot.setStyleSheet(f"color: {self.GREEN};")
            self._viz_timer.start(120)
        else:
            self._running = False
            self._worker.stop()
            self._btn.setText("📡  Tune In")
            self._set_btn_style(False)
            self._status_lbl.setText("Ready to tune in…")
            self._status_lbl.setStyleSheet(f"color: {self.MUTED};")
            self._dot.setStyleSheet(f"color: {self.MUTED};")
            self._viz_timer.stop()
            self._reset_bars()

    def _on_stats(self, loss: int):
        self._loss_box[1].setText(str(loss))

    def _on_error(self, msg: str):
        self._running = False
        self._viz_timer.stop()
        self._reset_bars()
        self._btn.setText("📡  Tune In")
        self._set_btn_style(False)
        self._status_lbl.setText(f"Error: {msg}")
        self._status_lbl.setStyleSheet(f"color: {self.RED};")
        self._dot.setStyleSheet(f"color: {self.RED};")

    def _animate_bars(self):
        import random
        for b in self._bars:
            h = random.randint(8, 52)
            b.setFixedHeight(h)

    def _reset_bars(self):
        for b in self._bars:
            b.setFixedHeight(8)

    def closeEvent(self, event):
        self._worker.stop()
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette for the whole app
    pal = QPalette()
    pal.setColor(QPalette.Window,     QColor("#0a0b10"))
    pal.setColor(QPalette.WindowText, QColor("#e2e8f0"))
    app.setPalette(pal)

    win = RadioWindow()
    win.show()
    sys.exit(app.exec_())