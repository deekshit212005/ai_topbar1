import torch
import json
import re
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

class LLMEngine:
    def __init__(self, model_key="llama_1b", config_path="config/paths.json"):
        with open(config_path, 'r') as f:
            self.paths = json.load(f)['llm']
        
        # Support mapping the key even if user swapped paths physically
        self.model_path = self.paths.get(model_key)
        if not self.model_path:
            print(f"❌ Model key {model_key} not found. Using raw path string if possible.")
            self.model_path = model_key

        # Detect model type for output filtering
        self.model_key = model_key
        self.model_type = "thinking" if "vibe" in model_key.lower() else "standard"
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = None
        self.model = None
        self.load_model()

    def load_model(self):
        print(f"🧠 Loading Brain from: {self.model_path}")
        
        # --- 1. VALIDATE MODEL PATH ---
        import os
        if not os.path.exists(self.model_path):
            print(f"❌ Model path does not exist: {self.model_path}")
            self.model = None
            self.tokenizer = None
            return
        
        # --- 2. MEMORY OPTIMIZATION (4-bit) ---
        # This allows 8B models to run on 6GB-8GB GPUs
        quantization_config = None
        use_quantization = False
        
        if self.device == "cuda":
            try:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                    llm_int8_enable_fp32_cpu_offload=True  # Enable CPU offload for large models
                )
                use_quantization = True
                print("⚡ 4-Bit Quantization Enabled (VRAM Saver)")
            except Exception as e:
                print(f"⚠️ Quantization setup failed: {e}. Loading standard (High VRAM).")

        try:
            # --- 3. LOAD TOKENIZER (Qwen Fixes) ---
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, 
                trust_remote_code=True
            )
            # Qwen often lacks a pad token, set it to EOS to prevent crashes
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            # --- 4. LOAD MODEL ---
            # Use custom device_map for better memory management
            load_kwargs = {
                "trust_remote_code": True,
                "low_cpu_mem_usage": True,
            }
            
            # Add quantization if available
            if use_quantization and quantization_config:
                load_kwargs["quantization_config"] = quantization_config
                load_kwargs["torch_dtype"] = torch.float16
                # Use sequential device map to allow CPU offloading
                load_kwargs["device_map"] = "sequential"
            else:
                # Non-quantized loading
                load_kwargs["device_map"] = "auto"
                if self.device == "cuda":
                    load_kwargs["torch_dtype"] = torch.float16
                else:
                    load_kwargs["torch_dtype"] = torch.float32
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                **load_kwargs
            )
            print("✅ Siris Brain (Qwen/Llama) Loaded")
            
        except ValueError as e:
            error_msg = str(e)
            if "Unrecognized model" in error_msg or "model_type" in error_msg:
                print(f"❌ Model Type Error: {e}")
                print("💡 This model type is not supported by transformers AutoModel.")
                print("   The Qwen3VL-4B-Thinking model may require specific model classes.")
                print("   Try using:")
                print("   - llama_1b (Llama 3.2 1B)")
                print("   - vibe_1.5b (Vibe 1.5B)")
                self.model = None
                self.tokenizer = None
            else:
                raise
        except RuntimeError as e:
            if "out of memory" in str(e).lower() or "oom" in str(e).lower():
                print(f"❌ Out of Memory Error: {e}")
                print("💡 Try:")
                print("   1. Close other applications")
                print("   2. Use a smaller model (llama_1b)")
                print("   3. Restart your computer")
                self.model = None
                self.tokenizer = None
            else:
                raise
        except Exception as e:
            print(f"❌ LLM Critical Error: {e}")
            print("Tip: If OOM, try closing other apps or use a smaller model.")
            self.model = None
            self.tokenizer = None

    def generate(self, prompt, system_prompt=None, max_tokens=200):
        if not self.model: return "Error: Brain offline."
        
        # Use model-specific system prompts
        if system_prompt is None:
            if self.model_type == "thinking":
                system_prompt = (
                    "You are Siris, an advanced AI assistant. "
                    "Think through the problem carefully, but provide only a concise, direct answer to the user. "
                    "Keep your final response brief and to the point."
                )
            else:
                system_prompt = "You are Siris, an advanced AI assistant."
        
        # Chat Template (Works for Llama 3 AND Qwen)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # Format Prompt
            formatted_prompt = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs, 
                    max_new_tokens=max_tokens,
                    pad_token_id=self.tokenizer.eos_token_id,
                    do_sample=True,
                    temperature=0.6, # Slightly lower for Qwen instruction following
                    top_p=0.9
                )
            
            # Decode
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            # Filter output for thinking models
            if self.model_type == "thinking":
                response = self._filter_output(response)
            
            return response.strip()
            
        except Exception as e:
            return f"Generation Error: {e}"
    
    def _filter_output(self, text):
        """Extract only the final answer from thinking model output"""
        # Remove <think>...</think> tags and content
        
        # Pattern to match <think>...</think> blocks
        think_pattern = r'<think>.*?</think>'
        filtered = re.sub(think_pattern, '', text, flags=re.DOTALL)
        
        # Clean up extra whitespace
        filtered = re.sub(r'\n\s*\n', '\n', filtered)
        filtered = filtered.strip()
        
        # If nothing left after filtering, return original (safety fallback)
        if not filtered:
            return text
        
        return filtered