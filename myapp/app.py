
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse      
import uvicorn
import os
from minio import Minio
from controllers.wasap_controller import WhatsapController
from controllers.telegramp_controller import TelegramController
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Document, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters
import asyncio
import requests
from dtos.dtos import driverDto
import io
from uuid import uuid4
import config.conf as conf
from jobs.worker import broker
from utils.utils import get_secret

logger = logging.getLogger(__name__)



VERIFY_TOKEN = get_secret("WHATSAPP_TOKEN")
TELEGRAM_TOKEN = get_secret("TELEGRAM_TOKEN")
DOMAIN = get_secret("DOMAIN")
MINIO_ENDPOINT = get_secret("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = get_secret("MINIO_ROOT_USER", "minio")
MINIO_SECRET_KEY = get_secret("MINIO_ROOT_PASSWORD", "minio123")
MINIO_SECURE = get_secret("MINIO_SECURE", "false").lower() == "true"

WEBHOOK_URL = f"https://{DOMAIN}/telegram/webhook"  # Debe ser HTTPS
controller = WhatsapController()
telegram_controller = TelegramController()

# MinIO client (runs inside your Docker network)
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

BUCKET_NAME = "uploads"
driver_join_text = r"^\s*🚖?\s*Join as Driver\s*$"

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Crear la aplicación de Telegram
    telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

    

    # --- REGISTRO DE HANDLERS ---
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(button_callback))
    telegram_app.add_handler(join_handler)
    telegram_app.add_handler(relay_handler)
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(driver_join_text), handle_message))
    telegram_app.add_handler(CommandHandler('cancel', cancel))

   
    # Init telegram bot
    await telegram_app.initialize()

    # Save it globally for FastAPI
    app.state.telegram_app = telegram_app
    
    set_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}"
    requests.get(set_webhook_url).json()
    
    logger.info(" Telegram webhook configurado OK")

    # Ensure bucket exists
    found = minio_client.bucket_exists(BUCKET_NAME)
    if not found:
        minio_client.make_bucket(BUCKET_NAME)

    # Start Taskiq broker so tasks can be enqueued
    await broker.startup()

    yield

    # Shutdown broker gracefully
    await broker.shutdown()

app = FastAPI(lifespan=lifespan)


# ---- Join Drivers Conversation ---

# Conversation states
DOCS, ASK_MESSAGE = 0,0

