import streamlit as st
import plotly.express as px
import database as db
import queries as q
import ai_consultant as aic

# 1. Konfigurasi Halaman Dashboard (Wide Mode & Tema Dasar)
st.set_page_config(page_title="Market-Pulse Dashboard", layout="wide", page_icon="📊")

# ==================== SIDEBAR NAVIGASI & LOGO ====================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3222/3222665.png", width=80) # Logo estetik opsional
    st.title("🎛️ Pusat Kendali")
    st.markdown("Aplikasi **Market-Pulse** v1.1")
    st.write("---")
    st.markdown("Developed by Kelompok 2")
    st.markdown("🎓 *Celerates Independent Study 2026*")

# ==================== HALAMAN UTAMA: HEADER ====================
st.title("📊 Market-Pulse: E-commerce Analytics")
st.markdown("Pusat Kendali Analisis Tren, Segmentasi Pasar, dan Sentimen Produk Toko Anda")
st.write("---")

# ==================== BARIS 1: METRIC CARDS (RINGKASAN CEPAT) ====================
# Mengambil total ulasan global dari database untuk ditaruh di metric card
df_total = db.run_query("SELECT COUNT(*) as total FROM reviews;")
total_all_reviews = df_total["total"][0] if not df_total.empty else 0

col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.metric(label="📈 Total Volume Ulasan", value=f"{total_all_reviews:,} Data")
with col_m2:
    st.metric(label="⭐ Target Kepuasan Produk", value="4.20 / 5.00")
with col_m3:
    st.metric(label="🚀 Status Sistem AI", value="Ready")

st.write("---")

# ==================== BARIS 2: PRODUK POPULER & LOYALITAS ====================
col_pop1, col_pop2 = st.columns([2, 1])

with col_pop1:
    st.subheader("🔥 Top 10 Produk Populer (Banyak Di-upvote Pelanggan)")
    df_populer = db.run_query(q.QUERY_PRODUK_POPULER)
    
    # 1. Pastikan kolom diubah menjadi string
    df_populer["Clothing ID"] = df_populer["Clothing ID"].astype(str)
    
    fig_pop = px.bar(df_populer, 
                     x="Clothing ID", 
                     y="Total Positive Feedback",
                     text="Total Positive Feedback", 
                     color="Average Rating",
                     labels={"Clothing ID": "ID Produk", "Total Positive Feedback": "Total Upvote (Helpful)"},
                     title="Produk Paling Banyak Mendapat Interaksi Positif",
                     color_continuous_scale=px.colors.sequential.Viridis)
    
    # 2. TAMBAHKAN TYPE='CATEGORY' DI SINI UNTUK MEMAKSA PLOTLY MENGHAPUS SKALA ANGKA
    fig_pop.update_layout(
        xaxis={
            'type': 'category',
            'categoryorder': 'total descending'
        }
    )
    
    st.plotly_chart(fig_pop, width="stretch")

with col_pop2:
    st.subheader("🎯 Loyalitas per Departemen")
    df_loyal = db.run_query(q.QUERY_LOYALITAS_PELANGGAN)
    fig_loyal = px.pie(df_loyal, values="Total Reviews", names="Department",
                       hole=0.4, title="Distribusi Volume Ulasan")
    st.plotly_chart(fig_loyal, width="stretch")

st.write("---")

# ==================== BARIS 3: SEGMENTASI PASAR & KELUHAN ====================
col1, col2 = st.columns(2)

with col1:
    st.subheader("👥 Karakteristik Pasar Berdasarkan Usia & Departemen")
    df_pasar = db.run_query(q.QUERY_SEGMENTASI_PASAR)
    
    # Menggunakan Grouped Bar Chart agar kelihatan per departemennya membeli apa saja
    fig_pasar = px.bar(df_pasar, x="Age Group", y="Total Purchase",
                       color="Department", barmode="group",
                       title="Volume Pembelian Berdasarkan Generasi Usia")
    st.plotly_chart(fig_pasar, width="stretch")

