
from db.models import Booking, Driver, BookingStatus, Notification
from datetime import datetime
from fastapi import  Request, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse 
from services.whatsapp_service import WhatsappSendMessageService , MessageRequest 
import os
from agent.agent import Agent
from services.notification_service import NotificationService
from services.booking_service import BookingService
from services.whatsapp_service import WhatsappSendMessageService
from services.match_service import MatchService


wasap_service = WhatsappSendMessageService()
VERIFY_TOKEN =os.getenv("WHATSAPP_TOKEN")


class WhatsapController:
    def __init__(self):
        pass  # Add dependencies if needed

    async def handle_webhook(self, request: Request):
        
        try:
            data = await request.json()
            print("Received webhook data:", data)

            # Check for real WhatsApp structure: "entry"
            entries = data.get("entry", [])

            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    field = change.get("field")

                    # Process only if it's a message event
                    if field == "messages":
                        messages = value.get("messages", [])
                        if not messages:
                            print("No messages in value.")
                            continue

                        for message in messages:
                            wa_id = message.get("from")
                            msg_type = message.get("type")
                            print(f"Received type: {msg_type} from {wa_id}")

                            if msg_type == "text":
                                await self._handle_text_message(message, wa_id)

                            elif msg_type == "button":
                               # self._handle_button_message(message, wa_id)
                               ...

                            else:
                                print(f"Unhandled message type: {msg_type}")

                    # ✅ (Optional) Handle other fields (statuses, etc.)
                    elif field == "statuses":
                        statuses = value.get("statuses", [])
                        print(f"Received statuses: {statuses}")

                    else:
                        print(f"Unhandled field: {field}")

        except Exception as e:
            print(f"❌ Error in handle_webhook: {e}")


    async def track_number(self, request: Request, identifier: str):
        try:
            
            service = MatchService()
            booking = await service.acceptance_booking(identifier)

            if not booking:
                raise HTTPException(status_code=404, detail="Booking not found")
            
            return RedirectResponse(f"tel:{booking.customer_channel_id}")

        except Exception as e:
            raise HTTPException(status_code=500, detail=e)
            

    async def _handle_text_message(self, message: dict, wa_id: str):
        """
        Handles plain text messages.
        """
        try:
            text_body = message["text"]["body"]
            # Example: ask your bot/agent
            print(text_body)
            agent_response = await self.askAgent(text_body, wa_id)
            print("Agent Response:", agent_response)
            wasap_service = WhatsappSendMessageService()
            await wasap_service.send_whatsapp_message(MessageRequest(to=wa_id, text=agent_response))
        except Exception as error: 
            print(f"❌ Error in handle_webhook: {error}")  
            raise Exception("Problems handle message text: {error}")
    
    

    async def askAgent(self, text: str, user_id:str) -> str:
        """
        Replace with your actual AI/bot call.
        """
        agent = Agent()
        answer = await agent.process_input(text, user_id)
        return answer

 
    async def verify_webhook(self, request: Request):
        mode = request.query_params.get('hub.mode')
        token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge')

        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return PlainTextResponse(content=challenge, status_code=200)
            else:
                return PlainTextResponse(content="Token inválido", status_code=403)
        return PlainTextResponse(content="Parámetros faltantes", status_code=400)