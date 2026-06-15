"""
ml_pipeline.py
==============
Pipeline Machine Learning untuk analisis sentimen dataset yang diunggah.
Mendukung dua mode:
  1. Train-On-The-Fly  : Dataset punya kolom rating → latih model baru
  2. Fallback Mode     : Dataset tanpa rating → gunakan model base yang ada
Dilengkapi stopwords Bahasa Indonesia bawaan (tanpa library eksternal).
"""

import os
import re
import pickle
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# ─── Stopwords Gabungan: Inggris + Indonesia ──────────────────────────────────

INDONESIAN_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "dalam", "tidak", "saya", "kami", "kita", "mereka",
    "dia", "anda", "aku", "kamu", "bisa", "ada", "sudah", "akan", "juga",
    "lebih", "sangat", "sekali", "tapi", "namun", "atau", "jika", "maka",
    "karena", "sehingga", "setelah", "sebelum", "sudah", "belum", "sedang",
    "masih", "hanya", "selalu", "sudah", "punya", "dapat", "lagi", "baru",
    "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan",
    "sembilan", "sepuluh", "pertama", "kedua", "ketiga", "oleh", "kepada",
    "atas", "bawah", "antara", "sejak", "hingga", "kalau", "meski",
    "walaupun", "supaya", "agar", "bahwa", "seperti", "ketika", "saat",
    "waktu", "setiap", "semua", "banyak", "sedikit", "sering", "kadang",
    "pernah", "jangan", "harus", "perlu", "sangat", "amat", "cukup",
    "memang", "tentu", "pasti", "mungkin", "kira", "katanya", "begitu",
    "demikian", "hal", "cara", "tahun", "hari", "bulan", "sama", "berbeda",
    "sy", "yg", "ga", "gak", "nggak", "ngga", "udah", "udh", "emg",
    "emang", "blm", "sdh", "krn", "karna", "bgt", "banget", "lg",
    "lagi", "kl", "klo", "kalo", "tp", "tapi", "tdk", "tidak",
}

# Gabungkan dengan stopwords Inggris dari sklearn, kecualikan kata negasi
NEGATION_WORDS = {"not", "no", "never", "without", "but", "tidak", "kurang", "belum", "bukan", "jangan", "tapi", "namun", "tanpa"}
ALL_STOPWORDS = (set(ENGLISH_STOP_WORDS) | INDONESIAN_STOPWORDS) - NEGATION_WORDS


# ─── Konstanta ────────────────────────────────────────────────────────────────

MIN_SAMPLES_PER_CLASS = 30  # Minimal sampel per kelas untuk Train-On-The-Fly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "model_sentimen.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "models", "vectorizer.pkl")


# ─── Fungsi: Pembersihan Teks ─────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Lowercase, hapus non-alfabet, hapus stopwords gabungan."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    words = [w for w in text.split() if w not in ALL_STOPWORDS and len(w) > 1]
    return " ".join(words)


# ─── Fungsi: Train-On-The-Fly ─────────────────────────────────────────────────

def run_train_on_the_fly(df: pd.DataFrame) -> dict | None:
    """
    Melatih model TF-IDF + Logistic Regression langsung dari dataset baru.
    Dataset sudah dibersihkan oleh upload_processor (kolom: _review_text, _rating).

    Returns dict: { "model", "vectorizer", "accuracy", "report_text", "mode" }
    """
    # Filter: hanya rating 1-2 (Negatif) dan 4-5 (Positif), buang rating 3
    df_train = df[df["_rating"].notna()].copy()
    df_train = df_train[df_train["_rating"] != 3]
    df_train["_sentiment"] = pd.Series(df_train["_rating"]).apply(lambda x: 1 if x >= 4 else 0)

    # Cek apakah cukup sampel per kelas
    class_counts = pd.Series(df_train["_sentiment"]).value_counts()
    if len(class_counts) < 2 or class_counts.min() < MIN_SAMPLES_PER_CLASS:
        return None  # Sinyal untuk menggunakan fallback

    # Bersihkan teks
    df_train["_cleaned"] = pd.Series(df_train["_review_text"]).apply(clean_text)
    df_train = df_train[pd.Series(df_train["_cleaned"]).str.strip() != ""]

    X = df_train["_cleaned"]
    y = df_train["_sentiment"]

    # Train-Test Split dengan stratifikasi
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # TF-IDF dengan ngram dan sublinear scaling
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 3),     # Tangkap frasa negasi dan penguat (unigram, bigram, trigram)
        sublinear_tf=True,      # Skalakan tf agar kata dominan tidak menguasai
        stop_words=list(ALL_STOPWORDS)
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # Logistic Regression dengan class_weight balanced
    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",  # Atasi data imbalanced positif/negatif
        C=1.0,
        solver="lbfgs"
    )
    model.fit(X_train_vec, y_train)

    y_pred = model.predict(X_test_vec)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=["Negatif", "Positif"], zero_division=0)  # type: ignore

    return {
        "model": model,
        "vectorizer": vectorizer,
        "accuracy": accuracy,
        "report_text": report,
        "mode": "train_on_the_fly"
    }


