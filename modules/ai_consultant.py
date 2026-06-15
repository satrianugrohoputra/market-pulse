"""
ai_consultant.py
================
Modul AI Consultant untuk Market-Pulse Dashboard.
Mengimplementasikan pipeline lengkap:
  1. Pre-flight Guardrail  : Cek lokal apakah query relevan e-commerce SEBELUM API dipanggil.
  2. RAG (TF-IDF)          : Ambil ulasan paling relevan dari dataset sebagai konteks.
  3. Prompt Engineering    : Bangun prompt terstruktur dengan grounding instruction ketat.
  4. Gemini API            : Generate laporan bisnis berdasarkan konteks ulasan.
  5. Hallucination Guard   : Verifikasi hasil laporan berakar dari data ulasan nyata.
"""

import re
import os
import hashlib
from typing import cast
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_EMBEDDING_MODEL = None

def get_embedding_model():
    """Lazy-load the SentenceTransformer model to save startup memory/time."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMBEDDING_MODEL = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _EMBEDDING_MODEL


def get_dataset_embeddings(df: pd.DataFrame, text_col: str) -> np.ndarray:
    """
    Mengambil atau menghitung vector embeddings untuk seluruh ulasan di dataset.
    Hasilnya disimpan dalam file cache .npy lokal agar pencarian berikutnya instan.
    """
    if df.empty:
        return np.empty((0, 0))

    # Gunakan sidik jari dataframe untuk membuat hash unik
    first_text = str(df.iloc[0].get(text_col, ''))
    last_text = str(df.iloc[-1].get(text_col, ''))
    length = len(df)
    fingerprint = f"{first_text}_{last_text}_{length}"
    df_hash = hashlib.md5(fingerprint.encode('utf-8')).hexdigest()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(base_dir, "models")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"embeddings_{df_hash}.npy")

    if os.path.exists(cache_path):
        try:
            return np.load(cache_path)
        except Exception:
            pass

    # Hitung jika tidak ada di cache
    model = get_embedding_model()
    corpus = df[text_col].fillna('').astype(str).tolist()
    embeddings = model.encode(corpus, show_progress_bar=False, convert_to_numpy=True)

    try:
        np.save(cache_path, embeddings)
    except Exception:
        pass

    return embeddings


# ─── Konstanta ────────────────────────────────────────────────────────────────

GEMINI_MODELS: dict[str, str] = {
    "gemini-3.1-flash-lite (Default — Hemat & Cepat)": "gemini-3.1-flash-lite",
    "gemini-3.5-flash (Premium — Terkuat)": "gemini-3.5-flash",
    "gemini-2.5-flash (Balanced — Lebih Cerdas)": "gemini-2.5-flash",
}

HALLUCINATION_THRESHOLD = 0.20
RAG_TOP_K = 15

# ─── Konstanta Guardrail ───────────────────────────────────────────────────────

# Kata kunci yang WAJIB ada (jika tidak ada satu pun, query langsung ditolak)
# Mencakup konteks: e-commerce, review, ulasan, rating, pembeli, penjual, produk, dll.
_ECOMMERCE_KEYWORDS = {
    # Produk & Transaksi
    "produk", "barang", "item", "product", "goods", "item",
    "beli", "jual", "beli", "order", "pesan", "transaksi", "purchase", "buy", "sell",
    "harga", "price", "diskon", "promo", "voucher", "discount", "murah", "mahal",
    "pengiriman", "kirim", "ongkir", "delivery", "shipping", "paket", "ekspedisi",
    "toko", "seller", "penjual", "merchant", "vendor", "store", "shop",
    "pembeli", "buyer", "customer", "pelanggan", "konsumen",
    # Ulasan & Sentimen
    "ulasan", "review", "rating", "bintang", "star", "feedback", "testimoni",
    "komentar", "keluhan", "komplain", "complaint", "puas", "kecewa",
    "bagus", "jelek", "buruk", "baik", "memuaskan", "recommend",
    "sentimen", "sentiment", "positif", "negatif",
    # Kategori Produk Fashion/E-commerce
    "pakaian", "baju", "fashion", "clothing", "dress", "celana", "kemeja",
    "ukuran", "size", "warna", "color", "kualitas", "quality", "bahan", "material",
    # Platform & Layanan
    "ecommerce", "marketplace", "platform", "layanan", "service", "garansi",
    "return", "refund", "komplain", "respon", "response",
    # Analisis Bisnis
    "analisis", "analysis", "trend", "tren", "insight", "laporan", "report",
    "performa", "performance", "penjualan", "sales", "revenue",
    "bisnis", "business", "strategi", "strategy", "pasar", "market",
}

# Kata kunci yang menjadi sinyal PASTI out-of-context
_HARD_BLOCK_KEYWORDS = {
    # Pemrograman & Teknologi Umum
    "python", "javascript", "java", "php", "html", "css", "coding", "program",
    "fungsi", "function", "variabel", "variable", "loop", "array", "database",
    "algoritma", "algorithm", "framework", "library", "debug", "error code",
    "github", "git", "docker", "kubernetes", "api design",
    # Ilmu Pengetahuan Umum
    "matematika", "fisika", "kimia", "biologi", "sejarah", "geografi",
    "physics", "chemistry", "biology", "history", "science", "mathematics",
    # Kesehatan & Medis
    "penyakit", "obat", "dokter", "rumah sakit", "medis", "kesehatan",
    "disease", "medicine", "doctor", "hospital", "health",
    # Hiburan & Sosial
    "film", "musik", "lagu", "game", "resep", "memasak", "olahraga", "sepak bola",
    "movie", "music", "recipe", "cooking", "football", "sports",
    # Keuangan di luar e-commerce
    "saham", "kripto", "bitcoin", "investasi saham", "forex", "trading",
    "stock", "crypto", "investment", "forex",
}


# ─── Layer 1: Pre-flight Guardrail (Lokal, Tanpa API) ─────────────────────────

def check_query_relevance(query: str) -> dict:
    """
    Memeriksa relevansi query SEBELUM memanggil API Gemini.
    Menggunakan pendekatan dua lapis:
      1. Hard Block: Jika mengandung kata kunci off-topic yang jelas, langsung tolak.
      2. Keyword Match: Harus mengandung minimal 1 kata kunci e-commerce.

    Returns:
        dict: {
            "allowed": bool,
            "reason": str  (pesan yang ditampilkan ke user jika ditolak)
        }
    """
    query_lower = query.lower().strip()
    query_words = set(re.findall(r'[a-zA-Z\u00C0-\u024F\u0100-\u024F]+', query_lower))

    # Layer 1a: Hard Block — tolak jika ada kata kunci terlarang
    hard_block_hits = query_words.intersection(_HARD_BLOCK_KEYWORDS)
    if hard_block_hits:
        return {
            "allowed": False,
            "reason": (
                f"❌ **Pertanyaan Ditolak — Di Luar Cakupan Dataset**\n\n"
                f"Pertanyaan Anda terdeteksi mengandung topik **'{', '.join(list(hard_block_hits)[:3])}'** "
                f"yang tidak berkaitan dengan data ulasan e-commerce.\n\n"
                f"**AI Business Consultant ini hanya dapat menganalisis:**\n"
                f"- Ulasan & rating produk dari dataset yang dipilih\n"
                f"- Sentimen pelanggan (positif / negatif)\n"
                f"- Keluhan, pujian, dan pengalaman pembeli\n"
                f"- Tren penjualan, kualitas produk, dan layanan toko\n\n"
                f"*API tidak dipanggil — tidak ada token yang terpakai.*"
            ),
        }

    # Layer 1b: Keyword Match — harus ada minimal 1 kata kunci e-commerce
    ecommerce_hits = query_words.intersection(_ECOMMERCE_KEYWORDS)

    # Cek juga substring matching untuk kata majemuk seperti "produk apa", "toko ini"
    full_match = any(kw in query_lower for kw in _ECOMMERCE_KEYWORDS)

    if not ecommerce_hits and not full_match:
        return {
            "allowed": False,
            "reason": (
                f"❌ **Pertanyaan Tidak Relevan dengan Dataset E-commerce**\n\n"
                f"Saya tidak dapat menemukan relevansi antara pertanyaan Anda dengan data "
                f"ulasan pelanggan yang tersedia di dataset.\n\n"
                f"**Contoh pertanyaan yang bisa saya jawab:**\n"
                f"- *\"Apa keluhan utama pelanggan tentang kualitas produk?\"*\n"
                f"- *\"Produk apa yang mendapat rating tertinggi?\"*\n"
                f"- *\"Mengapa banyak ulasan negatif tentang pengiriman?\"*\n"
                f"- *\"Apa yang paling banyak dipuji oleh pembeli?\"*\n\n"
                f"*API tidak dipanggil — tidak ada token yang terpakai.*"
            ),
        }

    return {"allowed": True, "reason": ""}


# ─── Layer 2: RAG Berbasis TF-IDF ─────────────────────────────────────────────

def retrieve_relevant_reviews(
    df: pd.DataFrame,
    query: str,
    sentiment_filter: str,
    search_method: str = "Pencarian Kata Kunci (TF-IDF)",
    top_k: int = RAG_TOP_K
) -> list[dict]:
    """
    Mengambil ulasan yang paling relevan dengan query menggunakan TF-IDF atau MiniLM semantic search.
    Mendukung filter sentimen dan mendeteksi kolom secara otomatis.
    """
    working_df = cast(pd.DataFrame, df.copy())

    # Deteksi kolom teks secara otomatis (dataset bawaan vs dataset upload)
    if '_review_text' in working_df.columns:
        text_col = '_review_text'
        rating_col = '_rating' if '_rating' in working_df.columns else None
    elif 'review_text' in working_df.columns:
        text_col = 'review_text'
        rating_col = 'rating' if 'rating' in working_df.columns else None
    else:
        return []

    # Buang baris yang teksnya kosong di awal agar index sinkron
    working_df = cast(pd.DataFrame, working_df[pd.Series(working_df[text_col]).astype(str).str.strip() != ""].copy())
    if working_df.empty:
        return []

    # Tambahkan index asli untuk memetakan vector embedding setelah filter
    working_df['_orig_idx'] = range(len(working_df))

    # Cek metode pencarian
    if "Semantik" in search_method:
        try:
            # 1. Hitung/Ambil Embedding untuk seluruh teks (sebelum difilter)
            full_embeddings = get_dataset_embeddings(cast(pd.DataFrame, working_df), text_col)
            
            # 2. Terapkan filter sentimen ke dataframe
            if rating_col:
                try:
                    working_df[rating_col] = pd.to_numeric(working_df[rating_col], errors='coerce')
                    if "Negatif" in sentiment_filter:
                        working_df = cast(pd.DataFrame, working_df[working_df[rating_col] <= 2])
                    elif "Positif" in sentiment_filter:
                        working_df = cast(pd.DataFrame, working_df[working_df[rating_col] >= 4])
                except Exception:
                    pass
            
            if working_df.empty:
                return []
            
            # Batasi head(5000) seperti versi legacy untuk efisiensi
            working_df = cast(pd.DataFrame, working_df.head(5000))
            
            # 3. Iris embedding untuk baris yang cocok dengan filter
            matched_indices = working_df['_orig_idx'].tolist()
            sliced_embeddings = full_embeddings[matched_indices]
            
            # 4. Hitung Query Embedding & similarity
            model = get_embedding_model()
            query_vec = model.encode([query], show_progress_bar=False, convert_to_numpy=True)
            
            scores = cosine_similarity(query_vec, sliced_embeddings).flatten()
            top_indices = np.argsort(scores)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                row = working_df.iloc[idx]
                score = scores[idx]
                results.append({
                    "review_text": str(row.get(text_col, '')),
                    "title": str(row.get('title', row.get('_title', ''))),
                    "rating": float(row.get(rating_col, 0)) if rating_col else 0,
                    "score": float(score),
                })
            return results
            
        except Exception:
            # Fallback otomatis ke TF-IDF jika ada masalah
            pass

    # --- FALLBACK / LEGACY TF-IDF KEYWORD SEARCH ---
    if rating_col:
        try:
            working_df[rating_col] = pd.to_numeric(working_df[rating_col], errors='coerce')
            if "Negatif" in sentiment_filter:
                working_df = cast(pd.DataFrame, working_df[working_df[rating_col] <= 2])
            elif "Positif" in sentiment_filter:
                working_df = cast(pd.DataFrame, working_df[working_df[rating_col] >= 4])
        except Exception:
            pass

    working_df = cast(pd.DataFrame, working_df.head(5000))
    if working_df.empty:
        return []

    corpus = pd.Series(working_df[text_col]).fillna('').astype(str).tolist()
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words='english',
        ngram_range=(1, 2)
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return []

    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, tfidf_matrix).flatten()
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        row = working_df.iloc[idx]
        score = scores[idx]
        results.append({
            "review_text": str(row.get(text_col, '')),
            "title": str(row.get('title', row.get('_title', ''))),
            "rating": float(row.get(rating_col, 0)) if rating_col else 0,
            "score": float(score),
        })

    return results


# ─── Layer 3: Prompt Engineering ──────────────────────────────────────────────

def build_prompt(query: str, retrieved_reviews: list[dict], sentiment_filter: str, dataset_name: str = "Dataset Bawaan (ecommercereviews)") -> str:
    """
    Membuat prompt terstruktur dengan system instruction yang ketat:
    - Peran AI terbatas hanya pada analisis ulasan e-commerce.
    - Grounding wajib dari ulasan yang disediakan.
    - Format output konsisten.
    - Instruksi penolakan OOC sebagai lapisan sekunder.
    """
    # Format ulasan menjadi teks konteks
    context_parts = []
    for i, r in enumerate(retrieved_reviews, 1):
        snippet = r['review_text'][:350].replace('\n', ' ')
        rating_display = f"{r['rating']:.0f}/5" if r['rating'] else "N/A"
        title_display = r['title'] if r['title'] and r['title'] != 'nan' else '-'
        context_parts.append(
            f"[Ulasan #{i} | Rating: {rating_display} | Judul: '{title_display}']\n{snippet}"
        )
    context_text = "\n\n".join(context_parts) if context_parts else "Tidak ada ulasan yang ditemukan."

    prompt = f"""## PERAN & BATASAN SISTEM
