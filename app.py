import streamlit as st
import plotly.express as px
import database as db
import queries as q

# 1. Konfigurasi Halaman Dashboard (Wide Mode & Tema Dasar)
st.set_page_config(page_title="Market-Pulse Dashboard", layout="wide", page_icon="📊")

# ==================== SIDEBAR NAVIGASI & LOGO ====================
with st.sidebar:
    st.title("🎛️ Pusat Kendali")
    st.markdown("Aplikasi **Market-Pulse** v1.1")

    menu = st.radio(
        "Pilih Halaman Analisis:",
        [
            "📈 Dashboard Umum", 
            "⚠️ Analisis Komplain & Pasar", 
            "🔍 Pencarian Ulasan Dinamis", 
            "🔮 Simulator & Evaluator AI" 
        ]
    )

    st.write("---")
    st.markdown("Developed by Kelompok 2")
    st.markdown("🎓 *Celerates Independent Study 2026*")

# ==================== HALAMAN UTAMA: HEADER GLOBAL ====================
st.title("📊 Market-Pulse: E-Commerce Analytics")
st.markdown("Pusat Kendali Analisis Tren, Segmentasi Pasar, dan Sentimen Produk Toko Anda")
st.write("---")


# ==================== MENU 1: DASHBOARD UMUM ====================
if menu == "📈 Dashboard Umum":
    # ==================== BARIS 1: METRIC CARDS (RINGKASAN CEPAT) ====================
    df_total = db.run_query("SELECT COUNT(*) as total FROM reviews;")
    total_all_reviews = df_total["total"][0] if not df_total.empty else 0

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric(label="📈 Total Volume Ulasan", value=f"{total_all_reviews:,} Data")
    with col_m2:
        st.metric(label="⭐ Target Kepuasan Produk", value="4.20 / 5.00")
    with col_m3:
        st.metric(label="🚀 Status Sistem AI", value="Ready (Modul 7)")

    st.write("---")

    # ==================== BARIS 2: PRODUK POPULER & LOYALITAS ====================
    col_pop1, col_pop2 = st.columns([2, 1])

    with col_pop1:
        st.subheader("🔥 Top 10 Produk Populer (Banyak Di-upvote Pelanggan)")
        df_populer = db.run_query(q.QUERY_PRODUK_POPULER)
        
        df_populer["Clothing ID"] = df_populer["Clothing ID"].astype(str)
        
        fig_pop = px.bar(df_populer, 
                         x="Clothing ID", 
                         y="Total Positive Feedback",
                         text="Total Positive Feedback", 
                         color="Average Rating",
                         labels={"Clothing ID": "ID Produk", "Total Positive Feedback": "Total Upvote (Helpful)"},
                         title="Produk Paling Banyak Mendapat Interaksi Positif",
                         color_continuous_scale=px.colors.sequential.Viridis)
        
        fig_pop.update_layout(
            xaxis={
                'type': 'category',
                'categoryorder': 'total descending'
            }
        )
        st.plotly_chart(fig_pop, use_container_width=True)

    with col_pop2:
        st.subheader("🎯 Loyalitas per Departemen")
        df_loyal = db.run_query(q.QUERY_LOYALITAS_PELANGGAN)
        fig_loyal = px.pie(df_loyal, values="Total Reviews", names="Department",
                           hole=0.4, title="Distribusi Volume Ulasan")
        st.plotly_chart(fig_loyal, use_container_width=True)


