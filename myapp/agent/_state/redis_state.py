from .domain import BookingState, BookingStateRepository
from redis.asyncio import Redis 
import json
import re
import logging
from typing import Dict, Any, Optional
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from db.redis_db import redis_client as connection


logger = logging.getLogger(__name__)

class RedisState(BookingStateRepository):

    def __init__(self, session_id: str, redis_client: Optional[Redis] = None):
        self.redis = redis_client or connection
        self.key = self._validate_and_format_key(session_id)
        self.ttl = 86400 # for default 24h expressed as seconds
        
    
    def _validate_and_format_key(self, session_id: str) -> str:
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        
        # Sanitize session_id to prevent injection
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', session_id)
        if not sanitized:
            raise ValueError("session_id contains only invalid characters")
        
        return f"chat:state:{sanitized}" 
    
    async def get_state(self) -> BookingState:
        try:
            value = await self.redis.get(self.key)
            if value is None:
                logger.info(f"No state found in Redis for key {self.key}")
                return BookingState()
            
            # Parse JSON and validate
            data = json.loads(value) if isinstance(value, str) else value
            return BookingState.model_validate(data)
   
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Data parsing error for key {self.key}: {e}")
            return BookingState()
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error getting state for key {self.key}: {e}")
            return BookingState()
        

    async def set_state(self, state: BookingState) -> bool:
        try:
            result = await self.redis.setex(self.key, self.ttl, state.model_dump_json())
            return bool(result)
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error setting state for key {self.key}: {e}")
            return False
        
    async def clear(self) -> bool:
        if not self.key:
            logger.warning("No key set for cleaning.")
            return False
        try:
            result = await self.redis.delete(self.key)
            return bool(result)  # True if a key was deleted, False otherwise
        except (RedisError, RedisConnectionError) as e:
            logger.exception(f"Redis error deleting key {self.key}: {e}")
            return False


    def set_session(self, session_id: str):
        self.key = self._validate_and_format_key(session_id)
        

    async def update(self, data: Dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            raise ValueError(f"data must be a dictionary, got {type(data)}")
        
        try:
            # Get current state
            current_state = await self.get_state()
            
            # Aqui se pudiese comprobar que tipo de  data se va actualizar si es es del tipo


            # Update state with new data
            updated_state = current_state.model_copy(update=data)
            
            # Save updated state
            return await self.set_state(updated_state)
            
        except Exception as e:
            logger.error(f"Error updating state: {e}")
            return False

    async def is_complete(self) -> bool:
        """Check if the booking has all necessary info to proceed."""
        state = await self.get_state()
        return all([
            state.pickup_location,
            state.destination,
            state.pickup_time,
            state.passengers is not None
        ])

    async def summary(self) -> str:
        """Generate a human-readable summary of the booking."""
        state = await self.get_state()
        return (
            f"Pickup: {state.pickup_location or 'N/A'}, "
            f"Destination: {state.destination or 'N/A'}, "
            f"Time: {state.pickup_time or 'N/A'}, "
            f"Passengers: {state.passengers if state.passengers is not None else 'N/A'}, "
            f"Requests: {state.special_requests or 'None'}, "
            f"Confirmed: {'Yes' if state.confirmed else 'No'}"
        )

    async def confirm(self) -> bool:
        """Set the booking as confirmed if complete."""
        if await self.is_complete():
            return await self.update({"confirmed": True})
        else:
            raise ValueError("Cannot confirm booking: missing required information.")

    async def is_confirm(self) -> bool: 
        state = await self.get_state()
        return await self.is_complete() and state.confirmed