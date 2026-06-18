# 📊 Market-Pulse: E-Commerce Sentiment & Business Analytics

Market-Pulse is an interactive, Streamlit-powered dashboard designed to help e-commerce store owners and analysts extract actionable business intelligence from customer reviews. 

The application blends **local machine learning (fast & resource-friendly)** for sentiment classification with a **generative AI-powered Consultant (Google Gemini API)** using a Retrieval-Augmented Generation (RAG) approach to draft detailed business reports, all protected by custom local safety guardrails.

---

## ✨ Key Features & Functionality

### 1. Interactive Business Intelligence Dashboard
* **Product Insights**: Visualize the top 10 most popular products based on customer upvotes.
* **Customer Loyalty**: Analyze review distribution across departments with interactive pie charts.
* **Market Segmentation**: Track purchase volume and ratings across different age groups.
* **Pain Point Identification**: Spot categories with high complaint counts using automatic defect rate calculations.

### 2. Live Review Search & Filtering
* Filter and search through the built-in review database in real-time.
* Look up specific keywords (e.g., "fabric", "size", "delivery") alongside star ratings to drill down into specific customer experiences.

### 3. Smart Dataset Uploader
* Drag-and-drop custom `.csv` or `.xlsx` files directly.
* **Auto-Detection**: Dynamically detects the text column and rating column using intelligent keyword matching.
* **Validation & Cleaning**: Automatically handles null values, drops duplicate reviews, filters out invalid rows, and samples large datasets to ensure smooth performance.

### 4. Hybrid Sentiment Engine
* **Train-on-the-Fly**: If the uploaded dataset contains a rating column, the system automatically trains a fresh **TF-IDF + Logistic Regression** classification model tailored to that specific product domain.
* **Fallback Mode**: If no ratings are present, the app seamlessly falls back to a pre-trained base model.
* **Soft Weighted Ensemble Layer**: Blends the text probability ($P_{\text{text}}$, 60% weight) from the ML model with a prior probability based on the star rating ($P_{\text{rating}}$, 40% weight) to produce a combined confidence score. This prevents hard override conflicts and yields smoother sentiment labeling.
  * Rating prior mapping: 1 Star = 0.10, 2 Stars = 0.25, 3 Stars = 0.50, 4 Stars = 0.75, 5 Stars = 0.90.
  * Sentiment thresholds: $\ge 0.60$ is classified as **Positive**, $\le 0.40$ is classified as **Negative**, and nether is **Neutral**.
* **Context-Aware Preprocessing**: Preserves negation words (e.g., *not, no, tidak, kurang*) and leverages N-grams range `(1, 3)` to accurately predict phrases like *"not very good"*.

### 5. Interactive Dataset Explorer
* Dive into your freshly uploaded and analyzed datasets directly on the dashboard.
* **Real-Time Filtering**: Seamlessly filter reviews by keywords, star ratings (clean integer scale 1-5), and predicted sentiment (Positif / Negatif).
* **Clean Data Table**: Renders an unobstructed, full-width view of all matches containing only high-value columns (Teks Ulasan, Rating, Sentimen Prediksi) for a clean visual look.
* **Direct CSV Export**: Export your filtered analytical results as a clean CSV with one click.

### 6. AI Business Consultant (RAG)
* Ask business questions (e.g., *"Why are customers leaving negative reviews about shipping?"*) in plain language.
* **Dual Search Methods**:
  * **Keyword Search (TF-IDF)**: Matches literal keyword overlaps in reviews. Extremely fast.
  * **Two-Stage Semantic Search (MiniLM)**: 
    1. *Lexical Candidate Filtering*: Uses TF-IDF with bilingual query expansion (e.g., mapping Indonesian terms like *"kualitas"* to English *"quality"*) to fetch the top 100 candidate reviews.
    2. *Semantic Re-ranking*: Uses `paraphrase-multilingual-MiniLM-L12-v2` Sentence Transformers to embed and re-rank only these 100 candidates on the fly. This prevents CPU hangs, reducing query execution time from 15 minutes to **~3 seconds**.
* **Background Preloading**: The embedding model is loaded asynchronously in a background thread upon application startup, preventing the UI from freezing when the first semantic query is made.
* **Report Generation**: Passes this context to **Google Gemini** (supporting `gemini-3.5-flash`, `gemini-2.5-flash`, etc.) to draft a structured report with:
  * **Executive Summary** (Key findings and dataset context)
  * **Pain Points** (Key issues complete with direct customer quotes)
  * **Action Items** (Actionable business recommendations based on the data)
* **Pre-flight Guardrail**: Rejects off-topic prompts (like coding questions or general knowledge) locally before calling the Gemini API to prevent unnecessary token usage.
* **Hallucination Guard**: Uses local quote matching and keyword overlap calculations to verify if the AI's report is grounded in the retrieved customer reviews, displaying a warning if the report strays from the actual data.

---

## 🛠️ Tech Stack & Libraries

* **Frontend & UI**: `streamlit` (v1.32.0+)
* **Visualization**: `plotly-express`
* **Data Manipulation**: `pandas`, `numpy`
* **Machine Learning**: `scikit-learn` (Logistic Regression, TF-IDF Vectorizer)
* **Embeddings & NLP**: `sentence-transformers` (MiniLM L12), `torch`
* **Generative AI**: `google-genai` SDK
* **Database (Fallback)**: Local Pandas-based Query Engine (PostgreSQL-free)

---

## 🚀 Getting Started

### Prerequisites
Make sure you have **Python 3.10+** installed on your system.

### 1. Installation
Clone this repository and install the required packages:
```bash
pip install -r requirements.txt
```

### 2. Configuration & Secrets
Create a `.streamlit/secrets.toml` file in the root of the project folder:
```toml
# Required for the AI Consultant
GEMINI_API_KEY = "your_actual_gemini_api_key_here"
```

### 3. Run the App
Launch the Streamlit dashboard:
```bash
streamlit run app.py
```

---

## 📁 Project Structure

```text
market-pulse/
│
├── app.py                      # Main Streamlit dashboard application
├── requirements.txt            # Dependency list
├── pyrefly.toml                # Linter configuration
├── system_design.md            # Target system design reference
├── README.md                   # Project documentation
│
├── data/
│   ├── ecommercereviews.csv       # Raw fallback dataset
│   └── ecommercereviews_clean.csv # Cleaned fallback dataset
│
├── models/
│   ├── model_sentimen.pkl      # Pre-trained base Logistic Regression model
│   └── vectorizer.pkl          # Pre-trained TF-IDF Vectorizer
│
├── modules/
│   ├── ai_consultant.py        # Pre-flight guardrails, RAG (Two-stage Semantic Search), and Hallucination Guard
│   ├── clean_csv.py            # CSV preprocessing helper
│   ├── database.py             # Local Pandas-based analytical query engine
│   ├── ml_pipeline.py          # TF-IDF + Logistic Regression classification (Soft Ensemble)
│   ├── queries.py              # Pre-defined analytical queries
│   └── upload_processor.py     # File validation and auto-column detection
│
└── scripts/
    └── train_model.py          # Offline script to clean data and retrain ML model
```
