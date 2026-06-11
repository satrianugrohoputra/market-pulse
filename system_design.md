# System Design: Hybrid E-Commerce Sentiment Analyzer

This document serves as a comprehensive system design and architectural overview of the **Hybrid E-Commerce Sentiment Analyzer**. It is designed to act as a context-setter for LLMs or developers to quickly understand the project's objectives, architecture, current feature set, data schemas, and future roadmap.

---

## 1. Executive Summary & Objectives

The **Hybrid E-Commerce Sentiment Analyzer** is a Streamlit-based business intelligence tool that processes customer reviews. It integrates traditional statistical machine learning (NLP classification) with modern generative AI (Retrieval-Augmented Generation / RAG) to deliver fast, cost-effective, and highly contextual analysis.

### Primary Goals:
* **Cost Efficiency**: Use lightweight, local ML models (TF-IDF + Logistic Regression) for high-throughput sentiment classification (Positive/Negative).
* **Failsafe Accuracy**: Apply a rule-based override layer that resolves conflicts between ML predictions and customer star ratings.
* **Semantic Retrieval**: Support natural-language search over reviews using local multilingual sentence embeddings and vector stores.
* **Aspect-Based Summarization**: Leverage Google Gemini to analyze negative feedback and synthesize actionable business recommendations.
* **Self-Correcting RAG**: Employ a LangGraph workflow with a self-critique loop to ensure the quality, structure, and completeness of generated business reports.

---

## 2. High-Level Architecture & Tech Stack

The system implements a **hybrid architecture** that maps tasks to the most efficient computing model:

```
+--------------------------------------------------------------------------------+
|                                  USER INTERFACE                                |
|                                Streamlit Frontend                              |
+--------------------------------------------------------------------------------+
                                         |
                                         v
+------------------+     +-------------------------------+     +-----------------+
|  Traditional ML  |     |      Semantic Indexing        |     |   Generative AI |
|  scikit-learn    |     |  SentenceTransformers + Chroma|     |    LangGraph    |
+------------------+     +-------------------------------+     +-----------------+
| * TF-IDF +       |     | * Multilingual MiniLM         |     | * 6-Node Graph  |
|   Logistic Reg   |     | * In-memory Vector Database   |     | * Self-Critique |
| * Fast Local     |     | * Semantic Search (Cosine)    |     | * Google Gemini |
|   Classification |     | * 100% Local / Free Retrieval |     |   Synthesis     |
+------------------+     +-------------------------------+     +-----------------+
```

### Key Technologies:
* **UI/Dashboard**: `streamlit` (v1.32.0+)
* **Data Manipulation**: `pandas`, `numpy`
* **Plotting**: `plotly`
* **Machine Learning**: `scikit-learn` (Logistic Regression, TF-IDF Vectorizer, K-Means Clustering)
* **Embeddings**: `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2` - 120MB, handles EN/ID)
* **Vector Store**: `chromadb` (Ephemeral/In-Memory client)
* **Agent Framework**: `langgraph` (StateGraph workflow orchestration)
* **LLM Engine**: `google-genai` SDK (supports `gemini-3.1-flash-lite`, `gemini-2.5-flash`, etc.)

---

## 3. Core Functional Alur (System Flow)

1. **Initialization**: Trains a base Logistic Regression model on a balanced mix of all available datasets (`ecommercereviews.csv`, `datashopee.csv`, `tokopedia-product-reviews-2019.csv`, and `adidasvsnike.csv`) to avoid overfitting to a single product type or language.
2. **Ingestion & Auto-Routing**:
   * Accepts user-uploaded CSV files.
   * Auto-detects the review text column via keyword candidates.
   * Runs a rule-based classifier to detect domain (clothing, shoes, electronics, general) and language (English, Indonesian).
   * Automatically trains a domain-specific model in-memory if a rating column exists in the uploaded file.
3. **Sentiment Classification & Correction**:
   * Predicts sentiment using the active model.
   * Applies **Rule-Based Correction**:
     * Predict = Negative, Rating $\ge$ 4 $\rightarrow$ override to **Positive**.
     * Predict = Positive, Rating $\le$ 2 $\rightarrow$ override to **Negative**.
4. **Semantic Indexing**:
   * Generates embeddings for review texts and indexes them in ChromaDB.
5. **Smart Search**:
   * Computes cosine similarity between user search queries and indexed reviews to retrieve semantically matching items.
6. **Agentic RAG (AI Consultant)**:
   * Triggers a 7-node LangGraph workflow to build an aspect-based business report with automatic grounding verification.

---

## 4. LangGraph Workflow & State Schema

The Agentic RAG module runs a deterministic state graph designed to retrieve reviews, cluster them, request an LLM report, verify its grounding locally, and validate the quality of the report.

