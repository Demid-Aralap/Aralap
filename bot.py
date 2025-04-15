import logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from config import BOT_TOKEN, ADMINS
from db import save_observation, get_all_observations
import pandas as pd
from io import StringIO
from datetime import datetime
import threading
import http.server
import socketserver
import os
import mimetypes

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Этапы диалога
PHOTO, DATE, LOCATION, FULLNAME, CONSENT, NEXT = range(6)

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\nЭтот бот собирает наблюдения за опылителями для научных исследований.\n\nВы даете согласие на использование ваших данных в исследовательских целях?",
        reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return CONSENT

# Обработка согласия
async def consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.lower() != "да":
        await update.message.reply_text("Хорошо, данные не будут использованы. Вы можете завершить диалог командой /cancel.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    await update.message.reply_text("Спасибо! Хотите указать ФИО? (можно пропустить)", reply_markup=ReplyKeyboardMarkup([["Пропустить"]], one_time_keyboard=True, resize_keyboard=True))
    return FULLNAME

# Обработка ФИО
async def fullname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text != "Пропустить":
        context.user_data['fullname'] = update.message.text
    else:
        context.user_data['fullname'] = None

    await update.message.reply_text("Отправьте одно или несколько фото/видео наблюдения 🐝", reply_markup=ReplyKeyboardRemove())
    context.user_data['media'] = []
    return PHOTO

# Прием фото/видео/документов
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    file_id = None
    media_type = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        media_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "video"
    elif update.message.document:
        mime = update.message.document.mime_type or ""
        if mime.startswith("image"):
            media_type = "photo"
        elif mime.startswith("video"):
            media_type = "video"
        else:
            await update.message.reply_text("Документ должен быть фото или видео.")
            return PHOTO
        file_id = update.message.document.file_id

    if file_id:
        context.user_data['media'].append(file_id)
        await update.message.reply_text("Добавлено! Можете отправить ещё или нажмите \"Далее\".",
            reply_markup=ReplyKeyboardMarkup([["Далее"]], one_time_keyboard=True, resize_keyboard=True))
    return PHOTO

# После фото — дата
async def date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Укажите дату и время наблюдения (например, 13-04-2025 15:30)")
    return DATE

# Обработка даты
async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        dt = datetime.strptime(update.message.text, "%d-%m-%Y %H:%M")
        context.user_data['datetime'] = dt
    except ValueError:
        await update.message.reply_text("Неверный формат. Введите как 13-04-2025 15:30")
        return DATE

    await update.message.reply_text("Теперь отправьте геолокацию или напишите адрес/координаты места наблюдения.")
    return LOCATION

# Обработка локации
async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lat, lon, address = None, None, None
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
    elif update.message.text:
        text = update.message.text.strip()
        address = text
        # Пробуем извлечь координаты из текста
        import re
        match = re.search(r'(-?\d+(\.\d+)?)[,\s]+(-?\d+(\.\d+)?)', text)
        if match:
            lat, lon = float(match.group(1)), float(match.group(3))

    context.user_data['latitude'] = lat
    context.user_data['longitude'] = lon
    context.user_data['address'] = address

    for file_id in context.user_data['media']:
        try:
            save_observation(
                user_id=update.message.from_user.id,
                photo_file_id=file_id,
                date=context.user_data['datetime'],
                latitude=lat,
                longitude=lon,
                address=address,
                fullname=context.user_data.get('fullname')
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении наблюдения: {e}")

    await update.message.reply_text("Наблюдение(-я) сохранено ✅\nХотите добавить ещё одно?",
        reply_markup=ReplyKeyboardMarkup([["Добавить ещё", "Завершить"]], one_time_keyboard=True, resize_keyboard=True))
    return NEXT

# Следующее наблюдение
async def next_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "Добавить ещё":
        context.user_data.clear()
        await update.message.reply_text("Отправьте фото/видео нового наблюдения 🐝")
        context.user_data['media'] = []
        return PHOTO
    else:
        await update.message.reply_text("Спасибо за участие! 💚", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

# Экспорт
async def export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMINS:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    observations = get_all_observations()
    if not observations:
        await update.message.reply_text("Наблюдений пока нет.")
        return

    df = pd.DataFrame(observations)

    file_links = []
    for file_id in df['photo_file_id']:
        try:
            file = await context.bot.get_file(file_id)
            file_links.append(file.file_path)
        except:
            file_links.append("Ошибка получения ссылки")

    df['file_link'] = file_links

    csv = df.to_csv(index=False)
    file = StringIO(csv)
    file.name = "observations.csv"
    await update.message.reply_document(document=file)

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Диалог отменён.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Заглушка HTTP-сервера для Render
def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Dummy server listening on port {port}")
        httpd.serve_forever()

# Основная функция
def main():
    threading.Thread(target=start_dummy_server, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("export", export))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONSENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, consent)],
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname)],
            PHOTO: [
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, photo),
                MessageHandler(filters.Regex("^Далее$"), date),
            ],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_date)],
            LOCATION: [MessageHandler(filters.LOCATION | filters.TEXT & ~filters.COMMAND, location)],
            NEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, next_step)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
