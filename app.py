import streamlit as st
import plotly.express as px
import pandas as pd
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

    # ==================== SIDEBAR: UPLOAD DATASET BARU ====================
    with st.expander("📤 Upload Dataset Baru  ▶", expanded=False):
        st.markdown("**Unggah file ulasan Anda sendiri** untuk dianalisis sentimennya secara otomatis.")
        st.caption("Format: `.csv` or `.xlsx` | Maks: 50 MB | Min: 100 baris")

        uploaded_file = st.file_uploader(
            label="Pilih file dataset:",
            type=["csv", "xlsx"],
            key="sidebar_file_uploader",
            label_visibility="collapsed"
        )

        if uploaded_file is not None:
            if st.session_state.get("_last_uploaded_name") != uploaded_file.name:
                st.session_state["_last_uploaded_name"] = uploaded_file.name
                st.session_state["_upload_result"] = None

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
                    st.caption("Lihat halaman **🔮 Simulator & Evaluator AI** untuk melihat hasil detil.")

    st.write("---")
    st.markdown("Developed by Kelompok 2")
    st.markdown("🎓 *Celerates Independent Study 2026*")


# ==================== HALAMAN UTAMA: HEADER GLOBAL ====================
st.title("📊 Market-Pulse: E-commerce Analytics")
st.markdown("Pusat Kendali Analisis Tren, Segmentasi Pasar, dan Sentimen Produk Toko Anda")
st.write("---")


# ==================== MENU 1: DASHBOARD UMUM ====================
if menu == "📈 Dashboard Umum":
    # ==================== BARIS 1: METRIC CARDS ====================
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
        st.subheader("🔥 Top 10 Produk Populer")
        df_populer = db.run_query(q.QUERY_PRODUK_POPULER)

        if not df_populer.empty:
            # 🔍 STRATEGI PRIORITAS SARMEN 1 & 2 (Nama Produk > ID Produk)
            sumbu_x = None
            label_x = "ID Produk" # Label default

            # Tahap 1: Berburu kolom Nama Barang terlebih dahulu (Prioritas Utama)
            for col in df_populer.columns:
                if "name" in str(col).lower() or "nama" in str(col).lower():
                    sumbu_x = col
                    label_x = "Nama Produk"
                    break
            
            # Tahap 2: Jika kolom Nama TIDAK ADA, baru berburu kolom ID Produk (Fallback)
            if not sumbu_x:
                for col in df_populer.columns:
                    if "id" in str(col).lower() or "clothing" in str(col).lower():
                        sumbu_x = col
                        label_x = "ID Produk"
                        break

            # Tahap 3: Jika dua-duanya gaib, paksa pakai kolom pertama di dataframe
            if not sumbu_x:
                sumbu_x = df_populer.columns[0]
                label_x = "Produk"
            
            # Konversi kolom target ke string agar kategori Plotly rapi
            df_populer[sumbu_x] = df_populer[sumbu_x].astype(str)

            # 🔍 DETEKSI SUMBU Y (Feedback/Upvote)
            sumbu_y = None
            for col in df_populer.columns:
                if "feedback" in str(col).lower() or "upvote" in str(col).lower() or "positive" in str(col).lower():
                    sumbu_y = col
                    break
            if not sumbu_y:
                sumbu_y = df_populer.columns[1] if len(df_populer.columns) > 1 else df_populer.columns[-1]

            # 🔍 DETEKSI SKALA WARNA (Rating)
            skala_warna = None
            for col in df_populer.columns:
                if "rating" in str(col).lower() or "avg" in str(col).lower():
                    skala_warna = col
                    break
            if not skala_warna:
                skala_warna = df_populer.columns[2] if len(df_populer.columns) > 2 else sumbu_y

            # Buat grafik Plotly Express
            fig_pop = px.bar(df_populer, 
                             x=sumbu_x, 
                             y=sumbu_y, 
                             text=sumbu_y, 
                             color=skala_warna, 
                             labels={sumbu_x: label_x, sumbu_y: "Total Upvote"},
                             title="Produk Paling Banyak Mendapat Interaksi Positif",
                             color_continuous_scale=px.colors.sequential.Viridis)
            
            fig_pop.update_layout(xaxis={'type': 'category', 'categoryorder': 'total descending'})
            st.plotly_chart(fig_pop, use_container_width=True)
        else:
            st.info("Belum ada data ulasan produk populer di database.")

    with col_pop2:
        st.subheader("🎯 Loyalitas per Departemen")
        df_loyal = db.run_query(q.QUERY_LOYALITAS_PELANGGAN)
        
        if not df_loyal.empty:
            # 1. Cek secara dinamis apakah ada data file yang di-upload oleh user
            _upload_result = st.session_state.get("_upload_result")
            df_aktif_loyal = _upload_result["df"] if (_upload_result is not None and _upload_result["ok"]) else df_loyal

            # 2. 🔍 PENGECEKAN AMAN SECARA DINAMIS (Anti-Crash Dataset Luar)
            # Kita pastikan kolom departemen ada di dataset yang sedang aktif (mendukung huruf besar/kecil)
            if "department" in df_aktif_loyal.columns or "Department" in df_aktif_loyal.columns or "department_name" in df_aktif_loyal.columns:
                
                # Tentukan nama kolom secara fleksibel agar sinkron dengan database online/offline
                v_col = "total_reviews" if "total_reviews" in df_loyal.columns else "Total Reviews"
                n_col = "department" if "department" in df_loyal.columns else "Department"
                
                fig_loyal = px.pie(df_loyal, values=v_col, names=n_col, hole=0.4, title="Distribusi Volume Ulasan")
                st.plotly_chart(fig_loyal, use_container_width=True)
            else:
                # 💡 JALUR FALLBACK SEPERTI INSIGHT 3 (Sesuai Pemikiran Juara Nashwan)
                st.write("") # Kasih jarak vertikal sedikit agar rapi
                st.info("ℹ️ Data **Departemen/Kategori Sektoral** tidak ditemukan dalam dataset ini untuk memetakan loyalitas pelanggan.")
                st.caption("Tips: Visualisasi ini membutuhkan kolom klasifikasi kategori seperti 'Department' atau 'Departemen'.")
        else:
            st.info("Belum ada data departemen.")


