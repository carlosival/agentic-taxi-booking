import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from db.models import Booking, Driver, Notification
from db.repositories.notification_repository import NotificationRepository
from db.db import get_async_session
from jobs.worker import notify_pending_bookings_task
from datetime import datetime, timezone, timedelta

@pytest.fixture(scope="function")
async def clean_database():
    ...


@pytest.fixture
async def test_booking_nodriver():
        async with get_async_session() as session:
            # Create test booking
            booking = Booking(
                pickup_location="Location A",
                destination="Location B",
                pickup_time="2025-07-10T12:00:00Z",
                passengers=2,
                special_requests="None",
                status="pending",  # important!
                customer_channel_id="123456789"
            )
            

            session.add(booking)
        
            await session.commit()
            await session.refresh(booking)
            

            return booking


@pytest.fixture
async def test_booking_driver():
        async with get_async_session() as session:
            # Create test booking
            booking = Booking(
                pickup_location="Location A",
                destination="Location B",
                pickup_time="2025-07-10T12:00:00Z",
                passengers=2,
                special_requests="None",
                status="pending",  # important!
                customer_channel_id="123456789"
            )


            # Example: UTC+2 offset
            offset = timedelta(hours=2)
            dt_with_offset = datetime.now(timezone(offset))
            dt_utc = dt_with_offset.astimezone(timezone.utc)

            # Create test booking with offset
            booking = Booking(
                pickup_location="Location A",
                destination="Location B",
                pickup_time="2025-07-10T12:00:00Z",
                passengers=2,
                special_requests="None",
                status="pending",  # important!
                customer_channel_id="123456789",
                timestamp_created = dt_utc

            )


            # Create test driver
            driver = Driver(
                name="Test Driver",
                channel_id="1234567890"
            )

            session.add(booking)
            session.add(driver)
            await session.commit()
            await session.refresh(booking)
            await session.refresh(driver)

            return booking, driver


class TestClass:

    @pytest.mark.asyncio
    async def test_notify_task_outdate_booking_notification(mock_kiq, test_booking_driver, clean_database ):

    @pytest.mark.asyncio
    async def test_notify_task_nobooking(mock_kiq, test_booking_driver, clean_database ):

    @pytest.mark.asyncio
    async def test_notify_task_nodriver(mock_kiq, test_booking_driver, clean_database ):
    
    @pytest.mark.asyncio
    async def test_notify_task_creates_notification(mock_kiq, test_booking_driver, clean_database ):
        booking, driver = test_booking_driver

        # Mock WhatsApp API to always succeed
        mock_kiq.return_value = {"status": "message sent"}

        #Send task manually to broker (simulate scheduler)
        await notify_pending_bookings_task.kiq()


        # Wait for the side effect (Notification entry to appear in DB)
        async def wait_for_notification(timeout=5):
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < timeout:
                async with get_async_session() as session:
                    stmt = select(Notification).where(
                        Notification.booking_id == booking.id,
                        Notification.driver_id == driver.id
                    )
                    result = await session.execute(stmt)
                    notification = result.scalar_one_or_none()
                    if notification:
                        return notification
                await asyncio.sleep(0.2)  # Small delay before retrying
            return None

        notification = await wait_for_notification()



        # Verify notification record created
        async with get_async_session() as session:
            booking_id: int = booking.id
            driver_id: int = driver.id
            stmt = select(Notification).where(Notification.booking_id == booking_id and Notification.driver_id == driver_id)

            result = await session.execute(stmt)
            print(result)
            notification = result.scalar_one_or_none()

            assert notification is not None
        