Kamu adalah AI Business Consultant khusus yang HANYA bertugas menganalisis data ulasan pelanggan e-commerce dari dataset yang diberikan. Kamu TIDAK memiliki pengetahuan atau wewenang di luar konteks ini.

**BATASAN KERAS (WAJIB DIPATUHI):**
1. Kamu HANYA boleh membahas topik yang berkaitan langsung dengan: ulasan pelanggan, rating produk, sentimen pembeli, kualitas produk, layanan penjual, pengalaman transaksi, tren penjualan, dan analisis bisnis e-commerce.
2. TOLAK DENGAN TEGAS jika pertanyaan menyentuh topik di luar ini (pemrograman, sains, hiburan, kesehatan, dll). Mulai jawaban dengan tag '[STATUS_OUT_OF_CONTEXT]'.
3. JANGAN pernah mengarang data, statistik, atau nama produk yang tidak ada di ulasan yang diberikan.
4. JANGAN memberikan saran umum yang tidak bersumber dari ulasan di bawah ini.

---

## SUMBER DATA ULASAN
Dataset: **{dataset_name}**
Filter sentimen: {sentiment_filter}
Sistem RAG telah mengambil **{len(retrieved_reviews)} ulasan** yang paling relevan dengan pertanyaan:

{context_text}

