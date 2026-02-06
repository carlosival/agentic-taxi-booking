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
from geopy.geocoders import Nominatim
from geopy import distance

logger = logging.getLogger(__name__)

from enum import IntEnum

coeffciente = [0.1,0.2,0.3,0.8]
price_km = 480*1.6 # Cambio al pais de location

class VehicleType(IntEnum):
    MOTO = 0
    ECONOMIC = 1
    CONFORT = 2
    VAN = 3

    @property
    def label(self) -> str:
        return self.name


def vehicle_type_from_string(value: str) -> VehicleType:
    upper = value.upper()
    allowed = ", ".join(f" {v.name}" for v in VehicleType)
    if not VehicleType[value.upper()]:
        raise ValueError(f"{upper} is not member of allowed values {allowed}")
    
    return VehicleType[value.upper()]

class DriverService:
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client or connection


    async def calcule_price(self, ava_drivers, pickup, dropoff, price_km):

    
                trip_dist_km = distance.distance(pickup, dropoff).km
                
                result_buckets = []
                
                # Iterate over the buckets (e.g., vehicle types)
                for bucket in ava_drivers:
                    processed_bucket = []
                    
                    # Iterate over the drivers in this specific bucket
                    for driver in bucket:
                        new_driver = driver.copy() # Avoid modifying original data
                        new_driver["price"] = driver["base_start"] + (trip_dist_km * coeffciente[vehicle_type_from_string(driver["meta"]["type"])] * price_km)
                        processed_bucket.append(new_driver)
                        
                    result_buckets.append(processed_bucket)
                    
                return result_buckets


    async def k_closest_points(self, lon: float, lat: float, k: int, max_radius_km: float = 50):
    
            # 1. Geo search (closest first)
            results = await self.redis.geosearch(
                name="locations",
                longitude=lon,
                latitude=lat,
                radius=max_radius_km,
                unit="km",
                withdist=True,
                withcoord=True,
                count=k,
                sort="ASC"
            )

            if not results:
                return []

            # 2. Pipeline metadata fetch
            pipe = self.redis.pipeline()
            for driver_id, _, _ in results:
                pipe.hgetall(f"driver:metadata:{driver_id}")

            metadata = await pipe.execute()

            drivers = [[],[],[],[]]

            

            # 3. Merge geo + metadata
            for (driver_id, dist, coords), meta in zip(results, metadata):

                drivers[vehicle_type_from_string(meta["type"])].append({
                        "id": driver_id,
                        "base_start": float(dist) * coeffciente[vehicle_type_from_string(meta["type"])] * price_km,
                        "distance_km": float(dist),
                        "longitude": float(coords[0]),
                        "latitude": float(coords[1]),
                        "metadata": meta,
                    })
                
                
            


    async def update_location(self, driver_info) -> bool:   
        if not driver_info:
            return False
        
        session_id = driver_info["user_id"]
        key = f"driver:location"
        key_metadata = f"driver:metadata:{session_id}"
        lon = driver_info["lon"]
        lat = driver_info["lat"]

        mapping = {
                    "last_lat": str(lat),
                    "last_lon": str(lon),
                    "last_update": str(int(time.time())),
                    
                }
        
        pipe = self.redis.pipeline()

        try:  
            

            # 1) Check if metadata key exists
            exists = await self.redis.exists(key_metadata)


            if not exists:
                # Get the driver info
                driver = None
                
                async with get_async_session() as session:
                    driver_repo = DriverRepository(session)
                    driver = await driver_repo.get_by_channel_id(session_id)        

                if driver:
                    mapping["channel"] = driver.channel
                    mapping["channel_id"] = driver.channel_id

                    # 1) Update GEO index (note: GEOADD lon lat member)
                    pipe.geoadd(key, (lon, lat, session_id))  
                    # 2) Update hash with metadata
                    pipe.hset(key_metadata, mapping=mapping)
                    await pipe.execute()
                    
                    return True
                
                return False


            # 1) Update GEO index (note: GEOADD lon lat member)
            pipe.geoadd(key, (lon, lat, session_id))  
            # 2) Update hash with metadata
            pipe.hset(key_metadata, mapping=mapping)
            await pipe.execute()  
                
            return True
        except (RedisConnectionError, RedisError) as error:
            logger.exception(f"Problems updating location of user {session_id}")
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