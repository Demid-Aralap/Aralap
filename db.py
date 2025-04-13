import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    return psycopg2.connect(
        host="db.plxgzgyqdpoutwtlzjmz.supabase.co",
        port="5432",
        user="postgres",
        password="Aralap2025!",  # ← сюда вставь свой реальный пароль
        dbname="postgres"
    )

def save_observation(user_id, photo_file_id, date, latitude=None, longitude=None, address=None):
    query = """
        INSERT INTO observations (user_id, photo_file_id, date_of_observation, latitude, longitude, address)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, photo_file_id, date, latitude, longitude, address))
        conn.commit()

def get_all_observations():
    query = "SELECT * FROM observations ORDER BY submitted_at DESC"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()