# ==================== MENU 2: ANALISIS KOMPLAIN & PASAR ====================
elif menu == "⚠️ Analisis Komplain & Pasar":
    # ==================== BARIS 3: SEGMENTASI PASAR & KELUHAN ====================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👥 Karakteristik Pasar Berdasarkan Usia & Departemen")
        df_pasar = db.run_query(q.QUERY_SEGMENTASI_PASAR)
        
        fig_pasar = px.bar(df_pasar, x="Age Group", y="Total Purchase",
                           color="Department", barmode="group",
                           title="Volume Pembelian Berdasarkan Generasi Usia")
        st.plotly_chart(fig_pasar, use_container_width=True)

    with col2:
        st.subheader("⚠️ Titik Masalah: Ulasan Negatif per Kategori")
        df_keluhan = db.run_query(q.QUERY_KELUHAN_PRODUK)
        
        fig_keluhan = px.bar(df_keluhan, 
                             x="Class", 
                             y="Defect Rate",
                             text="Negative Reviews", 
                             color="Defect Rate",
                             hover_data={
                                 "Division": True,     
                                 "Department": True,   
                                 "Class": True,        
                                 "Defect Rate": ":.2f" 
                             },
                             labels={"Defect Rate": "Rasio Cacat (%)", "Class": "Kategori Kelas"},
                             title="Kategori dengan Komplain > 10 Ulasan (Label: Jumlah Komplain)",
                             color_continuous_scale=px.colors.sequential.OrRd)
        
        fig_keluhan.update_layout(xaxis_categoryorder='total descending')
        st.plotly_chart(fig_keluhan, use_container_width=True)


# ==================== MENU 3: PENCARIAN ULASAN DINAMIS ====================
elif menu == "🔍 Pencarian Ulasan Dinamis":
    # ==================== BARIS 4: FITUR FILTER KATA KUNCI DINAMIS ====================
    st.subheader("🔍 Mesin Pencari & Penyaring Ulasan Pelanggan")
    st.markdown("Fitur interaktif untuk menyaring curhatan pelanggan berdasarkan kata kunci dan rating.")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        kata_kunci = st.text_input("Ketik Kata Kunci yang Dicari (Contoh: love, perfect, fabric, size):", "perfect")
    with col_f2:
        pilihan_rating = st.selectbox("Pilih Rating Ulasan Pelanggan:", [5, 4, 3, 2, 1], index=0)

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
        st.dataframe(df_dinamis, use_container_width=True)
    else:
        st.info(f"Tidak ada ulasan dengan kata kunci '{kata_kunci}' pada Rating {pilihan_rating}.")

    st.write("---")

    # ==================== BARIS 5: TABEL DETAIL EFEKTIVITAS ULASAN ====================
    st.subheader("💡 Efektivitas Ulasan Ekstrem Berdasarkan Rating")
    df_efektif = db.run_query(q.QUERY_EFEKTIVITAS_ULASAN)
    st.dataframe(df_efektif, use_container_width=True)


# ==================== MENU 4: WADAH MODUL AI KELOMPOK (BARU) ====================
elif menu == "🔮 Simulator & Evaluator AI":
    st.title("🔮 Pusat Kendali Kecerdasan Buatan (AI Modules)")
    st.markdown("Halaman ini dipersiapkan untuk integrasi model Machine Learning (NLP) dan Generative AI (Gemini).")
    st.write("---")
    
    # Wadah Tugas Teman TI
    st.subheader("🤖 Modul 1: Simulator Prediksi Sentimen Ulasan (ML x NLP)")
    st.caption("Status: *In Development* (Assigned to: Teman TI)")
    ulasan_baru = st.text_area("Coba Ketik Ulasan Pelanggan di Sini:", placeholder="Type a review here...")
    if st.button("Uji Prediksi Sentimen"):
        st.info("Fitur sedang dikembangkan oleh tim NLP Specialist menggunakan model klasifikasi Scikit-learn.")
        
    st.write("---")
    
    # Wadah Tugas Anak MI
    st.subheader("💡 Modul 2: AI Auto-Evaluator (GenAI x Prompt Engineering)")
    st.caption("Status: *In Development* (Assigned to: Anak MI)")
    if st.button("Minta Rekomendasi Bisnis Otomatis"):
        st.warning("Fitur sedang dikembangkan oleh GenAI Engineer menggunakan integrasi Google Gemini API.")
