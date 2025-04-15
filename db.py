from supabase import create_client, Client
import os
from datetime import datetime
import asyncio

SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://your-project.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "your-secret-api-key"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def save_observation(user_id, photo_file_id, date: datetime, latitude=None, longitude=None, address=None, fullname=None):
    loop = asyncio.get_event_loop()
    data = {
        "user_id": user_id,
        "photo_file_id": photo_file_id,
        "datetime": date.isoformat(),
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "fullname": fullname,
    }
    # Выполняем блокирующий вызов в отдельном потоке
    await loop.run_in_executor(None, lambda: supabase.table("observations").insert(data).execute())

def get_all_observations():
    response = supabase.table("observations").select("*").execute()
    return response.data
