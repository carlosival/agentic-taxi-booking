from db.models import Booking, Driver, BookingStatus, Notification
from datetime import datetime
from fastapi import  Request, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse 
from services.telegram_service import MessageRequest, TelegramSendMessageService
import os
from agent.agent import Agent
from services.notification_service import NotificationService
from services.booking_service import BookingService
from services.whatsapp_service import WhatsappSendMessageService
from services.match_service import MatchService
from services.driver_service import DriverService
from services.relay_service import RelayService
from dtos.dtos import driverDto
class TelegramController:
        
        def __init__(self):
            pass  # Add dependencies if needed

        async def relay_message(self, from_user, booking_identifier, msg):    

            try:
                relay_service = RelayService()
                await relay_service.relay_message("TELEGRAM", from_user, booking_identifier, msg)
                               
            except Exception as error: 
                print(f"❌ Error in handle_webhook: {error}")  
                raise Exception("Problems handle message text: {error}") 
        
        async def handle_button_accept(self, data:str):   
             
            try:
                notification_id = data.split("_")[-1]
                math_service = MatchService()
                await math_service.acceptance_booking(notification_id)
                               
            except Exception as error: 
                print(f"❌ Error in handle_webhook: {error}")  
                raise Exception("Problems handle message text: {error}")

            

        async def handle_text_message(self, message: str, user_info: dict):
            """
            Handles plain text messages.
            """
            try:
                text = message
                agent_response = await self.askAgent(text, user_info)
                wa_id = user_info.get("user_id", None)
                print("Agent Response:", agent_response)
                telegram_service = TelegramSendMessageService()
                await telegram_service.send_telegram_message(MessageRequest(to=wa_id, text=agent_response))
            except Exception as error: 
                print(f"❌ Error in handle_webhook: {error}")  
                raise Exception("Problems handle message text: {error}")
        
        async def create_driver(self, data: driverDto):
                try:
                    drv_service = DriverService()
                    driver = await drv_service.create_driver(data)
                    return driver
                except Exception as error: 
                    print(f"❌ Error in handle_webhook: {error}")  
                    raise Exception("Problems handle message text: {error}")
             

        async def askAgent(self, text: str, user_info:dict) -> str:
            """
            Replace with your actual AI/bot call.
            """
            agent = Agent()
            answer = await agent.process_input(text, user_info)
            return answer