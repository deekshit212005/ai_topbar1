import os
import json
import time
import uuid
from datetime import datetime

class ChatManager:
    def __init__(self, history_dir="chat_history", max_tokens=50000):
        self.history_dir = history_dir
        self.max_tokens = max_tokens
        self.current_chat_id = None
        self.current_chat_data = None
        self.token_count = 0
        
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)
            
        self.load_latest_or_create()

    def load_latest_or_create(self):
        # Find latest chat file
        files = [f for f in os.listdir(self.history_dir) if f.endswith('.json')]
        if not files:
            self.create_new_chat()
        else:
            # Sort by modification time
            latest_file = max(files, key=lambda x: os.path.getmtime(os.path.join(self.history_dir, x)))
            self.load_chat(latest_file.replace('.json', ''))

    def create_new_chat(self, name=None):
        self.current_chat_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.current_chat_data = {
            "id": self.current_chat_id,
            "name": name or f"Chat {timestamp}",
            "created_at": timestamp,
            "messages": [],
            "token_count": 0
        }
        self.token_count = 0
        self.save_chat()
        print(f"🆕 Created new chat: {self.current_chat_data['name']}")

    def load_chat(self, chat_id):
        path = os.path.join(self.history_dir, f"{chat_id}.json")
        try:
            with open(path, 'r') as f:
                self.current_chat_data = json.load(f)
                self.current_chat_id = self.current_chat_data.get("id", chat_id)
                self.token_count = self.current_chat_data.get("token_count", 0)
                print(f"📂 Loaded chat: {self.current_chat_data.get('name', chat_id)}")
        except Exception as e:
            print(f"❌ Failed to load chat {chat_id}: {e}")
            self.create_new_chat()

    def save_chat(self):
        if not self.current_chat_id: return
        
        path = os.path.join(self.history_dir, f"{self.current_chat_id}.json")
        try:
            with open(path, 'w') as f:
                json.dump(self.current_chat_data, f, indent=4)
        except Exception as e:
            print(f"❌ Failed to save chat: {e}")

    def add_message(self, role, content, tokens_approx=0):
        if not self.current_chat_data:
            self.create_new_chat()
            
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.current_chat_data["messages"].append(message)
        
        # Update token count (approximate if not provided)
        if tokens_approx == 0:
            tokens_approx = len(content) // 4  # Rough estimate
            
        self.token_count += tokens_approx
        self.current_chat_data["token_count"] = self.token_count
        
        self.save_chat()
        
        # Check for rotation
        if self.token_count >= self.max_tokens:
            print(f"🔄 Token limit reached ({self.token_count}/{self.max_tokens}). Starting new chat.")
            self.create_new_chat()

    def get_context(self, limit=10):
        """Get recent messages for LLM context"""
        if not self.current_chat_data: return []
        return self.current_chat_data["messages"][-limit:]

    def set_chat_name(self, name):
        if self.current_chat_data:
            self.current_chat_data["name"] = name
            self.save_chat()
