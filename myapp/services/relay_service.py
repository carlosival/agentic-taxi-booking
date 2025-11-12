
from services.whatsapp_service import MessageRequest, WhatsappSendMessageService 
from services.notification_service import  NotificationService
from services.telegram_service import MessageRequest, TelegramSendMessageService
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
import asyncio

import logging



logger = logging.getLogger(__name__)



class RelayService:


    async def guess_destination(self, from_user, channel):

        booking = None

        try: 
            async with get_async_session() as session:
                booking_repo = BookingRepository(session)
                booking = await booking_repo.get_by_user_or_driver(from_user) # get from_user's booking, joined with driver

                if booking and booking.driver:
                    if booking.customer_channel_id == from_user and channel == booking.customer_channel:
                        return ("to driver", booking.identifier, booking.driver.channel_id, booking.driver.channel)
                    if booking.driver.channel_id == from_user and channel == booking.driver.channel:
                        return ("to user", booking.identifier, booking.channel_id, booking.channel)
                return None
        except Exception as error:
            logger.exception(error)
            return None

    async def relay_message(self, to_plataform, to_user, text):
                try:
                    # Forward to correct connector
                    await self.send_to_platform(to_plataform, to_user, text)
                except Exception as error:
                    logger.exception(error)
                    raise

    async def relay_message_deprecated(self, from_platform, from_user, booking_ident, text):
        try:
            async with get_async_session() as session:
                booking_repo = BookingRepository(session)
                booking = await booking_repo.get_by_identifier(booking_ident)
                
                receiver_platform = None
                receiver_id = None

                if not booking:
                    raise ValueError("Booking not found")

                driver = booking.driver


                if from_user == booking.customer_channel_id:
                    receiver_platform = driver.channel
                    receiver_id = driver.channel_id
                elif from_user == driver.channel_id:
                    receiver_platform = booking.customer_channel
                    receiver_id = booking.customer_channel_id
 

                # Forward to correct connector
                await self.send_to_platform(receiver_platform, receiver_id, text)

        except Exception as error:
            raise

    async def send_to_platform(self, platform, user_id, text):
        try:
            if platform == "TELEGRAM":
                await TelegramSendMessageService().send_telegram_message(MessageRequest(to=user_id, text=text))
            
        except Exception as error:
            raise