import streamlit as st
import plotly.express as px
import modules.database as db
import modules.queries as q
import modules.ai_consultant as aic
import modules.upload_processor as up
import modules.ml_pipeline as mlp

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
    st.write("---")

    # ==================== SIDEBAR: UPLOAD DATASET BARU ====================
    with st.expander("📤 Upload Dataset Baru  ▶", expanded=False):
        st.markdown("**Unggah file ulasan Anda sendiri** untuk dianalisis sentimennya secara otomatis.")
        st.caption("Format: `.csv` atau `.xlsx` | Maks: 50 MB | Min: 100 baris")

        uploaded_file = st.file_uploader(
            label="Pilih file dataset:",
            type=["csv", "xlsx"],
            key="sidebar_file_uploader",
            label_visibility="collapsed"
        )

        if uploaded_file is not None:
            # Simpan info file ke session agar Section 5 bisa membacanya
            if st.session_state.get("_last_uploaded_name") != uploaded_file.name:
                st.session_state["_last_uploaded_name"] = uploaded_file.name
                st.session_state["_upload_result"] = None  # Reset hasil lama

            st.info(f"📄 File dipilih: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")
            st.session_state["_uploaded_file"] = uploaded_file

            if st.button("🔍 Validasi & Proses", key="btn_sidebar_proses", use_container_width=False):
                with st.spinner("Memvalidasi dan membersihkan data..."):
                    result = up.process_upload(uploaded_file)
                st.session_state["_upload_result"] = result

            # Tampilkan status validasi ringkas di sidebar
            result = st.session_state.get("_upload_result")
            if result is not None:
                if not result["ok"]:
                    st.error(result["error"])
                else:
                    st.success(
                        f"✅ **Siap dianalisis!**\n\n"
                        f"- Baris valid: **{result['final_rows']:,}**\n"
                        f"- Kolom Ulasan: `{result['text_col']}`\n"
                        f"- Kolom Rating: `{result['rating_col'] or 'Tidak ditemukan'}`"
                    )
                    st.caption("Scroll ke bawah → lihat **Section 5** untuk hasil analisis.")

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
    
    st.plotly_chart(fig_pop, use_container_width=True)

with col_pop2:
    st.subheader("🎯 Loyalitas per Departemen")
    df_loyal = db.run_query(q.QUERY_LOYALITAS_PELANGGAN)
    fig_loyal = px.pie(df_loyal, values="Total Reviews", names="Department",
                       hole=0.4, title="Distribusi Volume Ulasan")
    st.plotly_chart(fig_loyal, use_container_width=True)

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
    st.plotly_chart(fig_pasar, use_container_width=True)

with col2:
    st.subheader("⚠️ Titik Masalah: Ulasan Negatif per Kategori")
    df_keluhan = db.run_query(q.QUERY_KELUHAN_PRODUK)
    
    # Menampilkan Defect Rate yang sudah diperbaiki tipe datanya kemarin
    fig_keluhan = px.bar(df_keluhan, x="Class", y="Defect Rate",
                         text="Negative Reviews", color="Defect Rate",
                         labels={"Defect Rate": "Rasio Cacat (%)", "Class": "Kategori Kelas"},
                         title="Kategori dengan Komplain > 10 Ulasan (Label: Jumlah Komplain)",
                         color_continuous_scale=px.colors.sequential.OrRd)
    st.plotly_chart(fig_keluhan, use_container_width=True)

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
    st.dataframe(df_dinamis, use_container_width=True, hide_index=True)
else:
    st.info(f"Tidak ada ulasan dengan kata kunci '{kata_kunci}' pada Rating {pilihan_rating}.")

st.write("---")

# ==================== BARIS 5: ANALISIS DATASET YANG DIUNGGAH ====================
st.subheader("📤 Analisis Dataset Baru yang Diunggah")
st.markdown(
    "Setelah mengunggah dan memvalidasi file dataset di **Sidebar kiri**, "
    "hasil analisis sentimen otomatis akan muncul di sini."
)

_upload_result = st.session_state.get("_upload_result")