# ==================== MENU 2: ANALISIS KOMPLAIN & PASAR ====================
elif menu == "⚠️ Analisis Komplain & Pasar":
    # ==================== BARIS 3: SEGMENTASI PASAR & KELUHAN ====================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👥 Karakteristik Pasar Berdasarkan Generasi Usia")
        
        # 1. Ambil data default dari database TERLEBIH DAHULU agar variabel df_pasar tercipta
        df_pasar = db.run_query(q.QUERY_SEGMENTASI_PASAR)
        
        # 2. Cek apakah ada file yang di-upload user untuk menentukan dataframe yang aktif
        _upload_result = st.session_state.get("_upload_result")
        df_aktif = _upload_result["df"] if (_upload_result is not None and _upload_result["ok"]) else df_pasar

        # 3. EKSEKUSI OPSI 1 (Sesuai Gambar Referensi Berhasil Kita Bahas)
        # Amankan pengecekan kolom secara fleksibel (mendukung huruf besar/kecil)
        if "age" in df_aktif.columns or "age_group" in df_aktif.columns or "Age Group" in df_aktif.columns:
            # Tentukan nama kolom sumbu secara dinamis agar tidak ValueError
            x_col = "age_group" if "age_group" in df_pasar.columns else "Age Group"
            y_col = "total_purchase" if "total_purchase" in df_pasar.columns else "Total Purchase"
            c_col = "department" if "department" in df_pasar.columns else "Department"
            
            fig_pasar = px.bar(df_pasar, x=x_col, y=y_col, color=c_col, barmode="group", 
                               labels={x_col: "Generasi Usia", y_col: "Volume Pembelian", c_col: "Departemen"},
                               title="Volume Pembelian Berdasarkan Generasi Usia")
            st.plotly_chart(fig_pasar, use_container_width=True)
        else:
            # Tampilkan kotak info biru estetik jika kolom usia tidak ada di dataset user
            st.info("ℹ️ Data **Usia Pelanggan** tidak ditemukan dalam dataset ini untuk menghasilkan analisis karakteristik pasar.")
            st.caption("Tips: Pastikan file yang Anda unggah memiliki kolom 'Age' atau 'Usia' jika ingin melihat tren pembelian antar generasi.")

    with col2:
        st.subheader("⚠️ Titik Masalah: Komplain Produk Terbanyak")
        df_keluhan = db.run_query(q.QUERY_KELUHAN_PRODUK)
    
        if not df_keluhan.empty:
            # Cek secara dinamis sumber data yang aktif
            _upload_result = st.session_state.get("_upload_result")
            df_aktif_keluhan = _upload_result["df"] if (_upload_result is not None and _upload_result["ok"]) else df_keluhan

            # 🔍 STRATEGI BUNGLON: Tentukan Sumbu X secara cerdas
            if "class" in df_aktif_keluhan.columns or "Class" in df_aktif_keluhan.columns:
                # Skenario A: Dataset lengkap bawaan (Mengelompokkan per Kelas pakaian)
                sumbu_x_keluhan = "class" if "class" in df_keluhan.columns else "Class"
                sumbu_y_keluhan = "defect_rate" if "defect_rate" in df_keluhan.columns else "Defect Rate"
                label_x_keluhan = "Kategori Kelas"
                title_keluhan = "Kategori Kelas dengan Komplain Terbanyak (Label: Jumlah Komplain)"
            elif "clothing_id" in df_aktif_keluhan.columns:
                # Skenario B: Dataset dinamis tanpa kelas (Otomatis beralih ke ID Produk!)
                df_aktif_keluhan["clothing_id"] = df_aktif_keluhan["clothing_id"].astype(str)
                sumbu_x_keluhan = "clothing_id"
                sumbu_y_keluhan = "negative_reviews" if "negative_reviews" in df_keluhan.columns else "Negative Reviews"
                label_x_keluhan = "ID Produk"
                title_keluhan = "Top 10 ID Produk dengan Ulasan Negatif Terbanyak"
            else:
                # Skenario C: Fallback darurat ke kolom pertama
                sumbu_x_keluhan = df_keluhan.columns[0]
                sumbu_y_keluhan = df_keluhan.columns[2] if len(df_keluhan.columns) > 2 else df_keluhan.columns[-1]
                label_x_keluhan = "Item Produk"
                title_keluhan = "Analisis Titik Masalah Produk"

            # Tampilkan teks label di atas batang secara aman
            t_col = "negative_reviews" if "negative_reviews" in df_keluhan.columns else "Negative Reviews"

            fig_keluhan = px.bar(df_keluhan, 
                                 x=sumbu_x_keluhan, 
                                 y=sumbu_y_keluhan, 
                                 text=t_col if t_col in df_keluhan.columns else None, 
                                 color=sumbu_y_keluhan,
                                 labels={sumbu_y_keluhan: "Tingkat Keluhan", sumbu_x_keluhan: label_x_keluhan},
                                 title=title_keluhan,
                                 color_continuous_scale=px.colors.sequential.OrRd)
            fig_keluhan.update_layout(xaxis_categoryorder='total descending')
            st.plotly_chart(fig_keluhan, use_container_width=True)
        else:
            st.info("Tidak ada data keluhan komplain untuk ditampilkan.")

