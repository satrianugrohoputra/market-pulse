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

# Memulai preloading model sentence-transformer di background thread agar UI responsif
aic.start_model_preloading()

# 1. Konfigurasi Halaman Dashboard (Wide Mode & Tema Dasar)
st.set_page_config(page_title="Market-Pulse Dashboard", layout="wide", page_icon="📊")

# ==================== SIDEBAR NAVIGASI & LOGO ====================
with st.sidebar:
    st.title("📊 Market-Pulse")
    st.markdown("Pusat Kendali Analisis E-commerce")
    st.write("---")
    
    menu = st.radio(
        "Pilih Halaman:",
        options=[
            "📈 Ringkasan Analisis",
            "⚠️ Analisis Komplain & Pasar",
            "🔍 Pencarian Ulasan Dinamis",
            "🔮 Simulator & Evaluator AI"
        ],
        index=0
    )
    
    st.write("---")
    
    _upload_result = st.session_state.get("_upload_result")
    
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


# ==================== MENU 1: DASHBOARD UMUM (RINGKASAN ANALYTICS) ====================
if menu == "📈 Ringkasan Analisis":
    # ── 🛠️ DETEKTOR SUMBER DATA DINAMIS ──
    _upload_result = st.session_state.get("_upload_result")
    is_user_data = _upload_result is not None and _upload_result["ok"]
    
    if is_user_data:
        # JALUR A: Jika user mengunggah dataset baru
        df_aktif_h1 = _upload_result["df"]
        total_all_reviews = len(df_aktif_h1)
        sumber_data_label = "📂 Dataset Anda"
    else:
        # JALUR B: Jika kosong, ambil dari database PostgreSQL bawaan toko
        df_total = db.run_query("SELECT COUNT(*) as total FROM reviews;")
        total_all_reviews = df_total["total"][0] if not df_total.empty else 0
        sumber_data_label = "🗄️ Database Default"
        # 💡 KUNCI PENYELAMAT: Amankan df_aktif_h1 agar variabelnya TETAP ADA dan tidak melempar NameError
        df_aktif_h1 = db.run_query(q.QUERY_PRODUK_POPULER) 

    # ==================== BARIS 1: METRIC CARDS ====================
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric(label="📈 Total Volume Ulasan", value=f"{total_all_reviews:,} Data")
    with col_m2:
        # Menghitung target kepuasan secara dinamis jika ada kolom rating
        if is_user_data and "_rating" in df_aktif_h1.columns:
            avg_rating_user = df_aktif_h1["_rating"].mean()
            st.metric(label="⭐ Rata-rata Rating Dataset", value=f"{avg_rating_user:.2f} / 5.00")
        else:
            st.metric(label="⭐ Target Kepuasan Produk", value="4.20 / 5.00")
    with col_m3:
        st.metric(label="🚀 Sumber Data Utama", value=sumber_data_label)

    st.write("---")

    # ==================== BARIS 2: PRODUK POPULER & LOYALITAS ====================
    col_pop1, col_pop2 = st.columns([2, 1])

    with col_pop1:
        st.subheader("🔥 Top 10 Produk Populer (Paling Banyak Diminati)")
        
        if is_user_data:
            df_populer = df_aktif_h1.copy()
        else:
            df_populer = db.run_query(q.QUERY_PRODUK_POPULER)

        if not df_populer.empty:
            # 🔍 STRATEGI PRIORITAS SUMBU X (Nama Produk > ID Produk)
            sumbu_x = None
            label_x = "ID Produk"

            for col in df_populer.columns:
                if "name" in str(col).lower() or "nama" in str(col).lower():
                    sumbu_x = col
                    label_x = "Nama Produk"
                    break
            
            if not sumbu_x:
                for col in df_populer.columns:
                    if "id" in str(col).lower() or "clothing" in str(col).lower() or "prod" in str(col).lower():
                        sumbu_x = col
                        label_x = "ID Produk"
                        break

            if not sumbu_x:
                sumbu_x = df_populer.columns[0]
                label_x = "Produk"
            
            df_populer[sumbu_x] = df_populer[sumbu_x].astype(str)

            sumbu_y = None
            label_y = "Volume Interaksi"

            for col in df_populer.columns:
                if any(k in str(col).lower() for k in ["reviews", "positive_feedback", "positive"]):
                    sumbu_y = col
                    label_y = "Jumlah Terjual"
                    break
            
            if not sumbu_y:
                for col in df_populer.columns:
                    if any(k in str(col).lower() for k in ["reviews", "review_count", "ulasan", "count"]):
                        sumbu_y = col
                        label_y = "Jumlah Terjual"
                        break

            # Pilihan terakhir jika semua buntu
            if not sumbu_y:
                sumbu_y = df_populer.columns[1] if len(df_populer.columns) > 1 else df_populer.columns[-1]

            # 🔍 DETEKSI SKALA WARNA (Rating / Harga)
            skala_warna = None
            for col in df_populer.columns:
                if any(k in str(col).lower() for k in ["rating", "avg", "score"]):
                    skala_warna = col
                    break
            if not skala_warna:
                skala_warna = sumbu_y

            # 🚀 PROSES AGREGASI AGAR GRAFIK TIDAK DUPLIKAT (On-The-Fly Pandas)
            if is_user_data:
                # Ambil tipe agregasi yang aman berdasarkan nama kolom
                agg_dict = {sumbu_y: "sum"}
                if skala_warna in df_populer.columns and skala_warna != sumbu_y:
                    agg_dict[skala_warna] = "mean"
                
                df_chart_pop = df_populer.groupby(sumbu_x).agg(agg_dict).reset_index()
                df_chart_pop = df_chart_pop.sort_values(by=sumbu_y, ascending=False).head(10)
            else:
                df_chart_pop = df_populer

            # Gambar grafik batang dengan label dinamis hasil pemikiran Nashwan
            fig_pop = px.bar(df_chart_pop, 
                             x=sumbu_x, 
                             y=sumbu_y, 
                             text=sumbu_y, 
                             color=skala_warna, 
                             labels={sumbu_x: label_x, sumbu_y: label_y},
                             title=f"10 {label_x} Teratas Berdasarkan {label_y}",
                             color_continuous_scale=px.colors.sequential.Viridis)
            
            fig_pop.update_layout(xaxis={'type': 'category', 'categoryorder': 'total descending'})
            st.plotly_chart(fig_pop, use_container_width=True)
        else:
            st.info("Belum ada data ulasan produk populer untuk ditampilkan.")

    with col_pop2:
        st.subheader("🎯 Loyalitas per Departemen")
        
        if is_user_data:
            df_loyal = df_aktif_h1.copy()
        else:
            df_loyal = db.run_query(q.QUERY_LOYALITAS_PELANGGAN)
        
        if not df_loyal.empty:
            # Cari kolom klasifikasi kategori/departemen
            n_col = None
            for col in df_loyal.columns:
                if any(k in str(col).lower() for k in ["department", "departemen", "brand", "category", "kategori", "class"]):
                    n_col = col
                    break
            
            if n_col:
                # Amankan pencarian kolom value secara super fleksibel (mendukung huruf besar, kecil, spasi)
                v_col = None
                for col in df_loyal.columns:
                    if any(k in str(col).lower() for k in ["count", "reviews", "review", "total", "feedback"]):
                        if col != n_col: # Jangan sampai sama dengan kolom nama
                            v_col = col
                            break
                
                if is_user_data:
                    df_chart_loyal = df_loyal.groupby(n_col).size().reset_index(name="Total Reviews")
                    v_col = "Total Reviews"
                else:
                    df_chart_loyal = df_loyal
                    if not v_col:
                        v_col = df_loyal.columns[1] if len(df_loyal.columns) > 1 else df_loyal.columns[-1]

                fig_loyal = px.pie(df_chart_loyal, values=v_col, names=n_col, hole=0.4, title="Distribusi Volume Ulasan")
                fig_loyal.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=350,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_loyal, use_container_width=True)
            else:
                st.info("ℹ️ Data **Kategori Sektoral/Departemen** tidak ditemukan dalam dataset ini.")
        else:
            st.info("Belum ada data departemen.")

