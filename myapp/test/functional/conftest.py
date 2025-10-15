import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from db.models import Booking
from db.models import Driver
from db.models import Notification

from db.repositories.notification_repository import NotificationRepository
from db.db import get_async_session




    
@pytest.fixture
def mock_kiq():
    with patch("jobs.worker.notify_driver_task.kiq", new_callable=AsyncMock) as mock:
        yield mock