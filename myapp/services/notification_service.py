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
from db.repositories.notification_repository import NotificationRepository
from db.models import Booking, BookingStatus, Notification
import asyncio
import config.conf as conf

logger = logging.getLogger(__name__)
telegram_service = TelegramSendMessageService()
whatsapp_service = WhatsappSendMessageService()



class NotificationService:
    def __init__(self):
        pass
        

    async def get_notification(self, identifier: str) -> Optional[Notification]:
        try:
            async with get_async_session() as session:
                notification_repo = NotificationRepository(session)
                return await notification_repo.get_by_identifier(identifier)
        except Exception as error:
                        #Log the exception
                        logging.exception(f"Error while processing booking: {error}") 
    
    async def get_notification_lock_booking(self, identifier: str) -> Optional[Notification]:
        try:
            async with get_async_session() as session:
                notification_repo = NotificationRepository(session)
                return await notification_repo.get_by_identifier(identifier)
        except Exception as error:
                        #Log the exception
                        logging.exception(f"Error while processing booking: {error}")

    async def notify_customer_driver_acceptance(self, identifier: str):
            try:
                 
                noti = await self.get_notification(identifier)
                if noti:
                    booking = noti.booking
                    driver = noti.driver

                    if booking and driver and booking.driver_id == driver.id:
                         

                        if booking.customer_channel == "WHATSAPP":   
                            # Notify customer
                            msg_to_customer = MessageRequest(
                                    to=str(booking.customer_channel_id),
                                    template="notify_to_client_driver_acceptance",
                                    language="es_ES",
                                    components=[
                                        {
                                            "type": "body",
                                            "parameters": [
                                                {"type": "text", "text": driver.channel_id},
                                            ]
                                        }
                                    ]
                                ) 
                            
                            whatsapp = WhatsappSendMessageService()
                            await whatsapp.send_whatsapp_message(msg_to_customer)
                    
                        if booking.customer_channel == "TELEGRAM":   
                            
                            if booking and driver and booking.driver_id == driver.id:
                                message1 = f"""✅ Booking confirmed!  A driver will contact you shortly with further details""" 
                                components = [{
                                    "ctype" : "inline_keyboard",
                                    "buttons": [
                                                    
                                                [{"text": "❌ Cancel", "callback_data": f"user_cancel_{booking.identifier}"}] 
                                                             
                                                ]
                                }]
                                await telegram_service.send_telegram_message(MessageRequest(to=booking.customer_channel_id, text=message1, components=components))
            
                            
                        if driver.channel == "TELEGRAM":
                                message2 = f""" ✅ You have granted the service for booking {booking.identifier}, communicate to the user for any details:""" 
                                components = [{
                                    "ctype" : "inline_keyboard",
                                    "buttons": [
                                                    
                                                [{"text": "❌ Cancel", "callback_data": f"driver_cancel_{booking.identifier}"}] 
                                                             
                                                ]
                                }]
                                await telegram_service.send_telegram_message(MessageRequest(to=driver.channel_id, text=message2))
                    
                    else:
                        
                        if driver.channel == "TELEGRAM":
                                message = f""" Service already assign to other driver""" 
                                await telegram_service.send_telegram_message(MessageRequest(to=driver.channel_id, text=message))
                          
                                  

            except Exception as error:
                print(error)
                     

    async def notify_driver(self, identifier: str):

            try:
                 
                noti = await self.get_notification(identifier)
                if noti:
                    booking = noti.booking
                    driver = noti.driver
                    tracking_id = noti.message_send_id    
                    template_notificacion = "event_details_reminder_1" # Plantilla de wasap para notificar al usuario que hay una reserva
                    
                    if driver.channel == conf.WHATSAPP_CHANNEL:

                            msg = MessageRequest(
                                                to=driver.channel_id,
                                                template=template_notificacion,
                                                language="es_ES",
                                                components=[
                                                    {
                                                        "type": "body",
                                                        "parameters": [
                                                            {"type": "text", "text": booking.pickup_location},
                                                            {"type": "text", "text": booking.destination},
                                                            {"type": "text", "text": booking.pickup_time},
                                                            {"type": "text", "text": booking.passengers},
                                                            {"type": "text", "text": booking.special_requests}
                                                        ]
                                                    },
                                                    {
                                                        "type": "button",
                                                        "sub_type": "url",
                                                        "index": "0",
                                                        "parameters": [
                                                            {"type": "text", "text": tracking_id}
                                                        ]
                                                    }
                                                ]
                                            )  
                            
                            whatsapp = WhatsappSendMessageService()
                            await whatsapp.send_whatsapp_message(msg)


                    if driver.channel == conf.TELEGRAM_CHANNEL:

                            message = f"""Service Request 
                                        Pickup: {booking.pickup_location}, 
                                        Destination: {booking.destination}, 
                                        Time: {booking.pickup_time}, 
                                        Passengers: {booking.passengers}, 
                                        Requests: {booking.special_requests} """

                            components = [{
                            "ctype" : "inline_keyboard",
                            "buttons": [
                                            [
                                                {"text": "✅ OK", "callback_data": f"driver_accept_{tracking_id}"},
                                                {"text": "❌ Ignore", "callback_data": f"driver_ignore_{tracking_id}"} 
                                                
                                            ]
                                        ]
                            }]
                            

                            await telegram_service.send_telegram_message(MessageRequest(to=driver.channel_id, text=message, components=components))

                        



            except Exception as error:
                print(error)      

    async def create_notification_pending_booking(self, booking_id)-> None:

                last_id = 0
                BATCH_SIZE = 300
                booking = None

                try: 
                    from jobs.worker import notify_drivers_task # Lazy import to break circular import dependency  

                    async with get_async_session() as session:
                        booking_repo = BookingRepository(session)
                        booking = await booking_repo.get_by_id(booking_id)
                        if not booking: return None


                    async with get_async_session() as session:
                            

                            driver_repo = DriverRepository(session)
                            while True:
                                drivers = await driver_repo.get_drivers_batch(last_id, BATCH_SIZE)
                                
                                if not drivers:
                                    break  # no more users, exit loop
                                
                                for driver in drivers:

                                    try:    
                                        
                                        noti =  await self.create_notification(driver.id, booking_id.id)
                                        
                                        if noti:
                                            asyncio.create_task(notify_drivers_task.kiq(noti.message_send_id))
                                    
                                    except Exception as error:
                                        continue


                                last_id = drivers[-1].id  
                                
                except Exception as error:
                        #Log the exception
                        logging.exception(f"Error while processing booking: {error}") 

    async def create_notification(self, driver_id:int, booking_id:int) -> Optional[Notification]:
        try:

            #Create Booking ORM:
            notification = Notification(
                driver_id=driver_id,
                booking_id=booking_id,
            )

            async with get_async_session() as session:
                notification_repo = NotificationRepository(session)
                return await notification_repo.create(notification)

        except Exception as error:
            logger.exception("Failed to create booking: %s", error)
            return None