
# repositories/driver_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, Sequence
from datetime import timedelta, timezone, datetime
from db.models import BookingStatus    
from db.models import Booking, Notification, Driver
from typing import Optional, Sequence
from uuid import UUID
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import OperationalError

import logging


logger = logging.getLogger(__name__)

class BookingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_pending_bookings(self) -> Sequence[Booking]:
            async with self.db.begin():

                timeout = timedelta(minutes=10)
                now = datetime.now(timezone.utc)
                cutoff_time = now - timeout

                stmt = select(Booking).where(
                    Booking.status == BookingStatus.pending.value,
                    Booking.timestamp_created >= cutoff_time
                ).limit(300)

                result = await self.db.execute(stmt)
                return result.scalars().all()
        

    async def lock_and_update_booking(self, noti_identifier: str):
        try:
            async with self.db.begin():
                stmt = (
                    select(Notification)
                    .join(Notification.booking)  # <-- join to Booking
                    .options(
                            joinedload(Notification.booking), 
                            joinedload(Notification.driver)
                            )
                    .where(
                    Notification.message_send_id == noti_identifier,
                    Booking.driver_id == None,                # ✅ use Booking directly
                    Booking.status == BookingStatus.pending   # optional: only if you have pending state
                )
                    .with_for_update(of=Booking, nowait=True)
                )
                result = await self.db.execute(stmt)
                notification = result.scalar_one_or_none()
                if notification:
                    notification.booking.driver_id = notification.driver.id
                    notification.booking.status = BookingStatus.confirmed
                    self.db.add(notification.booking)
                    
                
                return notification.booking
            
        except OperationalError as e:
            # PostgreSQL message when another transaction holds the lock
            if "could not obtain lock" in str(e) or "FOR UPDATE" in str(e):
                logging.warning(f"Row is locked, skipping update for {noti_identifier}")
                return None
            else:
                logging.exception("Database error during booking lock")
                raise
        except Exception as error:
                #Log the exception
                logging.exception(f"Error while processing booking: {error}")    
                raise

    async def get_by_id(self, booking_id: int) -> Optional[Booking]:
            async with self.db.begin():
                result = await self.db.execute(
                    select(Booking).where(Booking.id == booking_id)
                )
                return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: str) -> Optional[Booking]:
            async with self.db.begin():
                result = await self.db.execute(
                    select(Booking)
                    .options( 
                            joinedload(Booking.driver)
                            )
                    .where(Booking.identifier == identifier)
                )
                return result.scalar_one_or_none()
    
    async def get_by_noti_identifier(self, noti_identifier: str) -> Optional[Booking]:
            async with self.db.begin():
                result = await self.db.execute(
                    select(Booking).where(Booking.identifier == identifier).with_for_update()
                )
                return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[Booking]:
            async with self.db.begin():
                result = await self.db.execute(select(Booking))
                return result.scalars().all()

    async def create(self, booking: Booking) -> Booking:
            async with self.db.begin():
                self.db.add(booking)
                return booking

    async def update_status(self, booking_id: int, new_status: str) -> Optional[Booking]:
            async with self.db.begin():
                booking = await self.get_by_id(booking_id)
                if booking:
                    booking.status = new_status
                return booking