if _upload_result is None:
    st.info("💡 Belum ada dataset yang diunggah. Gunakan panel **📤 Upload Dataset Baru** di sidebar kiri untuk memulai.")
elif not _upload_result["ok"]:
    st.error(_upload_result["error"])
else:
    df_uploaded = _upload_result["df"]
    text_col = _upload_result["text_col"]
    rating_col = _upload_result["rating_col"]
    fname = st.session_state.get("_last_uploaded_name", "dataset")

    # ── Info Ringkas File ──────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📄 Total Baris Valid", f"{_upload_result['final_rows']:,}")
    with c2:
        st.metric("📝 Kolom Ulasan", text_col)
    with c3:
        st.metric("⭐ Kolom Rating", rating_col or "Tidak Ada")

    if _upload_result["is_sampled"]:
        st.warning(
            f"⚠️ Dataset asli memiliki lebih dari {up.MAX_ROWS:,} baris. "
            f"Sistem mengambil sampel acak **{up.MAX_ROWS:,} baris** untuk analisis."
        )

    # Preview 5 baris pertama
    with st.expander("🔎 Preview Data (5 baris pertama)", expanded=False):
        preview_cols = [c for c in ["_review_text", "_rating"] if c in df_uploaded.columns]
        st.dataframe(df_uploaded[preview_cols].head(), hide_index=True)

    # ── Tombol Analisis Sentimen ───────────────────────────────────────────────
    if st.button("🤖 Jalankan Analisis Sentimen", type="primary", key="btn_run_sentiment"):
        with st.spinner("Menganalisis sentimen... Harap tunggu sebentar."):
            df_result = mlp.predict_sentiments(df_uploaded)
            st.session_state["_df_analyzed"] = df_result

    # ── Tampilkan Hasil Analisis ───────────────────────────────────────────────
    df_analyzed = st.session_state.get("_df_analyzed")
    if df_analyzed is not None and "_predicted_label" in df_analyzed.columns:
        ml_mode = df_analyzed["_ml_mode"].iloc[0]
        ml_acc  = df_analyzed["_ml_accuracy"].iloc[0]
        n_corrected = int(df_analyzed["_is_corrected"].sum())

        # Info mode ML
        if ml_mode == "train_on_the_fly":
            st.success(
                f"✅ **Mode: Train-On-The-Fly** — Model dilatih khusus dari dataset ini. "
                f"Akurasi uji: **{ml_acc * 100:.2f}%**"
            )
        elif ml_mode == "fallback":
            st.info("ℹ️ **Mode: Fallback** — Menggunakan model sentimen base yang sudah ada (tidak ada kolom rating terdeteksi).")
        else:
            st.warning("⚠️ Model sentimen tidak tersedia. Jalankan `python train_model.py` terlebih dahulu.")

        if n_corrected > 0:
            st.caption(f"🔧 {n_corrected:,} prediksi dikoreksi secara otomatis oleh Rule-Based (berdasarkan rating bintang).")

        # Metrik hasil sentimen
        valid = df_analyzed[df_analyzed["_predicted_label"].isin(["Positif", "Negatif"])]
        n_pos = int((valid["_predicted_label"] == "Positif").sum())
        n_neg = int((valid["_predicted_label"] == "Negatif").sum())
        n_total = n_pos + n_neg

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("✅ Ulasan Positif", f"{n_pos:,}",
                      delta=f"{n_pos/n_total*100:.1f}%" if n_total else None)
        with m2:
            st.metric("❌ Ulasan Negatif", f"{n_neg:,}",
                      delta=f"-{n_neg/n_total*100:.1f}%" if n_total else None)
        with m3:
            st.metric("📊 Total Dianalisis", f"{n_total:,}")

        # Grafik distribusi sentimen
        if n_total > 0:
            import plotly.express as px
            sentiment_counts = valid["_predicted_label"].value_counts().reset_index()
            sentiment_counts.columns = ["Sentimen", "Jumlah"]
            fig_sent = px.pie(
                sentiment_counts,
                names="Sentimen",
                values="Jumlah",
                color="Sentimen",
                color_discrete_map={"Positif": "#22c55e", "Negatif": "#ef4444"},
                title=f"Distribusi Sentimen — {fname}",
                hole=0.45
            )
            st.plotly_chart(fig_sent, use_container_width=False)

        # Tabel hasil (bisa diunduh)
        show_cols = ["_review_text", "_rating", "_predicted_label", "_is_corrected"]
        show_cols = [c for c in show_cols if c in df_analyzed.columns]
        rename_map = {
            "_review_text": "Teks Ulasan",
            "_rating": "Rating",
            "_predicted_label": "Sentimen Prediksi",
            "_is_corrected": "Dikoreksi Rule-Based"
        }
        with st.expander("📋 Lihat Tabel Hasil Analisis", expanded=False):
            st.dataframe(
                df_analyzed[show_cols].rename(columns=rename_map),
                hide_index=True,
                use_container_width=False
            )

        # ── Opsi Ekspor/Simpan Hasil (Ekspor CSV & Simpan ke DB) ──────────────────
        st.markdown("---")
        st.markdown("#### 💾 Simpan / Ekspor Hasil Analisis")

        dl_col, db_col = st.columns(2)
        with dl_col:
            st.markdown("**1. Unduh Hasil Sebagai CSV**")
            st.caption("Unduh hasil prediksi sentimen dataset ini langsung ke komputer Anda.")
            csv_data = df_analyzed[show_cols].rename(columns=rename_map).to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV Hasil Analisis",
                data=csv_data,
                file_name=f"hasil_analisis_{fname}.csv",
                mime="text/csv",
                key="download_csv_btn",
                use_container_width=True
            )

        with db_col:
            st.markdown("**2. Simpan ke Database PostgreSQL**")
            st.caption("Simpan dataset beserta hasil analisis sentimen secara permanen ke database.")
            if st.button("💾 Simpan ke PostgreSQL", key="btn_save_db", use_container_width=True):
                with st.spinner("Menginisialisasi schema dan menyimpan data..."):
                    # 1. Init schema jika belum ada
                    schema_res = db.init_schema()
                    if not schema_res["ok"]:
                        st.error(f"❌ Gagal membuat schema: {schema_res['error']}")
                    else:
                        # 2. Insert metadata dataset
                        ds_res = db.insert_dataset(
                            file_name=fname,
                            row_count=len(df_analyzed)
                        )
                        if not ds_res["ok"]:
                            st.error(f"❌ Gagal menyimpan metadata dataset: {ds_res['error']}")
                        else:
                            # 3. Bulk insert ulasan
                            insert_res = db.bulk_insert_reviews(df_analyzed, ds_res["dataset_id"])
                            if insert_res["ok"]:
                                st.success(
                                    f"✅ **Berhasil disimpan!** "
                                    f"**{insert_res['inserted']:,} ulasan** dari `{fname}` "
                                    f"(Dataset ID: `{ds_res['dataset_id']}`) telah tersimpan di PostgreSQL."
                                )
                            else:
                                st.error(f"❌ Gagal menyimpan ulasan: {insert_res['error']}")

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