```
    START
      │
      ▼
    [A] parse_query        — rule-based, no LLM
      │
      ▼
    [B] route_domain       — uses domain/language already in state
      │
      ▼
    [C] retrieve_chunks    — ChromaDB semantic search
      │
      ▼
    [D] cluster_aspects    — sklearn KMeans grouping, no LLM
      │
      ▼
    [E] synthesize_report  — single Gemini call
      │
      ▼
    [G] hallucination_guard— local sentence similarity, no LLM
      │
      ▼
    [F] validate_report    — rule-based quality check
      │
      ├─ PASS ──────────────────────────────────► END
      │
      └─ FAIL (retry_count < MAX_RETRIES)
           │
           └─ refine_query ──────────────────────► [C] (with broader query)
```

### Graph Schema (`GraphState`):
```python
class GraphState(TypedDict, total=False):
    # Inputs
    query: str
    domain: str
    language: str
    rule_corrected_count: int
    top_k: int
    sentiment_filter: Optional[str]

    # Intermediates
    parsed_query: str
    effective_domain: str
    retrieved: list[dict]
    aspect_clusters: dict[str, list[str]]
    retry_count: int
    step_log: list[str]

    # Outputs
    report: str
    validation_passed: bool
    validation_notes: str
    error: Optional[str]
```

### The 7 Nodes:
1. **`parse_query` (Node A)**: Standardizes search keywords. If Indonesian words are found, expands the query with English synonyms.
2. **`route_domain` (Node B)**: Identifies the relevant business aspects depending on the detected product category (e.g., Fabric for clothing, Battery for electronics).
3. **`retrieve_chunks` (Node C)**: Queries ChromaDB. On retry attempts, expands the query width and increases retrieval depth (`top_k`).
4. **`cluster_aspects` (Node D)**: Runs local **K-Means clustering** on the embeddings of retrieved texts. Categorizes reviews into $K$ thematic subgroups without utilizing LLM tokens.
5. **`synthesize_report` (Node E)**: Performs the only LLM call. Sends the reviews, domain aspects, and pre-identified clusters to Google Gemini to draft a structured Markdown report.
6. **`hallucination_guard` (Node G)**: Computes the cosine similarity of the generated report's sentences/paragraphs against the retrieved review texts using the local `SentenceTransformer` model. If the average max similarity drops below `0.35` (meaning the LLM is generating claims not backed by the retrieved reviews), it flags the grounding check as failed and prepends a clear general-response warning to the report without forcing costly Gemini API retries.
7. **`validate_report` (Node F)**: A rule-based parser that verifies:
   * Presence of three required headers: `Executive Summary`, `Pain Points`, and `Action Items`.
   * Word count threshold ($\ge$ 40 words).
   * Absence of system error markers.

### Routing Logic:
* If validation **passes** or maximum retries are reached ($\ge 2$): Transition to `__end__`.
* If validation **fails**: Transition to `increment_retry` $\rightarrow$ loops back to `retrieve_chunks`.

---

## 5. Current Features

* **Base Model Dataset Mixing**: Base ML model is trained on a balanced mixture of English clothing reviews, Indonesian Shopee/Tokopedia comments, and shoe descriptions to ensure multi-domain, cross-lingual generalizability.
* **Local Hallucination Guard**: Employs sentence-transformer similarity locally to verify RAG grounding and warns the user if report claims are not directly backed by reviews, saving API token usage.
* **Dual-Language Routing**: Seamlessly handles English and Indonesian review datasets.
* **On-the-Fly Transfer Learning**: Trains custom models for uploaded files when ratings are present.
* **Zero-Cost Semantic Indexing**: Uses a local embedding model and an ephemeral SQLite-free vector store.
* **Unsupervised Clustering**: Pre-clusters reviews to organize Gemini's output before generation.
* **Self-Critique & Query Expansion**: Automatic self-validation prevents empty/truncated reports.
* **Interactive UI**: Live charts showing sentiment distributions, viral products, and red flag categories.

---

## 6. Future Roadmap

These features are planned for future development:

### A. Advanced Predictive Models
* **Cross-Domain Transfer Learning**: Implement domain adaptation techniques (e.g., CORAL or Adversarial Domain Adaptation) to enhance classification accuracy on unlabelled CSV uploads.
* **Deep Learning NLP Head**: Allow users to switch from Logistic Regression to a lightweight transformer-based classification head (e.g., DistilBERT) run locally via ONNX Runtime.

### B. Agent Refinement
* **Agentic Model Routing (Node B)**: Replace the rule-based router in Node B with a small classification model or LLM agent to map custom text columns to precise product micro-categories.

### C. Vector & Data Store Enhancements
* **Persistent Vector DB**: Migrate from Ephemeral ChromaDB to a disk-persisted directory to allow incremental indexing and comparison across multiple sessions.
* **User Feedback Loop**: Enable users to click "Incorrect Sentiment" directly in the interactive data explorer, saving corrections to a local CSV to periodically retrain the model.
