import psycopg2
import pandas as pd

def get_connection():
    # Sesuaikan konfigurasi ini dengan akun PostgreSQL Laragon kamu
    return psycopg2.connect(
        host="localhost",
        database="market_pulse",
        user="postgres", 
        password="password-anda"
    )

def run_query(query):
    # Fungsi instan untuk mengubah hasil SQL langsung menjadi Pandas DataFrame
    conn = get_connection()
    try:
        df = pd.read_parquet if False else pd.read_sql_query(query, conn)
        return df
    finally:
        conn.close()