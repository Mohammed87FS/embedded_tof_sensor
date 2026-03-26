"""
Sonar/radar-style visualization widget for distance data.
Draws concentric rings and a sweep line with distance indication.
"""

import math
from collections import deque

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QFont
from PyQt6.QtWidgets import QWidget


class SonarWidget(QWidget):
    MAX_RANGE_MM = 3000
    RING_COUNT = 6
    HISTORY_SIZE = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self._distance_mm = 0
        self._history: deque[int] = deque(maxlen=self.HISTORY_SIZE)
        self._sweep_angle = 0.0

        self._bg_color = QColor(10, 15, 10)
        self._ring_color = QColor(0, 180, 0, 60)
        self._sweep_color = QColor(0, 255, 0, 120)
        self._blip_color = QColor(0, 255, 80, 200)
        self._text_color = QColor(0, 200, 0)
        self._faded_blip = QColor(0, 255, 80, 40)

    def update_distance(self, distance_mm: int) -> None:
        self._distance_mm = distance_mm
        self._history.append(distance_mm)
        self._sweep_angle = (self._sweep_angle + 6) % 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2
        radius = side * 0.45

        painter.fillRect(self.rect(), self._bg_color)

        # Concentric range rings
        pen = QPen(self._ring_color, 1)
        painter.setPen(pen)
        for i in range(1, self.RING_COUNT + 1):
            r = radius * i / self.RING_COUNT
            painter.drawEllipse(QPointF(cx, cy), r, r)

        # Ring labels
        font = QFont("Monospace", 8)
        painter.setFont(font)
        painter.setPen(QPen(self._text_color, 1))
        for i in range(1, self.RING_COUNT + 1):
            r = radius * i / self.RING_COUNT
            label = f"{int(self.MAX_RANGE_MM * i / self.RING_COUNT)} mm"
            painter.drawText(QPointF(cx + 4, cy - r + 12), label)

        # Crosshairs
        painter.setPen(QPen(self._ring_color, 0.5))
        painter.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))
        painter.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))

        # Sweep line
        angle_rad = math.radians(self._sweep_angle)
        sx = cx + radius * math.cos(angle_rad)
        sy = cy - radius * math.sin(angle_rad)
        sweep_pen = QPen(self._sweep_color, 2)
        painter.setPen(sweep_pen)
        painter.drawLine(QPointF(cx, cy), QPointF(sx, sy))

        # Sweep fade trail
        for i in range(1, 20):
            trail_angle = math.radians(self._sweep_angle - i * 2)
            trail_x = cx + radius * math.cos(trail_angle)
            trail_y = cy - radius * math.sin(trail_angle)
            alpha = max(5, 120 - i * 6)
            trail_pen = QPen(QColor(0, 180, 0, alpha), 1)
            painter.setPen(trail_pen)
            painter.drawLine(QPointF(cx, cy), QPointF(trail_x, trail_y))

        # Distance blip on sweep line
        if 0 < self._distance_mm < self.MAX_RANGE_MM:
            blip_r = (self._distance_mm / self.MAX_RANGE_MM) * radius
            bx = cx + blip_r * math.cos(angle_rad)
            by = cy - blip_r * math.sin(angle_rad)

            glow = QRadialGradient(QPointF(bx, by), 12)
            glow.setColorAt(0, self._blip_color)
            glow.setColorAt(1, QColor(0, 255, 80, 0))
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(bx, by), 8, 8)

        # Faded history blips
        for idx, dist in enumerate(self._history):
            if dist <= 0 or dist >= self.MAX_RANGE_MM:
                continue
            hist_angle = math.radians(self._sweep_angle - (len(self._history) - idx) * 6)
            hist_r = (dist / self.MAX_RANGE_MM) * radius
            hx = cx + hist_r * math.cos(hist_angle)
            hy = cy - hist_r * math.sin(hist_angle)
            age_alpha = max(10, int(40 * (idx / max(len(self._history), 1))))
            painter.setBrush(QBrush(QColor(0, 255, 80, age_alpha)))
            painter.drawEllipse(QPointF(hx, hy), 3, 3)

        # Distance text overlay
        painter.setPen(QPen(self._text_color, 1))
        big_font = QFont("Monospace", 14, QFont.Weight.Bold)
        painter.setFont(big_font)
        dist_text = f"{self._distance_mm} mm" if self._distance_mm > 0 else "---"
        painter.drawText(
            QRectF(cx - 80, cy + radius * 0.6, 160, 30),
            Qt.AlignmentFlag.AlignCenter,
            dist_text,
        )

        painter.end()
