import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

def get_connection():
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dbname=DB_CONFIG["database"]
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
