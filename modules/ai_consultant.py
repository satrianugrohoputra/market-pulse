"""
ai_consultant.py
================
Modul AI Consultant untuk Market-Pulse Dashboard.
Mengimplementasikan tiga fitur utama:
  1. RAG sederhana berbasis TF-IDF dari CSV dataset lokal.
  2. Panggilan LLM Gemini dengan prompt engineering terstruktur.
  3. Hallucination Guard berbasis cosine similarity (lokal, gratis).
"""

import re
import os
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ─── Konstanta ────────────────────────────────────────────────────────────────

GEMINI_MODELS: dict[str, str] = {
    "gemini-3.1-flash-lite (Default — Hemat & Cepat)": "gemini-3.1-flash-lite",
    "gemini-3.5-flash (Premium — Terkuat)": "gemini-3.5-flash",
    "gemini-2.5-flash (Balanced — Lebih Cerdas)": "gemini-2.5-flash",
}

# Ambang batas grounding: jika skor kesamaan rata-rata laporan < threshold ini,
# Hallucination Guard menandai laporan sebagai "tidak sepenuhnya dari data".
HALLUCINATION_THRESHOLD = 0.20

# Jumlah ulasan yang diambil via RAG sebagai konteks Gemini
RAG_TOP_K = 15


# ─── Fitur 2: RAG Berbasis TF-IDF ─────────────────────────────────────────────

def retrieve_relevant_reviews(df: pd.DataFrame, query: str, sentiment_filter: str, top_k: int = RAG_TOP_K) -> list[dict]:
    """
    Mengambil ulasan yang paling relevan dengan query menggunakan TF-IDF cosine similarity.
    Mendukung dua nama kolom teks: 'review_text' (dataset bawaan) dan '_review_text' (dataset upload).
    """
    working_df = df.copy()

    # Deteksi kolom teks secara otomatis (dataset bawaan vs dataset upload)
    if '_review_text' in working_df.columns:
        text_col = '_review_text'
        rating_col = '_rating' if '_rating' in working_df.columns else None
    elif 'review_text' in working_df.columns:
        text_col = 'review_text'
        rating_col = 'rating' if 'rating' in working_df.columns else None
    else:
        return []

    # Filter berdasarkan sentimen (hanya jika kolom rating tersedia)
    if rating_col:
        try:
            working_df[rating_col] = pd.to_numeric(working_df[rating_col], errors='coerce')
            if "Negatif" in sentiment_filter:
                working_df = working_df[working_df[rating_col] <= 2]
            elif "Positif" in sentiment_filter:
                working_df = working_df[working_df[rating_col] >= 4]
        except Exception:
            pass

    # Buang baris yang teksnya kosong
    working_df = working_df[working_df[text_col].astype(str).str.strip() != ""].head(5000)
    if working_df.empty:
        return []

    # Bangun TF-IDF matrix
    corpus = working_df[text_col].fillna('').astype(str).tolist()
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words='english',
        ngram_range=(1, 2)
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return []

    # Hitung skor kemiripan
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, tfidf_matrix).flatten()
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        row = working_df.iloc[idx]
        score = scores[idx]
        # Normalisasi nama kolom untuk output yang konsisten
        results.append({
            "review_text": str(row.get(text_col, '')),
            "title": str(row.get('title', row.get('_title', ''))),
            "rating": float(row.get(rating_col, 0)) if rating_col else 0,
            "score": float(score),
        })

    return results


# ─── Fitur 1: Prompt Engineering & Pemanggilan Gemini ─────────────────────────

