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
from services.geolocation_service import MapboxService
from dtos.dtos import driverDto
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Document, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters
from utils.utils import get_secret
import io
import requests
import logging
import io
from uuid import uuid4
import config.conf as conf
from db.storage import minio_client
import asyncio

logger = logging.getLogger(__name__)
relay_service = RelayService()

# Conversation states
DOCS, ASK_MESSAGE = 0,0
driver_join_text = r"^\s*🚖?\s*Join as Driver\s*$"
BUCKET_NAME = "uploads"
DOMAIN = get_secret("DOMAIN")
TELEGRAM_TOKEN = get_secret("TELEGRAM_TOKEN")
WEBHOOK_URL = f"https://{DOMAIN}/telegram/webhook"  # Debe ser HTTPS


class TelegramController:
        
        def __init__(self):
            pass  # Add dependencies as needed


        def join_handler(self):

            return   ConversationHandler(
            entry_points=[ 
                    CommandHandler('join', self.join_driver), 
                    MessageHandler(filters.Regex(driver_join_text), self.join_driver)
                ],
            states={
                DOCS: [MessageHandler(filters.Document.ALL | filters.PHOTO, self.collect_docs)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
            allow_reentry=True,
            )  

        def relay_handler(self): 
                return ConversationHandler(
                entry_points=[
                            CommandHandler("message", self.relay_message),
                            MessageHandler(filters.Regex("^Send Message$"), self.relay_message)
                            ],
                states={
                    ASK_MESSAGE: [ 
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_message), 
                        CallbackQueryHandler(self.cancel_callback, pattern="cancel_callback")
                        ]    
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
                allow_reentry=True,
                per_user=True,
                per_chat=True
               
                )
            

        # --- Build the app
        async def create_telegram_app(self) -> Application:
                """
                Initializes the Telegram bot application and registers all handlers.
                Returns the ready-to-use Application object.
                """
                # Create the application
                app = Application.builder().token(TELEGRAM_TOKEN).build()

                # Register handlers
                app.add_handler(CommandHandler("start", self.start))
                app.add_handler(CallbackQueryHandler(self.button_callback))
                app.add_handler(self.join_handler())
                app.add_handler(self.relay_handler())
                app.add_handler(MessageHandler(filters.LOCATION, self.handle_location))
                #app.add_handler(MessageHandler(filters.LOCATION & filters.UpdateType.EDITED_MESSAGE, self.handle_location))
                app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r"driver_join_text"), self.handle_message))
                app.add_handler(CommandHandler('cancel', self.cancel))

                # Initialize asynchronously
                await app.initialize()
                
                set_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}"
                requests.get(set_webhook_url).json()
    
                logger.info(" Telegram webhook configurado OK")


                return app    

        # ---- Join Drivers Conversation ---


        # --- MENÚ PRINCIPAL ---
        async def start(self, update: Update, context):
            # Always visible menu buttons
            keyboard = [["Send Message", "🚖 Join as Driver"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            await update.message.reply_text("Welcome!", reply_markup=reply_markup)

        # --- CALLBACK DE BOTONES ---
        async def button_callback(self, update: Update, context):
            query = update.callback_query
            data = query.data
            await query.answer()

            if data.startswith("driver_accept"):
                await self.handle_button_accept(data)
            elif data.startswith("cancel_message"): 
                await self.cancel_callback(update, context)
            elif data.startswith("driver_ignore"):
                await query.edit_message_reply_markup(reply_markup=None)
            
            elif data.startswith("user_cancel"):
                await query.edit_message_reply_markup(reply_markup=None)

            elif data == "help":
                await query.edit_message_text("Sección de ayuda ℹ️") 

        async def handle_button_accept(self, data:str):   
                
                try:
                    notification_id = data.split("_")[-1]
                    math_service = MatchService()
                    await math_service.acceptance_booking(notification_id)
                                
                except Exception as error: 
                    print(f"❌ Error in handle_webhook: {error}")  
                    raise Exception("Problems handle message text: {error}")

        # --- Cancel handler (for inline Cancel button) ---
        async def cancel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            
            query = update.callback_query
            await query.answer()  # Acknowledge the button press quickly

            # 🗑️ Delete the message that contained the inline keyboard
            try:
                await query.message.delete()
            except Exception as e:
                # Fallback in case message was already deleted or can't be removed
                print(f"Could not delete message: {e}")

            return ConversationHandler.END

        async def join_driver(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
            """Entry point for /join. Ask user for the first document."""
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_message")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Please send driving license as PDF or image file", reply_markup = reply_markup
            )
            # initialize storage for this user in conversation
            context.user_data['uploaded_docs'] = []
            return DOCS
   


        async def collect_docs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        
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
                
            drv =  await self.create_driver({"channel_id":str(update.message.from_user.id),"channel":"TELEGRAM", "docs": [object_name]})
            
            if drv:
                await message.reply_text("Welcome aboard! Driver registration completed")
            else:
                await message.reply_text("Something went wrong while creating the user. Please try again later")


            context.user_data.clear()
            return ConversationHandler.END

        
        async def relay_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            
            # Look for last bookings of this persons and send a email to the other
            src = update.message.from_user.id
            
            dst = await relay_service.guess_destination(from_user=str(src),channel="TELEGRAM")
            
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



        async def ask_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                        await relay_service.relay_message(to_plataform=channel,to_user=channel_id, text=text)
                        
                        
                    except Exception as error:
                        await  update.message.reply_text(f"❌ Failed to deliver message to..")
                    
                    finally:
                        return ConversationHandler.END
                    
                    
    
        async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
            """Allow user to cancel."""
            #context.user_data.pop('uploaded_docs', None)
            #context.user_data.pop('booking_id', None)
            context.user_data.clear()
            await update.message.reply_text("Join canceled.")
            return ConversationHandler.END

    

    

    

    

        #--- MENU Handle Message ---

        async def handle_message(self, update, context):
            
            text = update.message.text
            user = update.message.from_user
            
            user_id = str(user.id)
            user_info = { "channel": conf.TELEGRAM_CHANNEL, "user_id" : user_id}
            await self.handle_text_message(text, user_info)
            

        async def handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
                    msg = update.message
                    user = update.message.from_user
                    user_id = str(user.id)
                    user_info = { "channel": conf.TELEGRAM_CHANNEL, "user_id" : user_id}

                    if msg.venue:
                        # Can only be a user who send venue
                        # converto a json format string 
                        # call handler text message with the json string
                        venue_to_text =""
                        await self.handle_text_message(venue_to_text, user_info)
                    elif msg.location:
                        if msg.location.live_period:
                            await msg.reply_text("Live location received.")
                        else:
                            # Can only be a user who send venue
                            # converto a json format string 
                            # call handler text message with the json string
                            venue_to_text =""
                            await self.handle_text_message(venue_to_text, user_info)

        
    
        async def guess_destination(self, plataform="TELEGRAM", from_user=None):

            try:
                dst = await relay_service.guess_destination(from_user, plataform)
                return dst               
            except Exception as error: 
                raise Exception(f"Problems handle message text: {error}")                
    

                

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