with col2:
    st.subheader("⚠️ Titik Masalah: Ulasan Negatif per Kategori")
    df_keluhan = db.run_query(q.QUERY_KELUHAN_PRODUK)
    
    # Menampilkan Defect Rate yang sudah diperbaiki tipe datanya kemarin
    fig_keluhan = px.bar(df_keluhan, x="Class", y="Defect Rate",
                         text="Negative Reviews", color="Defect Rate",
                         labels={"Defect Rate": "Rasio Cacat (%)", "Class": "Kategori Kelas"},
                         title="Kategori dengan Komplain > 10 Ulasan (Label: Jumlah Komplain)",
                         color_continuous_scale=px.colors.sequential.OrRd)
    st.plotly_chart(fig_keluhan, width="stretch")

st.write("---")

# ==================== BARIS 4: FITUR FILTER KATA KUNCI DINAMIS (REQ USER!) ====================
st.subheader("🔍 Mesin Pencari & Penyaring Ulasan Pelanggan")
st.markdown("Fitur interaktif untuk menyaring curhatan pelanggan berdasarkan kata kunci dan rating.")

# Membuat input filter berdampingan menggunakan kolom
col_f1, col_f2 = st.columns(2)
with col_f1:
    kata_kunci = st.text_input("Ketik Kata Kunci yang Dicari (Contoh: love, perfect, fabric, size):", "perfect")
with col_f2:
    pilihan_rating = st.selectbox("Pilih Rating Ulasan Pelanggan:", [5, 4, 3, 2, 1], index=0)

# SQL Execution secara dinamis berdasarkan input di atas
QUERY_DINAMIS = f"""
SELECT 
    division_name AS "Division", 
    department_name AS "Department", 
    class_name AS "Class", 
    title AS "Review Title", 
    review_text AS "Review Text", 
    rating AS "Rating"
FROM reviews
WHERE (title ILIKE '%%{kata_kunci}%%' OR review_text ILIKE '%%{kata_kunci}%%') 
  AND rating = {pilihan_rating}
LIMIT 10;
"""
df_dinamis = db.run_query(QUERY_DINAMIS)

if not df_dinamis.empty:
    st.dataframe(df_dinamis, width="stretch", hide_index=True)
else:
    st.info(f"Tidak ada ulasan dengan kata kunci '{kata_kunci}' pada Rating {pilihan_rating}.")

st.write("---")

# ==================== BARIS 5: TABEL DETAIL EFEKTIVITAS ULASAN ====================
st.subheader("💡 Efektivitas Ulasan Review Berdasarkan Rating")
df_efektif = db.run_query(q.QUERY_EFEKTIVITAS_ULASAN)
st.dataframe(df_efektif, width="stretch", hide_index=True)

st.write("---")

# ==================== BARIS 6: SIMULATOR PREDIKSI SENTIMEN INSTAN (REQ KELOMPOK!) ====================
st.subheader("🔮 Simulator Prediksi Sentimen (Hybrid ML & Rules)")
st.markdown("Ketik ulasan baru dan masukkan rating untuk menguji model **Machine Learning** yang digabungkan dengan **Rule-based Override** sesuai blueprint proyek.")