# ==================== MENU 3: PENCARIAN ULASAN DINAMIS ====================
elif menu == "🔍 Pencarian Ulasan Dinamis":
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

    st.subheader("💡 Efektivitas Ulasan Ekstrem Berdasarkan Rating")
    df_efektif = db.run_query(q.QUERY_EFEKTIVITAS_ULASAN)
    if not df_efektif.empty:
        st.dataframe(df_efektif, use_container_width=True)


# ==================== MENU 4: PUSAT KENDALI AI KELOMPOK ====================
elif menu == "🔮 Simulator & Evaluator AI":
    st.title("🔮 Pusat Kendali Kecerdasan Buatan (AI Modules)")
    st.markdown("Halaman ini mengintegrasikan model Machine Learning (NLP) kelompok dan Konsultan AI Generatif Gemini.")
    st.write("---")
    
    # ── SUB-MENU A: ANALISIS DATASET YANG DIUNGGAH (SARMEN 2 - DINAMIS) ──
    st.subheader("📤 1. Analisis Dataset Baru yang Diunggah")
    st.markdown("Setelah mengunggah file dataset di **Sidebar kiri**, hasil analisis sentimen otomatis akan muncul di sini.")

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

        st.markdown("#### 📋 Data Ulasan yang Diunggah")
        preview_cols = [c for c in ["_review_text", "_rating"] if c in df_uploaded.columns]
        rename_preview = {"_review_text": "Teks Ulasan", "_rating": "Rating"}
        st.dataframe(df_uploaded[preview_cols].rename(columns=rename_preview), hide_index=True, use_container_width=True)

        if st.button("🤖 Jalankan Analisis Sentimen", type="primary", key="btn_run_sentiment"):
            with st.spinner("Menganalisis sentimen... Harap tunggu sebentar."):
                df_result = mlp.predict_sentiments(df_uploaded)
                st.session_state["_df_analyzed"] = df_result

        df_analyzed = st.session_state.get("_df_analyzed")
        if df_analyzed is not None and "_predicted_label" in df_analyzed.columns:
            ml_mode = df_analyzed["_ml_mode"].iloc[0]
            ml_acc  = df_analyzed["_ml_accuracy"].iloc[0]
            n_corrected = int(df_analyzed["_is_corrected"].sum())

            if ml_mode == "train_on_the_fly":
                st.success(f"✅ **Mode: Train-On-The-Fly** — Akurasi uji model: **{ml_acc * 100:.2f}%**")
            elif ml_mode == "fallback":
                st.info("ℹ️ **Mode: Fallback** — Menggunakan model sentimen base yang sudah ada.")

            if n_corrected > 0:
                st.caption(f"🔧 {n_corrected:,} prediksi dikoreksi secara otomatis oleh Rule-Based (berdasarkan bintang).")

            valid = df_analyzed[df_analyzed["_predicted_label"].isin(["Positif", "Negatif"])]
            n_pos, n_neg = int((valid["_predicted_label"] == "Positif").sum()), int((valid["_predicted_label"] == "Negatif").sum())
            n_total = n_pos + n_neg

            m1, m2, m3 = st.columns(3)
            with m1: st.metric("✅ Ulasan Positif", f"{n_pos:,}", delta=f"{n_pos/n_total*100:.1f}%" if n_total else None)
            with m2: st.metric("❌ Ulasan Negatif", f"{n_neg:,}", delta=f"-{n_neg/n_total*100:.1f}%" if n_total else None)
            with m3: st.metric("📊 Total Dianalisis", f"{n_total:,}")

            if n_total > 0:
                st.write("---")
                st.markdown("#### 📊 Visualisasi Analisis Detil")
                
                col_chart1, col_chart2, col_chart3 = st.columns([1.1, 1.2, 1.2])
                
                with col_chart1:
                    st.markdown("<p style='text-align: center; font-weight: bold;'>Distribusi Sentimen</p>", unsafe_allow_html=True)
                    sentiment_counts = valid["_predicted_label"].value_counts().reset_index()
                    sentiment_counts.columns = ["Sentimen", "Jumlah"]
                    fig_sent = px.pie(sentiment_counts, names="Sentimen", values="Jumlah", color="Sentimen",
                                      color_discrete_map={"Positif": "#22c55e", "Negatif": "#ef4444"}, hole=0.45)
                    fig_sent.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, showlegend=True,
                                           legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                    st.plotly_chart(fig_sent, use_container_width=True)
                
                # Cari kolom produk secara cerdas
                product_col = None
                potential_product_cols = ["clothing_id", "clothing id", "product_name", "product name", "product_id", "product id", "class_name", "class_name", "class", "item", "nama_produk", "nama produk", "produk", "id_produk", "id produk"]
                for col in df_analyzed.columns:
                    if col.lower().strip() in potential_product_cols:
                        product_col = col
                        break

                with col_chart2:
                    st.markdown("<p style='text-align: center; font-weight: bold; color: #22c55e;'>🌟 Top 5 Produk Terlaku (Positif)</p>", unsafe_allow_html=True)
                    if product_col:
                        df_pos_reviews = df_analyzed[df_analyzed["_predicted_label"] == "Positif"]
                        if not df_pos_reviews.empty:
                            top_5_pos = df_pos_reviews.groupby(product_col).size().reset_index(name="Jumlah")
                            top_5_pos[product_col] = top_5_pos[product_col].astype(str)
                            top_5_pos = top_5_pos.sort_values(by="Jumlah", ascending=True).tail(5)
                            fig_pos = px.bar(top_5_pos, x="Jumlah", y=product_col, orientation="h", text="Jumlah", color_discrete_sequence=["#22c55e"], labels={product_col: "Nama Item"})
                            fig_pos.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, xaxis=dict(showgrid=False))
                            st.plotly_chart(fig_pos, use_container_width=True)
                    else: st.caption("ℹ️ Unggah dataset dengan kolom produk untuk melihat produk populer.")

                with col_chart3:
                    st.markdown("<p style='text-align: center; font-weight: bold; color: #ef4444;'>⚠️ Top 5 Produk Bermasalah (Negatif)</p>", unsafe_allow_html=True)
                    if product_col:
                        df_neg_reviews = df_analyzed[df_analyzed["_predicted_label"] == "Negatif"]
                        if not df_neg_reviews.empty:
                            top_5_neg = df_neg_reviews.groupby(product_col).size().reset_index(name="Jumlah")
                            top_5_neg[product_col] = top_5_neg[product_col].astype(str)
                            top_5_neg = top_5_neg.sort_values(by="Jumlah", ascending=True).tail(5)
                            fig_neg = px.bar(top_5_neg, x="Jumlah", y=product_col, orientation="h", text="Jumlah", color_discrete_sequence=["#ef4444"], labels={product_col: "Nama Item"})
                            fig_neg.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, xaxis=dict(showgrid=False))
                            st.plotly_chart(fig_neg, use_container_width=True)
                    else: st.caption("ℹ️ Unggah dataset dengan kolom produk untuk melihat produk bermasalah.")

            st.write("---")
            st.markdown("### 🔎 Eksplorasi & Saring Hasil Analisis")
            col_uf1, col_uf2, col_uf3 = st.columns(3)
            with col_uf1: keyword_filter = st.text_input("Cari Ulasan (Kata Kunci):", placeholder="Ketik kata kunci...", key="uploaded_keyword_filter")
            with col_uf2:
                rating_options = ["Semua Rating"] + [str(int(r)) for r in sorted(df_analyzed["_rating"].dropna().unique().tolist())] if "_rating" in df_analyzed.columns else ["Semua Rating"]
                selected_rating = st.selectbox("Filter Rating:", options=rating_options, index=0, key="uploaded_rating_filter")
            with col_uf3: selected_sentiment = st.selectbox("Filter Sentimen:", options=["Semua Sentimen", "Positif", "Negatif"], index=0, key="uploaded_sentiment_filter")

            df_filtered = df_analyzed.copy()
            if keyword_filter.strip(): df_filtered = df_filtered[df_filtered["_review_text"].fillna("").str.lower().str.contains(keyword_filter.lower(), na=False)]
            if selected_rating != "Semua Rating": df_filtered = df_filtered[df_filtered["_rating"] == float(selected_rating)]
            if selected_sentiment != "Semua Sentimen": df_filtered = df_filtered[df_filtered["_predicted_label"] == selected_sentiment]

            st.caption(f"📊 Menampilkan **{len(df_filtered):,}** dari **{len(df_analyzed):,}** ulasan.")
            show_cols = [c for c in ["_review_text", "_rating", "_predicted_label", "_is_corrected"] if c in df_filtered.columns]
            rename_map = {"_review_text": "Teks Ulasan", "_rating": "Rating", "_predicted_label": "Sentimen Prediksi", "_is_corrected": "Dikoreksi Rule-Based"}
            st.dataframe(df_filtered[show_cols].rename(columns=rename_map), hide_index=True, use_container_width=True)

            st.markdown("---")
            st.markdown("#### 💾 Ekspor Hasil Analisis")
            csv_data = df_analyzed[show_cols].rename(columns=rename_map).to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download CSV Hasil Analisis", data=csv_data, file_name=f"hasil_analisis_{fname}.csv", mime="text/csv", use_container_width=True)

    st.write("---")
    
    # ── SUB-MENU B: SIMULATOR PREDIKSI SENTIMENT INSTAN (SOFT ENSEMBLE) ──
    st.subheader("🔮 2. Simulator Prediksi Sentimen (Hybrid ML & Rules)")
    st.markdown("Ketik ulasan baru dan masukkan rating untuk menguji model **Soft Weighted Ensemble Model**.")
    
    current_dir = os.path.dirname(__file__)
    model_path = os.path.join(current_dir, "models", "model_sentimen.pkl")
    vectorizer_path = os.path.join(current_dir, "models", "vectorizer.pkl")

    if os.path.exists(model_path) and os.path.exists(vectorizer_path):
        try:
            with open(model_path, "rb") as f: model = pickle.load(f)
            with open(vectorizer_path, "rb") as f: vectorizer = pickle.load(f)
                
            col1, col2 = st.columns([2, 1])
            with col1: user_review = st.text_area("Tulis ulasan produk Anda di sini (Bahasa Inggris):", placeholder="Contoh: The product quality is amazing! Highly recommended.", height=120, key="sim_user_review")
            with col2: rating_choice = st.selectbox("Masukkan Rating Ulasan:", options=["Prediksi ML Murni (Tanpa Rating)", "1 Bintang (Negatif)", "2 Bintang (Negatif)", "3 Bintang (Netral)", "4 Bintang (Positif)", "5 Bintang (Positif)"], index=0, key="sim_rating_choice")
            
            if st.button("Analisis Sentimen Hybrid", type="primary", use_container_width=True, key="btn_run_hybrid"):
                if user_review.strip():
                    cleaned_text = mlp.clean_text(user_review)
                    vectorized_text = vectorizer.transform([cleaned_text])
                    ml_prediction = model.predict(vectorized_text)[0]
                    probability = model.predict_proba(vectorized_text)[0]
                    
                    p_text = float(probability[1])
                    rating_map = {"1 Bintang (Negatif)": 0.10, "2 Bintang (Negatif)": 0.25, "3 Bintang (Netral)": 0.50, "4 Bintang (Positif)": 0.75, "5 Bintang (Positif)": 0.90}
                    
                    if rating_choice in rating_map:
                        p_final = (0.60 * p_text) + (0.40 * rating_map[rating_choice])
                        use_ensemble_note = True
                    else:
                        p_final = p_text
                        use_ensemble_note = False
                        
                    final_sentiment = "Positif" if p_final >= 0.60 else ("Negatif" if p_final <= 0.40 else "Netral")
                    
                    st.markdown("### 📊 Hasil Analisis Sentimen")
                    ml_label = "🟢 POSITIF" if ml_prediction == 1 else "🔴 NEGATIF"
                    st.info(f"🤖 **Prediksi Model ML**: {ml_label} (Tingkat Keyakinan: {(probability[1] if ml_prediction==1 else probability[0])*100:.2f}%)")
                    
                    if final_sentiment == "Positif":
                        st.success(f"🟢 **Sentimen Akhir: POSITIF** (Skor Gabungan: {p_final*100:.2f}%)")
                        if use_ensemble_note: st.caption("ℹ️ *Sentimen Akhir merupakan hasil kombinasi bobot (Ensemble) dari Model ML (60%) and Rating Bintang (40%).*")
                        st.balloons()
                    elif final_sentiment == "Negatif":
                        st.error(f"🔴 **Sentimen Akhir: NEGATIF** (Skor Gabungan: {p_final*100:.2f}%)")
                        if use_ensemble_note: st.caption("ℹ️ *Sentimen Akhir merupakan hasil kombinasi bobot (Ensemble) dari Model ML (60%) and Rating Bintang (40%).*")
                    else:
                        st.warning(f"🟡 **Sentimen Akhir: NETRAL** (Skor Gabungan: {p_final*100:.2f}%)")
                else: st.warning("Silakan masukkan teks ulasan terlebih dahulu.")
        except Exception as e: st.error(f"Terjadi kesalahan saat memproses model: {e}")
    else: st.info("💡 Simulator siap! Menunggu file model pkl.")

    st.write("---")

