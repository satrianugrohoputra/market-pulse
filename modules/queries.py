# 1. Loyalitas Pelanggan Berdasarkan Departemen (Recommended Rate)
QUERY_LOYALITAS_PELANGGAN = """
SELECT 
    r.division_name as "Division",
    r.department_name as "Department", 
    r.class_name as "Class", 
    count(*) as "Total Reviews",
    round(AVG(r.recommended_ind) * 100, 2) as "Recommendation Percentage",
    round(AVG(r.rating), 2) as "Average Rating"
FROM reviews r 
WHERE r.department_name IS NOT NULL
GROUP BY r.division_name, r.department_name, r.class_name
ORDER BY "Total Reviews" DESC;
"""

# 2. Analisis Keluhan pada Produk dengan Rating Rendah
QUERY_KELUHAN_PRODUK = """
SELECT 
    r.division_name as "Division",
    r.department_name as "Department",
    r.class_name as "Class",
    count(case when r.rating <= 2 then 1 END) as "Negative Reviews",
    count(*) as "Total Reviews",
    round((count(case when r.rating <= 2 then 1 END)::numeric / count(*)) * 100, 2) as "Defect Rate"
FROM reviews r 
WHERE r.class_name IS NOT NULL 
GROUP BY r.division_name, r.department_name, r.class_name 
HAVING count(case when r.rating <= 2 then 1 END) > 10
ORDER BY "Negative Reviews" DESC;
"""

# 3. Efektivitas Ulasan Terhadap Engagement (Positive Feedback)
QUERY_EFEKTIVITAS_ULASAN = """
SELECT 
    r.rating as "Rating",
    round(AVG(r.positive_feedback_count), 2) as "Average Helpful Votes",
    MAX(r.positive_feedback_count) as "Max Helpful Votes"
FROM reviews r 
GROUP BY r.rating 
ORDER BY r.rating DESC;
"""

# 4. Segmentasi Pasar Berdasarkan Kelompok Usia
QUERY_SEGMENTASI_PASAR = """
SELECT 
    case 
        when age < 30 then 'Gen Z'
        when age between 30 and 45 then 'Milenial'
        else 'Gen X/Boomers'
    end as "Age Group",
    r.department_name as "Department",
    count(*) as "Total Purchase",
    round(avg(r.rating), 2) as "Average Rating"
FROM reviews r
WHERE r.department_name IS NOT NULL 
GROUP BY "Age Group", r.department_name
ORDER BY "Age Group", "Total Purchase" DESC;
"""

# 5. Tren Kata Kunci dalam Judul Ulasan (Dibuat Standar Dasar untuk Inisialisasi)
QUERY_KEYWORDS_BASE = """
SELECT
    r.clothing_id as "Clothing ID",
    r.division_name as "Division",
    r.department_name as "Department",
    r.class_name as "Class",
    r.title as "Review Title",
    r.review_text as "Review Text",
    r.rating as "Rating"
FROM reviews r
WHERE r.title IS NOT NULL
LIMIT 15;
"""

# 6. Kategori Produk Paling Populer Berdasarkan Positive Feedback
QUERY_PRODUK_POPULER = """
SELECT 
    r.clothing_id::VARCHAR as "clothing_id",
    count(*) as "review_count",
    sum(r.positive_feedback_count) as "total_positive_feedback",
    round(avg(r.rating), 2) as "average_rating",
    round(avg(r.recommended_ind) * 100, 2) as "recommended_rate"
FROM reviews r 
WHERE r.clothing_id IS NOT NULL
GROUP BY r.clothing_id 
ORDER BY "total_positive_feedback" DESC
LIMIT 10;
"""