"""
upload_processor.py
===================
Modul untuk memvalidasi, mendeteksi kolom, dan membersihkan dataset
yang diunggah oleh user melalui fitur Dynamic Multi-Dataset Upload.
"""

import re
import io
import pandas as pd

# ─── Konstanta Deteksi Kolom ──────────────────────────────────────────────────

# Kata kunci untuk mencari kolom teks ulasan (case-insensitive)
TEXT_COLUMN_KEYWORDS = [
    "review", "text", "comment", "ulasan", "komentar",
    "feedback", "isi", "deskripsi", "pesan", "pendapat", "content"
]

# Kata kunci untuk mencari kolom rating/bintang
RATING_COLUMN_KEYWORDS = [
    "rating", "score", "star", "bintang", "nilai", "poin",
    "point", "grade", "skor"
]

# Batas maksimum dataset
MAX_FILE_SIZE_MB = 50
MAX_ROWS = 30_000
MIN_ROWS = 100  # Dataset di bawah ini akan ditolak


# ─── Fungsi: Validasi File ────────────────────────────────────────────────────

def validate_file(uploaded_file) -> dict:
    """
    Memeriksa ekstensi dan ukuran file yang diunggah.
    Returns: dict { "ok": bool, "error": str | None }
    """
    # Cek ekstensi
    filename = uploaded_file.name.lower()
    if not (filename.endswith(".csv") or filename.endswith(".xlsx")):
        return {
            "ok": False,
            "error": (
                "❌ Format file tidak didukung. "
                "Hanya file berekstensi **.csv** atau **.xlsx** yang diterima."
            )
        }

    # Cek ukuran (dalam byte → MB)
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return {
            "ok": False,
            "error": (
                f"❌ Ukuran file terlalu besar ({file_size_mb:.1f} MB). "
                f"Batas maksimal adalah **{MAX_FILE_SIZE_MB} MB**."
            )
        }

    return {"ok": True, "error": None}


# ─── Fungsi: Baca File ke DataFrame ──────────────────────────────────────────

def read_file_to_df(uploaded_file) -> pd.DataFrame:
    """
    Membaca file CSV atau XLSX menjadi pandas DataFrame.
    """
    filename = uploaded_file.name.lower()
    try:
        if filename.endswith(".csv"):
            # Coba berbagai encoding agar tidak crash untuk file UTF-8 atau Latin
            for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding=enc, on_bad_lines="skip")
                    return df
                except UnicodeDecodeError:
                    continue
            raise ValueError("Gagal membaca file CSV. Pastikan encoding file adalah UTF-8.")
        elif filename.endswith(".xlsx"):
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, engine="openpyxl")
            return df
    except Exception as e:
        raise ValueError(f"Gagal membaca file: {str(e)}")
    raise ValueError("Format file tidak didukung.")


# ─── Fungsi: Deteksi Kolom Dinamis ───────────────────────────────────────────

def detect_columns(df: pd.DataFrame) -> dict:
    """
    Mendeteksi kolom teks ulasan dan kolom rating secara otomatis
    berdasarkan daftar kata kunci yang telah didefinisikan.

    Returns: dict {
        "text_col": str | None,
        "rating_col": str | None,
        "ok": bool,
        "error": str | None
    }
    """
    cols_lower = {col.lower().strip(): col for col in df.columns}

    text_col = None
    rating_col = None

    # Cari kolom teks ulasan
    for keyword in TEXT_COLUMN_KEYWORDS:
        for col_lower, col_original in cols_lower.items():
            if keyword in col_lower:
                text_col = col_original
                break
        if text_col:
            break

    # Cari kolom rating
    for keyword in RATING_COLUMN_KEYWORDS:
        for col_lower, col_original in cols_lower.items():
            if keyword in col_lower:
                rating_col = col_original
                break
        if rating_col:
            break

    # Kolom teks wajib ada
    if text_col is None:
        col_list = ", ".join([f"`{c}`" for c in df.columns.tolist()])
        return {
            "text_col": None,
            "rating_col": None,
            "ok": False,
            "error": (
                "❌ **Kolom teks ulasan tidak ditemukan** di file Anda.\n\n"
                f"Kolom yang tersedia: {col_list}\n\n"
                "Sistem memerlukan kolom dengan nama yang mengandung salah satu kata kunci berikut:\n"
                "- **Bahasa Inggris**: `review`, `text`, `comment`, `feedback`, `content`\n"
                "- **Bahasa Indonesia**: `ulasan`, `komentar`, `isi`, `pendapat`, `deskripsi`\n\n"
                "Silakan ubah nama kolom ulasan Anda sesuai salah satu di atas, lalu coba unggah ulang."
            )
        }

    return {
        "text_col": text_col,
        "rating_col": rating_col,
        "ok": True,
        "error": None
    }


