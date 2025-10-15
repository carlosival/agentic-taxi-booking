
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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Document
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init telegram bot
    await telegram_app.initialize()
    set_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}"
    resp = requests.get(set_webhook_url).json()
    print("Webhook configurado:", resp)

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

# Crear la aplicación de Telegram
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

# ---- Join Drivers Conversation ---

DOC1, DOC2, DOC3 = range(3)
DOCS = 0

async def join_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /join. Ask user for the first document."""
    await update.message.reply_text(
        "Please send document 1 of 3.\n"
        "You can send any file (PDF, DOCX, image, etc.).\n"
        "Send /cancel to stop."
    )
    # initialize storage for this user in conversation
    context.user_data['uploaded_docs'] = []
    return DOCS

async def collect_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect documents and reply OK when 3 are received."""
    doc = update.message.document
    if not doc:
        await update.message.reply_text("That’s not a document. Please send a valid file.")
        return DOCS

    context.user_data['uploaded_docs'].append(doc)
    count = len(context.user_data['uploaded_docs'])

    if count < 3:
        await update.message.reply_text(f"Got document {count}. Please send document {count+1}.")
        # Create driver
        return DOCS
    else:
        # 3 documents received
        await update.message.reply_text("✅ OK, I received all 3 documents.")
        
        
        process_docs = []
        for d in context.user_data["uploaded_docs"]:
            # Download file from Telegram
            telegram_file = await d.get_file()
            file_bytes = io.BytesIO()
            await telegram_file.download_to_memory(out=file_bytes)
            file_bytes.seek(0)

            # Upload to MinIO
            object_name = f"{update.message.from_user.id}/{uuid4()}"
            await asyncio.to_thread(
                minio_client.put_object,
                BUCKET_NAME,
                object_name,
                file_bytes,
                length=len(file_bytes.getvalue()),
                content_type=d.mime_type or "application/octet-stream"
            )
            process_docs.append(object_name)



        await telegram_controller.create_driver({"channel_id":str(update.message.from_user.id),"channel":"TELEGRAM", "docs": process_docs})

        context.user_data.clear()
        return ConversationHandler.END


async def receive_carnet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive first document and ask for the second."""
    doc: Document = update.message.document
    if not doc:
        await update.message.reply_text("That's not a document. Please send a file (document).")
        return DOC1

    # download and save
    file = await context.bot.get_file(doc.file_id)
    local_path = f"doc_1_{doc.file_unique_id}_{doc.file_name or doc.file_id}"
    await file.download_to_drive(custom_path=local_path)

    context.user_data['uploaded_docs'].append(local_path)
    await update.message.reply_text("Received document 1. Now please send document 2 of 3.")
    return DOC2

async def receive_licencia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive second document and ask for the third."""
    doc: Document = update.message.document
    if not doc:
        await update.message.reply_text("That's not a document. Please send a file (document).")
        return DOC2

    file = await context.bot.get_file(doc.file_id)
    local_path = f"doc_2_{doc.file_unique_id}_{doc.file_name or doc.file_id}"
    await file.download_to_drive(custom_path=local_path)

    context.user_data['uploaded_docs'].append(local_path)
    await update.message.reply_text("Received document 2. Now please send document 3 of 3.")
    return DOC3

async def receive_matriculacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive third document and finish."""
    doc: Document = update.message.document
    if not doc:
        await update.message.reply_text("That's not a document. Please send a file (document).")
        return DOC3

    file = await context.bot.get_file(doc.file_id)
    local_path = f"doc_3_{doc.file_unique_id}_{doc.file_name or doc.file_id}"
    await file.download_to_drive(custom_path=local_path)

    context.user_data['uploaded_docs'].append(local_path)

    # Completed
    uploaded = context.user_data.get('uploaded_docs', [])
    await update.message.reply_text(
        "All 3 documents received ✅\n"
        + "\n".join(f"{i+1}: {p}" for i, p in enumerate(uploaded))
        + "\n\nThank you!"
    )

    # Here you can process the files in uploaded (e.g., move to permanent storage, send to admin, parse, etc.)
    # Clear conversation data:
    context.user_data.pop('uploaded_docs', None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allow user to cancel."""
    context.user_data.pop('uploaded_docs', None)
    await update.message.reply_text("Upload canceled. To start again send /join")
    return ConversationHandler.END

conv_handler = ConversationHandler(
        entry_points=[CommandHandler('join', join_driver)],
        states={
            DOCS: [MessageHandler(filters.Document.ALL, collect_docs)]
            #DOC1: [MessageHandler(filters.Document.ALL, receive_carnet)],
            #DOC2: [MessageHandler(filters.Document.ALL, receive_licencia)],
            #DOC3: [MessageHandler(filters.Document.ALL, receive_matriculacion)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=False,
    )

# --- MENÚ PRINCIPAL ---
async def start(update: Update, context):
    # Always visible menu buttons
    keyboard = [["🚖 Book a Taxi", "Join","ℹ️ Help"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=reply_markup
    )

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
        
    elif data.startswith("driver_cancel"):
        await query.edit_message_reply_markup(reply_markup=None)

    elif data == "help":
        await query.edit_message_text("Sección de ayuda ℹ️")

# --- REGISTRO DE HANDLERS ---
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("message", message_command))
telegram_app.add_handler(CallbackQueryHandler(button_callback))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(conv_handler)
telegram_app.add_handler(CommandHandler('cancel', cancel))

# Define a route for the root URL
@app.get("/")
async def read_root():
     
     return {"Hello": "World"}



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
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

# define main   
if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)




