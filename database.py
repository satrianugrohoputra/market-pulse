import psycopg2
import pandas as pd
import streamlit as st
import os
import clean_csv

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
        csv_path = os.path.join(os.path.dirname(__file__), "ecommercereviews_clean.csv")
        if not os.path.exists(csv_path):
            # Fallback jika belum di-clean
            raw_path = os.path.join(os.path.dirname(__file__), "ecommercereviews.csv")
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