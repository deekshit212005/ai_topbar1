import json
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

class STTEngine(QObject):
    transcription_ready = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.model = None
        self.is_loaded = False
        self.use_openai_whisper = False
        
        # Load config
        with open("config/paths.json", "r") as f:
            self.model_path = json.load(f)["stt"]["model_path"]
            
        self.load_model()
        
    def load_model(self):
        try:
            print(f"Loading Whisper model from {self.model_path}...")
            # Logic: If .pt file, force OpenAI whisper
            if self.model_path.endswith(".pt"):
                print("⚠️ .pt file detected. Using openai-whisper.")
                import whisper
                self.model = whisper.load_model(self.model_path)
                self.use_openai_whisper = True
                self.is_loaded = True
                print("✅ OpenAI Whisper model loaded successfully")
                return

            # Default to Faster Whisper
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.model_path, device="cpu", compute_type="int8")
            self.is_loaded = True
            print("✅ Faster-Whisper model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading Whisper model: {e}")
            self.is_loaded = False
    
    def transcribe_audio(self, audio_data, sample_rate=16000):
        if not self.is_loaded:
            return "STT model not loaded"
        
        try:
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            audio_float = audio_data.astype(np.float32).flatten()
            max_val = np.abs(audio_float).max()
            if max_val > 1.0:
                audio_float = audio_float / max_val
            
            if self.use_openai_whisper:
                result = self.model.transcribe(audio_float, language='en', fp16=False)
                text = result['text'].strip()
            else:
                segments, info = self.model.transcribe(audio_float, language='en')
                text = " ".join([segment.text for segment in segments]).strip()
            
            print(f"📄 Transcription: '{text}'")
            self.transcription_ready.emit(text)
            return text
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return ""