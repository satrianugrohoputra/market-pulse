# pyrefly: ignore [untyped-import]
import psycopg2
import pandas as pd
import streamlit as st
import os
import modules.clean_csv as clean_csv

# Globals to cache CSV data in memory
_df_cache = None
_db_warning_shown = False

def get_connection():
    # Sesuaikan konfigurasi ini dengan akun PostgreSQL Laragon kamu
    return psycopg2.connect(
        host="localhost",
        database="market_pulse",
        user="postgres", 
        password=st.secrets.get("DB_PASSWORD", "password-anda")
    )

def get_csv_data():
    global _df_cache
    if _df_cache is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        csv_path = os.path.join(base_dir, "data", "ecommercereviews_clean.csv")
        if not os.path.exists(csv_path):
            # Fallback jika belum di-clean
            raw_path = os.path.join(base_dir, "data", "ecommercereviews.csv")
            if os.path.exists(raw_path):
                # Clean on the fly
                clean_csv.clean_csv_file()
            else:
                raise FileNotFoundError(f"File dataset {csv_path} atau {raw_path} tidak ditemukan.")
        
        # Membaca data CSV yang sudah bersih
        df = pd.read_csv(csv_path, on_bad_lines='skip')
        
        # Bersihkan nama kolom agar seragam dengan schema SQL
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        
        # Ganti nama kolom index kosong jika ada
        if df.columns[0] == "" or df.columns[0].startswith("unnamed"):
            df.rename(columns={df.columns[0]: "id"}, inplace=True)
            
        # Isi data yang kosong dan konversi tipe data secara aman (coerce errors to NaN)
        df['title'] = df['title'].fillna('').astype(str)
        df['review_text'] = df['review_text'].fillna('').astype(str)
        
        df['recommended_ind'] = pd.to_numeric(df['recommended_ind'], errors='coerce').fillna(0).astype(int)
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce').fillna(0).astype(int)
        df['age'] = pd.to_numeric(df['age'], errors='coerce').fillna(0).astype(int)
        df['positive_feedback_count'] = pd.to_numeric(df['positive_feedback_count'], errors='coerce').fillna(0).astype(int)
        
        # Hanya ambil data dengan rating valid 1 s.d. 5 (membuang data bergeser/malformed)
        df = df[df['rating'].between(1, 5)]
        
        _df_cache = df.reset_index(drop=True)
    return _df_cache

