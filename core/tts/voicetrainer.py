import os
import torch
import json
import time
from PyQt6.QtCore import QObject, pyqtSignal
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

class VoiceTrainer(QObject):
    progress_update = pyqtSignal(int, str)
    finished = pyqtSignal(str)

    def __init__(self, config_path="config/paths.json"):
        super().__init__()
        with open(config_path, 'r') as f:
            self.paths = json.load(f)['tts']
        
        self.config = None
        self.model = None

    def load_model(self):
        self.progress_update.emit(10, "⏳ Loading XTTS Core...")
        self.config = XttsConfig()
        self.config.load_json(self.paths['config'])
        self.model = Xtts.init_from_config(self.config)
        
        # --- FIX: Added speaker_file_path ---
        self.model.load_checkpoint(
            self.config, 
            checkpoint_path=self.paths['checkpoint'], 
            vocab_path=self.paths['vocab'], 
            speaker_file_path=self.paths['speakers'], # <--- CRITICAL FIX
            use_deepspeed=False
        )
        
        if torch.cuda.is_available(): 
            self.model.cuda()
        self.progress_update.emit(30, "✅ XTTS Core Ready.")

    def process_voice(self, audio_file, voice_name):
        if not self.model:
            self.load_model()

        self.progress_update.emit(40, f"🎙️ Analyzing Audio: {os.path.basename(audio_file)}...")
        time.sleep(0.5) 
        
        self.progress_update.emit(60, "🧠 Computing Latents...")
        gpt_cond_latent, speaker_embedding = self.model.get_conditioning_latents(audio_path=[audio_file])
        
        self.progress_update.emit(80, "💾 Saving Voice Model...")
        
        data = {
            "gpt_cond_latent": gpt_cond_latent.cpu().numpy().tolist(),
            "speaker_embedding": speaker_embedding.cpu().numpy().tolist()
        }
        
        save_path = f"models/voices/{voice_name}.json"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, "w") as f:
            json.dump(data, f)
            
        self.progress_update.emit(100, f"✅ Voice '{voice_name}' Saved!")
        time.sleep(1)
        self.finished.emit(voice_name)