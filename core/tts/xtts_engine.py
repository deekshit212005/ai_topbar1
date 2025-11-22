import json
import torch
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

class XTTSEngine:
    def __init__(self):
        with open("config/paths.json", "r") as f:
            paths = json.load(f)["tts"]
        
        print("🗣️ Loading XTTS...")
        config = XttsConfig()
        config.load_json(paths["config"])
        self.model = Xtts.init_from_config(config)
        self.model.load_checkpoint(config, checkpoint_path=paths["checkpoint"], vocab_path=paths["vocab"], use_deepspeed=False)
        if torch.cuda.is_available(): self.model.cuda()
        print("✅ XTTS Loaded")

    def speak(self, text, output_file="output.wav"):
        # Note: XTTS requires a reference audio file to clone style. 
        # Ensure 'reference.wav' exists in root or pass a path.
        metrics = self.model.inference(
            text, "en", 
            self.model.get_conditioning_latents(audio_path=["reference.wav"])[0],
            self.model.get_conditioning_latents(audio_path=["reference.wav"])[1],
            output_path=output_file
        )
        return output_file