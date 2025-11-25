
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse      
import uvicorn
import os
from controllers.wasap_controller import WhatsapController
from controllers.telegramp_controller import TelegramController
from telegram import Update


from jobs.worker import broker
from utils.utils import get_secret

logger = logging.getLogger(__name__)
wasap_controller = WhatsapController()



@asynccontextmanager
async def lifespan(app: FastAPI):

    # Save it globally for FastAPI
    app.state.telegram_app = await TelegramController().create_telegram_app()
    
    # Start Taskiq broker so tasks can be enqueued
    await broker.startup()

    yield

    # Shutdown broker gracefully
    await broker.shutdown()

app = FastAPI(lifespan=lifespan)




# Define a route for the root URL
@app.get("/")
async def read_root():
     
    return {"Hello": "World"}

# Define a route for the root URL
@app.get("/health")
async def health():

    # Need to add all necesary request to external services(Test Deploy)
    return {"Health": "OK"}

# Webhook verification (GET)
@app.get("/webhook")
async def verify_webhook(request: Request):

        return await wasap_controller.verify_webhook(request)  # Correctly await the asynchronous method
    
    

# Get track call
@app.get("/track_call")
async def track_call(request: Request, number: str):
    print(number)
    #return RedirectResponse(f"tel:{number}")
    result = await wasap_controller.track_number(request, number)
    return result 

# Webhook event reception (POST)
@app.post("/webhook")
async def receive_event(request: Request):
    try:
       print("paso por aqui")
       return await wasap_controller.handle_webhook(request) 
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        return {"status": "received"}
    

# Telegram webhook
# --- RUTA DEL WEBHOOK PARA FASTAPI ---
@app.post("/telegram/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()

    # Access telegram app from FastAPI state
    telegram_app = req.app.state.telegram_app

    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

# define main   
if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)




