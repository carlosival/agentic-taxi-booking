"""
This controls information between agent an WHATSAP Input and OutPut
"""
from pydantic import BaseModel
import requests
from fastapi import FastAPI, HTTPException
import os
from requests.exceptions import RequestException
from typing import Optional, Dict, Any, List

ACCESS_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
GRAPH_URL = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

class MessageRequest(BaseModel):
    to: str
    text: Optional[str] = None
    template: Optional[str] = None
    language: Optional[str] = "en_US"
    components: Optional[List[Dict[str, Any]]] = None  # For template variables


class WhatsappSendMessageService:

    def __init__(self):
        pass


    def format_payload(self, req: MessageRequest) -> Dict[str, Any]:

        payload: dict[str, Any] = { }

        """
        Build a WhatsApp API payload.
        Supports:
          - Plain text message
          - Template message with any valid components structure
          - Valid components structure
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": req.to
        }

        if req.template:
            payload["type"] = "template"
            payload["template"] = {
                "name": req.template,
                "language": {"code": req.language },
            }

            if req.components:
                payload["template"]["components"] = req.components

        elif req.text:
            payload["type"] = "text"
            payload["text"] = {"body": req.text}

        else:
            raise ValueError("Either text or template must be provided.")

        return payload    

    async def send_whatsapp_message(self, message_req: MessageRequest):
        
        
        try:
            payload = self.format_payload(message_req)
            response = requests.post(GRAPH_URL, headers=HEADERS, json=payload, timeout=10)
            response.raise_for_status()
            
            return {"status": "message sent", "response": response.json()}

        except RequestException as e:
            #logging.error(f"Request failed: {e}")
            raise HTTPException(status_code=503, detail="Failed to contact WhatsApp API")

        except ValueError:
            #logging.error("Invalid JSON response from WhatsApp API")
            raise HTTPException(status_code=502, detail="Invalid response from WhatsApp API")

    