# Menggunakan path relative terhadap app.py (folder models)
current_dir = os.path.dirname(__file__)
model_path = os.path.join(current_dir, "models", "model_sentimen.pkl")
vectorizer_path = os.path.join(current_dir, "models", "vectorizer.pkl")

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
        
        if st.button("Analisis Sentimen Hybrid", type="primary", use_container_width=True):
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

# ── Pemilihan Sumber Data RAG ────────────────────────────────────────────────
_has_uploaded = st.session_state.get("_upload_result") is not None and st.session_state["_upload_result"].get("ok")
_uploaded_fname = st.session_state.get("_last_uploaded_name", "dataset yang diunggah")

if _has_uploaded:
    rag_data_source = st.radio(
        "📁 **Sumber Data untuk AI Consultant:**",
        options=[
            f"📂 Dataset yang Diunggah: `{_uploaded_fname}`",
            "🗄️ Dataset Bawaan (ecommercereviews)"
        ],
        index=0,
        horizontal=True,
        key="rag_data_source_radio"
    )
else:
    rag_data_source = "🗄️ Dataset Bawaan (ecommercereviews)"
    st.caption("💡 Untuk menganalisis dataset Anda sendiri, upload terlebih dahulu di panel **📤 Upload Dataset Baru** di sidebar kiri.")

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
    selected_model_id = (
        aic.GEMINI_MODELS.get(selected_model_label, "gemini-3.1-flash-lite")
        if selected_model_label
        else "gemini-3.1-flash-lite"
    )

    sentiment_filter = st.selectbox(
        "📊 Filter Ulasan:",
        options=["Semua Ulasan", "Hanya Negatif (Rating ≤ 2)", "Hanya Positif (Rating ≥ 4)"],
        index=0,
        key="ai_sentiment_filter"
    )

