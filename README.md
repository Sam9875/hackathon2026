# Supplier Intelligence Engine

> **AI-powered supplier discovery platform** — Natural language search with semantic matching across 2,500+ European manufacturers.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-Vector_Search-yellow)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?logo=sqlite&logoColor=white)

---

## 🎯 The Problem

When procurement departments need to identify new suppliers in unfamiliar markets, verticals, or geographies, the process is almost entirely manual: Google searches, directory lookups, word of mouth, trade fairs. Information exists, but it is **not collected in one place, not structured, and not intelligently queryable**.

## ✅ The Solution

An end-to-end tool that allows a procurement user to **search in natural language**, e.g.:

> *"Find manufacturing companies in Italy, with revenue above 30 million euros, that produce packaging machinery"*

…and receive a list of **real, verified suppliers** with all the operational information needed to initiate first contact.

---

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Wikidata    │ ──▶ │   Ingest &   │ ──▶ │  Embedding   │ ──▶ │  Streamlit   │
│  SPARQL API  │     │  Clean/Store │     │  FAISS Index │     │  Search UI   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                      pipeline/            pipeline/            app.py
                      ingest.py            embed.py
```

### Pipeline Flow

1. **Ingestion** (`pipeline/ingest.py`) — Queries Wikidata SPARQL for manufacturing companies in Italy & Germany (2,500+ per country), cleans/normalizes data, stores in SQLite
2. **Embedding** (`pipeline/embed.py`) — Generates semantic embeddings with `all-MiniLM-L6-v2` and builds a FAISS vector index
3. **Search** (`search/engine.py`) — Combines structured NL filter extraction with FAISS semantic search
4. **UI** (`app.py`) — Streamlit interface with relevance scores, filter banners, and match type indicators

---

## 📊 Data Per Supplier

| Category | Attributes |
|----------|-----------|
| **Identity** | Company name, VAT number, country, city, HQ, founding date |
| **Contacts** | Website, email (derived), phone |
| **Offer** | Product description, categories, keywords |
| **Operations** | Served geographies |
| **Quality** | Certifications (ISO, IATF, HACCP, etc.) |
| **Size** | Revenue, employee count |
| **Source** | Wikidata URL, extraction timestamp |

---

## 🔍 Search Capabilities

The search engine supports **granular queries** across multiple dimensions:

| Dimension | Example |
|-----------|---------|
| 🌍 **Geography** | *"in Italy"*, *"German companies"*, *"based in Milan"* |
| 💰 **Revenue** | *"revenue above 30 million"*, *"revenue below 1 billion"* |
| 👥 **Size** | *"more than 500 employees"*, *"fewer than 100 employees"* |
| 🏅 **Quality** | *"ISO 9001 certified"*, *"HACCP"*, *"IATF 16949"* |
| 🏭 **Products** | *"packaging machinery"*, *"automotive components"*, *"food processing"* |

**Semantic matching**: Even if your wording doesn't match exactly, the AI finds suppliers by *meaning*. Searching *"bottle capping equipment"* can find suppliers tagged as *"packaging machinery"*.

---

## 🚀 Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/<your-username>/supplier-intelligence.git
cd supplier-intelligence

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the pipeline (fetches ~2,500 real suppliers from Wikidata)
python pipeline/db_setup.py
python pipeline/ingest.py
python pipeline/embed.py

# 5. Launch the UI
streamlit run app.py
```

---

## 📁 Project Structure

```
supplier-db/
├── app.py                  # Streamlit web interface
├── requirements.txt        # Python dependencies
├── README.md
├── .gitignore
├── pipeline/
│   ├── db_setup.py         # SQLite schema initialization
│   ├── ingest.py           # Wikidata SPARQL ingestion & cleaning
│   ├── embed.py            # Sentence embedding + FAISS index
│   └── enrich.py           # Optional website meta enrichment
├── search/
│   └── engine.py           # NL parser + FAISS semantic search engine
└── data/                   # Generated at runtime (gitignored)
    ├── suppliers.db        # SQLite database
    ├── suppliers.faiss     # FAISS vector index
    └── id_map.json         # FAISS index → supplier ID mapping
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **Data Source** | Wikidata SPARQL |
| **Database** | SQLite |
| **Embeddings** | SentenceTransformers (`all-MiniLM-L6-v2`) |
| **Vector Search** | FAISS (L2 distance) |
| **NL Parsing** | Regex-based structured extraction |
| **Frontend** | Streamlit |

---

## 📝 License

MIT