# ==================== MENU 2: ANALISIS KOMPLAIN & PASAR ====================
elif menu == "⚠️ Analisis Komplain & Pasar":
    st.title("⚠️ Analisis Komplain & Pasar")
    st.markdown("Identifikasi area masalah dan segmentasi pasar toko Anda.")
    st.write("---")

    _upload_result = st.session_state.get("_upload_result")
    is_user_data = _upload_result is not None and _upload_result["ok"]
    
    if is_user_data:
        df_aktif = _upload_result["df"]
    else:
        df_aktif = db.run_query(q.QUERY_SEGMENTASI_PASAR)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👥 Karakteristik Pasar Berdasarkan Generasi Usia")
        
        if not df_aktif.empty and any(k in "".join(df_aktif.columns).lower() for k in ["age", "usia"]):
            # Skenario jika data default database
            if not is_user_data:
                x_col = "age_group" if "age_group" in df_aktif.columns else "Age Group"
                y_col = "total_purchase" if "total_purchase" in df_aktif.columns else "Total Purchase"
                c_col = "department" if "department" in df_aktif.columns else "Department"
                df_chart_pasar = df_aktif
            else:
                # Skenario hitung on-the-fly dari file upload user
                age_col = [c for c in df_aktif.columns if "age" in c.lower() or "usia" in c.lower()][0]
                dept_col = [c for c in df_aktif.columns if any(k in c.lower() for k in ["dept", "brand", "cat"])][0] if any(any(k in c.lower() for k in ["dept", "brand", "cat"]) for c in df_aktif.columns) else df_aktif.columns[0]
                
                df_aktif['Age Group'] = df_aktif[age_col].apply(lambda age: 'Gen Z' if age < 30 else ('Milenial' if 30 <= age <= 45 else 'Gen X/Boomers'))
                df_chart_pasar = df_aktif.groupby(['Age Group', dept_col]).size().reset_index(name="Total Purchase")
                x_col, y_col, c_col = 'Age Group', 'Total Purchase', dept_col

            fig_pasar = px.bar(df_chart_pasar, x=x_col, y=y_col, color=c_col, barmode="group", 
                               labels={x_col: "Generasi Usia", y_col: "Volume Pembelian", c_col: "Departemen"},
                               title="Volume Pembelian Berdasarkan Generasi Usia")
            st.plotly_chart(fig_pasar, use_container_width=True)
        else:
            st.info("ℹ️ Data **Usia Pelanggan** tidak ditemukan dalam dataset ini untuk menghasilkan analisis karakteristik pasar.")

    with col2:
        st.subheader("⚠️ Titik Masalah: Komplain Produk Terbanyak")
        
        if is_user_data:
            df_keluhan = df_aktif.copy()
        else:
            df_keluhan = db.run_query(q.QUERY_KELUHAN_PRODUK)
    
        if not df_keluhan.empty:
            # 🔍 STRATEGI BUNGLON DASHBOARD: Tentukan Sumbu X secara cerdas
            if "class" in df_keluhan.columns or "Class" in df_keluhan.columns:
                sumbu_x_keluhan = "class" if "class" in df_keluhan.columns else "Class"
                sumbu_y_keluhan = "defect_rate" if "defect_rate" in df_keluhan.columns else "Defect Rate"
                df_chart_keluhan = df_keluhan
                label_x_keluhan = "Kategori Kelas"
                title_keluhan = "Kategori Kelas dengan Komplain Terbanyak"
            else:
                # Skenario adaptif: Cari kolom ID barang atau nama barang
                id_col = [c for c in df_keluhan.columns if any(k in c.lower() for k in ["id", "prod", "item"])][0] if any(any(k in c.lower() for k in ["id", "prod", "item"]) for c in df_keluhan.columns) else df_keluhan.columns[0]
                rat_col = "_rating" if "_rating" in df_keluhan.columns else ([c for c in df_keluhan.columns if "rat" in c.lower()][0] if any("rat" in c.lower() for c in df_keluhan.columns) else df_keluhan.columns[1])
                
                # Hitung ulasan negatif (Rating <= 2) jika offline user data
                if is_user_data:
                    df_neg = df_keluhan[df_keluhan[rat_col] <= 2]
                    df_chart_keluhan = df_neg.groupby(id_col).size().reset_index(name="Negative Reviews").sort_values("Negative Reviews", ascending=False).head(10)
                    sumbu_y_keluhan = "Negative Reviews"
                else:
                    df_chart_keluhan = df_keluhan
                    sumbu_y_keluhan = "negative_reviews" if "negative_reviews" in df_keluhan.columns else df_keluhan.columns[1]

                df_chart_keluhan[id_col] = df_chart_keluhan[id_col].astype(str)
                sumbu_x_keluhan = id_col
                label_x_keluhan = "ID/Nama Produk"
                title_keluhan = "Top 10 Komoditas Produk dengan Keluhan Ulasan Negatif Terbanyak"

            fig_keluhan = px.bar(df_chart_keluhan, x=sumbu_x_keluhan, y=sumbu_y_keluhan, text=sumbu_y_keluhan, color=sumbu_y_keluhan,
                                 labels={sumbu_y_keluhan: "Jumlah Komplain", sumbu_x_keluhan: label_x_keluhan},
                                 title=title_keluhan, color_continuous_scale=px.colors.sequential.OrRd)
            fig_keluhan.update_layout(xaxis_categoryorder='total descending')
            st.plotly_chart(fig_keluhan, use_container_width=True)
        else:
            st.info("Tidak ada data keluhan komplain untuk ditampilkan.")