def build_prompt(query: str, retrieved_reviews: list[dict], sentiment_filter: str, dataset_name: str = "Dataset Bawaan (ecommercereviews)") -> str:
    """
    Membuat prompt terstruktur yang menggabungkan:
    - Instruksi peran dan format laporan.
    - Konteks ulasan yang ditemukan via RAG.
    - Pertanyaan bisnis dari user.
    - Nama sumber dataset agar Gemini tahu dari mana data berasal.
    """
    # Format ulasan menjadi teks konteks
    context_parts = []
    for i, r in enumerate(retrieved_reviews, 1):
        snippet = r['review_text'][:300].replace('\n', ' ')
        rating_display = f"{r['rating']:.0f}/5" if r['rating'] else "N/A"
        title_display = r['title'] if r['title'] and r['title'] != 'nan' else '-'
        context_parts.append(
            f"[Ulasan #{i} | Rating: {rating_display} | Judul: '{title_display}']\n{snippet}"
        )
    context_text = "\n\n".join(context_parts) if context_parts else "Tidak ada ulasan yang ditemukan."

    prompt = f"""Kamu adalah **AI Business Consultant** untuk platform e-commerce. Tugasmu adalah menganalisis data ulasan pelanggan dari dataset yang diberikan dan memberikan laporan bisnis yang actionable, terstruktur, dan berdampak tinggi.

---

## SUMBER DATA
Dataset yang digunakan: **{dataset_name}**
Filter yang digunakan: {sentiment_filter}
Berikut adalah {len(retrieved_reviews)} ulasan pelanggan yang paling relevan dengan topik analisis (diambil secara otomatis oleh sistem RAG):

{context_text}

---

## PERTANYAAN BISNIS DARI USER
{query}

---

## INSTRUKSI PENTING

**Aturan Grounding (WAJIB DIIKUTI):**
- Jawab HANYA berdasarkan data ulasan yang diberikan di atas. Jika pertanyaan membutuhkan data spesifik yang tidak ada di dalam ulasan, nyatakan dengan jelas bahwa data tersebut tidak tersedia di dataset.
- JANGAN mengarang fakta, angka, atau nama produk yang tidak muncul di ulasan yang diberikan.
- Jika ada kutipan relevan dari ulasan, sertakan potongan kutipannya (dalam tanda kutip) sebagai bukti grounding.

**Aturan Out-of-Context (WAJIB DIIKUTI):**
- Jika pertanyaan user SAMA SEKALI tidak berhubungan dengan analisis data ulasan e-commerce (misalnya: cara membuat program, sains umum, hiburan, atau topik non-bisnis lainnya), WAJIB mulai jawaban dengan tag '[STATUS_OUT_OF_CONTEXT]' di baris pertama. Lanjutkan dengan penjelasan sopan bahwa topik tersebut di luar cakupan dataset, lalu tetap berikan jawaban singkat.
- Jika pertanyaan BERHUBUNGAN dengan data ulasan, JANGAN sertakan tag '[STATUS_OUT_OF_CONTEXT]'.

**Format Laporan jika Dalam Konteks (Gunakan 3 header ini secara berurutan):**

### Executive Summary
(Ringkasan 2-3 kalimat tentang kondisi sentimen dan temuan utama berdasarkan ulasan yang dianalisis. Sebutkan nama dataset sumbernya.)

### Pain Points (Masalah Utama Pelanggan)
(Daftar bullet point masalah utama yang ditemukan dari ulasan, disertai kutipan langsung dari ulasan jika ada)

### Action Items (Rekomendasi Perbaikan)
(Daftar bullet point rekomendasi konkret yang bisa dilakukan tim bisnis berdasarkan temuan di atas)

---
Tulis laporan dalam Bahasa Indonesia. Gunakan formatting Markdown yang rapi."""
    return prompt


def call_gemini(api_key: str, model_id: str, prompt: str) -> str:
    """
    Memanggil Gemini API menggunakan google-genai SDK.
    Mengembalikan teks respons atau pesan error.
    """
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
        )
        return response.text or ""
    except Exception as e:
        return f"**[ERROR Gemini API]**: {str(e)}"


# ─── Fitur 3: Hallucination Guard ─────────────────────────────────────────────

