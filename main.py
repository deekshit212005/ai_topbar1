from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread

from ui.topbar.topbar import TopBarUI
from core.stt.whisper_engine import STTEngine
from core.llm.llama_engine import LLMEngine
from core.tools.search import google_search
from core.tts.voicetrainer import VoiceTrainer
from core.tts.voiceuser import VoiceUser
from core.chat.chat_manager import ChatManager
from core.chat.chat_namer import ChatNamer

class SirisWorker(QObject):
    response_ready = pyqtSignal(str)
    
    def __init__(self, llm, chat_manager, internet_default=True):
        super().__init__()
        self.llm = llm
        self.chat_manager = chat_manager
        self.use_internet = internet_default
    
    def process(self, query):
        # Get context from chat history
        history = self.chat_manager.get_context(limit=5)
        
        # Build context string or pass messages if LLM supports it
        # For now, we'll prepend recent history to the query if needed, 
        # but LLMEngine.generate takes a prompt. 
        # Ideally we should update LLMEngine to accept messages.
        # For now, we'll stick to simple prompt or context injection.
        
        if self.use_internet:
            search_results = google_search(query)
            context = f"Web Results:\\n{search_results}\\n\\nUser Query: {query}"
        else:
            context = query
            
        # Add history context if available (simple concatenation for now)
        if history:
            hist_text = "\\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
            full_prompt = f"History:\\n{hist_text}\\n\\nCurrent User Query: {context}"
        else:
            full_prompt = context
        
        response = self.llm.generate(full_prompt)
        self.response_ready.emit(response)

class SirisApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # 1. LOAD SETTINGS
        self.settings_file = "config/user_settings.json"
        self.settings = self.load_settings()
        
        # 2. INIT UI (Pass settings so checkboxes are correct)
        self.ui = TopBarUI(initial_settings=self.settings)
        
        # 3. INIT BACKEND (Use saved settings)
        self.stt = STTEngine()
        
        # Load Saved Model
        print(f"⚙️ Loading Saved Model: {self.settings['model']}")
        self.llm = LLMEngine(model_key=self.settings["model"])
        
        # Init Chat System
        self.chat_manager = ChatManager()
        self.chat_namer = ChatNamer(self.llm)
        
        self.worker = SirisWorker(self.llm, self.chat_manager, internet_default=self.settings["internet"])
        
        # TTS Components
        self.voice_trainer = None
        self.voice_user = None 
        self.training_thread = None
        
        # Initialize TTS if Output is "Speech" or "Both"
        if "Speech" in self.settings["output"] or "Both" in self.settings["output"]:
            print("⚙️ Initializing TTS System...")
            threading.Thread(target=self.init_tts).start()

        # Connections
        self.stt.transcription_ready.connect(self.handle_transcription)
        self.worker.response_ready.connect(self.handle_ai_response)
        self.ui.setting_changed.connect(self.handle_setting_change)
        self.ui.add_voice_signal.connect(self.train_new_voice)
        
        self.is_recording = False
        self.stream = None
        self.audio_buffer = []
        
        self.shortcut = QShortcut(QKeySequence("Ctrl+Space"), self.ui)
        self.shortcut.activated.connect(self.toggle_recording)
        
        self.ui.show()

    def load_settings(self):
        defaults = {
            "internet": True,
            "model": "llama_1b",
            "output": "Both",
            "input": "Microphone",
            "last_voice": "default"
        }
        try:
            with open(self.settings_file, "r") as f:
                data = json.load(f)
                # Merge with defaults to ensure no missing keys
                return {**defaults, **data}
        except:
            return defaults

    def save_settings(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"❌ Failed to save settings: {e}")

    def handle_setting_change(self, key, value):
        print(f"⚙️ Setting Change: {key} -> {value}")
        
        if key == "internet":
            self.settings["internet"] = (value == "True")
            self.worker.use_internet = self.settings["internet"]
            
        elif key == "output":
            self.settings["output"] = value
            if ("Speech" in value or "Both" in value) and self.voice_user is None:
                self.ui.status_label.setText("Initializing Voice...")
                threading.Thread(target=self.init_tts).start()

        elif key == "voice_select":
            self.settings["last_voice"] = value
            if not self.voice_user:
                self.init_tts() 
            else:
                self.voice_user.load_voice(value)
                self.ui.status_label.setText(f"Voice: {value}")
            
        elif key == "model":
            self.settings["model"] = value
            self.ui.status_label.setText(f"Loading {value}...")
            def switch():
                self.llm = LLMEngine(model_key=value)
                self.worker.llm = self.llm
                self.ui.status_label.setText("Siris Ready")
            threading.Thread(target=switch).start()
            
        elif key == "input":
            self.settings["input"] = value

        # Save immediately
        self.save_settings()
        # Update menu UI to reflect checkmarks
        self.ui.setup_settings_menu()

    def init_tts(self):
        if not self.voice_user:
            # Fix import if needed, but assuming VoiceUser is in core.tts.voiceuser
            from core.tts.voiceuser import VoiceUser
            self.voice_user = VoiceUser()
            # Connect word highlighting signal
            self.voice_user.word_spoken.connect(self.ui.highlight_word)
            # Load last used voice
            target_voice = self.settings.get("last_voice", "default")
            print(f"🗣️ Loading Saved Voice: {target_voice}")
            self.voice_user.load_voice(target_voice)

    def train_new_voice(self, name, path):
        self.voice_trainer = VoiceTrainer()
        self.training_thread = QThread()
        self.voice_trainer.moveToThread(self.training_thread)
        
        self.training_thread.started.connect(lambda: self.voice_trainer.process_voice(path, name))
        self.voice_trainer.progress_update.connect(self.ui.progress_dialog.update_status)
        self.voice_trainer.finished.connect(self.on_training_finished)
        self.voice_trainer.finished.connect(self.training_thread.quit)
        self.voice_trainer.finished.connect(self.voice_trainer.deleteLater)
        self.training_thread.finished.connect(self.training_thread.deleteLater)
        
        self.training_thread.start()

    def on_training_finished(self, voice_name):
        self.ui.refresh_voice_list()
        # Auto-select new voice
        self.settings["last_voice"] = voice_name
        self.save_settings()
        
        if self.voice_user:
            self.voice_user.load_voice(voice_name)
        self.ui.status_label.setText(f"Voice '{voice_name}' Ready")

    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.ui.status_label.setText("Siris Listening...")
            self.ui.status_label.setStyleSheet("color: #ff00ff; background: transparent; font-weight: bold;")
            self.audio_buffer = []
            
            device_idx = None
            if self.settings["input"] == "System Audio":
                 try:
                    devs = sd.query_devices()
                    for i, dev in enumerate(devs):
                        if "Stereo Mix" in dev['name'] and dev['max_input_channels'] > 0:
                            device_idx = i
                            break
                 except: pass

            try:
                self.stream = sd.InputStream(device=device_idx, channels=1, samplerate=16000, callback=self.audio_callback)
                self.stream.start()
            except:
                self.ui.status_label.setText("Mic Error")
        else:
            self.is_recording = False
            self.ui.status_label.setText("Siris Thinking...")
            self.ui.status_label.setStyleSheet("color: #00ffff; background: transparent; font-weight: bold;")
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
            
            if len(self.audio_buffer) > 0:
                full_audio = np.concatenate(self.audio_buffer, axis=0)
                threading.Thread(target=lambda: self.stt.transcribe_audio(full_audio)).start()

    def audio_callback(self, indata, frames, time, status):
        if self.is_recording:
            self.audio_buffer.append(indata.copy())
            try:
                vol = np.linalg.norm(indata) * 5
                self.ui.waveform.update_amplitudes(vol, vol)
            except: pass

    def handle_transcription(self, text):
        if not text:
            self.reset_ui()
            return
        
        self.ui.status_label.setText(f"You: {text}")
        
        # Add to chat history
        self.chat_manager.add_message("user", text)
        
        # Check if we need to name the chat
        if len(self.chat_manager.current_chat_data["messages"]) <= 4:
             # Run naming in background
             threading.Thread(target=self.update_chat_name).start()
             
        threading.Thread(target=lambda: self.worker.process(text)).start()

    def update_chat_name(self):
        # Only name if it's a default name
        current_name = self.chat_manager.current_chat_data.get("name", "")
        if "Chat 20" in current_name: # Checks for default timestamp name
            new_name = self.chat_namer.generate_name(self.chat_manager.current_chat_data["messages"])
            if new_name:
                self.chat_manager.set_chat_name(new_name)
                print(f"🏷️ Chat Renamed: {new_name}")

    def handle_ai_response(self, response):
        print(f"Siris: {response}")
        
        # Add to chat history
        self.chat_manager.add_message("assistant", response)
        
        output_mode = self.settings["output"]
        
        if "Text" in output_mode or "Both" in output_mode:
            self.ui.status_label.setText(f"Siris: {response}")
            
        if "Speech" in output_mode or "Both" in output_mode:
            if self.voice_user:
                # Prepare UI for word highlighting
                self.ui.set_text_for_highlighting(response)
                threading.Thread(target=lambda: self.voice_user.speak(response)).start()
            else:
                print("⚠️ TTS not ready yet.")

        QTimer.singleShot(10000, self.reset_ui)

    def reset_ui(self):
        self.ui.status_label.setText("Siris Online. Press Ctrl+Space.")
        self.ui.status_label.setStyleSheet("color: #00ffff; background: transparent;")

if __name__ == "__main__":
    siris = SirisApp()
    sys.exit(siris.app.exec())