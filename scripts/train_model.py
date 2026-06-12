"""
train_model.py
==============
Script training model Logistic Regression + TF-IDF untuk analisis sentimen
dataset e-commerce bawaan (ecommercereviews_clean.csv).

Parameter yang digunakan (sesuai Fase 5 blueprint):
  - TfidfVectorizer: ngram_range=(1,2), sublinear_tf=True, max_features=5000
  - LogisticRegression: class_weight='balanced', max_iter=1000
  - train_test_split: stratify=y, test_size=0.2
"""

import pandas as pd
import re
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

# ─── Stopwords Gabungan Indonesia + Inggris ───────────────────────────────────
INDONESIAN_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "dalam", "tidak", "saya", "kami", "kita", "mereka",
    "dia", "anda", "aku", "kamu", "bisa", "ada", "sudah", "akan", "juga",
    "lebih", "sangat", "sekali", "tapi", "namun", "atau", "jika", "maka",
    "karena", "sehingga", "setelah", "sebelum", "belum", "sedang", "masih",
    "hanya", "selalu", "baru", "oleh", "kepada", "atas", "bawah", "antara",
    "sejak", "hingga", "kalau", "meski", "walaupun", "supaya", "agar",
    "bahwa", "seperti", "ketika", "saat", "waktu", "setiap", "semua",
    "banyak", "sedikit", "sering", "kadang", "pernah", "jangan", "harus",
    "perlu", "amat", "cukup", "memang", "tentu", "pasti", "mungkin",
    "kira", "begitu", "demikian", "hal", "cara", "tahun", "hari", "bulan",
    "sy", "yg", "ga", "gak", "nggak", "ngga", "udah", "udh", "emg",
    "emang", "blm", "sdh", "krn", "karna", "bgt", "banget", "lg", "kl",
    "klo", "kalo", "tp", "tdk",
}
ALL_STOPWORDS = list(set(ENGLISH_STOP_WORDS) | INDONESIAN_STOPWORDS)


# ─── Fungsi: Pembersihan Teks ─────────────────────────────────────────────────
def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    # Hapus tanda baca dan karakter selain huruf
    text = re.sub(r'[^a-z\s]', '', text)
    # Hapus stopwords gabungan
    words = text.split()
    words = [w for w in words if w not in ALL_STOPWORDS and len(w) > 1]
    return " ".join(words)


import sys

# ─── Fungsi Utama: Training ────────────────────────────────────────────────────
def train_and_save():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "data", "ecommercereviews_clean.csv")

    # Buat file clean jika belum ada
    if not os.path.exists(csv_path):
        sys.path.append(base_dir)
        from modules import clean_csv
        clean_csv.clean_csv_file()

    print("[INFO] Membaca dataset...")
    df = pd.read_csv(csv_path, on_bad_lines='skip')

    # Normalisasi nama kolom
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Konversi dan validasi rating
    df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
    df = df.dropna(subset=['rating'])

    # Filter: hanya rating 1-2 (Negatif) dan 4-5 (Positif), buang rating 3
    print("[INFO] Memproses data ulasan...")
    df_clean = df[df['rating'] != 3].copy()

    # Label sentimen biner: 4-5 = Positif (1), 1-2 = Negatif (0)
    df_clean['sentiment'] = df_clean['rating'].apply(lambda x: 1 if x >= 4 else 0)

    # Bersihkan teks ulasan
    df_clean['review_text'] = df_clean['review_text'].astype(str)
    df_clean['cleaned_text'] = df_clean['review_text'].apply(clean_text)

    # Hapus baris teks kosong setelah cleaning
    df_clean = df_clean[df_clean['cleaned_text'].str.strip() != ""]

    # Laporan distribusi kelas
    class_dist = df_clean['sentiment'].value_counts()
    print(f"   Distribusi kelas -> Positif: {class_dist.get(1,0):,} | Negatif: {class_dist.get(0,0):,}")

    X = df_clean['cleaned_text']
    y = df_clean['sentiment']

    # -- Train-Test Split dengan Stratifikasi --
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y          # Jaga proporsi kelas positif/negatif tetap seimbang
    )
    print(f"   Train: {len(X_train):,} | Test: {len(X_test):,}")

    # -- TF-IDF Vectorizer (Fase 5 update) --
    print("[INFO] Ekstraksi fitur menggunakan TF-IDF (ngram_range=(1,2))...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),     # Tangkap frasa: "tidak bagus", "sangat memuaskan"
        sublinear_tf=True,      # Skalakan frekuensi kata agar lebih adil
        stop_words=ALL_STOPWORDS
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # -- Logistic Regression (Fase 5 update) --
    print("[INFO] Melatih model Logistic Regression (class_weight=balanced)...")
    model = LogisticRegression(
        max_iter=1000,
        class_weight='balanced',    # Atasi imbalance positif >> negatif
        C=1.0,
        solver='lbfgs'
    )
    model.fit(X_train_vec, y_train)

    # -- Evaluasi --
    y_pred = model.predict(X_test_vec)
    acc = accuracy_score(y_test, y_pred)
    print(f"[RESULT] Akurasi model: {acc * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Negatif", "Positif"], zero_division=0))

    # -- Simpan Model & Vectorizer --
    model_path = os.path.join(base_dir, "models", "model_sentimen.pkl")
    vectorizer_path = os.path.join(base_dir, "models", "vectorizer.pkl")

    print(f"[INFO] Menyimpan model ke {model_path}...")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    print(f"[INFO] Menyimpan vectorizer ke {vectorizer_path}...")
    with open(vectorizer_path, "wb") as f:
        pickle.dump(vectorizer, f)

    print("[DONE] Proses training selesai!")
    return acc


if __name__ == "__main__":
    train_and_save()
