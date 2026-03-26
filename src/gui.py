"""
Main GUI window — live distance display, time-series graph, sonar, and 3D visualization.
Supports multi-target display from VL53L3CX.
"""

import numpy as np
import pyqtgraph as pg

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QGridLayout, QTabWidget,
)

from sensor import BaseSensor, SensorReading
from sonar_widget import SonarWidget
from view3d_widget import View3DWidget


class MainWindow(QMainWindow):
    BUFFER_SIZE = 200
    UPDATE_INTERVAL_MS = 100

    def __init__(self, sensor: BaseSensor):
        super().__init__()
        self._sensor = sensor
        self._running = False
        self._data_buf_t1 = np.zeros(self.BUFFER_SIZE)
        self._data_buf_t2 = np.zeros(self.BUFFER_SIZE)
        self._buf_idx = 0

        self.setWindowTitle("VL53L3CX — ToF Distance Monitor")
        self.setMinimumSize(1050, 650)
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        left = QVBoxLayout()

        # --- Primary distance ---
        dist_group = QGroupBox("Target 1 (nearest)")
        dist_layout = QVBoxLayout(dist_group)
        self._dist_label = QLabel("--- mm")
        self._dist_label.setFont(QFont("Monospace", 34, QFont.Weight.Bold))
        self._dist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dist_label.setStyleSheet("color: #00cc44;")
        dist_layout.addWidget(self._dist_label)
        left.addWidget(dist_group)

        # --- Secondary target ---
        t2_group = QGroupBox("Target 2 (far)")
        t2_layout = QVBoxLayout(t2_group)
        self._t2_label = QLabel("--- mm")
        self._t2_label.setFont(QFont("Monospace", 20, QFont.Weight.Bold))
        self._t2_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._t2_label.setStyleSheet("color: #4488ff;")
        t2_layout.addWidget(self._t2_label)
        left.addWidget(t2_group)

        # --- Stats ---
        stats_group = QGroupBox("Statistics")
        stats_grid = QGridLayout(stats_group)
        self._min_label = QLabel("Min: ---")
        self._max_label = QLabel("Max: ---")
        self._avg_label = QLabel("Avg: ---")
        self._targets_label = QLabel("Targets: 0")
        for i, lbl in enumerate([self._min_label, self._max_label,
                                  self._avg_label, self._targets_label]):
            lbl.setFont(QFont("Monospace", 11))
            stats_grid.addWidget(lbl, i // 2, i % 2)
        left.addWidget(stats_group)

        # --- Controls ---
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

        # --- Right panel: graph + tabbed viz ---
        right = QVBoxLayout()

        # Time-series graph (both targets)
        pg.setConfigOptions(antialias=True)
        self._plot_widget = pg.PlotWidget(title="Distance Over Time")
        self._plot_widget.setLabel("left", "Distance", units="mm")
        self._plot_widget.setLabel("bottom", "Samples")
        self._plot_widget.setYRange(0, 3000)
        self._plot_widget.setBackground("#1a1a1a")
        self._plot_widget.addLegend(offset=(10, 10))
        self._curve_t1 = self._plot_widget.plot(
            pen=pg.mkPen(color="#00ff55", width=2), name="Target 1"
        )
        self._curve_t2 = self._plot_widget.plot(
            pen=pg.mkPen(color="#4488ff", width=2, style=Qt.PenStyle.DashLine),
            name="Target 2",
        )
        right.addWidget(self._plot_widget, stretch=2)

        # Tabbed visualization: Sonar | 3D View
        self._viz_tabs = QTabWidget()
        self._viz_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #333; background: #0a0f0a; }
            QTabBar::tab {
                background: #1e1e1e; color: #aaa; padding: 6px 16px;
                border: 1px solid #333; border-bottom: none; border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected { background: #0a0f0a; color: #00ff55; }
        """)
        self._sonar = SonarWidget()
        self._view3d = View3DWidget()
        self._viz_tabs.addTab(self._sonar, "Sonar")
        self._viz_tabs.addTab(self._view3d, "3D View")
        right.addWidget(self._viz_tabs, stretch=2)

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
        reading: SensorReading = self._sensor.read()
        valid_targets = [t for t in reading.targets if t.valid]
        idx = self._buf_idx % self.BUFFER_SIZE

        t1_dist = valid_targets[0].distance_mm if len(valid_targets) >= 1 else 0
        t2_dist = valid_targets[1].distance_mm if len(valid_targets) >= 2 else 0
        self._data_buf_t1[idx] = t1_dist
        self._data_buf_t2[idx] = t2_dist
        self._buf_idx += 1

        # Target 1 label
        if t1_dist > 0:
            self._dist_label.setText(f"{t1_dist} mm")
            color = "#00cc44" if t1_dist > 300 else "#ff4444"
            self._dist_label.setStyleSheet(f"color: {color};")
        else:
            self._dist_label.setText("---")
            self._dist_label.setStyleSheet("color: #555;")

        # Target 2 label
        if t2_dist > 0:
            self._t2_label.setText(f"{t2_dist} mm")
            self._t2_label.setStyleSheet("color: #4488ff;")
        else:
            self._t2_label.setText("---")
            self._t2_label.setStyleSheet("color: #555;")

        # Stats (based on primary target)
        filled = min(self._buf_idx, self.BUFFER_SIZE)
        data_slice = self._data_buf_t1[:filled]
        valid_data = data_slice[data_slice > 0]
        if len(valid_data) > 0:
            self._min_label.setText(f"Min: {int(valid_data.min())} mm")
            self._max_label.setText(f"Max: {int(valid_data.max())} mm")
            self._avg_label.setText(f"Avg: {int(valid_data.mean())} mm")
        self._targets_label.setText(f"Targets: {len(valid_targets)}")

        # Graph
        self._curve_t1.setData(self._data_buf_t1[:filled])
        t2_slice = self._data_buf_t2[:filled]
        if np.any(t2_slice > 0):
            self._curve_t2.setData(t2_slice)

        # Sonar (primary target)
        self._sonar.update_distance(t1_dist)

        # 3D view (all targets)
        target_distances = [t.distance_mm for t in valid_targets]
        if target_distances:
            self._view3d.update_targets(target_distances)

    def closeEvent(self, event) -> None:
        if self._running:
            self._on_stop()
        event.accept()
