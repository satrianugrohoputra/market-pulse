import pandas as pd
import streamlit as st
import os
import modules.clean_csv as clean_csv

# Globals to cache CSV data in memory
_df_cache = None

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
        first_col = str(df.columns[0])
        if first_col == "" or first_col.startswith("unnamed"):
            df.rename(columns={df.columns[0]: "id"}, inplace=True)
            
        # Isi data yang kosong dan konversi tipe data secara aman (coerce errors to NaN)
        df['title'] = pd.Series(df['title']).fillna('').astype(str)
        df['review_text'] = pd.Series(df['review_text']).fillna('').astype(str)
        
        df['recommended_ind'] = pd.Series(pd.to_numeric(df['recommended_ind'], errors='coerce')).fillna(0).astype(int)
        df['rating'] = pd.Series(pd.to_numeric(df['rating'], errors='coerce')).fillna(0).astype(int)
        df['age'] = pd.Series(pd.to_numeric(df['age'], errors='coerce')).fillna(0).astype(int)
        df['positive_feedback_count'] = pd.Series(pd.to_numeric(df['positive_feedback_count'], errors='coerce')).fillna(0).astype(int)
        
        # Hanya ambil data dengan rating valid 1 s.d. 5 (membuang data bergeser/malformed)
        df = df[df['rating'].between(1, 5)]
        
        _df_cache = df.reset_index(drop=True)
    return _df_cache

def run_query(query):
    """
    Pemrosesan query analitik menggunakan engine lokal berbasis Pandas DataFrame.
    Tidak ada ketergantungan PostgreSQL sama sekali.
    """
    df_all = get_csv_data()
    q_clean = query.strip().lower().replace('\n', ' ')
    
    # 1. Total Reviews Metrik
    if "select count(*) as total from reviews" in q_clean:
        return pd.DataFrame({"total": [len(df_all)]})
        
    # 2. Loyalitas: QUERY_LOYALITAS_PELANGGAN
    elif "recommendation percentage" in q_clean:
        gp = df_all.groupby(['division_name', 'department_name', 'class_name']).agg(
            total_reviews=('id', 'count'),
            rec_pct=('recommended_ind', lambda x: round(x.mean() * 100, 2)),
            avg_rating=('rating', lambda x: round(x.mean(), 2))
        ).reset_index()
        gp.columns = ["Division", "Department", "Class", "Total Reviews", "Recommendation Percentage", "Average Rating"]
        return pd.DataFrame(gp).sort_values(by="Total Reviews", ascending=False)
        
    # 3. Keluhan: QUERY_KELUHAN_PRODUK
    elif "defect rate" in q_clean:
        gp = df_all.groupby(['division_name', 'department_name', 'class_name']).agg(
            neg_reviews=('rating', lambda x: (x <= 2).sum()),
            total_reviews=('id', 'count')
        ).reset_index()
        gp['Defect Rate'] = round((gp['neg_reviews'] / gp['total_reviews']) * 100, 2)
        gp.columns = ["Division", "Department", "Class", "Negative Reviews", "Total Reviews", "Defect Rate"]
        gp = gp[gp["Negative Reviews"] > 10]
        return pd.DataFrame(gp).sort_values(by="Negative Reviews", ascending=False)
        
    # 4. Efektivitas: QUERY_EFEKTIVITAS_ULASAN
    elif "average helpful votes" in q_clean:
        gp = df_all.groupby('rating').agg(
            avg_helpful=('positive_feedback_count', lambda x: round(x.mean(), 2)),
            max_helpful=('positive_feedback_count', 'max')
        ).reset_index()
        gp.columns = ["Rating", "Average Helpful Votes", "Max Helpful Votes"]
        return pd.DataFrame(gp).sort_values(by="Rating", ascending=False).reset_index(drop=True)
        
    # 5. Segmentasi: QUERY_SEGMENTASI_PASAR
    elif "age group" in q_clean:
        df_temp = df_all.copy()
        df_temp['Age Group'] = pd.Series(df_temp['age']).apply(
            lambda age: 'Gen Z' if age < 30 else ('Milenial' if 30 <= age <= 45 else 'Gen X/Boomers')
        )
        gp = df_temp.groupby(['Age Group', 'department_name']).agg(
            total_purchase=('id', 'count'),
            avg_rating=('rating', lambda x: round(x.mean(), 2))
        ).reset_index()
        gp.columns = ["Age Group", "Department", "Total Purchase", "Average Rating"]
        return pd.DataFrame(gp).sort_values(by=["Age Group", "Total Purchase"], ascending=[True, False])
        
    # 6. Populer: QUERY_PRODUK_POPULER (VERSI FIX TOTAL ANTI-KOSONG)
        # Kita buat deteksinya super sensitif, kalau ada kata 'positive' atau 'feedback' atau 'populer' langsung eksekusi!
    elif "feedback" in q_clean or "positive" in q_clean or "populer" in q_clean or "clothing_id" in q_clean:
        # Ambil data dari cache CSV lokal
        gp = df_all.groupby('clothing_id').agg(
            review_count=('id', 'count'),
            total_feedback=('positive_feedback_count', 'sum'),
            avg_rating=('rating', lambda x: round(x.mean(), 2)),
            rec_rate=('recommended_ind', lambda x: round(x.mean() * 100, 2))
        ).reset_index()
            
        # Paksa susun kolomnya dengan huruf kecil semua
        gp.columns = ["clothing_id", "review_count", "total_positive_feedback", "average_rating", "recommended_rate"]
            
        # Urutkan berdasarkan feedback positif terbanyak dan ambil 10 besar
        df_final_pop = gp.sort_values(by="total_positive_feedback", ascending=False).head(10).reset_index(drop=True)
        return df_final_pop
        
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
                pd.Series(filtered['title']).str.lower().str.contains(keyword_val) | 
                pd.Series(filtered['review_text']).str.lower().str.contains(keyword_val)
            ]
        
        result = pd.DataFrame(filtered[['division_name', 'department_name', 'class_name', 'title', 'review_text', 'rating']]).head(10)
        result.columns = ["Division", "Department", "Class", "Review Title", "Review Text", "Rating"]
        return result.reset_index(drop=True)
        
    # default jika query tidak dikenal
    return pd.DataFrame()
