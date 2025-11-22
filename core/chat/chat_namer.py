import threading

class ChatNamer:
    def __init__(self, llm_engine):
        self.llm = llm_engine
        
    def generate_name(self, messages):
        """Generate a short name for the chat based on initial messages"""
        if not messages or len(messages) < 2:
            return None
            
        # Prepare prompt for naming
        conversation_text = ""
        for msg in messages[:3]:  # Use first 3 messages
            conversation_text += f"{msg['role']}: {msg['content']}\n"
            
        prompt = (
            f"Analyze the following conversation start and generate a very short, descriptive title (max 4-5 words). "
            f"Do not use quotes. Just the title.\n\n"
            f"Conversation:\n{conversation_text}\n\nTitle:"
        )
        
        try:
            # Use a separate thread or just call generate if it's fast enough
            # Since we are usually calling this in background, direct call is fine
            name = self.llm.generate(prompt, max_tokens=20)
            
            # Cleanup
            name = name.strip().strip('"').strip("'")
            if len(name) > 50: name = name[:47] + "..."
            
            return name
        except Exception as e:
            print(f"⚠️ Failed to name chat: {e}")
            return None
