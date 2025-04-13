import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackContext
from telegram.ext import filters
from config import BOT_TOKEN, ADMINS, LANGUAGES, DEFAULT_LANGUAGE
from db import save_observation, get_all_observations
import pandas as pd
from io import StringIO

# Включаем логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

PHOTO, DATE, LOCATION = range(3)

# Функция старта
async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    language = DEFAULT_LANGUAGE  # Тут можно добавить выбор языка
    await update.message.reply_text(f"Привет, {user.first_name}! Отправь мне фото опылителя 🐝")
    return PHOTO

# Прием фото
async def photo(update: Update, context: CallbackContext):
    user = update.message.from_user
    context.user_data['photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("Отлично! Укажи дату наблюдения (например, 2025-04-13) или нажми 'Сегодня'.")
    return DATE

# Сохранение даты наблюдения
async def date(update: Update, context: CallbackContext):
    date = update.message.text
    context.user_data['date'] = date
    await update.message.reply_text("Теперь отправь свою геолокацию или напиши адрес места наблюдения.")
    return LOCATION

# Сохранение локации
async def location(update: Update, context: CallbackContext):
    if update.message.location:
        context.user_data['latitude'] = update.message.location.latitude
        context.user_data['longitude'] = update.message.location.longitude
    else:
        context.user_data['address'] = update.message.text

    # Сохранение в базу данных
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

# Экспорт CSV для админов
async def export(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMINS:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    observations = get_all_observations()
    df = pd.DataFrame(observations)
    csv = df.to_csv(index=False)
    file = StringIO(csv)
    await update.message.reply_document(document=file, filename="observations.csv")
    
# Ошибка
async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("Диалог отменён.")
    return ConversationHandler.END

# Основная функция
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчик команд
    application.add_handler(CommandHandler("export", export))
    
    # Раздел диалога
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date)],
            LOCATION: [MessageHandler(filters.TEXT | filters.LOCATION, location)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conversation_handler)
    
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