def run_query(query):
    try:
        # Hubungkan ke database lokal
        conn = get_connection()
        try:
            df = pd.read_sql_query(query, conn)
            return df
        finally:
            conn.close()
    except Exception as db_err:
        # Jika database gagal terhubung (misal pada komputer teman atau server mati), 
        # jalankan fallback menggunakan Pandas dan ecommercereviews.csv lokal.
        global _db_warning_shown
        if not _db_warning_shown:
            try:
                st.sidebar.warning("⚠️ Mode Offline: Gagal terhubung ke PostgreSQL. Aplikasi menggunakan data CSV lokal.")
                _db_warning_shown = True
            except Exception:
                pass
            
        df_all = get_csv_data()
        q_clean = query.strip().lower().replace('\n', ' ')
        
        # 1. Total Reviews Metrik
        if "select count(*) as total from reviews" in q_clean:
            return pd.DataFrame({"total": [len(df_all)]})
            
        # 2. Loyalitas: QUERY_LOYALITAS_PELANGGAN
        elif "avg(r.recommended_ind)" in q_clean and "average rating" in q_clean and "clothing_id" not in q_clean:
            gp = df_all.groupby(['division_name', 'department_name', 'class_name']).agg(
                total_reviews=('id', 'count'),
                rec_pct=('recommended_ind', lambda x: round(x.mean() * 100, 2)),
                avg_rating=('rating', lambda x: round(x.mean(), 2))
            ).reset_index()
            gp.columns = ["Division", "Department", "Class", "Total Reviews", "Recommendation Percentage", "Average Rating"]
            return gp.sort_values(by="Total Reviews", ascending=False)
            
        # 3. Keluhan: QUERY_KELUHAN_PRODUK
        elif "defect rate" in q_clean:
            gp = df_all.groupby(['division_name', 'department_name', 'class_name']).agg(
                neg_reviews=('rating', lambda x: (x <= 2).sum()),
                total_reviews=('id', 'count')
            ).reset_index()
            gp['Defect Rate'] = round((gp['neg_reviews'] / gp['total_reviews']) * 100, 2)
            gp.columns = ["Division", "Department", "Class", "Negative Reviews", "Total Reviews", "Defect Rate"]
            gp = gp[gp["Negative Reviews"] > 10]
            return gp.sort_values(by="Negative Reviews", ascending=False)
            
        # 4. Efektivitas: QUERY_EFEKTIVITAS_ULASAN
        elif "average helpful votes" in q_clean:
            gp = df_all.groupby('rating').agg(
                avg_helpful=('positive_feedback_count', lambda x: round(x.mean(), 2)),
                max_helpful=('positive_feedback_count', 'max')
            ).reset_index()
            gp.columns = ["Rating", "Average Helpful Votes", "Max Helpful Votes"]
            return gp.sort_values(by="Rating", ascending=False).reset_index(drop=True)
            
        # 5. Segmentasi: QUERY_SEGMENTASI_PASAR
        elif "age group" in q_clean:
            df_temp = df_all.copy()
            df_temp['Age Group'] = df_temp['age'].apply(
                lambda age: 'Gen Z' if age < 30 else ('Milenial' if 30 <= age <= 45 else 'Gen X/Boomers')
            )
            gp = df_temp.groupby(['Age Group', 'department_name']).agg(
                total_purchase=('id', 'count'),
                avg_rating=('rating', lambda x: round(x.mean(), 2))
            ).reset_index()
            gp.columns = ["Age Group", "Department", "Total Purchase", "Average Rating"]
            return gp.sort_values(by=["Age Group", "Total Purchase"], ascending=[True, False])
            
        # 6. Populer: QUERY_PRODUK_POPULER
        elif "total positive feedback" in q_clean:
            gp = df_all.groupby(['clothing_id', 'division_name', 'department_name', 'class_name']).agg(
                review_count=('id', 'count'),
                total_feedback=('positive_feedback_count', 'sum'),
                avg_rating=('rating', lambda x: round(x.mean(), 2)),
                rec_rate=('recommended_ind', lambda x: round(x.mean() * 100, 2))
            ).reset_index()
            gp.columns = ["Clothing ID", "Division", "Department", "Class", "Review Count", "Total Positive Feedback", "Average Rating", "Recommended Rate"]
            return gp.sort_values(by="Total Positive Feedback", ascending=False).head(10).reset_index(drop=True)
            
        # 7. Dinamis: QUERY_DINAMIS
        elif "ilike" in q_clean:
            import re
            rating_match = re.search(r"rating\s*=\s*(\d+)", q_clean)
            rating_val = int(rating_match.group(1)) if rating_match else 5
            
            # Cari keyword di query
            keyword_match = re.search(r"title\s+ilike\s+'%%(.*?)%%'", q_clean)
            if not keyword_match:
                keyword_match = re.search(r"title\s+ilike\s+'%(.*?)%'", q_clean)
            keyword_val = keyword_match.group(1) if keyword_match else ""
            
            filtered = df_all[df_all['rating'] == rating_val]
            if keyword_val:
                keyword_val = keyword_val.lower()
                filtered = filtered[
                    filtered['title'].str.lower().str.contains(keyword_val) | 
                    filtered['review_text'].str.lower().str.contains(keyword_val)
                ]
            
            result = filtered[['division_name', 'department_name', 'class_name', 'title', 'review_text', 'rating']].head(10)
            result.columns = ["Division", "Department", "Class", "Review Title", "Review Text", "Rating"]
            return result.reset_index(drop=True)
            
        # default jika query tidak dikenal
        return pd.DataFrame()


