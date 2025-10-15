
from services.driver_service import DriverService
from services.match_service import MatchService
from services.notification_service import NotificationService
from services.telegram_service import TelegramSendMessageService, MessageRequest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from dtos.dtos import driverDto
import logging


logger = logging.getLogger(__name__)
telegram_service = TelegramSendMessageService()
noti_service = NotificationService()
match_service = MatchService()
driver_Service = DriverService()



async def _create_driver_task(data: driverDto):
    try:  
        await driver_Service.create_driver(data)
    except Exception as e:
        print(f"Error in notify_pending_bookings task: {e}")




async def _notify_driver_task(id_notification: str):
    try:  
        await noti_service.notify_driver(id_notification)
    except Exception as e:
        print(f"Error in notify_pending_bookings task: {e}")


async def _create_notification_pending_booking_task(id_booking: int):
    try:  
        await match_service.create_notification_pending_booking(id_booking)
    except Exception as e:
        print(f"Error in notify_pending_bookings task: {e}")




async def _notify_customer_driver_acceptance_task(id: str):
    try:
        await noti_service.notify_customer_driver_acceptance(id)
    except Exception as e:
        print(f"Error in notify_pending_bookings task: {e}")



        





    







