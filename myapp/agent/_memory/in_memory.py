from typing import List, Dict, Optional
from .interfaces import Memory

class InMemoryMemory(Memory):
    def __init__(self, in_memory: Optional[List[Dict]] = None):
        self.in_memory = in_memory or []
        
    def set_memory(self, in_memory: List[Dict]) -> None:
        self.in_memory = in_memory

    def add_user_message(self, message: str) -> None:
        if not message or not isinstance(message, str):
            raise ValueError("message must be a non-empty string")
        self._add_message("user", message)

    def add_ai_message(self, message: str, action: str) -> None:
        if not message or not isinstance(message, str):
            raise ValueError("message must be a non-empty string")
        if not action or not isinstance(action, str):
            raise ValueError("action must be a non-empty string")
        self._add_message("ai", message, action)

    def _add_message(self, role: str, content: str, action: Optional[str] = None) -> None:
        if role == "user":
            entry = {"role": role, "content": content}
        else:
            entry = {"role": role, "action": action, "content": content}
        
        self.in_memory.append(entry)

    def get_messages(self, limit: int) -> List[Dict[str, str]]:
        if limit is not None and limit > 0:
            return self.in_memory[-limit:]
        return self.in_memory.copy()
    
    def clear(self) -> None:
        self.in_memory.clear()
    
    def get_message_count(self) -> int:
        return len(self.in_memory)