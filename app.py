import streamlit as st
import plotly.express as px
import database as db
import queries as q

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
    st.metric(label="🚀 Status Sistem AI", value="Ready (Modul 7)")

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
    st.dataframe(df_dinamis, use_container_width=True)
else:
    st.info(f"Tidak ada ulasan dengan kata kunci '{kata_kunci}' pada Rating {pilihan_rating}.")

st.write("---")

# ==================== BARIS 5: TABEL DETAIL EFEKTIVITAS ULASAN ====================
st.subheader("💡 Efektivitas Ulasan Ekstrem Berdasarkan Rating")
df_efektif = db.run_query(q.QUERY_EFEKTIVITAS_ULASAN)
st.dataframe(df_efektif, use_container_width=True)