st.caption(f"🔧 Model aktif: `{selected_model_id}` | Akan menganalisis hingga **{aic.RAG_TOP_K} ulasan** paling relevan dari dataset.")

# ── Tombol Generate Insight ─────────────────────────────────────────────────────
if st.button("✨ Generate Insight", type="primary", use_container_width=True, key="btn_generate_insight"):
    if not ai_query.strip():
        st.warning("⚠️ Silakan tulis pertanyaan bisnis Anda terlebih dahulu.")
        st.stop()
    else:
        # Ambil API key dari secrets
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            st.error("❌ API Key Gemini tidak ditemukan di `.streamlit/secrets.toml`. Tambahkan: `GEMINI_API_KEY = \"...key-anda...\"`")
        else:
            # Tentukan sumber data dan nama dataset berdasarkan pilihan radio
            if _has_uploaded and "Diunggah" in rag_data_source:
                df_for_rag = st.session_state["_upload_result"]["df"]
                dataset_name = _uploaded_fname
            else:
                df_for_rag = db.get_csv_data()
                dataset_name = "Dataset Bawaan (ecommercereviews)"

            import pandas as pd
            df_for_rag_df = df_for_rag if isinstance(df_for_rag, pd.DataFrame) else pd.DataFrame(df_for_rag)

            with st.spinner(f"🔍 Memeriksa relevansi & mencari ulasan dari '{dataset_name}'..."):
                result = aic.run_ai_consultant(
                    df=df_for_rag_df,
                    query=ai_query,
                    api_key=api_key,
                    model_id=selected_model_id,
                    sentiment_filter=sentiment_filter,
                    dataset_name=dataset_name,
                )

            # ── Cek: Apakah query diblokir Pre-flight Guardrail? ────────────────────
            if result.get("blocked"):
                st.markdown("---")
                st.error(result["block_reason"])
                st.info(
                    "💡 **Tip**: AI Consultant ini dirancang khusus untuk menganalisis data "
                    "ulasan e-commerce. Pastikan pertanyaan Anda berkaitan dengan ulasan produk, "
                    "rating, sentimen pelanggan, atau performa toko."
                )
            else:
                report = result["report"]
                retrieved_count = result["retrieved_count"]
                guard = result["guard_result"]
                grounding_score = guard["score"]
                used_dataset = result.get("dataset_name", "")

                # ── Status Grounding Badge ───────────────────────────────────
                st.markdown("---")
                st.caption(f"🗂️ Sumber data RAG: **{used_dataset}** | Filter: **{sentiment_filter}** | Model: `{selected_model_id}`")
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
                        st.warning("⚠️ **Jawaban Umum / Kurang Data**")

                # ── Tampilkan Hallucination Warning Jika Perlu ────────────────────
                if not guard["grounded"] and guard["warning"]:
                    st.warning(guard["warning"])

                # ── Tampilkan Laporan Gemini ─────────────────────────────────
                st.markdown("### 📋 Laporan AI Business Insight")
                st.markdown(report)
