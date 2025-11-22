import torch
import json
import numpy as np
import time
import threading
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
import sounddevice as sd
from PyQt6.QtCore import QObject, pyqtSignal
from transformers import GPT2PreTrainedModel
from transformers.generation import GenerationMixin

# --- MONKEY PATCH FOR TTS/TRANSFORMERS COMPATIBILITY ---
# Fixes: 'GPT2InferenceModel' object has no attribute 'generate'
try:
    from transformers.models.gpt2.modeling_gpt2 import GPT2LMHeadModel
except ImportError:
    pass

class VoiceUser(QObject):
    word_spoken = pyqtSignal(int, str, int)  # word_index, word_text, total_words
    
    def __init__(self, config_path="config/paths.json"):
        super().__init__()
        with open(config_path, 'r') as f:
            self.paths = json.load(f)['tts']
        
        self.config = XttsConfig()
        self.config.load_json(self.paths['config'])
        self.model = Xtts.init_from_config(self.config)
        
        try:
            # Load checkpoint with all required paths
            self.model.load_checkpoint(
                self.config, 
                checkpoint_path=self.paths['checkpoint'], 
                vocab_path=self.paths['vocab'], 
                speaker_file_path=self.paths['speakers'],
                use_deepspeed=False
            )
            
            # Move to CUDA if available
            if torch.cuda.is_available(): 
                self.model.cuda()
            
            # Verify the model has the necessary components
            if not hasattr(self.model, 'inference'):
                raise AttributeError("XTTS model missing 'inference' method")
            
            # --- RUNTIME PATCH FOR GPT2InferenceModel ---
            # The XTTS model uses a GPT model internally (self.model.gpt)
            # We need to ensure IT has the generate method.
            if hasattr(self.model, 'gpt'):
                gpt_model = self.model.gpt
                if not hasattr(gpt_model, 'generate'):
                    print("🔧 Patching GPT model with GenerationMixin...")
                    # Dynamically add GenerationMixin to the object's class
                    gpt_model_class = gpt_model.__class__
                    if GenerationMixin not in gpt_model_class.__bases__:
                        gpt_model_class.__bases__ = (GenerationMixin,) + gpt_model_class.__bases__
                        print("✅ Patch applied: GenerationMixin added to bases")
            
            print("✅ TTS Model Loaded Successfully")
            
        except Exception as e:
            print(f"❌ TTS Initialization Error: {e}")
            print("💡 TTS may not work properly. Check model files.")
            self.model = None
        
        self.latents = None

    def load_voice(self, voice_name):
        path = f"models/voices/{voice_name}.json"
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                if self.model:
                    self.latents = (
                        torch.tensor(data['gpt_cond_latent']).to(self.model.device),
                        torch.tensor(data['speaker_embedding']).to(self.model.device)
                    )
                else:
                    self.latents = (
                        torch.tensor(data['gpt_cond_latent']),
                        torch.tensor(data['speaker_embedding'])
                    )
            print(f"🗣️ Loaded Voice: {voice_name}")
        except FileNotFoundError:
            print("⚠️ Voice file not found.")
        except Exception as e:
            print(f"❌ Error loading voice: {e}")

    def speak(self, text):
        if not self.model:
            print("❌ TTS model not loaded. Cannot generate speech.")
            return
            
        if not self.latents: 
            print("❌ No voice loaded. Add a voice in settings first.")
            return

        # Limit text length to prevent TTS errors (max ~200 chars for safety)
        if len(text) > 200:
            text = text[:197] + "..."
            print("⚠️  Text truncated to fit TTS limits")

        print("🔊 Generating Audio...")
        try:
            # Use the inference method which is the standard XTTS API
            out = self.model.inference(
                text, "en", self.latents[0], self.latents[1], temperature=0.7
            )
            audio_data = np.array(out['wav'])
            
            # Split text into words for highlighting
            words = text.split()
            total_words = len(words)
            
            # Calculate audio duration and time per word
            sample_rate = 24000
            audio_duration = len(audio_data) / sample_rate
            time_per_word = audio_duration / total_words if total_words > 0 else 0
            
            # Start playback in a separate thread
            def play_audio():
                sd.play(audio_data, sample_rate)
                sd.wait()
                print("✅ Speech playback complete")
            
            playback_thread = threading.Thread(target=play_audio, daemon=True)
            playback_thread.start()
            
            # Emit word signals with timing
            for i, word in enumerate(words):
                time.sleep(time_per_word)
                self.word_spoken.emit(i, word, total_words)
            
            # Wait for playback to complete
            playback_thread.join()
            
        except AttributeError as e:
            print(f"❌ TTS Error: {e}")
            print("💡 The TTS model may be incompatible or corrupted.")
            print("   Try reinstalling the TTS library: pip install TTS --upgrade")
        except AssertionError as e:
            print(f"❌ TTS Error: {e}")
            print("   Text was too long for TTS engine")
        except Exception as e:
            print(f"❌ TTS Error: {e}")