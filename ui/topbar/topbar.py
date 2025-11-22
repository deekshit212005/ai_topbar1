import sys
import os
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QMenu, 
                             QScrollArea, QFrame, QFileDialog, QMessageBox, QInputDialog)
from PyQt6.QtGui import QGuiApplication, QFont, QAction
from PyQt6.QtCore import Qt, pyqtSignal

from ui.topbar.widgets import cm_to_px, CloseIcon, SettingsIcon, VoiceProgressDialog
from ui.topbar.waveform import WaveformWidget

class TopBarUI(QWidget):
    setting_changed = pyqtSignal(str, str)
    add_voice_signal = pyqtSignal(str, str)

    def __init__(self, initial_settings=None, parent=None):
        super().__init__(parent)
        self.settings = initial_settings or {}
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("background-color: rgba(10, 10, 15, 250);")

        screen_geo = QGuiApplication.primaryScreen().availableGeometry()
        # Increased height by 50% (0.70 + 0.70/2 = 1.05)
        self.bar_height = cm_to_px(1.05)
        self.bar_width = screen_geo.width()
        
        self.setFixedSize(self.bar_width, self.bar_height)
        self.move(0, 0)

        # --- LAYOUT ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 0, 10, 0)
        main_layout.setSpacing(0)

        # 1. LEFT: Icons
        self.icons_widget = QWidget()
        self.icons_layout = QHBoxLayout(self.icons_widget)
        self.icons_layout.setContentsMargins(0,0,0,0)
        self.icons_layout.setSpacing(12)
        
        self.close_btn = CloseIcon()
        self.settings_btn = SettingsIcon()
        
        # Load Internet State from Settings
        self.internet_enabled = self.settings.get("internet", True)
        self.setup_settings_menu()
        
        self.icons_layout.addWidget(self.close_btn)
        self.icons_layout.addWidget(self.settings_btn)
        
        # 2. CENTER: Text Area (50%)
        self.center_container = QWidget()
        self.center_container.setFixedWidth(int(self.bar_width * 0.50))
        self.center_layout = QHBoxLayout(self.center_container)
        self.center_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.scroll_area.setStyleSheet("""
            QScrollArea { 
                background: rgba(30, 30, 40, 150); 
                border: 1px solid rgba(100, 100, 255, 50); 
                border-radius: 10px;
            }
            QScrollBar:vertical { background: #1a1a1a; width: 4px; }
            QScrollBar::handle:vertical { background: #00ffff; border-radius: 2px; } 
        """)

        self.status_label = QLabel("Siris Online. Press Ctrl+Space.", self)
        font = QFont("Segoe UI", 11); font.setBold(True)
        self.status_label.setFont(font)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.RichText)  # Enable HTML formatting
        self.status_label.setStyleSheet("color: #00ffff; background: transparent; letter-spacing: 1px; padding: 5px;")

        self.scroll_area.setWidget(self.status_label)
        self.center_layout.addWidget(self.scroll_area)

        # 3. RIGHT: Waveform (updated to match new topbar height)
        self.waveform = WaveformWidget(width_cm=3.5, height_cm=1.05, parent=self)

        main_layout.addWidget(self.icons_widget, 0, Qt.AlignmentFlag.AlignLeft)
        main_layout.addStretch(1)
        main_layout.addWidget(self.center_container, 0, Qt.AlignmentFlag.AlignCenter)
        main_layout.addStretch(1)
        main_layout.addWidget(self.waveform, 0, Qt.AlignmentFlag.AlignRight)

        self.progress_dialog = None
        self.current_text = ""  # Store current text for highlighting
        self.current_words = []  # Store words list

        if sys.platform.startswith("win"):
            try: self._register_appbar()
            except: pass

    def highlight_word(self, word_index, word_text, total_words):
        """Highlight the currently spoken word and jump scroll"""
        if not self.current_words:
            return
        
        # Build HTML with highlighted word
        html_parts = []
        for i, word in enumerate(self.current_words):
            if i < word_index:
                # Already spoken - full white
                html_parts.append(f'<span style="color: #ffffff;">{word}</span>')
            elif i == word_index:
                # Currently speaking - cyan and bold
                html_parts.append(f'<span style="color: #00ffff; font-weight: bold;">{word}</span>')
            else:
                # Not yet spoken - light white
                html_parts.append(f'<span style="color: #cccccc;">{word}</span>')
        
        html_text = ' '.join(html_parts)
        self.status_label.setText(html_text)
        
        # Jump scroll instead of smooth scroll
        # Calculate approximate position of current word
        label_height = self.status_label.height()
        scroll_area_height = self.scroll_area.height()
        
        # Estimate vertical position based on word index
        progress = word_index / total_words if total_words > 0 else 0
        target_y = int(progress * label_height)
        
        # Jump to target position (no animation)
        scroll_value = max(0, target_y - scroll_area_height // 2)
        # Disable smooth scrolling by setting value directly
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scroll_value)
    
    def set_text_for_highlighting(self, text):
        """Store text and prepare for word highlighting"""
        self.current_text = text
        self.current_words = text.split()
        
        # Initialize with all words in light white
        html_parts = [f'<span style="color: #cccccc;">{word}</span>' for word in self.current_words]
        html_text = ' '.join(html_parts)
        self.status_label.setText(html_text)
        
        # Scroll to bottom to keep new input visible
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def setup_settings_menu(self):
        self.menu = QMenu(self)
        self.menu.setStyleSheet("""
            QMenu { background-color: #0f0f15; color: #00ffff; border: 1px solid #333; font-weight: bold; }
            QMenu::item { padding: 6px 25px; }
            QMenu::item:selected { background-color: #222; color: #fff; }
        """)
        
        # 1. Internet
        self.web_action = QAction(self.get_internet_icon_text(), self.menu)
        self.web_action.triggered.connect(self.toggle_internet_state)
        self.menu.addAction(self.web_action)
        self.menu.addSeparator()

        # 2. AI Model
        model_menu = self.menu.addMenu("🧠 Siris Brain")
        current_model = self.settings.get("model", "llama_1b")
        for m in ["llama_1b", "Qwen3VL-4B-Thinking", "vibe_1.5b"]:
            a = model_menu.addAction(f"{m} {'(Active)' if m == current_model else ''}")
            a.triggered.connect(lambda checked, x=m: self.setting_changed.emit("model", x))

        # 3. Output Mode
        out_menu = self.menu.addMenu("🔊 Output Settings")
        mode_menu = out_menu.addMenu("Mode")
        current_out = self.settings.get("output", "Both")
        for o in ["Text Only", "Speech Only", "Both"]:
            a = mode_menu.addAction(f"{o} {'(✓)' if o == current_out else ''}")
            a.triggered.connect(lambda checked, x=o: self.setting_changed.emit("output", x))
            
        # Voices
        self.voice_menu = out_menu.addMenu("Select Voice")
        self.refresh_voice_list()

        # 4. Input Mode
        in_menu = self.menu.addMenu("🎤 Input Mode")
        current_in = self.settings.get("input", "Microphone")
        for i in ["Microphone", "System Audio"]:
            a = in_menu.addAction(f"{i} {'(✓)' if i == current_in else ''}")
            a.triggered.connect(lambda checked, x=i: self.setting_changed.emit("input", x))

        self.menu.addSeparator()
        
        voice_action = self.menu.addAction("🎙️ Add New Voice")
        voice_action.triggered.connect(self.open_voice_dialog)

        self.settings_btn.set_menu(self.menu)

    def refresh_voice_list(self):
        self.voice_menu.clear()
        voices_dir = "models/voices"
        if not os.path.exists(voices_dir): os.makedirs(voices_dir)
        files = [f for f in os.listdir(voices_dir) if f.endswith(".json")]
        
        current_voice = self.settings.get("last_voice", "default")
        
        if not files:
            self.voice_menu.addAction("No voices found").setEnabled(False)
            return

        for f in files:
            voice_name = os.path.splitext(f)[0]
            label = f"🗣️ {voice_name} {'(Active)' if voice_name == current_voice else ''}"
            a = self.voice_menu.addAction(label)
            a.triggered.connect(lambda checked, x=voice_name: self.setting_changed.emit("voice_select", x))

    def get_internet_icon_text(self):
        return "🌍 Internet Access: ON 🟢" if self.internet_enabled else "🌍 Internet Access: OFF 🔴"

    def toggle_internet_state(self):
        self.internet_enabled = not self.internet_enabled
        self.web_action.setText(self.get_internet_icon_text())
        self.setting_changed.emit("internet", str(self.internet_enabled))

    def open_voice_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Voice Sample", "", "Audio (*.wav *.mp3)")
        if path:
            text, ok = QInputDialog.getText(self, "Voice Name", "Enter a name for this voice:")
            if ok and text:
                self.progress_dialog = VoiceProgressDialog(self)
                self.progress_dialog.show()
                self.add_voice_signal.emit(text, path)

    def _register_appbar(self):
        ABM_NEW = 0x00000000; ABM_SETPOS = 0x00000003; ABE_TOP = 1
        class APPBARDATA(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uCallbackMessage", wintypes.UINT),
                        ("uEdge", wintypes.UINT), ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]
        self.abd = APPBARDATA(); self.abd.cbSize = ctypes.sizeof(APPBARDATA); self.abd.hWnd = int(self.winId()); self.abd.uEdge = ABE_TOP
        ctypes.windll.shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(self.abd))
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.abd.rc.left = 0; self.abd.rc.top = 0; self.abd.rc.right = screen.width(); self.abd.rc.bottom = self.bar_height
        ctypes.windll.shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(self.abd))
        self.setGeometry(self.abd.rc.left, self.abd.rc.top, self.abd.rc.right - self.abd.rc.left, self.abd.rc.bottom - self.abd.rc.top)
