import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from config import BOT_TOKEN, ADMINS, LANGUAGES, DEFAULT_LANGUAGE
from db import save_observation, get_all_observations
import pandas as pd
from io import StringIO

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Этапы диалога
PHOTO, DATE, LOCATION = range(3)

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Отправь мне фото опылителя 🐝"
    )
    return PHOTO

# Прием фото
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['photo'] = update.message.photo[-1].file_id
    await update.message.reply_text(
        "Отлично! Укажи дату наблюдения (например, 2025-04-13) или нажми 'Сегодня'."
    )
    return DATE

# Сохранение даты
async def date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['date'] = update.message.text
    await update.message.reply_text(
        "Теперь отправь геолокацию или напиши адрес места наблюдения."
    )
    return LOCATION

# Сохранение локации и запись в БД
async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.location:
        context.user_data['latitude'] = update.message.location.latitude
        context.user_data['longitude'] = update.message.location.longitude
    else:
        context.user_data['address'] = update.message.text

    save_observation(
        user_id=update.message.from_user.id,
        photo_file_id=context.user_data['photo'],
        date=context.user_data['date'],
        latitude=context.user_data.get('latitude'),
        longitude=context.user_data.get('longitude'),
        address=context.user_data.get('address')
    )

    await update.message.reply_text("Наблюдение сохранено! Спасибо 💚")
    return ConversationHandler.END

# Экспорт наблюдений (только для админов)
async def export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMINS:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    observations = get_all_observations()
    if not observations:
        await update.message.reply_text("Наблюдений пока нет.")
        return

    df = pd.DataFrame(observations)
    csv = df.to_csv(index=False)
    file = StringIO(csv)
    file.name = "observations.csv"

    await update.message.reply_document(document=file)

# Отмена диалога
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Диалог отменён.")
    return ConversationHandler.END

# Основная функция
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Команда экспорта
    application.add_handler(CommandHandler("export", export))

    # Обработка диалога
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date)],
            LOCATION: [MessageHandler(filters.LOCATION | filters.TEXT, location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conversation_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
