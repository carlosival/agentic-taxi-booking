import os
from typing import Protocol, Any
from taskiq_aio_pika import AioPikaBroker
from taskiq.schedule_sources import LabelScheduleSource
from taskiq import TaskiqScheduler
from utils.utils import get_secret

class HasKiq(Protocol):
    def kiq(self, *args: Any, **kwargs: Any) -> Any: ...
    async def kiq_async(self, *args: Any, **kwargs: Any) -> Any: ...

# Get RabbitMQ URL from env

rabbitmq_user = get_secret("RABBITMQ_USER")
rabbitmq_pass = get_secret("RABBITMQ_PASSWORD")
rabbitmq_host = get_secret("RABBITMQ_HOST")
rabbitmq_port = get_secret("RABBITMQ_PORT")
rabbitmq_url = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}"
print("🐇 Using RabbitMQ URL:", rabbitmq_url)

# Define the broker
broker = AioPikaBroker(rabbitmq_url)


# Import task after broker to avoid circular imports
from jobs.task import (
    _notify_driver_task,
    _create_notification_pending_booking_task,
    _notify_customer_driver_acceptance_task,
    _create_driver_task,
    
)



scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)



# Now safely define tasks here


create_driver_task: HasKiq = broker.task(
    _create_driver_task,
    retry_count=5,
    retry_delay=10,
)

notify_drivers_task: HasKiq = broker.task(
    _notify_driver_task,
    retry_count=5,
    retry_delay=10,
)


notify_customer_driver_acceptance_task: HasKiq = broker.task(
    _notify_customer_driver_acceptance_task,
    retry_count=5,
    retry_delay=10,
)

create_notification_pending_booking_task: HasKiq = broker.task(
    _create_notification_pending_booking_task,
    retry_count=5,
    retry_delay=10,
) 
