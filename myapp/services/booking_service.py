import uuid
from services.whatsapp_service import MessageRequest, WhatsappSendMessageService 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.repositories.booking_repository import BookingRepository
from db.repositories.driver_repository import DriverRepository
from db.repositories.notification_repository import NotificationRepository
from db.models import Booking, BookingStatus, Notification
from db.db import get_async_session
from typing import Dict, Optional, Sequence
from uuid import uuid4, UUID
from datetime import datetime
from agent._state.domain import BookingState
from uuid import UUID
import logging
import asyncio

whatsapp_service = WhatsappSendMessageService()

logger = logging.getLogger(__name__)

class BookingService:
    
                    
        async def create_booking( self, booking_state: BookingState, customer: Dict ) -> Optional[Booking]:
                try:
                    
                    new_booking = None

                    from jobs.worker import create_notification_pending_booking_task # Lazy import to break circular import dependency
                    # Convert to Booking ORM:
                    booking = Booking(
                    pickup_location=booking_state.pickup_location,
                    destination=booking_state.destination,
                    pickup_time=booking_state.pickup_time,
                    passengers=booking_state.passengers,
                    special_requests=booking_state.special_requests
                    )

                    booking.customer_channel_id = customer["user_id"]
                    booking.customer_channel = customer["channel"]
                    
                    async with get_async_session() as session:
                            booking_repo = BookingRepository(session)    
                            new_booking = await booking_repo.create(booking)
                            

                            
                    if new_booking:
                        # Notify drivers Fire-and-forget: enqueue task, don't await        
                        asyncio.create_task(create_notification_pending_booking_task.kiq(int(new_booking.id)))

                    return  new_booking   

                except Exception as error:
                    logger.exception("Failed to create booking: %s", error)
                    return None