# ==================== BARIS 7: AI CONSULTANT (RAG + GEMINI + GUARDRAILS) ====================
    st.write("---")
    st.subheader("🤖 3. AI Business Consultant (Powered by Gemini)")
    st.markdown("Ajukan pertanyaan bisnis Anda. AI akan mengekstrak data ulasan via RAG lalu merangkumnya menggunakan Google Gemini.")

    # 🚨 DEKLARASI ULANG VARIABEL YANG HILANG (Penyelamat NameError)
    _has_uploaded = st.session_state.get("_upload_result") is not None and st.session_state["_upload_result"].get("ok")
    _uploaded_fname = st.session_state.get("_last_uploaded_name", "dataset yang diunggah")

    search_method = st.selectbox("🔍 Metode Pencarian:", options=["Pencarian Kata Kunci (TF-IDF)", "Pencarian Semantik (MiniLM)"], index=0, key="rag_search_method")
    
    # Penentuan sumber data berdasarkan status upload user
    if _has_uploaded:
        rag_data_source = st.radio("📁 **Sumber Data untuk AI Consultant:**", options=[f"📂 Dataset yang Diunggah: `{_uploaded_fname}`", "🗄️ Dataset Bawaan (ecommercereviews)"], index=0, horizontal=True, key="rag_source")
    else:
        rag_data_source = "🗄️ Dataset Bawaan (ecommercereviews)"
        st.caption("💡 Untuk menganalisis dataset Anda sendiri, upload terlebih dahulu di panel **📤 Upload Dataset Baru** di sidebar kiri.")

    col_ai1, col_ai2 = st.columns([2, 1])
    with col_ai1: 
        ai_query = st.text_area("💬 Pertanyaan Bisnis Anda:", placeholder="Contoh: Apa keluhan utama pelanggan tentang kualitas bahan pakaian?", height=100, key="rag_query")
    with col_ai2:
        selected_model_label = st.selectbox("🧠 Pilih Model Gemini:", options=list(aic.GEMINI_MODELS.keys()), index=0, key="rag_model")
        selected_model_id = aic.GEMINI_MODELS.get(selected_model_label, "gemini-3.1-flash-lite")
        sentiment_filter = st.selectbox("📊 Filter Ulasan:", options=["Semua Ulasan", "Hanya Negatif (Rating ≤ 2)", "Hanya Positif (Rating ≥ 4)"], index=0, key="rag_filter")

    st.caption(f"🔧 Model aktif: `{selected_model_id}` | Menganalisis hingga **{aic.RAG_TOP_K} ulasan** paling relevan.")

    if st.button("✨ Generate Insight", type="primary", use_container_width=True, key="btn_gemini_run"):
        if not ai_query.strip(): 
            st.warning("⚠️ Silakan tulis pertanyaan bisnis Anda terlebih dahulu.")
        else:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
            if not api_key: 
                st.error("❌ API Key Gemini tidak ditemukan di secrets.toml.")
            else:
                # Pilih dataframe target berdasarkan radio button secara aman
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
                        search_method=search_method, 
                        dataset_name=dataset_name
                    )

                # ── Cek Guardrail Lapis Pertama (Pre-flight Guardrail) ──
                if result.get("blocked"):
                    st.markdown("---")
                    st.error(result["block_reason"])
                    st.info("💡 **Tip**: AI Consultant ini dirancang khusus untuk menganalisis ulasan e-commerce.")
                else:
                    report = result["report"]
                    retrieved_count = result["retrieved_count"]
                    guard = result["guard_result"]
                    
                    st.markdown("---")
                    st.caption(f"🗂️ Sumber data RAG: **{result.get('dataset_name', '')}** | Metode: **{result.get('search_method', 'TF-IDF')}**")
                    
                    b_c1, b_c2, b_c3 = st.columns(3)
                    with b_c1: st.metric("📄 Ulasan Dianalisis (RAG)", f"{retrieved_count} ulasan")
                    with b_c2: st.metric("🛡️ Grounding Score", f"{guard['score'] * 100:.1f}%")
                    with b_c3:
                        if guard["grounded"]: st.success("✅ **Grounded in Data**")
                        else: st.warning("⚠️ **Jawaban Umum / Kurang Data**")

                    if not guard["grounded"] and guard["warning"]: 
                        st.warning(guard["warning"])
                        
                    st.markdown("### 📋 Laporan AI Business Insight")
                    st.markdown(report)