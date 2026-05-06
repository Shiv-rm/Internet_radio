# client_gui.py - Member 4
# PyQt5 desktop UI with tabbed Audio/Video display,
# volume slider, and QoS statistics dashboard.
import sys
import random
import threading
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFrame, QSlider, QTabWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QPalette, QImage, QPixmap

from client_network import NetworkReceiver
from client_audio import AudioPlayer
from config import MCAST_GRP, MCAST_PORT, PKT_AUDIO, PKT_VIDEO


class _Signals(QObject):
    stats_updated = pyqtSignal(dict)
    video_frame   = pyqtSignal(bytes)
    error         = pyqtSignal(str)


class RadioWorker:
    def __init__(self, signals):
        self._signals = signals
        self._running = False
        self._thread  = None
        self._network = None
        self._audio   = None
        self._lock    = threading.Lock()

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
                self._network.sock.close()
            except Exception:
                pass

    def set_volume(self, vol):
        if self._audio:
            self._audio.volume = vol

    def _loop(self):
        try:
            self._network = NetworkReceiver()
            self._network.sock.settimeout(1.0)
            self._audio = AudioPlayer()
        except Exception as e:
            self._signals.error.emit(f"Setup error: {e}")
            self._running = False
            return

        while True:
            with self._lock:
                if not self._running:
                    break
            try:
                pkt_type, payload, stats = self._network.receive_packet()
                if pkt_type == PKT_AUDIO:
                    self._audio.play(payload)
                elif pkt_type == PKT_VIDEO:
                    self._signals.video_frame.emit(payload)
                self._signals.stats_updated.emit(stats)
            except OSError:
                continue
            except Exception as e:
                self._signals.error.emit(str(e))
                break

        if self._audio:
            self._audio.close()
        self._running = False