async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        
        # Look for last bookings of this persons and send a email to the other
        src = update.message.from_user.id
        
        dst = await telegram_controller.guess_destination(from_user=str(src))
        
        if dst:
            
            dst_text, booking_id, channel_id, channel = dst
            context.user_data["booking_id"] = booking_id
            context.user_data["channel_id"] = channel_id
            context.user_data["channel"] = channel
            
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_message")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f'''📨 You can send a message {dst_text} related to booking {booking_id}
                Please enter the message :''',
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            return ASK_MESSAGE
        
        await update.message.reply_text('Could not find any related booking', parse_mode="Markdown")
        
        return ConversationHandler.END




async def ask_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
                booking_id = context.user_data["booking_id"]
                channel_id = context.user_data["channel_id"]
                channel = context.user_data["channel"]
                text = update.message.text
                sender = str(update.message.from_user.id)

                try:
                    # await update.message.reply_text(f"⏳ Sending message to ...")
                    msg = f''' 
                            related to booking {booking_id}\n 
                            {text}    
                        '''
                    await telegram_controller.relay_message(to_user=channel_id, msg=msg)
                    
                    
                except Exception as error:
                    await  update.message.reply_text(f"❌ Failed to deliver message to..")
                
                finally:
                    return ConversationHandler.END
                
                
async def join_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /join. Ask user for the first document."""
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_message")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Please send driving license as PDF or image file", reply_markup = reply_markup
    )
    # initialize storage for this user in conversation
    context.user_data['uploaded_docs'] = []
    return DOCS
""" 
async def set_bot_commands(app):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help information"),
        BotCommand("join", "Get information about the bot"),
    ]
    await app.bot.set_my_commands(commands) """


async def collect_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    """
    Collect ONE document or image, process it, upload to MinIO, and end.
    """
    message = update.message
    file_obj = message.document or (message.photo[-1] if message.photo else None)

    # Validate file type
    if not file_obj:
        await message.reply_text("⚠️ Please send a valid document or image.")
        return "WAITING_FOR_FILE"

    await message.reply_text("📥 File received! Processing...")
    
    
    # Download file from Telegram
    telegram_file = await file_obj.get_file()
    file_bytes = io.BytesIO()
    await telegram_file.download_to_memory(out=file_bytes)
    file_bytes.seek(0)

    # Detect mime type properly
    if message.document:
        content_type = message.document.mime_type or "application/octet-stream"
    elif message.photo:
        content_type = "image/jpeg"  # Telegram always sends photos as JPEG
    else:
        content_type = "application/octet-stream"

    # Upload to MinIO
    object_name = f"{update.message.from_user.id}/{uuid4()}"
    await asyncio.to_thread(
        minio_client.put_object,
        BUCKET_NAME,
        object_name,
        file_bytes,
        length=len(file_bytes.getvalue()),
        content_type=content_type
    )
        
    drv =  await telegram_controller.create_driver({"channel_id":str(update.message.from_user.id),"channel":"TELEGRAM", "docs": [object_name]})
    
    if drv:
        await message.reply_text("Welcome aboard! Driver registration completed")
    else:
        await message.reply_text("Something went wrong while creating the user. Please try again later")


    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allow user to cancel."""
    #context.user_data.pop('uploaded_docs', None)
    #context.user_data.pop('booking_id', None)
    context.user_data.clear()
    await update.message.reply_text("Join canceled.")
    return ConversationHandler.END

# --- Cancel handler (for inline Cancel button) ---
async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    query = update.callback_query
    await query.answer()  # Acknowledge the button press quickly

    # 🗑️ Delete the message that contained the inline keyboard
    try:
        await query.message.delete()
    except Exception as e:
        # Fallback in case message was already deleted or can't be removed
        print(f"Could not delete message: {e}")

    return ConversationHandler.END

relay_handler = ConversationHandler(
    entry_points=[
                  CommandHandler("message", relay_message),
                  MessageHandler(filters.Regex("^Send Message$"), relay_message)
                  ],
    states={
        ASK_MESSAGE: [ 
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_message), 
            CallbackQueryHandler(cancel_callback, pattern="cancel_callback")
            ]    
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)

join_handler = ConversationHandler(
        entry_points=[ 
                CommandHandler('join', join_driver), 
                MessageHandler(filters.Regex(driver_join_text), join_driver)
            ],
        states={
            DOCS: [MessageHandler(filters.Document.ALL | filters.PHOTO, collect_docs)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

# --- MENÚ PRINCIPAL ---
async def start(update: Update, context):
    # Always visible menu buttons
    keyboard = [["Send Message", "🚖 Join as Driver"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text("Welcome!", reply_markup=reply_markup)

#--- MENU Handle Message ---

async def handle_message(update, context):
    
    text = update.message.text
    user = update.message.from_user
    
    user_id = str(user.id)
    user_info = { "channel": conf.TELEGRAM_CHANNEL, "user_id" : user_id}
    await telegram_controller.handle_text_message(text, user_info)
    

async def message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if len(args) >= 3:
        booking_id = args[0]
        text = ' '.join(args[1:])
        status_message = await update.message.reply_text(f"⏳ Sending message to ...")

        try:

            await telegram_controller.relay_message( str(update.message.from_user.id), booking_id, text)
            await status_message.edit_text(f"✅ {text}")

        except Exception as error:
            await status_message.edit_text(f"❌ Failed to deliver message to..")

    


# --- CALLBACK DE BOTONES ---
async def button_callback(update: Update, context):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("driver_accept"):
        await telegram_controller.handle_button_accept(data)
    elif data.startswith("cancel_message"): 
        await cancel_callback(update, context)
    elif data.startswith("driver_ignore"):
        await query.edit_message_reply_markup(reply_markup=None)
    
    elif data.startswith("user_cancel"):
        await query.edit_message_reply_markup(reply_markup=None)

    elif data == "help":
        await query.edit_message_text("Sección de ayuda ℹ️")



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

        return await controller.verify_webhook(request)  # Correctly await the asynchronous method
    
    


# Get track call
@app.get("/track_call")
async def track_call(request: Request, number: str):
    print(number)
    #return RedirectResponse(f"tel:{number}")
    result = await controller.track_number(request, number)
    return result 

# Webhook event reception (POST)
@app.post("/webhook")
async def receive_event(request: Request):
    try:
       print("paso por aqui")
       return await controller.handle_webhook(request) 
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