# ─── Fungsi: Fallback Mode ────────────────────────────────────────────────────

def run_fallback_load() -> dict | None:
    """
    Memuat model base (model_sentimen.pkl + vectorizer.pkl) yang sudah ada.
    Returns None jika file pkl tidak ditemukan.
    """
    if not os.path.exists(MODEL_PATH) or not os.path.exists(VECTORIZER_PATH):
        return None
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(VECTORIZER_PATH, "rb") as f:
        vectorizer = pickle.load(f)
    return {
        "model": model,
        "vectorizer": vectorizer,
        "accuracy": None,
        "report_text": None,
        "mode": "fallback"
    }


# ─── Fungsi: Prediksi Sentimen ────────────────────────────────────────────────

def predict_sentiments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Memprediksi sentimen seluruh baris di DataFrame (kolom _review_text wajib ada).
    Secara otomatis memilih Train-On-The-Fly atau Fallback.

    Returns: DataFrame dengan kolom tambahan:
      - _cleaned_text     : teks yang sudah dibersihkan
      - _predicted_ind    : 1=Positif, 0=Negatif
      - _predicted_label  : 'Positif' / 'Negatif'
      - _is_corrected     : True jika dikoreksi rule-based dari rating
      - _ml_mode          : mode yang digunakan ('train_on_the_fly'/'fallback'/'unavailable')
      - _ml_accuracy      : akurasi model (None jika fallback)
    """
    df = df.copy()
    df["_cleaned_text"] = df["_review_text"].apply(clean_text)

    # Tentukan mode ML
    has_rating = "_rating" in df.columns and df["_rating"].notna().sum() > 0
    ml_result = None

    if has_rating:
        ml_result = run_train_on_the_fly(df)

    if ml_result is None:
        ml_result = run_fallback_load()

    if ml_result is None:
        # Tidak ada model sama sekali
        df["_predicted_ind"] = None
        df["_predicted_label"] = "Tidak Tersedia"
        df["_is_corrected"] = False
        df["_ml_mode"] = "unavailable"
        df["_ml_accuracy"] = None
        return df

    model = ml_result["model"]
    vectorizer = ml_result["vectorizer"]
    mode = ml_result["mode"]
    accuracy = ml_result["accuracy"]

    # Vectorize dan prediksi
    valid_mask = df["_cleaned_text"].str.strip() != ""
    X_vec = vectorizer.transform(df.loc[valid_mask, "_cleaned_text"])
    predictions = model.predict(X_vec)

    df["_predicted_ind"] = None
    df.loc[valid_mask, "_predicted_ind"] = predictions
    df["_predicted_label"] = pd.Series(df["_predicted_ind"]).map(lambda x: {1: "Positif", 0: "Negatif"}.get(x))
    df["_is_corrected"] = False

    # Rule-Based Correction: koreksi prediksi yang bertabrakan dengan rating
    if has_rating:
        # Rating 1-2 tapi diprediksi Positif → koreksi ke Negatif
        mask_false_pos = (df["_rating"] <= 2) & (df["_predicted_ind"] == 1)
        df.loc[mask_false_pos, "_predicted_ind"] = 0
        df.loc[mask_false_pos, "_predicted_label"] = "Negatif"
        df.loc[mask_false_pos, "_is_corrected"] = True

        # Rating 4-5 tapi diprediksi Negatif → koreksi ke Positif
        mask_false_neg = (df["_rating"] >= 4) & (df["_predicted_ind"] == 0)
        df.loc[mask_false_neg, "_predicted_ind"] = 1
        df.loc[mask_false_neg, "_predicted_label"] = "Positif"
        df.loc[mask_false_neg, "_is_corrected"] = True

    df["_ml_mode"] = mode
    df["_ml_accuracy"] = accuracy
    return df