# ─── Fungsi: Inisialisasi Schema Database ────────────────────────────────────

def init_schema():
    """
    Membuat tabel 'datasets' dan menambahkan kolom baru ke tabel 'reviews'
    jika belum ada. Aman dijalankan berkali-kali (idempotent).
    """
    ddl_datasets = """
    CREATE TABLE IF NOT EXISTS datasets (
        id                SERIAL PRIMARY KEY,
        file_name         VARCHAR(255)  NOT NULL,
        uploaded_at       TIMESTAMP     DEFAULT NOW(),
        detected_domain   VARCHAR(100),
        detected_language VARCHAR(20),
        row_count         INTEGER,
        is_base_dataset   BOOLEAN DEFAULT FALSE
    );
    """
    ddl_reviews_cols = """
    ALTER TABLE reviews
        ADD COLUMN IF NOT EXISTS dataset_id           INTEGER REFERENCES datasets(id) ON DELETE CASCADE,
        ADD COLUMN IF NOT EXISTS predicted_ind        INTEGER,
        ADD COLUMN IF NOT EXISTS predicted_sentiment  VARCHAR(20),
        ADD COLUMN IF NOT EXISTS is_corrected         BOOLEAN DEFAULT FALSE;
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(ddl_datasets)
        cur.execute(ddl_reviews_cols)
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── Fungsi: Insert Metadata Dataset ─────────────────────────────────────────

def insert_dataset(file_name: str, row_count: int,
                   detected_language: str = "unknown",
                   detected_domain: str = "general") -> dict:
    """
    Menyimpan metadata dataset baru ke tabel 'datasets'.
    Returns: dict { "ok": bool, "dataset_id": int | None, "error": str | None }
    """
    sql = """
    INSERT INTO datasets (file_name, row_count, detected_language, detected_domain)
    VALUES (%s, %s, %s, %s)
    RETURNING id;
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, (file_name, row_count, detected_language, detected_domain))
        dataset_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "dataset_id": dataset_id, "error": None}
    except Exception as e:
        return {"ok": False, "dataset_id": None, "error": str(e)}


# ─── Fungsi: Bulk Insert Ulasan ───────────────────────────────────────────────

def bulk_insert_reviews(df: pd.DataFrame, dataset_id: int, chunksize: int = 1000) -> dict:
    """
    Menyimpan ulasan hasil analisis ke tabel 'reviews' secara bulk
    (1000 baris per batch agar tidak timeout).

    DataFrame harus memiliki kolom: _review_text, _rating, _predicted_ind,
    _predicted_label, _is_corrected.

    Returns: dict { "ok": bool, "inserted": int, "error": str | None }
    """
    sql = """
    INSERT INTO reviews
        (review_text, rating, dataset_id, predicted_ind, predicted_sentiment, is_corrected)
    VALUES (%s, %s, %s, %s, %s, %s);
    """
    total_inserted = 0
    try:
        conn = get_connection()
        cur = conn.cursor()

        rows = df[["_review_text", "_rating", "_predicted_ind",
                   "_predicted_label", "_is_corrected"]].values.tolist()

        for i in range(0, len(rows), chunksize):
            batch = rows[i : i + chunksize]
            data = [
                (r[0], float(r[1]) if r[1] is not None and str(r[1]) != "nan" else None,
                 dataset_id,
                 int(r[2]) if r[2] is not None else None,
                 r[3], bool(r[4]))
                for r in batch
            ]
            cur.executemany(sql, data)
            conn.commit()
            total_inserted += len(batch)

        cur.close()
        conn.close()
        return {"ok": True, "inserted": total_inserted, "error": None}
    except Exception as e:
        return {"ok": False, "inserted": total_inserted, "error": str(e)}