def hallucination_guard(report_text: str, retrieved_reviews: list[dict]) -> dict:
    """
    Memeriksa apakah teks laporan Gemini 'berakar' (grounded) pada data ulasan yang diambil.
    
    Karena ulasan dalam Bahasa Inggris sedangkan laporan dalam Bahasa Indonesia,
    metode TF-IDF murni akan menghasilkan skor rendah akibat perbedaan bahasa (vocab mismatch).
    
    Algoritma Hybrid ini mengatasi perbedaan bahasa dengan cara:
    1. Mencari kutipan (quotes) bahasa Inggris dari ulasan yang dikutip langsung oleh Gemini.
    2. Menghitung overlap kata kunci non-stopwords (bilingual/loanwords/brand terms).
    3. Menggabungkan kedua skor tersebut secara adil.
    
    Returns:
        dict dengan key: 'grounded' (bool), 'score' (float), 'warning' (str)
    """
    if not retrieved_reviews or not report_text.strip():
        return {"grounded": False, "score": 0.0, "warning": "Tidak ada data ulasan untuk verifikasi."}

    # Kumpulkan corpus ulasan
    review_corpus = [r['review_text'] for r in retrieved_reviews if r['review_text'].strip()]
    if not review_corpus:
        return {"grounded": False, "score": 0.0, "warning": "Ulasan kosong, tidak bisa memverifikasi."}

    # 1. Quote Matching: Cari teks di dalam tanda kutip ("..." atau '...')
    # Gemini biasanya menyertakan kutipan ulasan asli bahasa Inggris di laporan Indonesia
    quotes = re.findall(r'"([^"]*)"', report_text) + re.findall(r"'([^']*)'", report_text)
    quotes = [q.strip().lower() for q in quotes if len(q.strip()) > 3]

    if quotes:
        found_quotes = 0
        for q in quotes:
            if any(q in rev.lower() for rev in review_corpus):
                found_quotes += 1
        quote_score = found_quotes / len(quotes)
    else:
        # Jika tidak ada kutipan sama sekali, set default 1.0 (lewati filter kutipan)
        quote_score = 1.0

    # 2. Key Term Overlap: Menghitung overlap kata kunci non-stopwords
    report_words = set(re.findall(r'[a-zA-Z]{3,}', report_text.lower()))
    
    # Kumpulan stopwords umum Bahasa Indonesia dan Bahasa Inggris
    stop_words = {
        "yang", "dan", "untuk", "adalah", "pada", "dalam", "dengan", "dari", "ini", "itu", 
        "akan", "telah", "oleh", "atau", "hanya", "secara", "terdapat", "adanya", "beberapa", 
        "pelanggan", "ulasan", "produk", "laporan", "analisis", "rekomendasi", "masalah", 
        "utama", "serta", "yaitu", "karena", "bahwa", "sebagai", "dapat", "kami", "anda",
        "the", "and", "for", "with", "this", "that", "from", "they", "were", "have", "been", "was"
    }
    
    clean_report_words = report_words - stop_words

    # Kumpulkan semua kata unik dari review corpus
    review_words = set()
    for rev in review_corpus:
        review_words.update(re.findall(r'[a-zA-Z]{3,}', rev.lower()))

    if clean_report_words:
        matching_words = clean_report_words.intersection(review_words)
        term_score = len(matching_words) / len(clean_report_words)
    else:
        term_score = 1.0

    # 3. Hitung Hybrid Grounding Score
    # Jika ada kutipan langsung, itu menjadi bukti grounding yang sangat kuat (bobot 70%)
    if quotes:
        grounding_score = (quote_score * 0.7) + (term_score * 0.3)
    else:
        grounding_score = term_score

    # Klasifikasi status grounding
    grounded = grounding_score >= HALLUCINATION_THRESHOLD
    warning = ""
    if not grounded:
        warning = (
            "⚠️ **Hallucination Guard**: Sebagian isi laporan ini mungkin **tidak sepenuhnya "
            "bersumber dari dataset ulasan Anda** (Grounding Score rendah). "
            "Gemini memberikan jawaban berdasarkan pengetahuan umumnya. "
            "Tetap periksa hasil ini sebelum digunakan untuk keputusan bisnis."
        )

    return {"grounded": grounded, "score": grounding_score, "warning": warning}


# ─── Fungsi Utama: Jalankan Pipeline Lengkap ──────────────────────────────────

def run_ai_consultant(
    df: pd.DataFrame,
    query: str,
    api_key: str,
    model_id: str,
    sentiment_filter: str,
    dataset_name: str = "Dataset Bawaan (ecommercereviews)"
) -> dict:
    """
    Menjalankan full pipeline: RAG → Prompt Engineering → Gemini → Hallucination Guard.

    Args:
        df: DataFrame berisi ulasan (bisa dataset bawaan atau dataset upload).
        dataset_name: Nama sumber dataset — ditampilkan di prompt & UI agar transparan.

    Returns:
        dict dengan key: 'report', 'retrieved_count', 'guard_result', 'dataset_name'
    """
    # Step 1 — RAG: Ambil ulasan relevan
    retrieved = retrieve_relevant_reviews(df, query, sentiment_filter)

    # Step 2 — Prompt Engineering: Bangun prompt (sertakan nama dataset)
    prompt = build_prompt(query, retrieved, sentiment_filter, dataset_name)

    # Step 3 — Gemini: Generate laporan
    report = call_gemini(api_key, model_id, prompt)

    # Cek deteksi out-of-context tag
    out_of_context = "[STATUS_OUT_OF_CONTEXT]" in report

    # Bersihkan tag agar tidak tampil di laporan final
    cleaned_report = re.sub(r'\[STATUS_OUT_OF_CONTEXT\]', '', report, flags=re.IGNORECASE).strip()

    # Step 4 — Hallucination Guard: Verifikasi grounding
    guard_result = hallucination_guard(cleaned_report, retrieved)

    if out_of_context:
        guard_result["grounded"] = False
        guard_result["score"] = 0.0
        guard_result["warning"] = (
            "⚠️ **Pemberitahuan**: Pertanyaan Anda terdeteksi berada di luar konteks ulasan e-commerce. "
            "AI memberikan jawaban umum berdasarkan pengetahuan umumnya (bukan dari ulasan)."
        )

    return {
        "report": cleaned_report,
        "retrieved_count": len(retrieved),
        "guard_result": guard_result,
        "dataset_name": dataset_name,
    }
