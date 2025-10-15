from typing import Sequence, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

from db.models import Notification, ReplyStatus
from db.repositories.base_repository import BaseRepository  
import logging
from uuid import UUID

class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Notification)

    async def get_by_identifier(self, identifier: str) -> Optional[Notification]:
        
        try:
            async with self.db.begin():    
                # Lock Notification & fetch related Booking + Driver
                stmt = (
                    select(Notification)
                    .options(
                        joinedload(Notification.booking),
                        joinedload(Notification.driver)
                    )
                    .where(Notification.message_send_id == identifier)
                )
                result = await self.db.execute(stmt)
                return result.scalar_one_or_none()
        except SQLAlchemyError as error:
            # Log the error for debugging
            logging.exception(f"Error while fetching notification by identifier: {error}")
            return None


    async def create(self, obj: Notification) -> Notification:
            async with self.db.begin():
                self.db.add(obj)
                await self.db.flush()  # Optional: to persist before refresh
                await self.db.refresh(obj)
                return obj

    async def list_by_driver_id(self, driver_id: int) -> Sequence[Notification]:
        async with self.db.begin():
            stmt = select(Notification).where(Notification.driver_id == driver_id)
            result = await self.db.execute(stmt)
            return result.scalars().all()

    async def list_by_booking_id(self, booking_id: int) -> Sequence[Notification]:
        async with self.db.begin():
            stmt = select(Notification).where(Notification.booking_id == booking_id)
            result = await self.db.execute(stmt)
            return result.scalars().all()

    async def list_by_reply_status(
        self, reply_status: ReplyStatus
    ) -> Sequence[Notification]:
        async with self.db.begin():
            stmt = select(Notification).where(Notification.reply_status == reply_status)
            result = await self.db.execute(stmt)
            return result.scalars().all()

    async def get_by_message_send_id(
        self, message_send_id: str
    ) -> Optional[Notification]:
        async with self.db.begin():
            stmt = select(Notification).where(Notification.message_send_id == message_send_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
