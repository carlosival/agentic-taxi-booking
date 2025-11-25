from db.repositories.notification_repository import NotificationRepository
from db.repositories.booking_repository import BookingRepository
from db.repositories.driver_repository import DriverRepository
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db.models import Booking, Notification
from typing import Dict, Optional, Sequence
from uuid import uuid4, UUID
from datetime import datetime
from agent._state.domain import BookingState
import logging
from services.whatsapp_service import MessageRequest, WhatsappSendMessageService
from services.telegram_service import TelegramSendMessageService
from db.db import get_async_session
from db.repositories.driver_repository import DriverRepository
from db.models import Driver
from dtos.dtos import driverDto
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from db.redis_db import redis_client as connection
from redis.asyncio import Redis 
import time

logger = logging.getLogger(__name__)


class DriverService:
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client or connection

    async def update_location(self, driver_info) -> bool:   
        if not driver_info:
            return False
        
        session_id = driver_info.session_id
        key = f"driver:location:{session_id}"
        key_metadata = f"driver:{session_id}"
        lon = driver_info.lon
        lat = driver_info.lat
        
        try:  
            pipe = self.redis.pipeline()
            # 1) Update GEO index (note: GEOADD lon lat member)
            pipe.geoadd(key, {session_id: (lon, lat)})  
            # Initialize once
            pipe.hsetnx(key_metadata, "status", "available")
            # 2) Update hash with metadata
            pipe.hset(key_metadata, mapping={
                "last_lat": str(lat),
                "last_lon": str(lon),
                "last_update": str(int(time.time())),
                
            })
            pipe.execute()  
            
            return True
        except (RedisConnectionError, RedisError) as error:
            logger.exception(f"Problems updating location of user {session_id}", error)
            return False 


    async def create_driver(self, data:driverDto) -> Optional[Notification]:
        try:

            docs = data.get("docs")
            if not docs or len(docs) < 1:
                raise ValueError("At least 1 documents are required to create a driver")

            async with get_async_session() as session:
                driver_repo = DriverRepository(session)
                driver = driver = Driver(
                    channel=data.get("channel"),
                    channel_id=data.get("channel_id"),
                    licencia=docs[0],
                )
                return await driver_repo.create(driver)

        except Exception as error:
            logger.exception("Failed to create booking: %s", error)
            return None