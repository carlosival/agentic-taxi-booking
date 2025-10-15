
from db.repositories.notification_repository import NotificationRepository
from db.db import async_engine
from db.models import Base
from jobs.worker import broker
import pytest


@pytest.fixture(autouse=True)
async def start_broker():
    await broker.startup()
    yield
    await broker.shutdown()

@pytest.fixture(scope='session')
async def clean_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