class RadioWindow(QWidget):
    BG     = "#0a0b10"
    CARD   = "#181b2a"
    ACCENT = "#7c3aed"
    CYAN   = "#06b6d4"
    GREEN  = "#22c55e"
    RED    = "#ef4444"
    MUTED  = "#64748b"
    TEXT   = "#e2e8f0"

    def __init__(self):
        super().__init__()
        self._signals = _Signals()
        self._worker  = RadioWorker(self._signals)
        self._running = False

        self._signals.stats_updated.connect(self._on_stats)
        self._signals.video_frame.connect(self._on_video)
        self._signals.error.connect(self._on_error)

        self._build_ui()
        self._viz_timer = QTimer(self)
        self._viz_timer.timeout.connect(self._animate_bars)

    def _build_ui(self):
        self.setWindowTitle("IP Multicast Radio")
        self.setFixedSize(440, 640)
        self.setStyleSheet(f"background-color: {self.BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(10)

        # ── Header ──────────────────────────────────────────────
        hdr = QHBoxLayout()
        icon = QLabel("📻")
        icon.setFont(QFont("Arial", 22))
        hdr.addWidget(icon)
        titles = QVBoxLayout()
        t1 = QLabel("IP Multicast Radio")
        t1.setFont(QFont("Arial", 14, QFont.Bold))
        t1.setStyleSheet(f"color: {self.ACCENT};")
        t2 = QLabel("Multimedia over IP — UDP Receiver")
        t2.setFont(QFont("Arial", 9))
        t2.setStyleSheet(f"color: {self.MUTED};")
        titles.addWidget(t1)
        titles.addWidget(t2)
        hdr.addLayout(titles)
        hdr.addStretch()
        root.addLayout(hdr)

        # ── Status row (shared) ─────────────────────────────────
        sf = QFrame()
        sf.setStyleSheet(f"background:{self.CARD}; border-radius:8px;")
        sf_lay = QHBoxLayout(sf)
        sf_lay.setContentsMargins(12, 6, 12, 6)
        self._dot = QLabel("●")
        self._dot.setFont(QFont("Arial", 11))
        self._dot.setStyleSheet(f"color: {self.MUTED};")
        self._status_lbl = QLabel("Ready to tune in…")
        self._status_lbl.setFont(QFont("Arial", 10))
        self._status_lbl.setStyleSheet(f"color: {self.MUTED};")
        sf_lay.addWidget(self._dot)
        sf_lay.addWidget(self._status_lbl)
        sf_lay.addStretch()
        root.addWidget(sf)

        # ── Tabbed content ──────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {self.CARD};
                border-radius: 10px;
                border: 1px solid #2a2d3e;
            }}
            QTabBar::tab {{
                background: {self.BG};
                color: {self.MUTED};
                padding: 8px 24px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: {self.CARD};
                color: {self.ACCENT};
            }}
        """)

        # ── Audio Tab ───────────────────────────────────────────
        audio_tab = QWidget()
        audio_tab.setStyleSheet(f"background: {self.CARD};")
        a_lay = QVBoxLayout(audio_tab)
        a_lay.setContentsMargins(16, 16, 16, 16)
        a_lay.setSpacing(12)

        # Visualizer
        self._bars = []
        bar_row = QHBoxLayout()
        bar_row.setSpacing(3)
        for _ in range(24):
            b = QFrame()
            b.setFixedWidth(8)
            b.setFixedHeight(6)
            b.setStyleSheet(f"background-color: {self.ACCENT}; border-radius: 3px;")
            bar_row.addWidget(b)
            self._bars.append(b)
        bar_box = QWidget()
        bar_box.setLayout(bar_row)
        bar_box.setFixedHeight(80)
        bar_box.setStyleSheet(f"background: {self.BG}; border-radius: 8px;")
        a_lay.addWidget(bar_box)

        # Volume
        vf = QWidget()
        vf.setStyleSheet(f"background: {self.BG}; border-radius: 8px;")
        vf_lay = QHBoxLayout(vf)
        vf_lay.setContentsMargins(12, 8, 12, 8)
        vol_icon = QLabel("🔊")
        vol_icon.setFont(QFont("Arial", 13))
        vf_lay.addWidget(vol_icon)
        self._vol_slider = QSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{background:{self.MUTED};height:5px;border-radius:2px;}}
            QSlider::handle:horizontal {{background:{self.ACCENT};width:14px;height:14px;margin:-5px 0;border-radius:7px;}}
            QSlider::sub-page:horizontal {{background:{self.ACCENT};border-radius:2px;}}
        """)
        self._vol_slider.valueChanged.connect(self._on_volume)
        self._vol_lbl = QLabel("80%")
        self._vol_lbl.setFont(QFont("Arial", 9))
        self._vol_lbl.setStyleSheet(f"color:{self.TEXT};")
        self._vol_lbl.setFixedWidth(32)
        vf_lay.addWidget(self._vol_slider)
        vf_lay.addWidget(self._vol_lbl)
        a_lay.addWidget(vf)

        # Audio codec info
        info = QLabel("Codec: PCM 16-bit  ·  44100 Hz  ·  Stereo")
        info.setAlignment(Qt.AlignCenter)
        info.setFont(QFont("Arial", 9))
        info.setStyleSheet(f"color:{self.MUTED};")
        a_lay.addWidget(info)
        a_lay.addStretch()

        self._tabs.addTab(audio_tab, "🎵  Audio")

        # ── Video Tab ───────────────────────────────────────────
        video_tab = QWidget()
        video_tab.setStyleSheet(f"background: {self.CARD};")
        v_lay = QVBoxLayout(video_tab)
        v_lay.setContentsMargins(16, 16, 16, 16)
        v_lay.setSpacing(10)

        self._video_lbl = QLabel("No video stream")
        self._video_lbl.setFixedSize(340, 240)
        self._video_lbl.setAlignment(Qt.AlignCenter)
        self._video_lbl.setStyleSheet(
            f"background: {self.BG}; border-radius: 8px; color: {self.MUTED};")
        self._video_lbl.setFont(QFont("Arial", 10))
        vid_row = QHBoxLayout()
        vid_row.addStretch()
        vid_row.addWidget(self._video_lbl)
        vid_row.addStretch()
        v_lay.addLayout(vid_row)

        vinfo = QLabel("Video: JPEG  ·  320×240  ·  15 fps")
        vinfo.setAlignment(Qt.AlignCenter)
        vinfo.setFont(QFont("Arial", 9))
        vinfo.setStyleSheet(f"color:{self.MUTED};")
        v_lay.addWidget(vinfo)
        v_lay.addStretch()

        self._tabs.addTab(video_tab, "🎬  Video")

        root.addWidget(self._tabs)

        # ── Stats row (shared) ──────────────────────────────────
        r1 = QHBoxLayout()
        r1.setSpacing(10)
        self._loss_val    = self._make_stat("Packet Loss", "0", "packets")
        self._reorder_val = self._make_stat("Reordered", "0", "packets")
        r1.addWidget(self._loss_val[0])
        r1.addWidget(self._reorder_val[0])
        root.addLayout(r1)

        # ── Tune button (shared) ────────────────────────────────
        self._btn = QPushButton("📡  Tune In")
        self._btn.setFixedHeight(46)
        self._btn.setFont(QFont("Arial", 12, QFont.Bold))
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self._toggle)
        self._set_btn_style(False)
        root.addWidget(self._btn)

        # Footer
        ft = QLabel(f"Multicast: {MCAST_GRP}:{MCAST_PORT}")
        ft.setAlignment(Qt.AlignCenter)
        ft.setFont(QFont("Arial", 8))
        ft.setStyleSheet(f"color: {self.MUTED};")
        root.addWidget(ft)

    def _make_stat(self, label, value, unit):
        f = QFrame()
        f.setStyleSheet(f"background:{self.CARD}; border-radius:10px;")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(12, 8, 12, 8)
        l = QLabel(label.upper())
        l.setFont(QFont("Arial", 7, QFont.Bold))
        l.setStyleSheet(f"color:{self.MUTED};")
        v = QLabel(value)
        v.setFont(QFont("Arial", 16, QFont.Bold))
        v.setStyleSheet(f"color:{self.ACCENT};")
        u = QLabel(unit)
        u.setFont(QFont("Arial", 8))
        u.setStyleSheet(f"color:{self.MUTED};")
        lay.addWidget(l)
        lay.addWidget(v)
        lay.addWidget(u)
        return f, v

    def _set_btn_style(self, on):
        c = self.RED if on else self.ACCENT
        self._btn.setStyleSheet(
            f"QPushButton{{background:{c};color:white;border-radius:12px;border:none;}}")

    # ── Slots ───────────────────────────────────────────────────
    def _toggle(self):
        if not self._running:
            self._running = True
            self._worker.start()
            self._btn.setText("⏹  Tune Out")
            self._set_btn_style(True)
            self._status_lbl.setText("Streaming Live")
            self._status_lbl.setStyleSheet(f"color:{self.GREEN};")
            self._dot.setStyleSheet(f"color:{self.GREEN};")
            self._viz_timer.start(120)
        else:
            self._running = False
            self._worker.stop()
            self._btn.setText("📡  Tune In")
            self._set_btn_style(False)
            self._status_lbl.setText("Ready to tune in…")
            self._status_lbl.setStyleSheet(f"color:{self.MUTED};")
            self._dot.setStyleSheet(f"color:{self.MUTED};")
            self._video_lbl.setPixmap(QPixmap())
            self._video_lbl.setText("No video stream")
            self._viz_timer.stop()
            self._reset_bars()

    def _on_stats(self, stats):
        self._loss_val[1].setText(str(stats['lost_packets']))
        self._reorder_val[1].setText(str(stats['reordered']))

    def _on_video(self, jpeg_data):
        img = QImage.fromData(jpeg_data)
        if not img.isNull():
            self._video_lbl.setPixmap(
                QPixmap.fromImage(img).scaled(340, 240, Qt.KeepAspectRatio,
                                              Qt.SmoothTransformation))

    def _on_volume(self, val):
        self._vol_lbl.setText(f"{val}%")
        self._worker.set_volume(val / 100.0)

    def _on_error(self, msg):
        self._running = False
        self._viz_timer.stop()
        self._reset_bars()
        self._btn.setText("📡  Tune In")
        self._set_btn_style(False)
        self._status_lbl.setText(f"Error: {msg}")
        self._status_lbl.setStyleSheet(f"color:{self.RED};")
        self._dot.setStyleSheet(f"color:{self.RED};")

    def _animate_bars(self):
        for b in self._bars:
            b.setFixedHeight(random.randint(6, 70))

    def _reset_bars(self):
        for b in self._bars:
            b.setFixedHeight(6)

    def closeEvent(self, event):
        self._worker.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#0a0b10"))
    pal.setColor(QPalette.WindowText, QColor("#e2e8f0"))
    app.setPalette(pal)
    win = RadioWindow()
    win.show()
    sys.exit(app.exec_())