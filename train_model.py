import pandas as pd
import re
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

def clean_text(text):
    if not isinstance(text, str):
        return ""
    # Lowercase
    text = text.lower()
    # Hapus tanda baca dan karakter selain huruf
    text = re.sub(r'[^a-z\s]', '', text)
    # Hapus stopwords (menggunakan ENGLISH_STOP_WORDS bawaan sklearn)
    words = text.split()
    words = [w for w in words if w not in ENGLISH_STOP_WORDS]
    return " ".join(words)

def train_and_save():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, "ecommercereviews_clean.csv")
    
    # Check if cleaned CSV exists, if not clean it
    if not os.path.exists(csv_path):
        import clean_csv
        clean_csv.clean_csv_file()
        
    print("Membaca dataset...")
    df = pd.read_csv(csv_path, on_bad_lines='skip')
    
    # Bersihkan nama kolom agar mudah dibaca
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    
    # Konversi rating ke numeric dan hapus yang tidak valid
    df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
    df = df.dropna(subset=['rating'])
    
    # Filter out rating 3 agar klasifikasi biner kontras (Positif vs Negatif)
    print("Memproses data ulasan...")
    df_clean = df[df['rating'] != 3].copy()
    
    # rating 4-5 = Positif (1), rating 1-2 = Negatif (0)
    df_clean['sentiment'] = df_clean['rating'].apply(lambda x: 1 if x >= 4 else 0)
    
    # Gunakan kolom review_text, paksa jadi string
    df_clean['review_text'] = df_clean['review_text'].astype(str)
    df_clean['cleaned_text'] = df_clean['review_text'].apply(clean_text)
    
    # Hapus baris yang kosong setelah dibersihkan
    df_clean = df_clean[df_clean['cleaned_text'] != ""]
    
    X = df_clean['cleaned_text']
    y = df_clean['sentiment']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Ekstraksi fitur menggunakan TF-IDF...")
    vectorizer = TfidfVectorizer(max_features=5000)
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    
    print("Melatih model Logistic Regression...")
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train_vec, y_train)
    
    # Evaluasi sederhana
    y_pred = model.predict(X_test_vec)
    acc = accuracy_score(y_test, y_pred)
    print(f"Model berhasil dilatih dengan akurasi: {acc * 100:.2f}%")
    
    # Simpan model dan vectorizer ke pickle
    model_path = os.path.join(current_dir, "model_sentimen.pkl")
    vectorizer_path = os.path.join(current_dir, "vectorizer.pkl")
    
    print(f"Menyimpan model ke {model_path}...")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
        
    print(f"Menyimpan vectorizer ke {vectorizer_path}...")
    with open(vectorizer_path, "wb") as f:
        pickle.dump(vectorizer, f)
        
    print("Proses training selesai!")

if __name__ == "__main__":
    train_and_save()
