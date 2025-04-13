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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO observations (user_id, photo_file_id, date_of_observation, latitude, longitude, address)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, photo_file_id, date, latitude, longitude, address))
    conn.commit()
    cur.close()
    conn.close()

def get_all_observations():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM observations ORDER BY submitted_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
