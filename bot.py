import os
import logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, ConversationHandler, filters)
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Supabase credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Telegram Bot Token
TOKEN = os.environ.get("BOT_TOKEN")

# States for ConversationHandler
PHOTO, LOCATION, FULLNAME, CONFIRM = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data['media'] = []
    await update.message.reply_text(
        "Привет! Я бот проекта Aralap. Пожалуйста, отправьте фото или видео наблюдения (можно несколько)."
    )
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    file_id = None
    media_type = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        media_type = "фото"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "видео"
    elif update.message.document:
        mime = update.message.document.mime_type or ""
        if mime.startswith("image"):
            media_type = "фото"
        elif mime.startswith("video"):
            media_type = "видео"
        else:
            await update.message.reply_text("Документ должен быть фото или видео.")
            return PHOTO
        file_id = update.message.document.file_id

    if file_id:
        context.user_data['media'].append(file_id)
        await update.message.reply_text(
            f"{media_type.capitalize()} добавлено! Можете отправить ещё или нажмите \"Далее\".",
            reply_markup=ReplyKeyboardMarkup([["Далее"]], one_time_keyboard=True, resize_keyboard=True)
        )

    return PHOTO

async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.location:
        context.user_data['location'] = {
            'latitude': update.message.location.latitude,
            'longitude': update.message.location.longitude
        }
        await update.message.reply_text("Спасибо! Теперь введите ваше имя и фамилию.")
        return FULLNAME
    else:
        address = update.message.text
        context.user_data['address'] = address
        await update.message.reply_text("Спасибо! Теперь введите ваше имя и фамилию.")
        return FULLNAME

async def fullname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['fullname'] = update.message.text
    await update.message.reply_text(
        "Спасибо! Ваши данные сохранены. Хотите отправить ещё одно наблюдение? (Да/Нет)",
        reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
    )
    await save_observation(context.user_data)
    return CONFIRM

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.lower() == "да":
        context.user_data.clear()
        context.user_data['media'] = []
        await update.message.reply_text("Отправьте следующее фото или видео.")
        return PHOTO
    else:
        await update.message.reply_text("Спасибо за участие! До встречи.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

async def save_observation(data):
    record = {
        "media": ",".join(data.get("media", [])),
        "latitude": data.get("location", {}).get("latitude") if data.get("location") else None,
        "longitude": data.get("location", {}).get("longitude") if data.get("location") else None,
        "address": data.get("address"),
        "fullname": data.get("fullname"),
        "timestamp": datetime.utcnow().isoformat()
    }
    supabase.table("observations").insert(record).execute()

async def export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = supabase.table("observations").select("*").execute()
    data = result.data
    if not data:
        await update.message.reply_text("Нет сохранённых наблюдений.")
        return

    df = pd.DataFrame(data)
    csv = df.to_csv(index=False, sep=";")
    with open("observations.csv", "w", encoding="utf-8") as f:
        f.write(csv)

    with open("observations.csv", "rb") as f:
        await update.message.reply_document(document=f, filename="observations.csv")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHOTO: [
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.IMAGE | filters.Document.VIDEO, photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, photo),
            ],
            LOCATION: [
                MessageHandler(filters.LOCATION, location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, location),
            ],
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("export", export))
    application.run_polling()
