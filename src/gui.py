"""
Main GUI window — live distance display and time-series graph.
"""

import numpy as np
import pyqtgraph as pg

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from sensor import BaseSensor


class MainWindow(QMainWindow):
    BUFFER_SIZE = 200
    # ~20 Hz UI; VL53L3CX timing budget 50 ms caps useful rate near 15–20 Hz
    UPDATE_INTERVAL_MS = 50
    DISPLAY_MAX_MM = 2000

    def __init__(self, sensor: BaseSensor, auto_start: bool = False):
        super().__init__()
        self._sensor = sensor
        self._running = False
        self._data_buffer = np.zeros(self.BUFFER_SIZE)
        self._buf_idx = 0

        self.setWindowTitle("VL53L3CX — ToF Distance Monitor")
        self.setMinimumSize(800, 500)
        self._setup_ui()
        self._setup_timer()

        if auto_start:
            self._on_start()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._dist_label = QLabel("--- mm")
        self._dist_label.setFont(QFont("Monospace", 36, QFont.Weight.Bold))
        self._dist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dist_label.setStyleSheet("color: #00cc44;")
        layout.addWidget(self._dist_label)

        pg.setConfigOptions(antialias=True)
        self._plot_widget = pg.PlotWidget(title="Distance Over Time")
        self._plot_widget.setLabel("left", "Distance", units="mm")
        self._plot_widget.setLabel("bottom", "Samples")
        self._plot_widget.setYRange(0, self.DISPLAY_MAX_MM)
        self._plot_widget.setBackground("#1a1a1a")
        self._plot_curve = self._plot_widget.plot(pen=pg.mkPen(color="#00ff55", width=2))
        layout.addWidget(self._plot_widget, stretch=1)

        ctrl = QHBoxLayout()
        self._start_btn = QPushButton("Start")
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        ctrl.addWidget(self._start_btn)
        ctrl.addWidget(self._stop_btn)
        layout.addLayout(ctrl)

        self.setStyleSheet("""
            QMainWindow, QWidget { background: #121212; color: #e0e0e0; }
            QPushButton {
                background: #1e1e1e; border: 1px solid #444;
                border-radius: 4px; padding: 8px 16px;
                color: #e0e0e0; font-size: 13px;
            }
            QPushButton:hover { background: #2a2a2a; }
            QPushButton:disabled { color: #555; }
        """)

    def _setup_timer(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(self.UPDATE_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    def _on_start(self) -> None:
        self._sensor.start()
        self._running = True
        self._timer.start()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _on_stop(self) -> None:
        self._timer.stop()
        self._sensor.stop()
        self._running = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _tick(self) -> None:
        reading = self._sensor.read()

        self._data_buffer[self._buf_idx % self.BUFFER_SIZE] = reading.distance_mm
        self._buf_idx += 1

        if reading.valid:
            self._dist_label.setText(f"{reading.distance_mm} mm")
            color = "#00cc44" if reading.distance_mm > 300 else "#ff4444"
            self._dist_label.setStyleSheet(f"color: {color};")
        elif reading.status == 2:
            self._dist_label.setText("…")
            self._dist_label.setStyleSheet("color: #888;")
        elif reading.status == 4:
            self._dist_label.setText("NO TARGET")
            self._dist_label.setStyleSheet("color: #ffaa44;")
        else:
            self._dist_label.setText("ERR")
            self._dist_label.setStyleSheet("color: #ff4444;")

        filled = min(self._buf_idx, self.BUFFER_SIZE)
        if self._buf_idx >= self.BUFFER_SIZE:
            # Unroll ring buffer into chronological order (oldest → newest)
            ordered = np.roll(self._data_buffer, -(self._buf_idx % self.BUFFER_SIZE))
        else:
            ordered = self._data_buffer[:filled]

        self._plot_curve.setData(ordered)

    def closeEvent(self, event) -> None:
        if self._running:
            self._on_stop()
        event.accept()
