"""
3D visualization using pyqtgraph.opengl.
Shows detected targets as glowing points in 3D space with a history trail.
Designed for both fixed-sensor mode (targets along Z-axis) and
future servo-scan mode (targets spread across XZ-plane).
"""

import numpy as np
from collections import deque

import pyqtgraph.opengl as gl


class View3DWidget(gl.GLViewWidget):
    MAX_RANGE_MM = 3000
    TRAIL_LENGTH = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.setCameraPosition(distance=4000, elevation=25, azimuth=45)
        self.setBackgroundColor(10, 12, 10)

        self._trail: deque[list[np.ndarray]] = deque(maxlen=self.TRAIL_LENGTH)
        self._sweep_angle = 0.0

        self._setup_scene()

    def _setup_scene(self) -> None:
        grid = gl.GLGridItem()
        grid.setSize(4000, 4000)
        grid.setSpacing(500, 500)
        grid.setColor((40, 80, 40, 80))
        self.addItem(grid)

        self._origin_dot = gl.GLScatterPlotItem(
            pos=np.array([[0, 0, 0]]),
            color=np.array([[0.2, 0.8, 0.2, 1.0]]),
            size=10,
            pxMode=True,
        )
        self.addItem(self._origin_dot)

        axis_lines = np.array([
            [0, 0, 0], [500, 0, 0],
            [0, 0, 0], [0, 500, 0],
            [0, 0, 0], [0, 0, 500],
        ])
        axis_colors = np.array([
            [1, 0.2, 0.2, 0.6], [1, 0.2, 0.2, 0.6],
            [0.2, 1, 0.2, 0.6], [0.2, 1, 0.2, 0.6],
            [0.2, 0.2, 1, 0.6], [0.2, 0.2, 1, 0.6],
        ])
        self._axes = gl.GLLinePlotItem(
            pos=axis_lines, color=axis_colors, width=2, mode="lines"
        )
        self.addItem(self._axes)

        self._range_rings = []
        for r_mm in [500, 1000, 1500, 2000, 2500, 3000]:
            theta = np.linspace(0, 2 * np.pi, 64)
            ring_pts = np.column_stack([
                r_mm * np.cos(theta),
                np.zeros(64),
                r_mm * np.sin(theta),
            ])
            ring = gl.GLLinePlotItem(
                pos=ring_pts, color=(0.15, 0.5, 0.15, 0.3), width=1
            )
            self.addItem(ring)
            self._range_rings.append(ring)

        self._target_scatter = gl.GLScatterPlotItem(
            pos=np.zeros((1, 3)),
            color=np.array([[0, 1, 0.3, 1.0]]),
            size=18,
            pxMode=True,
        )
        self.addItem(self._target_scatter)

        self._trail_scatter = gl.GLScatterPlotItem(
            pos=np.zeros((1, 3)),
            color=np.array([[0, 1, 0.3, 0.1]]),
            size=4,
            pxMode=True,
        )
        self.addItem(self._trail_scatter)

        self._beam_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, 0, 1000]]),
            color=(0, 1, 0.2, 0.3),
            width=1.5,
        )
        self.addItem(self._beam_line)

    def update_targets(self, targets_mm: list[int], sweep_angle: float | None = None) -> None:
        """
        Update with new target distances.
        targets_mm: list of distances in mm (1-2 values from multi-target).
        sweep_angle: if set, places targets radially (for servo-scan mode).
                     If None, targets are placed along the Z-axis (fixed sensor).
        """
        if sweep_angle is not None:
            self._sweep_angle = sweep_angle
        else:
            self._sweep_angle = (self._sweep_angle + 3) % 360

        angle_rad = np.radians(self._sweep_angle)

        live_points = []
        for dist in targets_mm:
            if dist <= 0 or dist >= self.MAX_RANGE_MM:
                continue
            x = dist * np.sin(angle_rad)
            z = dist * np.cos(angle_rad)
            live_points.append(np.array([x, 0, z]))

        if not live_points:
            return

        points = np.array(live_points)
        n = len(points)
        colors = np.zeros((n, 4))
        sizes = np.zeros(n)
        for i, dist in enumerate(targets_mm[:n]):
            intensity = 1.0 - (dist / self.MAX_RANGE_MM) * 0.6
            if i == 0:
                colors[i] = [0, 1, 0.3, intensity]
                sizes[i] = 20
            else:
                colors[i] = [0.3, 0.6, 1, intensity * 0.8]
                sizes[i] = 14

        self._target_scatter.setData(pos=points, color=colors, size=sizes)

        furthest = max(targets_mm)
        beam_end = np.array([
            furthest * 1.2 * np.sin(angle_rad),
            0,
            furthest * 1.2 * np.cos(angle_rad),
        ])
        self._beam_line.setData(pos=np.array([[0, 0, 0], beam_end]))

        self._trail.append(live_points)
        self._rebuild_trail()

    def _rebuild_trail(self) -> None:
        all_pts = []
        all_colors = []
        total = len(self._trail)
        for i, frame_pts in enumerate(self._trail):
            age = (i + 1) / total
            for pt in frame_pts:
                all_pts.append(pt)
                alpha = 0.05 + 0.25 * age
                all_colors.append([0, 0.8 * age, 0.3 * age, alpha])

        if not all_pts:
            return

        self._trail_scatter.setData(
            pos=np.array(all_pts),
            color=np.array(all_colors),
            size=4,
        )
