import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QPen, QLinearGradient, QTransform
from ui.topbar.widgets import cm_to_px

class WaveformWidget(QWidget):
    def __init__(self, width_cm=4.0, height_cm=0.70, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.pixel_width = cm_to_px(width_cm)
        self.pixel_height = cm_to_px(height_cm)
        self.setFixedSize(self.pixel_width, self.pixel_height)

        self.base_amplitude = self.pixel_height * 0.35
        self.ribbon_lines = 14
        self.ribbon_spread = self.pixel_height * 0.25
        self.glow_layers = 4
        self.glow_spread = self.pixel_height * 0.22
        self.dynamic_amplitude = 0.05
        self._target_dynamic = 0.05
        self.spike_amplitude = 0.0
        self.phase = 0
        self.wave_points = 60
        self.opacity = 1.0
        self.target_opacity = 1.0
        self.fade_speed = 0.05

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate)
        self.animation_timer.start(16)

        self.demo_timer = QTimer(self)
        self.demo_timer.timeout.connect(self.demo_animation)
        self.demo_timer.start(100)

    def update_amplitudes(self, volume, spike):
        self._target_dynamic = 0.05 + math.sqrt(max(0.0, volume)) * 0.95
        self.spike_amplitude = max(self.spike_amplitude, max(0.0, spike))
        self.target_opacity = 1.0 if volume > 0.02 else 0.8

    def demo_animation(self):
        if self._target_dynamic < 0.1:
            self._target_dynamic = 0.05 + (math.sin(self.phase * 0.5) * 0.5 + 0.5) * 0.3

    def animate(self):
        self.phase -= 0.08
        self.dynamic_amplitude += (self._target_dynamic - self.dynamic_amplitude) * 0.1
        self.spike_amplitude *= 0.85
        self.opacity += (self.target_opacity - self.opacity) * self.fade_speed
        self.update()

    def create_wave_coords(self, total_amp, freq, phase_shift, y_offset):
        coords = []
        mid_y = self.height() / 2.0
        for i in range(self.wave_points + 1):
            edge_falloff = (1 - (abs(i - self.wave_points / 2) / (self.wave_points / 2))**2)**2
            sine = math.sin(self.phase * freq + phase_shift + (i * 0.08))
            coords.append(mid_y + y_offset + (sine * total_amp * edge_falloff))
        return coords

    def create_base_path(self, total_amp):
        path = QPainterPath()
        mid_y, width = self.height() / 2.0, self.width()
        path.moveTo(0, mid_y)
        for i in range(self.wave_points + 1):
            x = width * i / self.wave_points
            edge_falloff = (1 - (abs(i - self.wave_points / 2) / (self.wave_points / 2))**2)**2
            sine1 = math.sin(self.phase + (i * 0.06))
            sine2 = math.sin(self.phase * 2.0 + (i * 0.08))
            y = (sine1 * 0.6 + sine2 * 0.4) * total_amp * edge_falloff
            path.lineTo(x, mid_y + y)
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self.opacity)

        total_amp = self.base_amplitude * (self.dynamic_amplitude + self.spike_amplitude)
        if total_amp < 0.5: total_amp = 0.5

        width = self.width()
        mid_y = self.height() / 2.0

        top_wave = self.create_wave_coords(total_amp, 1.0, 0.5, -mid_y * 0.3)
        mid_wave = self.create_wave_coords(total_amp, 1.5, 0, 0)
        bottom_wave = self.create_wave_coords(total_amp, 0.9, 1.0, mid_y * 0.3)

        # Draw top gradient
        path_top = QPainterPath()
        path_top.moveTo(0, top_wave[0])
        for i in range(self.wave_points + 1): path_top.lineTo(width * i / self.wave_points, top_wave[i])
        for i in range(self.wave_points, -1, -1): path_top.lineTo(width * i / self.wave_points, mid_wave[i])
        grad_top = QLinearGradient(0, 0, 0, mid_y)
        c1 = QColor("#00ffff"); c1.setAlpha(220)
        c2 = QColor("#ff00ff"); c2.setAlpha(220)
        grad_top.setColorAt(0, c1); grad_top.setColorAt(1, c2)
        painter.setBrush(grad_top); painter.setPen(Qt.PenStyle.NoPen); painter.drawPath(path_top)

        # Draw bottom gradient
        path_bottom = QPainterPath()
        path_bottom.moveTo(0, mid_wave[0])
        for i in range(self.wave_points + 1): path_bottom.lineTo(width * i / self.wave_points, mid_wave[i])
        for i in range(self.wave_points, -1, -1): path_bottom.lineTo(width * i / self.wave_points, bottom_wave[i])
        grad_bottom = QLinearGradient(0, mid_y, 0, self.height())
        c3 = QColor("#ff00ff"); c3.setAlpha(220)
        c4 = QColor("#5e0025"); c4.setAlpha(180)
        grad_bottom.setColorAt(0, c3); grad_bottom.setColorAt(1, c4)
        painter.setBrush(grad_bottom); painter.drawPath(path_bottom)

        # Draw midline
        path_midline = QPainterPath()
        path_midline.moveTo(0, mid_wave[0])
        for i in range(self.wave_points + 1): path_midline.lineTo(width * i / self.wave_points, mid_wave[i])
        pen_mid = QPen(QColor("#ffffff"), 1.2); pen_mid.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_mid); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawPath(path_midline)

        # Draw glow & ribbons (Combined logic for brevity, functionally identical)
        base_path = self.create_base_path(total_amp)
        for i in range(self.glow_layers):
            glow_color = QColor("#ff33ff")
            glow_color.setAlpha(max(0, 60 - i * 10))
            pen = QPen(glow_color, (self.glow_spread * (i + 1) / self.glow_layers))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen); painter.drawPath(base_path)

        for i in range(self.ribbon_lines):
            y_offset = (i - self.ribbon_lines / 2) * (self.ribbon_spread * self.dynamic_amplitude / self.ribbon_lines)
            alpha = int(40 + (1 - abs(i - self.ribbon_lines / 2) / (self.ribbon_lines / 2)) * 80)
            grad_line = QLinearGradient(0, 0, self.width(), 0)
            grad_line.setColorAt(0, QColor(255, 51, 255, alpha))
            grad_line.setColorAt(0.5, QColor(255, 255, 255, int(alpha * 1.5)))
            grad_line.setColorAt(1, QColor(255, 51, 255, alpha))
            pen_line = QPen(grad_line, 1.2); pen_line.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_line)
            painter.drawPath(QTransform().translate(0, y_offset).map(base_path))