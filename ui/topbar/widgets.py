import sys
from PyQt6.QtWidgets import QWidget, QSizePolicy, QDialog, QVBoxLayout, QProgressBar, QLabel
from PyQt6.QtGui import QPainter, QColor, QPen, QGuiApplication
from PyQt6.QtCore import Qt, QTimer

# --- HELPER FUNCTION (This was missing) ---
def cm_to_px(cm: float) -> int:
    screen = QGuiApplication.primaryScreen()
    if not screen:
        return int(cm * 37.795) # Fallback if no screen detected
    dpi = screen.physicalDotsPerInch() or screen.logicalDotsPerInch() or 96
    inch_per_cm = 1 / 2.54
    return int(cm * inch_per_cm * dpi)

# --- ICONS ---
class SettingsIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#808080"))
        # Draw gear shape
        painter.drawEllipse(1, 1, 14, 14)
        painter.setBrush(QColor("#0f0f19")) # Hole in middle
        painter.drawEllipse(5, 5, 6, 6)

    def mousePressEvent(self, event):
        if self.menu:
            self.menu.exec(self.mapToGlobal(event.pos()))

    def set_menu(self, menu):
        self.menu = menu

class CloseIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color = QColor("#ffffff")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(4, 4, self.width()-4, self.height()-4)
        painter.drawLine(4, self.height()-4, self.width()-4, 4)
        
    def mousePressEvent(self, event):
        sys.exit()

# --- PROGRESS DIALOG ---
class VoiceProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Siris Voice Training")
        self.setFixedSize(400, 150)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Styling
        self.setStyleSheet("""
            QDialog { 
                background-color: rgba(15, 15, 20, 250); 
                border: 1px solid #333; 
                border-radius: 10px;
            }
            QLabel { 
                color: #00ffff; 
                font-family: 'Segoe UI';
                font-size: 12pt; 
                font-weight: bold; 
                background: transparent;
            }
            QProgressBar {
                border: 1px solid #333;
                background-color: #1a1a1a;
                height: 10px;
                text-align: center;
                color: transparent;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #00ffff;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.status_label = QLabel("Initializing...", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        layout.addWidget(self.status_label)
        layout.addSpacing(10)
        layout.addWidget(self.progress_bar)

    def update_status(self, percent, text):
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)
        if percent >= 100:
            QTimer.singleShot(1500, self.accept)