# ==================== MENU 3: PENCARIAN ULASAN DINAMIS ====================
elif menu == "🔍 Pencarian Ulasan Dinamis":
    st.title("🔍 Mesin Pencari & Penyaring Ulasan Pelanggan")
    st.markdown("Fitur interaktif untuk menyaring curhatan pelanggan berdasarkan kata kunci dan rating secara dinamis.")
    st.write("---")

    # Deteksi status upload data user
    _upload_result = st.session_state.get("_upload_result")
    is_user_data = _upload_result is not None and _upload_result["ok"]

    # ── PANEL INPUT SEBAGAI FILTER UTAMA ──
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        kata_kunci = st.text_input("Ketik Kata Kunci yang Dicari (Contoh: love, perfect, bad, quality, size):", "perfect")
    with col_f2:
        pilihan_rating = st.selectbox("Pilih Rating Ulasan Pelanggan:", [5, 4, 3, 2, 1], index=0)

# ── PROSES PENGAMBILAN DATA (DUAL-SOURCE DINAMIS) ──
    if is_user_data:
        # JALUR A: Cari langsung di memori Dataframe hasil upload user (Versi Fixed Kolom Description)
        df_mentah_h3 = _upload_result["df"].copy()
        
        # 🔍 DETEKSI KOLOM TEKS ULTRA-CERDAS (Mendukung 'Description' milik Adidas/Nike)
        user_txt_col = None
        for col in df_mentah_h3.columns:
            if any(k in str(col).lower() for k in ["review", "text", "ulasan", "desc", "content", "comment"]):
                user_txt_col = col
                break
        if not user_txt_col:
            user_txt_col = df_mentah_h3.columns[0] # Fallback darurat ke kolom pertama jika buntu

        # 🔍 DETEKSI KOLOM RATING ULTRA-CERDAS
        user_rat_col = None
        for col in df_mentah_h3.columns:
            if any(k in str(col).lower() for k in ["rat", "bintang", "score"]):
                user_rat_col = col
                break
        if not user_rat_col:
            user_rat_col = df_mentah_h3.columns[1]

        # Jalankan filter pencarian teks secara case-insensitive (huruf besar kecil disamakan)
        mask_keyword = df_mentah_h3[user_txt_col].fillna("").str.lower().str.contains(kata_kunci.lower(), na=False)
        mask_rating = df_mentah_h3[user_rat_col] == pilihan_rating
        
        # Ambil maksimal 5 baris teratas saja sesuai reques dari Nashwan!
        df_dinamis = df_mentah_h3[mask_keyword & mask_rating].head(5)
        
        # Bersihkan kolom-kolom internal sistem agar tidak merusak PyArrow
        for internal_col in ["_review_text", "_rating", "_cleaned_text", "_predicted_label", "_predicted_ind", "_is_corrected"]:
            if internal_col in df_dinamis.columns:
                df_dinamis = df_dinamis.drop(columns=[internal_col])
    else:
        # JALUR B: Fallback ke Database Default SQL jika user belum upload apa pun
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
        LIMIT 5; -- Kita ganti LIMIT jadi 5 juga biar adil dengan versi upload!
        """
        df_dinamis = db.run_query(QUERY_DINAMIS)

    # ── TAMPILKAN HASILNYA KE LAYAR ──
    st.markdown(f"#### 📋 Hasil Penyaringan 5 Ulasan Teratas (Rating {pilihan_rating})")
    if not df_dinamis.empty:
        st.dataframe(df_dinamis, use_container_width=True, hide_index=True)
    else:
        # 💡 PESAN INFO SESUAI NIAT SAKTI NASHWAN
        st.info(f"ℹ️ Tidak ada ulasan yang mengandung kata kunci '{kata_kunci}' pada Rating {pilihan_rating} di dataset ini.")

    st.write("---")

    # ── BAGIAN SUB-TABEL BAWAH: EFEKTIVITAS ULASAN (HANYA UNTUK DATASET DEFAULT/SINKRON) ──
    st.subheader("💡 Efektivitas Ulasan Ekstrem Berdasarkan Kategori")
    
    if is_user_data:
        # Jika dataset luar, hitung statistik sederhana dari data user agar halaman bawah tidak kosong hantu
        df_user_full = _upload_result["df"]
        user_txt_col = "_review_text" if "_review_text" in df_user_full.columns else [c for c in df_user_full.columns if "review" in c.lower() or "text" in c.lower()][0]
        user_rat_col = "_rating" if "_rating" in df_user_full.columns else [c for c in df_user_full.columns if "rat" in c.lower()][0]
        
        # Hitung ringkasan performa dataset user on-the-fly
        st.caption("Analisis statistik performa kepuasan kata kunci bermasalah pada dataset Anda:")
        df_efektif_user = df_user_full.groupby(user_rat_col).size().reset_index(name="Jumlah Ulasan")
        st.dataframe(df_efektif_user.rename(columns={user_rat_col: "Rating Bintang"}), use_container_width=True, hide_index=True)
    else:
        # Jika default, panggil query bawaan asli milik kelompok
        df_efektif = db.run_query(q.QUERY_EFEKTIVITAS_ULASAN)
        if not df_efektif.empty:
            st.dataframe(df_efektif, use_container_width=True, hide_index=True)

elif menu == "🔮 Simulator & Evaluator AI":
    st.title("🔮 Pusat Kendali Kecerdasan Buatan (AI Modules)")
    st.markdown("Halaman ini mengintegrasikan model Machine Learning (NLP) kelompok dan Konsultan AI Generatif Gemini.")
    st.write("---")

    # Ambil API Key dari secrets
    api_key = st.secrets.get("GEMINI_API_KEY")

    # ── SUB-MENU A: ANALISIS DATASET BARU YANG DIUNGGAH (BATCH PREDICTION) ──
    st.subheader("📤 1. Analisis Dataset Baru yang Diunggah")
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

        # Tampilkan tabel data ulasan yang diunggah secara langsung (scrollable)
        st.markdown("#### 📋 Data Ulasan yang Diunggah")
        preview_cols = [c for c in ["_review_text", "_rating"] if c in df_uploaded.columns]
        rename_preview = {"_review_text": "Teks Ulasan", "_rating": "Rating"}
        st.dataframe(
            df_uploaded[preview_cols].rename(columns=rename_preview),
            hide_index=True,
            use_container_width=True
        )

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

            # ─── ADAPTIVE VISUALIZATION: Smart Schema Detector ────────────────────
            if n_total > 0:
                # ── Detektor Skema Semantik: Temukan kolom yang relevan secara ketat ──
                
                # Kata kunci POSITIF untuk kolom produk
                _PRODUCT_KEYWORDS = [
                    "product_name", "product name", "productname",
                    "product_id", "product id", "product",
                    "clothing_id", "clothing id",
                    "item_name", "item name", "item",
                    "brand", "category", "kategori",
                    "nama_produk", "nama produk", "produk",
                    "class_name", "class name", "class",
                    "article", "sku", "model",
                ]
                # Kata kunci BLACKLIST — kolom ini jangan pernah dianggap produk
                _PRODUCT_BLACKLIST = [
                    "user", "username", "author", "reviewer", "penulis",
                    "nama_user", "nama user", "nama_pelanggan",
                    "date", "tanggal", "time", "timestamp", "created", "visited",
                    "rating", "review", "ulasan", "text", "comment", "komentar",
                    "description", "desc", "feedback", "content",
                    "_review_text", "_rating", "_predicted_label",
                    "_predicted_ind", "_is_corrected", "_cleaned_text", "_ml_accuracy",
                ]
                # Kata kunci untuk kolom tanggal
                _DATE_KEYWORDS = ["date", "tanggal", "time", "timestamp", "created_at", "visited"]

                product_col = None
                date_col = None
                category_col = None

                # Cari kolom produk dengan seleksi KETAT
                for col in df_analyzed.columns:
                    col_clean = col.lower().strip()
                    # Lewati kolom blacklist
                    if any(bl in col_clean for bl in _PRODUCT_BLACKLIST):
                        continue
                    # Cek pencocokan kata kunci produk
                    if col_clean in _PRODUCT_KEYWORDS or any(pk in col_clean for pk in _PRODUCT_KEYWORDS):
                        product_col = col
                        break

                # Cari kolom kategori/brand sebagai fallback product_col
                if not product_col:
                    for col in df_analyzed.columns:
                        col_clean = col.lower().strip()
                        if any(bl in col_clean for bl in _PRODUCT_BLACKLIST):
                            continue
                        if any(k in col_clean for k in ["brand", "merek", "category", "kategori", "dept", "department"]):
                            category_col = col
                            break

                # Tentukan kolom terbaik untuk grafik (produk > kategori > None)
                chart_item_col = product_col or category_col

                # Cari kolom tanggal
                for col in df_analyzed.columns:
                    col_clean = col.lower().strip()
                    if any(dk in col_clean for dk in _DATE_KEYWORDS):
                        date_col = col
                        break

                st.write("---")
                st.markdown("#### 📊 Visualisasi Analisis Detil")

                col_chart1, col_chart2, col_chart3 = st.columns([1.1, 1.2, 1.2])

                # ── SLOT 1: Donut Chart Distribusi Sentimen (selalu tampil) ──────────
                with col_chart1:
                    st.markdown("<p style='text-align: center; font-weight: bold;'>Distribusi Sentimen</p>", unsafe_allow_html=True)
                    sentiment_counts = valid["_predicted_label"].value_counts().reset_index()
                    sentiment_counts.columns = ["Sentimen", "Jumlah"]
                    fig_sent = px.pie(
                        sentiment_counts,
                        names="Sentimen",
                        values="Jumlah",
                        color="Sentimen",
                        color_discrete_map={"Positif": "#22c55e", "Negatif": "#ef4444"},
                        hole=0.45
                    )
                    fig_sent.update_layout(
                        margin=dict(l=10, r=10, t=10, b=10),
                        height=280,
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig_sent, use_container_width=True)

                # ── SLOT 2 & 3: Adaptif berdasarkan ketersediaan kolom ────────────────
                if chart_item_col:
                    # ─ SKENARIO A: Kolom produk/kategori ditemukan ─────────────────────
                    label_item = "Kategori/Brand" if chart_item_col == category_col else "Nama Produk"

                    with col_chart2:
                        st.markdown("<p style='text-align: center; font-weight: bold; color: #22c55e;'>🌟 Top 5 Produk Terlaku (Positif)</p>", unsafe_allow_html=True)
                        df_pos_reviews = df_analyzed[df_analyzed["_predicted_label"] == "Positif"]
                        if not df_pos_reviews.empty:
                            top_5_pos = df_pos_reviews.groupby(chart_item_col).size().reset_index(name="Jumlah")
                            top_5_pos[chart_item_col] = top_5_pos[chart_item_col].astype(str).str[:35]
                            top_5_pos = top_5_pos.sort_values(by="Jumlah", ascending=True).tail(5)
                            fig_pos = px.bar(
                                top_5_pos, x="Jumlah", y=chart_item_col,
                                orientation="h", text="Jumlah",
                                color_discrete_sequence=["#22c55e"],
                                labels={chart_item_col: label_item, "Jumlah": "Ulasan"}
                            )
                            fig_pos.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, xaxis=dict(showgrid=False), yaxis=dict(categoryorder="total ascending"))
                            st.plotly_chart(fig_pos, use_container_width=True)
                        else:
                            st.info("Tidak ada ulasan positif.")

                    with col_chart3:
                        st.markdown("<p style='text-align: center; font-weight: bold; color: #ef4444;'>⚠️ Top 5 Produk Bermasalah (Negatif)</p>", unsafe_allow_html=True)
                        df_neg_reviews = df_analyzed[df_analyzed["_predicted_label"] == "Negatif"]
                        if not df_neg_reviews.empty:
                            top_5_neg = df_neg_reviews.groupby(chart_item_col).size().reset_index(name="Jumlah")
                            top_5_neg[chart_item_col] = top_5_neg[chart_item_col].astype(str).str[:35]
                            top_5_neg = top_5_neg.sort_values(by="Jumlah", ascending=True).tail(5)
                            fig_neg = px.bar(
                                top_5_neg, x="Jumlah", y=chart_item_col,
                                orientation="h", text="Jumlah",
                                color_discrete_sequence=["#ef4444"],
                                labels={chart_item_col: label_item, "Jumlah": "Ulasan"}
                            )
                            fig_neg.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, xaxis=dict(showgrid=False), yaxis=dict(categoryorder="total ascending"))
                            st.plotly_chart(fig_neg, use_container_width=True)
                        else:
                            st.info("Tidak ada ulasan negatif.")

                else:
                    # ─ SKENARIO B: Tidak ada kolom produk → Keyword Frequency Fallback ──
                    import collections

                    def _get_top_words(df_subset, text_col_name="_cleaned_text", fallback_col="_review_text", top_n=5):
                        """Hitung kata paling sering muncul dari ulasan, pakai cleaned_text atau review_text."""
                        src_col = text_col_name if text_col_name in df_subset.columns else fallback_col
                        all_words = []
                        for txt in df_subset[src_col].dropna().astype(str):
                            words = [w for w in txt.lower().split() if len(w) > 3]
                            all_words.extend(words)
                        counter = collections.Counter(all_words)
                        return counter.most_common(top_n)

                    # Tampilkan peringatan kontekstual yang informatif
                    with col_chart2:
                        st.markdown("<p style='text-align: center; font-weight: bold; color: #22c55e;'>💬 Top 5 Kata Kunci (Ulasan Positif)</p>", unsafe_allow_html=True)
                        df_pos = df_analyzed[df_analyzed["_predicted_label"] == "Positif"]
                        if not df_pos.empty:
                            top_words_pos = _get_top_words(df_pos)
                            if top_words_pos:
                                df_kw_pos = pd.DataFrame(top_words_pos, columns=["Kata", "Frekuensi"]).sort_values("Frekuensi", ascending=True)
                                fig_kw_pos = px.bar(
                                    df_kw_pos, x="Frekuensi", y="Kata",
                                    orientation="h", text="Frekuensi",
                                    color_discrete_sequence=["#22c55e"],
                                    labels={"Kata": "Kata Kunci", "Frekuensi": "Kemunculan"}
                                )
                                fig_kw_pos.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, xaxis=dict(showgrid=False), yaxis=dict(categoryorder="total ascending"))
                                st.plotly_chart(fig_kw_pos, use_container_width=True)
                            else:
                                st.info("Tidak ada kata kunci yang dapat diekstrak.")
                        else:
                            st.info("Tidak ada ulasan positif.")

                    with col_chart3:
                        st.markdown("<p style='text-align: center; font-weight: bold; color: #ef4444;'>⚠️ Top 5 Kata Keluhan (Ulasan Negatif)</p>", unsafe_allow_html=True)
                        df_neg = df_analyzed[df_analyzed["_predicted_label"] == "Negatif"]
                        if not df_neg.empty:
                            top_words_neg = _get_top_words(df_neg)
                            if top_words_neg:
                                df_kw_neg = pd.DataFrame(top_words_neg, columns=["Kata", "Frekuensi"]).sort_values("Frekuensi", ascending=True)
                                fig_kw_neg = px.bar(
                                    df_kw_neg, x="Frekuensi", y="Kata",
                                    orientation="h", text="Frekuensi",
                                    color_discrete_sequence=["#ef4444"],
                                    labels={"Kata": "Kata Kunci", "Frekuensi": "Kemunculan"}
                                )
                                fig_kw_neg.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280, xaxis=dict(showgrid=False), yaxis=dict(categoryorder="total ascending"))
                                st.plotly_chart(fig_kw_neg, use_container_width=True)
                            else:
                                st.info("Tidak ada kata kunci yang dapat diekstrak.")
                        else:
                            st.info("Tidak ada ulasan negatif.")

                    # Tampilkan info banner menjelaskan mengapa chart produk tidak ada
                    st.info(
                        "ℹ️ **Kolom Produk/Brand Tidak Terdeteksi** — "
                        "Dataset Anda tidak memiliki kolom nama produk/kategori yang dikenali sistem "
                        "(seperti `product_name`, `brand`, `category`). "
                        "Visualisasi di atas menampilkan **frekuensi kata kunci** dari ulasan sebagai gantinya."
                    )

                # ─ SKENARIO C: Tren Sentimen berdasarkan Waktu (jika kolom tanggal ada) ─
                if date_col:
                    try:
                        df_trend = df_analyzed.copy()
                        df_trend["_date_parsed"] = pd.to_datetime(df_trend[date_col], errors="coerce")
                        df_trend = df_trend.dropna(subset=["_date_parsed"])
                        df_trend["_month"] = df_trend["_date_parsed"].dt.to_period("M").astype(str)

                        df_trend_grp = (
                            df_trend[df_trend["_predicted_label"].isin(["Positif", "Negatif"])]
                            .groupby(["_month", "_predicted_label"])
                            .size()
                            .reset_index(name="Jumlah")
                        )

                        if not df_trend_grp.empty and df_trend_grp["_month"].nunique() > 1:
                            st.markdown("---")
                            st.markdown("#### 📈 Tren Sentimen dari Waktu ke Waktu")
                            fig_trend = px.line(
                                df_trend_grp,
                                x="_month", y="Jumlah", color="_predicted_label",
                                color_discrete_map={"Positif": "#22c55e", "Negatif": "#ef4444"},
                                markers=True,
                                labels={"_month": "Bulan", "Jumlah": "Jumlah Ulasan", "_predicted_label": "Sentimen"},
                                title="Volume Ulasan Positif vs Negatif per Bulan"
                            )
                            fig_trend.update_layout(height=320, xaxis_tickangle=-30)
                            st.plotly_chart(fig_trend, use_container_width=True)
                    except Exception:
                        pass  # Abaikan jika kolom tanggal tidak bisa di-parse


            # ── Penyaring Interaktif Hasil Analisis ───────────────────────────────────
            st.write("---")
            st.markdown("### 🔎 Eksplorasi & Saring Hasil Analisis")
            st.markdown("Gunakan filter di bawah untuk menelusuri hasil analisis sentimen ulasan yang Anda unggah secara interaktif.")

            col_uf1, col_uf2, col_uf3 = st.columns(3)
            with col_uf1:
                keyword_filter = st.text_input(
                    "Cari Ulasan (Kata Kunci):",
                    placeholder="Ketik kata kunci untuk mencari...",
                    key="uploaded_keyword_filter"
                )
            with col_uf2:
                rating_options = ["Semua Rating", "1", "2", "3", "4", "5"]
                selected_rating = st.selectbox(
                    "Filter Rating:",
                    options=rating_options,
                    index=0,
                    key="uploaded_rating_filter"
                )
            with col_uf3:
                selected_sentiment = st.selectbox(
                    "Filter Sentimen:",
                    options=["Semua Sentimen", "Positif", "Negatif"],
                    index=0,
                    key="uploaded_sentiment_filter"
                )

            # Proses filtering dataframe secara dinamis
            df_filtered = df_analyzed.copy()

            # 1. Filter Kata Kunci
            if keyword_filter.strip() != "":
                df_filtered = df_filtered[
                    df_filtered["_review_text"].fillna("").str.lower().str.contains(keyword_filter.lower(), na=False)
                ]

            # 2. Filter Rating
            if selected_rating != "Semua Rating":
                val_rating = float(selected_rating)
                df_filtered = df_filtered[df_filtered["_rating"] == val_rating]

            # 3. Filter Sentimen
            if selected_sentiment != "Semua Sentimen":
                df_filtered = df_filtered[df_filtered["_predicted_label"] == selected_sentiment]

            # Tampilkan statistik jumlah baris tercocok
            total_matched = len(df_filtered)
            st.caption(f"📊 Menampilkan **{total_matched:,}** dari **{len(df_analyzed):,}** ulasan hasil filter.")

            # Tampilkan dataframe interaktif (scrollable & lebar penuh)
            show_cols = ["_review_text", "_rating", "_predicted_label"]
            show_cols = [c for c in show_cols if c in df_filtered.columns]
            rename_map = {
                "_review_text": "Teks Ulasan",
                "_rating": "Rating",
                "_predicted_label": "Sentimen Prediksi"
            }

            st.dataframe(
                df_filtered[show_cols].rename(columns=rename_map),
                hide_index=True,
                use_container_width=True
            )

            # ── Opsi Ekspor Hasil (Ekspor CSV) ──────────────────
            st.markdown("---")
            st.markdown("#### 💾 Ekspor Hasil Analisis")
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

    st.write("---")

    # ── SUB-MENU B: SIMULATOR PREDIKSI SENTIMENT INSTAN (ML X NLP) ──
    st.subheader("🔮 2. Simulator Prediksi Sentimen (Hybrid ML & Rules)")
    st.markdown("Ketik ulasan baru dan masukkan rating untuk menguji model **Machine Learning** yang digabungkan dengan **Rule-based Override** sesuai blueprint proyek.")

    import os
    import pickle
    import re
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    # Fungsi preprocessing
    def preprocess_input(text):
        if not isinstance(text, str):
            return ""
        text = text.lower()
        text = re.sub(r'[^a-z\s]', '', text)
        words = text.split()
        words = [w for w in words if w not in ENGLISH_STOP_WORDS]
        return " ".join(words)

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
                    height=120,
                    key="sim_user_review"
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
                    index=0,
                    key="sim_rating_choice"
                )
            
            if st.button("Analisis Sentimen Hybrid", type="primary", use_container_width=True, key="btn_run_sim"):
                if user_review.strip() != "":
                    cleaned_text = mlp.clean_text(user_review)
                    vectorized_text = vectorizer.transform([cleaned_text])
                    ml_prediction = model.predict(vectorized_text)[0] # 0 = Negatif, 1 = Positif
                    probability = model.predict_proba(vectorized_text)[0] # [prob_neg, prob_pos]
                    
                    p_text = float(probability[1])
                    
                    rating_map = {
                        "1 Bintang (Negatif)": 0.10,
                        "2 Bintang (Negatif)": 0.25,
                        "3 Bintang (Netral)": 0.50,
                        "4 Bintang (Positif)": 0.75,
                        "5 Bintang (Positif)": 0.90
                    }
                    
                    if rating_choice in rating_map:
                        p_rating = rating_map[rating_choice]
                        w_text = 0.60
                        w_rating = 0.40
                        p_final = (w_text * p_text) + (w_rating * p_rating)
                        use_ensemble_note = True
                    else:
                        p_final = p_text
                        use_ensemble_note = False
                    
                    if p_final >= 0.60:
                        final_sentiment = "Positif"
                    elif p_final <= 0.40:
                        final_sentiment = "Negatif"
                    else:
                        final_sentiment = "Netral"
                    
                    st.markdown("### 📊 Hasil Analisis Sentimen")
                    
                    ml_label = "🟢 POSITIF" if ml_prediction == 1 else "🔴 NEGATIF"
                    ml_conf = probability[1] if ml_prediction == 1 else probability[0]
                    st.info(f"🤖 **Prediksi Model ML**: {ml_label} (Tingkat Keyakinan: {ml_conf*100:.2f}%)")
                    
                    if final_sentiment == "Positif":
                        st.success(f"🟢 **Sentimen Akhir: POSITIF** (Skor Gabungan: {p_final*100:.2f}%)")
                        if use_ensemble_note:
                            st.caption("ℹ️ *Catatan: Sentimen Akhir merupakan hasil kombinasi bobot (Ensemble) dari Model ML (60%) dan Rating Bintang (40%).*")
                        st.balloons()
                    elif final_sentiment == "Negatif":
                        st.error(f"🔴 **Sentimen Akhir: NEGATIF** (Skor Gabungan: {p_final*100:.2f}%)")
                        if use_ensemble_note:
                            st.caption("ℹ️ *Catatan: Sentimen Akhir merupakan hasil kombinasi bobot (Ensemble) dari Model ML (60%) dan Rating Bintang (40%).*")
                    else:
                        st.warning(f"🟡 **Sentimen Akhir: NETRAL** (Skor Gabungan: {p_final*100:.2f}%)")
                        if use_ensemble_note:
                            st.caption("ℹ️ *Catatan: Sentimen Akhir merupakan hasil kombinasi bobot (Ensemble) dari Model ML (60%) dan Rating Bintang (40%).*")
                else:
                    st.warning("Silakan masukkan teks ulasan terlebih dahulu.")
        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses model: {e}")
    else:
        st.info("💡 **Status**: Simulator siap! Menunggu file `model_sentimen.pkl` dan `vectorizer.pkl` diletakkan di folder proyek oleh tim Machine Learning.")

    st.write("---")

    # ── SUB-MENU C: AI BUSINESS CONSULTANT (RAG + GEMINI + HALLUCINATION GUARD) ──
    st.subheader("🤖 3. AI Business Consultant (Powered by Gemini)")
    st.markdown(
        "Ajukan pertanyaan bisnis Anda dalam bahasa alami. "
        "AI akan mencari ulasan yang paling relevan dari dataset (**RAG**), "
        "lalu merangkum temuan menggunakan **Google Gemini**, "
        "dilengkapi **Hallucination Guard** untuk memverifikasi keakuratan jawaban."
    )

    # ── Pemilihan Sumber Data RAG ────────────────────────────────────────────────
    _has_uploaded = st.session_state.get("_upload_result") is not None and st.session_state["_upload_result"].get("ok")
    _uploaded_fname = st.session_state.get("_last_uploaded_name", "dataset yang diunggah")

    search_method = st.selectbox("🔍 Metode Pencarian:", options=["Pencarian Kata Kunci (TF-IDF)", "Pencarian Semantik (MiniLM)"], index=0, key="rag_search_method")
    
    # Penentuan sumber data berdasarkan status upload user
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
        selected_model_label = st.selectbox(
            "🧠 Pilih Model Gemini:",
            options=list(aic.GEMINI_MODELS.keys()),
            index=0,
            key="rag_model"
        )
        selected_model_id = aic.GEMINI_MODELS.get(selected_model_label, "gemini-3.1-flash-lite")
        
        sentiment_filter = st.selectbox(
            "📊 Filter Ulasan:",
            options=["Semua Ulasan", "Hanya Negatif (Rating ≤ 2)", "Hanya Positif (Rating ≥ 4)"],
            index=0,
            key="rag_filter"
        )
        
        search_method = st.selectbox(
            "🔍 Metode Pencarian:",
            options=["Pencarian Kata Kunci (TF-IDF)", "Pencarian Semantik (MiniLM)"],
            index=0,
            help=(
                "• **Pencarian Kata Kunci (TF-IDF)**: Mencari kecocokan kata persis. Sangat cepat.\n"
                "• **Pencarian Semantik (MiniLM)**: Mencari berdasarkan kesamaan arti ulasan, mendukung ulasan bilingual (EN/ID)."
            ),
            key="ai_search_method"
        )

    st.caption(f"🔧 Model aktif: `{selected_model_id}` | Akan menganalisis hingga **{aic.RAG_TOP_K} ulasan** paling relevan dari dataset.")

    st.caption(f"🔧 Model aktif: `{selected_model_id}` | Menganalisis hingga **{aic.RAG_TOP_K} ulasan** paling relevan.")

    if st.button("✨ Generate Insight", type="primary", use_container_width=True, key="btn_gemini_run"):
        if not ai_query.strip(): 
            st.warning("⚠️ Silakan tulis pertanyaan bisnis Anda terlebih dahulu.")
        elif not api_key:
            st.error("🔑 API Key tidak ditemukan. Pastikan file `.streamlit/secrets.toml` berisi `GEMINI_API_KEY` yang valid.")
        else:
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
                used_method = result.get("search_method", "TF-IDF")

                st.markdown("---")
                st.caption(f"🗂️ Sumber data RAG: **{used_dataset}** | Metode: **{used_method}**")
                
                b_c1, b_c2, b_c3 = st.columns(3)
                with b_c1: 
                    st.metric("📄 Ulasan Dianalisis (RAG)", f"{retrieved_count} ulasan")
                with b_c2: 
                    st.metric("🛡️ Grounding Score", f"{grounding_score * 100:.1f}%")
                with b_c3:
                    if guard["grounded"]: 
                        st.success("✅ **Grounded in Data**")
                    else: 
                        st.warning("⚠️ **Jawaban Umum / Kurang Data**")

                if not guard["grounded"] and guard["warning"]: 
                    st.warning(guard["warning"])
                    
                st.markdown("### 📋 Laporan AI Business Insight")
                st.markdown(report)