"""
Main GUI window — live distance display, time-series graph, and sonar visualization.
Single-target mode.
"""

import numpy as np
import pyqtgraph as pg

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QGridLayout,
)

from sensor import BaseSensor
from sonar_widget import SonarWidget


class MainWindow(QMainWindow):
    BUFFER_SIZE = 200
    UPDATE_INTERVAL_MS = 100

    def __init__(self, sensor: BaseSensor):
        super().__init__()
        self._sensor = sensor
        self._running = False
        self._data_buffer = np.zeros(self.BUFFER_SIZE)
        self._buf_idx = 0

        self.setWindowTitle("VL53L3CX — ToF Distance Monitor")
        self.setMinimumSize(900, 600)
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # --- Left panel: metrics + controls ---
        left = QVBoxLayout()

        dist_group = QGroupBox("Live Distance")
        dist_layout = QVBoxLayout(dist_group)
        self._dist_label = QLabel("--- mm")
        self._dist_label.setFont(QFont("Monospace", 36, QFont.Weight.Bold))
        self._dist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dist_label.setStyleSheet("color: #00cc44;")
        dist_layout.addWidget(self._dist_label)
        left.addWidget(dist_group)

        stats_group = QGroupBox("Statistics")
        stats_grid = QGridLayout(stats_group)
        self._min_label = QLabel("Min: ---")
        self._max_label = QLabel("Max: ---")
        self._avg_label = QLabel("Avg: ---")
        self._signal_label = QLabel("Signal: ---")
        for i, lbl in enumerate([self._min_label, self._max_label,
                                  self._avg_label, self._signal_label]):
            lbl.setFont(QFont("Monospace", 11))
            stats_grid.addWidget(lbl, i // 2, i % 2)
        left.addWidget(stats_group)

        ctrl_group = QGroupBox("Controls")
        ctrl_layout = QHBoxLayout(ctrl_group)
        self._start_btn = QPushButton("Start")
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        ctrl_layout.addWidget(self._start_btn)
        ctrl_layout.addWidget(self._stop_btn)
        left.addWidget(ctrl_group)

        left.addStretch()
        root.addLayout(left, stretch=1)

        # --- Right panel: graph + sonar ---
        right = QVBoxLayout()

        pg.setConfigOptions(antialias=True)
        self._plot_widget = pg.PlotWidget(title="Distance Over Time")
        self._plot_widget.setLabel("left", "Distance", units="mm")
        self._plot_widget.setLabel("bottom", "Samples")
        self._plot_widget.setYRange(0, 3000)
        self._plot_widget.setBackground("#1a1a1a")
        self._plot_curve = self._plot_widget.plot(
            pen=pg.mkPen(color="#00ff55", width=2)
        )
        right.addWidget(self._plot_widget, stretch=2)

        self._sonar = SonarWidget()
        right.addWidget(self._sonar, stretch=2)

        root.addLayout(right, stretch=2)

        self.setStyleSheet("""
            QMainWindow, QWidget { background: #121212; color: #e0e0e0; }
            QGroupBox {
                border: 1px solid #333; border-radius: 6px;
                margin-top: 8px; padding-top: 14px; font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 4px;
            }
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
        else:
            self._dist_label.setText("ERR")
            self._dist_label.setStyleSheet("color: #ff4444;")

        filled = min(self._buf_idx, self.BUFFER_SIZE)
        data_slice = self._data_buffer[:filled]
        valid_data = data_slice[data_slice > 0]
        if len(valid_data) > 0:
            self._min_label.setText(f"Min: {int(valid_data.min())} mm")
            self._max_label.setText(f"Max: {int(valid_data.max())} mm")
            self._avg_label.setText(f"Avg: {int(valid_data.mean())} mm")
        self._signal_label.setText(f"Signal: {reading.signal_rate:.1f}")

        self._plot_curve.setData(data_slice)
        self._sonar.update_distance(reading.distance_mm)

    def closeEvent(self, event) -> None:
        if self._running:
            self._on_stop()
        event.accept()