# ─── Fungsi: Pembersihan Data ─────────────────────────────────────────────────

def clean_data(df: pd.DataFrame, text_col: str, rating_col: str | None = None) -> pd.DataFrame:
    """
    Membersihkan DataFrame: hapus null, duplikat, konversi tipe data.
    Returns DataFrame yang sudah bersih.
    """
    df = df.copy()

    # Normalisasi nama kolom internal
    df["_review_text"] = pd.Series(df[text_col]).astype(str).str.strip()

    # Hapus baris dengan teks kosong atau terlalu pendek (< 3 karakter)
    df = pd.DataFrame(df[pd.Series(df["_review_text"]).str.len() >= 3])
    df = pd.DataFrame(df[pd.Series(df["_review_text"]) != "nan"])

    # Hapus duplikat berdasarkan teks ulasan
    df = df.drop_duplicates(subset=["_review_text"])

    # Proses kolom rating (jika ada)
    if rating_col and rating_col in df.columns:
        df["_rating"] = pd.to_numeric(df[rating_col], errors="coerce")
        # Hanya rating 1–5 yang valid
        df["_rating"] = df["_rating"].where(df["_rating"].between(1, 5), other=None)
    else:
        df["_rating"] = None

    # Reset index
    df = df.reset_index(drop=True)
    return df


# ─── Fungsi Utama: Proses Upload ─────────────────────────────────────────────

def process_upload(uploaded_file) -> dict:
    """
    Menjalankan full pipeline validasi → baca → deteksi kolom → bersihkan data.

    Returns: dict {
        "ok": bool,
        "error": str | None,
        "df": pd.DataFrame | None,
        "text_col": str | None,
        "rating_col": str | None,
        "original_rows": int,
        "final_rows": int,
        "is_sampled": bool,
        "col_info": dict
    }
    """
    # Step 1 — Validasi file
    val = validate_file(uploaded_file)
    if not val["ok"]:
        return {"ok": False, "error": val["error"], "df": None,
                "text_col": None, "rating_col": None,
                "original_rows": 0, "final_rows": 0,
                "is_sampled": False, "col_info": {}}

    # Step 2 — Baca file
    try:
        df_raw = read_file_to_df(uploaded_file)
    except ValueError as e:
        return {"ok": False, "error": str(e), "df": None,
                "text_col": None, "rating_col": None,
                "original_rows": 0, "final_rows": 0,
                "is_sampled": False, "col_info": {}}

    original_rows = len(df_raw)

    # Step 3 — Deteksi kolom
    col_result = detect_columns(df_raw)
    if not col_result["ok"]:
        return {"ok": False, "error": col_result["error"], "df": None,
                "text_col": None, "rating_col": None,
                "original_rows": original_rows, "final_rows": 0,
                "is_sampled": False, "col_info": col_result}

    text_col = col_result["text_col"]
    rating_col = col_result["rating_col"]

    # Step 4 — Bersihkan data
    df_clean = clean_data(df_raw, text_col, rating_col)
    final_rows = len(df_clean)

    # Step 5 — Cek minimum baris (setelah dibersihkan)
    if final_rows < MIN_ROWS:
        return {
            "ok": False,
            "error": (
                f"❌ **Dataset terlalu kecil** setelah dibersihkan (tersisa **{final_rows} baris**).\n\n"
                f"Minimum yang diperlukan adalah **{MIN_ROWS} baris** ulasan agar analisis sentimen "
                f"menghasilkan hasil yang bermakna. Silakan gunakan dataset yang lebih lengkap."
            ),
            "df": None, "text_col": text_col, "rating_col": rating_col,
            "original_rows": original_rows, "final_rows": final_rows,
            "is_sampled": False, "col_info": col_result
        }

    # Step 6 — Random sampling jika terlalu besar
    is_sampled = False
    if final_rows > MAX_ROWS:
        df_clean = df_clean.sample(n=MAX_ROWS, random_state=42).reset_index(drop=True)
        is_sampled = True

    return {
        "ok": True,
        "error": None,
        "df": df_clean,
        "text_col": text_col,
        "rating_col": rating_col,
        "original_rows": original_rows,
        "final_rows": len(df_clean),
        "is_sampled": is_sampled,
        "col_info": col_result
    }
