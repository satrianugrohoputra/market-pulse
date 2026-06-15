import streamlit as st
import plotly.express as px
import re
import os
import pickle
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Import modul lokal kelompok dari folder 'modules'
from modules import database as db
from modules import queries as q
from modules import ai_consultant as aic
from modules import upload_processor as up
from modules import ml_pipeline as mlp

# 1. Konfigurasi Halaman Dashboard (Wide Mode & Tema Dasar)
st.set_page_config(page_title="Market-Pulse Dashboard", layout="wide", page_icon="📊")

# ==================== SIDEBAR NAVIGASI & LOGO (SATU WADAH) ====================
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

    # FITUR UPLOAD TEMANMU: Dimasukkan ke sidebar agar efisien
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
            if st.session_state.get("_last_uploaded_name") != uploaded_file.name:
                st.session_state["_last_uploaded_name"] = uploaded_file.name
                st.session_state["_upload_result"] = None  # Reset hasil lama

            st.info(f"📄 File dipilih: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")
            st.session_state["_uploaded_file"] = uploaded_file

            if st.button("🔍 Validasi & Proses", key="btn_sidebar_proses", use_container_width=False):
                with st.spinner("Memvalidasi dan membersihkan data..."):
                    result = up.process_upload(uploaded_file)
                st.session_state["_upload_result"] = result

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
                    st.caption("Lihat **Halaman 4 (Simulator & Evaluator AI)** untuk memproses hasil analisis.")

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
        
        fig_pop.update_layout(xaxis={'type': 'category', 'categoryorder': 'total descending'})
        st.plotly_chart(fig_pop, use_container_width=True)

    with col_pop2:
        st.subheader("🎯 Loyalitas per Departemen")
        df_loyal = db.run_query(q.QUERY_LOYALITAS_PELANGGAN)
        fig_loyal = px.pie(df_loyal, values="Total Reviews", names="Department", hole=0.4, title="Distribusi Volume Ulasan")
        st.plotly_chart(fig_loyal, use_container_width=True)