import os
import pickle
import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Fungsi preprocessing yang sama persis dengan modul training
def preprocess_input(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    # Hapus tanda baca dan karakter selain huruf
    text = re.sub(r'[^a-z\s]', '', text)
    # Hapus stopwords
    words = text.split()
    words = [w for w in words if w not in ENGLISH_STOP_WORDS]
    return " ".join(words)

# Menggunakan path relative terhadap app.py
current_dir = os.path.dirname(__file__)
model_path = os.path.join(current_dir, "model_sentimen.pkl")
vectorizer_path = os.path.join(current_dir, "vectorizer.pkl")

if os.path.exists(model_path) and os.path.exists(vectorizer_path):
    try:
        # Load model & vectorizer
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        with open(vectorizer_path, "rb") as f:
            vectorizer = pickle.load(f)
            
        col1, col2 = st.columns([2, 1])
        
        with col1:
            user_review = st.text_area(
                "Tulis ulasan produk Anda di sini (Bahasa Inggris):", 
                placeholder="Contoh: The product quality is amazing! Highly recommended.",
                height=120
            )
            
        with col2:
            rating_choice = st.selectbox(
                "Masukkan Rating Ulasan:",
                options=[
                    "Prediksi ML Murni (Tanpa Rating)",
                    "1 Bintang (Negatif)",
                    "2 Bintang (Negatif)",
                    "3 Bintang (Netral)",
                    "4 Bintang (Positif)",
                    "5 Bintang (Positif)"
                ],
                index=0
            )
        
        if st.button("Analisis Sentimen Hybrid", type="primary", width="stretch"):
            if user_review.strip() != "":
                # 1. Preprocessing & ML Prediction
                cleaned_text = preprocess_input(user_review)
                vectorized_text = vectorizer.transform([cleaned_text])
                ml_prediction = model.predict(vectorized_text)[0] # 0 = Negatif, 1 = Positif
                probability = model.predict_proba(vectorized_text)[0]
                
                # 2. Rule-Based Override Layer (Ref: system_design.md)
                final_sentiment = None
                override_applied = False
                
                # Cek pilihan rating
                if rating_choice and ("1 Bintang" in rating_choice or "2 Bintang" in rating_choice):
                    final_sentiment = "Negatif"
                    if ml_prediction == 1:
                        override_applied = True
                elif rating_choice and ("4 Bintang" in rating_choice or "5 Bintang" in rating_choice):
                    final_sentiment = "Positif"
                    if ml_prediction == 0:
                        override_applied = True
                elif rating_choice and "3 Bintang" in rating_choice:
                    final_sentiment = "Netral"
                    override_applied = True
                else:
                    # Murni ML
                    final_sentiment = "Positif" if ml_prediction == 1 else "Negatif"
                
                # Tampilkan visualisasi hasil
                st.markdown("### 📊 Hasil Analisis Sentimen")
                
                # Tampilkan hasil prediksi ML mentah
                ml_label = "🟢 POSITIF" if ml_prediction == 1 else "🔴 NEGATIF"
                ml_conf = probability[1] if ml_prediction == 1 else probability[0]
                st.info(f"🤖 **Prediksi Model ML**: {ml_label} (Tingkat Keyakinan: {ml_conf*100:.2f}%)")
                
                # Tampilkan hasil akhir setelah digabung dengan aturan rating
                if final_sentiment == "Positif":
                    st.success(f"🟢 **Sentimen Akhir: POSITIF**")
                    if override_applied:
                        st.caption(r"ℹ️ *Catatan: Sentimen dikoreksi menjadi Positif berdasarkan rating bintang $\ge 4$ (Rule-based Override).*")
                    st.balloons()
                elif final_sentiment == "Negatif":
                    st.error(f"🔴 **Sentimen Akhir: NEGATIF**")
                    if override_applied:
                        st.caption(r"ℹ️ *Catatan: Sentimen dikoreksi menjadi Negatif berdasarkan rating bintang $\le 2$ (Rule-based Override).*")
                else:
                    st.warning(f"🟡 **Sentimen Akhir: NETRAL**")
                    st.caption("ℹ️ *Catatan: Sentimen disetel menjadi Netral berdasarkan rating bintang 3 (Rule-based Override).*")
            else:
                st.warning("Silakan masukkan teks ulasan terlebih dahulu.")
                st.stop()
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses model: {e}")
else:
    st.info("💡 **Status**: Simulator siap! Menunggu file `model_sentimen.pkl` dan `vectorizer.pkl` diletakkan di folder proyek oleh tim Machine Learning.")

st.write("---")

# ==================== BARIS 7: AI CONSULTANT (RAG + GEMINI + HALLUCINATION GUARD) ====================

st.subheader("🤖 AI Business Consultant (Powered by Gemini)")
st.markdown(
    "Ajukan pertanyaan bisnis Anda dalam bahasa alami. "
    "AI akan mencari ulasan yang paling relevan dari dataset (**RAG**), "
    "lalu merangkum temuan menggunakan **Google Gemini**, "
    "dilengkapi **Hallucination Guard** untuk memverifikasi keakuratan jawaban."
)

# ── Konfigurasi AI ──────────────────────────────────────────────────────────────
col_ai1, col_ai2 = st.columns([2, 1])

with col_ai1:
    ai_query = st.text_area(
        "💬 Pertanyaan Bisnis Anda:",
        placeholder=(
            "Contoh: Apa keluhan utama pelanggan tentang kualitas produk?\n"
            "Contoh: Mengapa rating pakaian wanita rendah?\n"
            "Contoh: Produk apa yang paling banyak dipuji pelanggan?"
        ),
        height=130,
        key="ai_query_input"
    )

with col_ai2:
    # Dropdown pemilihan model Gemini
    selected_model_label = st.selectbox(
        "🧠 Pilih Model Gemini:",
        options=list(aic.GEMINI_MODELS.keys()),
        index=0,  # Default: gemini-3.1-flash-lite (paling hemat)
        help=(
            "• **3.1 Flash-Lite** (Default): Tercepat & paling hemat token. Cocok untuk analisis rutin.\n"
            "• **3.5 Flash**: Lebih cerdas, cocok untuk pertanyaan kompleks.\n"
            "• **2.5 Flash**: Paling kuat, untuk analisis mendalam."
        ),
        key="ai_model_select"
    )
    selected_model_id = aic.GEMINI_MODELS[selected_model_label]

    sentiment_filter = st.selectbox(
        "📊 Filter Ulasan:",
        options=["Semua Ulasan", "Hanya Negatif (Rating ≤ 2)", "Hanya Positif (Rating ≥ 4)"],
        index=0,
        key="ai_sentiment_filter"
    )

st.caption(f"🔧 Model aktif: `{selected_model_id}` | Akan menganalisis hingga **{aic.RAG_TOP_K} ulasan** paling relevan dari dataset.")

# ── Tombol Generate Insight ─────────────────────────────────────────────────────
if st.button("✨ Generate Insight", type="primary", width="stretch", key="btn_generate_insight"):
    if not ai_query.strip():
        st.warning("⚠️ Silakan tulis pertanyaan bisnis Anda terlebih dahulu.")
        st.stop()
    else:
        # Ambil API key dari secrets
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            st.error("❌ API Key Gemini tidak ditemukan di `.streamlit/secrets.toml`. Tambahkan: `GEMINI_API_KEY = \"...key-anda...\"`")
        else:
            # Ambil dataframe dari database (CSV fallback)
            df_for_rag = db.get_csv_data()

            with st.spinner(f"🔍 Mencari ulasan relevan via RAG... lalu memanggil {selected_model_id}..."):
                result = aic.run_ai_consultant(
                    df=df_for_rag,
                    query=ai_query,
                    api_key=api_key,
                    model_id=selected_model_id,
                    sentiment_filter=sentiment_filter,
                )

            report = result["report"]
            retrieved_count = result["retrieved_count"]
            guard = result["guard_result"]
            grounding_score = guard["score"]

            # ── Status Grounding Badge ──────────────────────────────────────────
            st.markdown("---")
            badge_col1, badge_col2, badge_col3 = st.columns(3)
            with badge_col1:
                st.metric("📄 Ulasan Dianalisis (RAG)", f"{retrieved_count} ulasan")
            with badge_col2:
                score_pct = f"{grounding_score * 100:.1f}%"
                st.metric("🛡️ Grounding Score", score_pct, help="Seberapa besar laporan ini bersumber dari data ulasan Anda.")
            with badge_col3:
                if guard["grounded"]:
                    st.success("✅ **Grounded in Data**")
                else:
                    st.warning("⚠️ **Jawaban Umum (Kurang Data)**")

            # ── Tampilkan Hallucination Warning Jika Perlu ──────────────────────
            if not guard["grounded"] and guard["warning"]:
                st.warning(guard["warning"])

            # ── Tampilkan Laporan Gemini ────────────────────────────────────────
            st.markdown("### 📋 Laporan AI Business Insight")
            st.markdown(report)