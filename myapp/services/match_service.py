import uuid
from services.whatsapp_service import MessageRequest, WhatsappSendMessageService 
from services.notification_service import  NotificationService
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
asyncio
import logging


whatsapp_service = WhatsappSendMessageService()
notification_service = NotificationService()

logger = logging.getLogger(__name__)

class MatchService:
    


    async def acceptance_booking(self, identifier:  str) -> Optional[Booking]:
            
            try:
               from jobs.worker import notify_customer_driver_acceptance_task # Lazy import to break circular import dependency
               
               async with get_async_session() as session:
                    
                    booking_repo = BookingRepository(session)
                                
                    booking = await booking_repo.lock_and_update_booking(identifier)

                    asyncio.create_task(notify_customer_driver_acceptance_task.kiq(identifier))
                   

                    return booking

            except Exception as error:
                raise error 
                 
                 

    async def create_notification_pending_booking(self, booking_id: int)-> None:

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
                                    
                                    notif = await notification_service.create_notification(driver.id, booking.id)
                                    if notif:
                                        asyncio.create_task(notify_drivers_task.kiq(notif.message_send_id))
                                
                                except Exception as error:
                                    continue


                            last_id = drivers[-1].id  
                            
            except Exception as error:
                    #Log the exception
                    logging.exception(f"Error while processing booking: {error}")        

    
            

                
                 
                    

            