# ==================== MENU 2: ANALISIS KOMPLAIN & PASAR ====================
elif menu == "⚠️ Analisis Komplain & Pasar":
    # ==================== BARIS 3: SEGMENTASI PASAR & KELUHAN ====================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👥 Karakteristik Pasar Berdasarkan Usia & Departemen")
        df_pasar = db.run_query(q.QUERY_SEGMENTASI_PASAR)
        fig_pasar = px.bar(df_pasar, x="Age Group", y="Total Purchase", color="Department", barmode="group", title="Volume Pembelian Berdasarkan Generasi Usia")
        st.plotly_chart(fig_pasar, use_container_width=True)

    with col2:
        st.subheader("⚠️ Titik Masalah: Ulasan Negatif per Kategori")
        df_keluhan = db.run_query(q.QUERY_KELUHAN_PRODUK)
        fig_keluhan = px.bar(df_keluhan, 
                             x="Class", 
                             y="Defect Rate",
                             text="Negative Reviews", 
                             color="Defect Rate",
                             hover_data={"Division": True, "Department": True, "Class": True, "Defect Rate": ":.2f"},
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
        st.dataframe(df_dinamis, use_container_width=True, hide_index=True)
    else:
        st.info(f"Tidak ada ulasan dengan kata kunci '{kata_kunci}' pada Rating {pilihan_rating}.")

    st.write("---")

    # ==================== BARIS 5: TABEL DETAIL EFEKTIVITAS ULASAN ====================
    st.subheader("💡 Efektivitas Ulasan Ekstrem Berdasarkan Rating")
    df_efektif = db.run_query(q.QUERY_EFEKTIVITAS_ULASAN)
    st.dataframe(df_efektif, use_container_width=True)


# ==================== MENU 4: PUSAT KENDALI AI KELOMPOK ====================
elif menu == "🔮 Simulator & Evaluator AI":
    st.title("🔮 Pusat Kendali Kecerdasan Buatan (AI Modules)")
    st.markdown("Halaman ini mengintegrasikan model Machine Learning (NLP) kelompok dan Konsultan AI Generatif Gemini.")
    st.write("---")
    
    # ── SUB-MENU A: ANALISIS DATASET YANG DIUNGGAH (Milik Temanmu) ──
    st.subheader("📥 1. Analisis Dataset Baru yang Diunggah")
    st.markdown("Hasil analisis sentimen otomatis dari file yang diunggah via sidebar kiri.")

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

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("📄 Total Baris Valid", f"{_upload_result['final_rows']:,}")
        with c2: st.metric("📝 Kolom Ulasan", text_col)
        with c3: st.metric("⭐ Kolom Rating", rating_col or "Tidak Ada")

        if _upload_result["is_sampled"]:
            st.warning(f"⚠️ Dataset asli memiliki lebih dari {up.MAX_ROWS:,} baris. Sistem mengambil sampel acak **{up.MAX_ROWS:,} baris**.")

        with st.expander("🔎 Preview Data (5 baris pertama)", expanded=False):
            preview_cols = [c for c in ["_review_text", "_rating"] if c in df_uploaded.columns]
            st.dataframe(df_uploaded[preview_cols].head(), hide_index=True)

        if st.button("🤖 Jalankan Analisis Sentimen Bulk", type="primary", key="btn_run_sentiment"):
            with st.spinner("Menganalisis sentimen... Harap tunggu sebentar."):
                df_result = mlp.predict_sentiments(df_uploaded)
                st.session_state["_df_analyzed"] = df_result

        df_analyzed = st.session_state.get("_df_analyzed")
        if df_analyzed is not None and "_predicted_label" in df_analyzed.columns:
            ml_mode = df_analyzed["_ml_mode"].iloc[0]
            ml_acc  = df_analyzed["_ml_accuracy"].iloc[0]
            n_corrected = int(df_analyzed["_is_corrected"].sum())

            if ml_mode == "train_on_the_fly":
                st.success(f"✅ **Mode: Train-On-The-Fly** — Akurasi uji: **{ml_acc * 100:.2f}%**")
            elif ml_mode == "fallback":
                st.info("ℹ️ **Mode: Fallback** — Menggunakan model sentimen base yang sudah ada.")

            if n_corrected > 0:
                st.caption(f"🔧 {n_corrected:,} prediksi dikoreksi secara otomatis oleh Rule-Based.")

            valid = df_analyzed[df_analyzed["_predicted_label"].isin(["Positif", "Negatif"])]
            n_pos, n_neg = int((valid["_predicted_label"] == "Positif").sum()), int((valid["_predicted_label"] == "Negatif").sum())
            n_total = n_pos + n_neg

            m1, m2, m3 = st.columns(3)
            with m1: st.metric("✅ Ulasan Positif", f"{n_pos:,}", delta=f"{n_pos/n_total*100:.1f}%" if n_total else None)
            with m2: st.metric("❌ Ulasan Negatif", f"{n_neg:,}", delta=f"-{n_neg/n_total*100:.1f}%" if n_total else None)
            with m3: st.metric("📊 Total Dianalisis", f"{n_total:,}")

            if n_total > 0:
                sentiment_counts = valid["_predicted_label"].value_counts().reset_index()
                sentiment_counts.columns = ["Sentimen", "Jumlah"]
                fig_sent = px.pie(sentiment_counts, names="Sentimen", values="Jumlah", color="Sentimen",
                                  color_discrete_map={"Positif": "#22c55e", "Negatif": "#ef4444"},
                                  title=f"Distribusi Sentimen — {fname}", hole=0.45)
                st.plotly_chart(fig_sent, use_container_width=False)

            st.markdown("#### 💾 Simpan / Ekspor Hasil Analisis")
            dl_col, db_col = st.columns(2)
            with dl_col:
                csv_data = df_analyzed.to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Download CSV Hasil Analisis", data=csv_data, file_name=f"hasil_analisis_{fname}.csv", mime="text/csv", use_container_width=True)
            with db_col:
                if st.button("💾 Simpan ke PostgreSQL", key="btn_save_db", use_container_width=True):
                    with st.spinner("Menyimpan data ke PostgreSQL..."):
                        schema_res = db.init_schema()
                        if schema_res["ok"]:
                            ds_res = db.insert_dataset(file_name=fname, row_count=len(df_analyzed))
                            if ds_res["ok"]:
                                insert_res = db.bulk_insert_reviews(df_analyzed, ds_res["dataset_id"])
                                if insert_res["ok"]: st.success(f"✅ Berhasil disimpan ke PostgreSQL! Dataset ID: `{ds_res['dataset_id']}`")

    st.write("---")
    
    # ── SUB-MENU B: SIMULATOR PREDIKSI SENTIMENT INSTAN (ML X NLP) ──
    st.subheader("🔮 2. Simulator Prediksi Sentimen (Hybrid ML & Rules)")
    st.markdown("Ketik ulasan baru secara instan untuk menguji model klasifikasi.")
    
    def preprocess_input(text):
        if not isinstance(text, str): return ""
        text = text.lower()
        text = re.sub(r'[^a-z\s]', '', text)
        return " ".join([w for w in text.split() if w not in ENGLISH_STOP_WORDS])

    current_dir = os.path.dirname(__file__)
    model_path = os.path.join(current_dir, "models", "model_sentimen.pkl")
    vectorizer_path = os.path.join(current_dir, "models", "vectorizer.pkl")

    if os.path.exists(model_path) and os.path.exists(vectorizer_path):
        try:
            with open(model_path, "rb") as f: model = pickle.load(f)
            with open(vectorizer_path, "rb") as f: vectorizer = pickle.load(f)
                
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                user_review = st.text_area("Tulis ulasan produk Anda di sini (Bahasa Inggris):", placeholder="Type a review...", height=100, key="sim_review_text")
            with col_s2:
                rating_choice = st.selectbox("Masukkan Rating Ulasan:", ["Prediksi ML Murni (Tanpa Rating)", "1 Bintang (Negatif)", "2 Bintang (Negatif)", "3 Bintang (Netral)", "4 Bintang (Positif)", "5 Bintang (Positif)"], index=0, key="sim_rating_choice")
            
            if st.button("Analisis Sentimen Hybrid", type="primary", use_container_width=True, key="btn_run_hybrid"):
                if user_review.strip():
                    cleaned_text = preprocess_input(user_review)
                    vectorized_text = vectorizer.transform([cleaned_text])
                    ml_prediction = model.predict(vectorized_text)[0]
                    probability = model.predict_proba(vectorized_text)[0]
                    
                    final_sentiment = None
                    override_applied = False
                    
                    if "1 Bintang" in rating_choice or "2 Bintang" in rating_choice:
                        final_sentiment = "Negatif"
                        if ml_prediction == 1: override_applied = True
                    elif "4 Bintang" in rating_choice or "5 Bintang" in rating_choice:
                        final_sentiment = "Positif"
                        if ml_prediction == 0: override_applied = True
                    elif "3 Bintang" in rating_choice:
                        final_sentiment = "Netral"
                        override_applied = True
                    else:
                        final_sentiment = "Positif" if ml_prediction == 1 else "Negatif"
                    
                    st.markdown("### 📊 Hasil Analisis Sentimen")
                    ml_label = "🟢 POSITIF" if ml_prediction == 1 else "🔴 NEGATIF"
                    ml_conf = probability[1] if ml_prediction == 1 else probability[0]
                    st.info(f"🤖 **Prediksi Model ML**: {ml_label} (Tingkat Keyakinan: {ml_conf*100:.2f}%)")
                    
                    if final_sentiment == "Positif":
                        st.success(f"🟢 **Sentimen Akhir: POSITIF**")
                        if override_applied: st.caption("ℹ️ *Catatan: Sentimen dikoreksi menjadi Positif berdasarkan rating bintang (Rule-based Override).*")
                        st.balloons()
                    elif final_sentiment == "Negatif":
                        st.error(f"🔴 **Sentimen Akhir: NEGATIF**")
                        if override_applied: st.caption("ℹ️ *Catatan: Sentimen dikoreksi menjadi Negatif berdasarkan rating bintang (Rule-based Override).*")
                    else:
                        st.warning(f"🟡 **Sentimen Akhir: NETRAL**")
                else:
                    st.warning("Silakan masukkan teks ulasan terlebih dahulu.")
        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses model: {e}")
    else:
        st.info("💡 **Status**: Simulator siap! Menunggu file model klasifikasi diletakkan di folder oleh tim Machine Learning.")

    st.write("---")

    # ── SUB-MENU C: AI BUSINESS CONSULTANT (RAG + GEMINI) ──
    st.subheader("🤖 3. AI Business Consultant (Powered by Gemini)")
    st.markdown("Ajukan pertanyaan bisnis Anda. AI akan mengekstrak data ulasan via RAG lalu merangkumnya menggunakan Google Gemini.")

    _has_uploaded = st.session_state.get("_upload_result") is not None and st.session_state["_upload_result"].get("ok")
    _uploaded_fname = st.session_state.get("_last_uploaded_name", "dataset")

    if _has_uploaded:
        rag_data_source = st.radio("📁 **Sumber Data untuk AI Consultant:**", options=[f"📂 Dataset yang Diunggah: `{_uploaded_fname}`", "🗄️ Dataset Bawaan (ecommercereviews)"], index=0, horizontal=True, key="rag_source")
    else:
        rag_data_source = "🗄️ Dataset Bawaan (ecommercereviews)"

    col_ai1, col_ai2 = st.columns([2, 1])
    with col_ai1:
        ai_query = st.text_area("💬 Pertanyaan Bisnis Anda:", placeholder="Contoh: Apa keluhan utama pelanggan tentang kualitas bahan pakaian?", height=100, key="rag_query")
    with col_ai2:
        selected_model_label = st.selectbox("🧠 Pilih Model Gemini:", options=list(aic.GEMINI_MODELS.keys()), index=0, key="rag_model")
        selected_model_id = aic.GEMINI_MODELS.get(selected_model_label, "gemini-3.1-flash-lite")
        sentiment_filter = st.selectbox("📊 Filter Ulasan:", options=["Semua Ulasan", "Hanya Negatif (Rating ≤ 2)", "Hanya Positif (Rating ≥ 4)"], index=0, key="rag_filter")

    if st.button("✨ Generate Insight", type="primary", use_container_width=True, key="btn_gemini_run"):
        if not ai_query.strip():
            st.warning("⚠️ Silakan tulis pertanyaan bisnis Anda terlebih dahulu.")
        else:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
            if not api_key:
                st.error("❌ API Key Gemini tidak ditemukan di secrets.toml.")
            else:
                if _has_uploaded and "Diunggah" in rag_data_source:
                    df_for_rag = st.session_state["_upload_result"]["df"]
                    dataset_name = _uploaded_fname
                else:
                    df_for_rag = db.get_csv_data()
                    dataset_name = "Dataset Bawaan (ecommercereviews)"

                with st.spinner("🔍 Mencari data ulasan relevan via RAG..."):
                    result = aic.run_ai_consultant(df=df_for_rag, query=ai_query, api_key=api_key, model_id=selected_model_id, sentiment_filter=sentiment_filter, dataset_name=dataset_name)

                report = result["report"]
                retrieved_count = result["retrieved_count"]
                guard = result["guard_result"]
                
                st.markdown("---")
                b_c1, b_c2, b_c3 = st.columns(3)
                with b_c1: st.metric("📄 Ulasan Dianalisis (RAG)", f"{retrieved_count} ulasan")
                with b_c2: st.metric("🛡️ Grounding Score", f"{guard['score'] * 100:.1f}%")
                with b_c3:
                    if guard["grounded"]: st.success("✅ **Grounded in Data**")
                    else: st.warning("⚠️ **Jawaban Umum**")

                if not guard["grounded"] and guard["warning"]: st.warning(guard["warning"])
                st.markdown("### 📋 Laporan AI Business Insight")
                st.markdown(report)