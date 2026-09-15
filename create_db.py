import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    conn = psycopg2.connect(user="postgres", password="Abhi@2004", host="localhost", port="5432")
except Exception:
    try:
        conn = psycopg2.connect(user="postgres", password="password", host="localhost", port="5432")
    except Exception:
        try:
            conn = psycopg2.connect(user="postgres", password="postgres", host="localhost", port="5432")
        except Exception as e:
            print("Failed to connect to PostgreSQL:", e)
            exit(1)

conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

try:
    cursor.execute("CREATE DATABASE event_ai;")
    print("Database event_ai created successfully.")
except psycopg2.errors.DuplicateDatabase:
    print("Database event_ai already exists.")

cursor.close()
conn.close()
