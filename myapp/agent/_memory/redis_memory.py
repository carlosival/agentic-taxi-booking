from redis.asyncio import Redis 
import json
import re
import logging
from typing import List, Dict, Optional
from .interfaces import Memory
from utils.utils import get_secret
try:
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
except ImportError:
    RedisError = Exception
    RedisConnectionError = Exception

logger = logging.getLogger(__name__)

class RedisMemory(Memory):
    def __init__(self, session_id: str, redis_client: Optional[Redis] = None, 
                 host: str = 'localhost', port: int = 6379, db: int = 0, 
                 ttl: int = 86400, max_messages: int = 1000, password: Optional[str] = None):
        self.redis = redis_client or self._create_redis_client(host, port, db, password)
        self.key = self._validate_and_format_key(session_id)
        self.ttl = ttl
        self.max_messages = max_messages
    
    def _create_redis_client(self, host: str, port: int, db: int, password: Optional[str]) -> Redis:
        password = password or get_secret("REDIS_PASSWORD")
        
        return Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
    
    def _validate_and_format_key(self, session_id: str) -> str:
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        
        # Sanitize session_id to prevent injection
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', session_id)
        if not sanitized:
            raise ValueError("session_id contains only invalid characters")
        
        return f"chat:history:{sanitized}"

    async def add_user_message(self, message: str) -> bool:
        if not message or not isinstance(message, str):
            raise ValueError("message must be a non-empty string")
        return await self._add_message("user", message)

    async def add_ai_message(self, message: str, action: str) -> bool:
        if not message or not isinstance(message, str):
            raise ValueError("message must be a non-empty string")
        if not action or not isinstance(action, str):
            raise ValueError("action must be a non-empty string")
        return await self._add_message("ai", message, action)

    async def _add_message(self, role: str, content: str, action: Optional[str] = None) -> bool:
        try:
            entry = self._create_message_entry(role, content, action)
            
            async with self.redis.pipeline() as pipe:
                pipe.rpush(self.key, entry)
                pipe.expire(self.key, self.ttl)
            
                # Trim list to max_messages if needed
                if self.max_messages > 0:
                    pipe.ltrim(self.key, -self.max_messages, -1)
                
                await pipe.execute()
            return True

        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error adding message for key {self.key}: {e}")
            return False
        
    
    def _create_message_entry(self, role: str, content: str, action: Optional[str] = None) -> str:
        if role == "user":
            entry_data = {"role": role, "content": content}
        else:
            entry_data = {"role": role, "action": action, "content": content}
        
        return json.dumps(entry_data, ensure_ascii=False)

    async def get_messages(self, limit: int) -> List[Dict[str, str]]:
        try:
            if limit is not None and limit > 0:
                # Get only the last `limit` messages
                start = -limit
                end = -1
            else:
                # Get the full history
                start = 0
                end = -1

            entries = await self.redis.lrange(self.key, start, end)
            messages = []
            
            for entry in entries:
                try:
                    message = json.loads(entry)
                    # Validate message structure
                    if self._is_valid_message(message):
                        messages.append(message)
                    else:
                        logger.warning(f"Invalid message format: {entry}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message: {entry}, error: {e}")
                    continue
            
            return messages
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error getting messages for key {self.key}: {e}")
            return []
        
    
    def _is_valid_message(self, message: dict) -> bool:
        if not isinstance(message, dict):
            return False
        
        required_fields = {'role', 'content'}
        if not required_fields.issubset(message.keys()):
            return False
        
        # AI messages should have action field
        if message.get('role') == 'ai' and 'action' not in message:
            return False
        
        return True

    def set_session(self, session_id: str) -> None:
        self.key = self._validate_and_format_key(session_id)

    async def session_exists(self, session_id: str) -> bool:
        try:
            key = self._validate_and_format_key(session_id)
            return bool(await self.redis.exists(key))
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error checking session existence: {e}")
            return False

    async def clear(self) -> bool:
        try:
            result = await self.redis.delete(self.key)
            return bool(result)
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error clearing messages for key {self.key}: {e}")
            return False
        
    
    async def get_message_count(self) -> int:
        """Get the total number of messages in the session."""
        try:
            return await self.redis.llen(self.key)
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error getting message count for key {self.key}: {e}")
            return 0
        