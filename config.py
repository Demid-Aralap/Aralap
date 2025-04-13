# config.py

BOT_TOKEN = "YOUR_BOT_TOKEN"  # 🔐 Установи свой Telegram Bot Token

DB_CONFIG = {
    "host": "YOUR_DB_HOST.supabase.co",  # например, xyz.supabase.co
    "port": 5432,
    "user": "YOUR_DB_USER",              # например, postgres
    "password": "YOUR_DB_PASSWORD",
    "database": "postgres"
}

ADMINS = [123456789]  # Замени на свой Telegram user_id

DEFAULT_LANGUAGE = "ru"
LANGUAGES = ["ru", "kz"]
