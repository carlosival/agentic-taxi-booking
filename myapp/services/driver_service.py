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

logger = logging.getLogger(__name__)


class DriverService:
    def __init__(self):
        pass

    async def create_driver(self, data:driverDto) -> Optional[Notification]:
        try:

            docs = data.get("docs")
            if not docs or len(docs) < 3:
                raise ValueError("At least 3 documents are required to create a driver")

            async with get_async_session() as session:
                driver_repo = DriverRepository(session)
                driver = driver = Driver(
                    channel=data.get("channel"),
                    channel_id=data.get("channel_id"),
                    carnet=docs[0],
                    licencia=docs[1],
                    matricula=docs[2],
                )
                return await driver_repo.create(driver)

        except Exception as error:
            logger.exception("Failed to create booking: %s", error)
            return None