---

## PERTANYAAN YANG DIAJUKAN
{query}

---

## INSTRUKSI LAPORAN (JIKA DALAM KONTEKS)

Jawab HANYA berdasarkan ulasan di atas. Jika informasi spesifik tidak ada di ulasan, nyatakan: "Data tidak tersedia di dataset ini."

Gunakan format berikut secara berurutan:

### Executive Summary
(2-3 kalimat: kondisi sentimen keseluruhan & temuan utama. Sebutkan nama dataset dan jumlah ulasan yang dianalisis.)

### Pain Points (Masalah Utama)
(Bullet point masalah yang muncul dari ulasan. Sertakan kutipan langsung dalam tanda kutip sebagai bukti.)

### Action Items (Rekomendasi)
(Bullet point tindakan konkret berbasis temuan di atas. Hanya rekomendasikan hal yang didukung data.)

---
Format: Bahasa Indonesia, Markdown rapi."""
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


# ─── Layer 4: Hallucination Guard ─────────────────────────────────────────────

def hallucination_guard(report_text: str, retrieved_reviews: list[dict]) -> dict:
    """
    Memeriksa apakah teks laporan Gemini 'berakar' (grounded) pada data ulasan yang diambil.

    Algoritma Hybrid:
      1. Quote Matching  : Cari kutipan bahasa Inggris dari ulasan di dalam laporan.
      2. Key Term Overlap: Hitung tumpang tindih kata kunci non-stopwords.
      3. Weighted Score  : Gabungkan keduanya (kutipan = 70%, term = 30%).
    """
    if not retrieved_reviews or not report_text.strip():
        return {"grounded": False, "score": 0.0, "warning": "Tidak ada data ulasan untuk verifikasi."}

    review_corpus = [r['review_text'] for r in retrieved_reviews if r['review_text'].strip()]
    if not review_corpus:
        return {"grounded": False, "score": 0.0, "warning": "Ulasan kosong, tidak bisa memverifikasi."}

    # 1. Quote Matching
    quotes = re.findall(r'"([^"]*)"', report_text) + re.findall(r"'([^']*)'", report_text)
    quotes = [q.strip().lower() for q in quotes if len(q.strip()) > 3]

    if quotes:
        found_quotes = sum(1 for q in quotes if any(q in rev.lower() for rev in review_corpus))
        quote_score = found_quotes / len(quotes)
    else:
        quote_score = 1.0  # Tidak ada kutipan = lewati filter ini

    # 2. Key Term Overlap
    stop_words = {
        "yang", "dan", "untuk", "adalah", "pada", "dalam", "dengan", "dari", "ini", "itu",
        "akan", "telah", "oleh", "atau", "hanya", "secara", "terdapat", "adanya", "beberapa",
        "pelanggan", "ulasan", "produk", "laporan", "analisis", "rekomendasi", "masalah",
        "utama", "serta", "yaitu", "karena", "bahwa", "sebagai", "dapat", "kami", "anda",
        "the", "and", "for", "with", "this", "that", "from", "they", "were", "have", "been", "was",
        "data", "dataset", "tidak", "tersedia", "berdasarkan", "ulasan", "review",
    }
    report_words = set(re.findall(r'[a-zA-Z]{3,}', report_text.lower())) - stop_words

    review_words = set()
    for rev in review_corpus:
        review_words.update(re.findall(r'[a-zA-Z]{3,}', rev.lower()))

    if report_words:
        term_score = len(report_words.intersection(review_words)) / len(report_words)
    else:
        term_score = 1.0

    # 3. Weighted Hybrid Score
    grounding_score = (quote_score * 0.7 + term_score * 0.3) if quotes else term_score

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
    search_method: str = "Pencarian Kata Kunci (TF-IDF)",
    dataset_name: str = "Dataset Bawaan (ecommercereviews)"
) -> dict:
    """
    Menjalankan full pipeline dengan 5 lapisan:
      1. Pre-flight Guardrail (lokal, tanpa API call)
      2. RAG: Ambil ulasan relevan menggunakan TF-IDF atau Semantic Search
      3. Prompt Engineering: Bangun prompt terstruktur
      4. Gemini API: Generate laporan
      5. Hallucination Guard: Verifikasi grounding

    Returns:
        dict: {
            'report': str,
            'retrieved_count': int,
            'guard_result': dict,
            'dataset_name': str,
            'search_method': str,
            'blocked': bool,         # True jika query ditolak pre-flight
            'block_reason': str      # Pesan penolakan (kosong jika tidak diblokir)
        }
    """
    # ── Step 1: Pre-flight Guardrail (Lokal, TANPA memanggil API) ────────────
    relevance = check_query_relevance(query)
    if not relevance["allowed"]:
        return {
            "report": "",
            "retrieved_count": 0,
            "guard_result": {
                "grounded": False,
                "score": 0.0,
                "warning": ""
            },
            "dataset_name": dataset_name,
            "search_method": search_method,
            "blocked": True,
            "block_reason": relevance["reason"],
        }

    # ── Step 2: RAG — Ambil ulasan relevan ───────────────────────────────────
    retrieved = retrieve_relevant_reviews(df, query, sentiment_filter, search_method)

    # ── Step 3: Prompt Engineering ────────────────────────────────────────────
    prompt = build_prompt(query, retrieved, sentiment_filter, dataset_name)

    # ── Step 4: Gemini API ────────────────────────────────────────────────────
    report = call_gemini(api_key, model_id, prompt)

    # Cek deteksi out-of-context dari respons Gemini (secondary guardrail)
    out_of_context = "[STATUS_OUT_OF_CONTEXT]" in report
    cleaned_report = re.sub(r'\[STATUS_OUT_OF_CONTEXT\]', '', report, flags=re.IGNORECASE).strip()

    # ── Step 5: Hallucination Guard ───────────────────────────────────────────
    guard_result = hallucination_guard(cleaned_report, retrieved)

    if out_of_context:
        guard_result["grounded"] = False
        guard_result["score"] = 0.0
        guard_result["warning"] = (
            "⚠️ **Pemberitahuan**: Pertanyaan Anda terdeteksi berada di luar konteks "
            "ulasan e-commerce meskipun lolos seleksi awal. AI memberikan jawaban umum "
            "berdasarkan pengetahuan umumnya (bukan dari ulasan)."
        )

    return {
        "report": cleaned_report,
        "retrieved_count": len(retrieved),
        "guard_result": guard_result,
        "dataset_name": dataset_name,
        "search_method": search_method,
        "blocked": False,
        "block_reason": "",
    }
