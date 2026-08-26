# Research Nexus – University Research Knowledge Graph & Dataset Matching Engine


## Security & Local Developer Guidance

This project includes several built-in safety measures to avoid accidental secret leakage and to make mock AI mode explicit.

- Do NOT commit .env or service account key files. A sample .env.example is provided.
- To enable local pre-commit secret checks, run:

  cp pre-commit-checks.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

  or use a repository hooks path:

  git config core.hooksPath .githooks && mkdir -p .githooks && cp pre-commit-checks.sh .githooks/pre-commit && chmod +x .githooks/pre-commit

- Mock AI mode must never be enabled in production. If NODE_ENV=production and MOCK_AI=true the server will refuse to start.
- To run the backend locally with real OpenRouter credentials, set OPENROUTER_API_KEY in your environment and keep AI_PROVIDER=openrouter. If it's missing a prominent warning is logged at startup and the UI will surface that OpenRouter is not configured. – University Research Knowledge Graph & Dataset Matching Engine
An automated, cloud-ready AI knowledge graph platform designed to break down university research silos. It discovers cross-disciplinary papers, detects matching datasets across departments, surfaces hidden collaboration opportunities, and identifies potentially redundant studies.

---

## 🏛️ Problem Statement
University research is heavily siloed across disparate academic departments. Researchers struggle to discover:
- **Cross-disciplinary research & papers**
- **Matching benchmark datasets** used by adjacent labs (e.g. Computer Science and Biomedical Engineering both independently leveraging MIMIC-IV)
- **Hidden collaboration synergies** and co-authorship opportunities
- **Redundant or overlapping studies** duplicating compute and experimental effort

---

## 🚀 Target Google Cloud Architecture

```
                               ┌───────────────────────────────────────────────┐
                               │             RESEARCH NEXUS UI                 │
                               │  - Knowledge Graph (Cytoscape + Filters)     │
                               │  - Dataset Matching & Cross-Dept Reuse Hub    │
                               │  - Semantic Research Search & Embeddings      │
                               │  - Cross-Disciplinary Collaboration Insights  │
                               │  - Research Redundancy & Deduplication Engine │
                               │  - Multi-format Ingestion Studio (PDF/MD/ZIP) │
                               └───────────────────────┬───────────────────────┘
                                                       │ REST API / CORS
                                                       ▼
                               ┌───────────────────────────────────────────────┐
                               │       CLOUD RUN / FASTAPI BACKEND             │
                               │  - Ingestion Engine (PDF, MD, Code/ZIP, Py)   │
                               │  - Hybrid Entity & Relationship Extractor     │
                               │  - Vector Embedding Generator (Dual Engine)   │
                               │  - Graph & Synergy Analytics Engine           │
                               └──────────────┬─────────────────┬──────────────┘
                                              │                 │
                      ┌───────────────────────┘                 └───────────────────────┐
                      ▼                                                                 ▼
   ┌─────────────────────────────────────┐                           ┌─────────────────────────────────────┐
   │       OPENROUTER / GEMMA LAYER       │                           │      ALLOYDB / PGVECTOR LAYER       │
   │                                     │                           │                                     │
   │  [Cloud Mode]:                      │                           │  [Cloud Mode]:                      │
   │   - OpenRouter API (OpenAI-compatible) │                         │   - AlloyDB for PostgreSQL          │
   │   - google/gemma-4-31b-it           │                           │   - pgvector Cosine Search (<=>)    │
   │                                     │                           │                                     │
   │  [Local Fallback Mode]:             │                           │  [Local Fallback Mode]:             │
   │   - Smart Rule/NLP Heuristic Engine │                           │   - SQLite (research_nexus.db)      │
   │   - Deterministic 768-dim Embedder  │                           │   - Vector Cosine Distance Engine   │
   └─────────────────────────────────────┘                           └─────────────────────────────────────┘
```

- **OpenRouter**: google/gemma-4-31b-it via the server-side OpenAI-compatible OpenRouter API for analysis and graph extraction.
- **AlloyDB / PostgreSQL (pgvector)**: Persistent knowledge graph store, document catalog, and vector similarity search (`<=>`).
- **Cloud Run**: Containerized backend API and async ingestion engine.
- **Frontend**: Interactive Cytoscape knowledge graph, real-time dataset matching hub, collaboration analytics, and redundancy insights.

---

## 🌟 Key Features

1. **First-Class Dataset Matching Hub**:
   - Explicitly identifies datasets shared across departments:
   > **"🔥 MIMIC-IV is being used by research projects across 2 departments (Computer Science, Biomedical Engineering)"**
   - Displays applied methods, active researchers, and joint data asset opportunities.

2. **Multi-Format Document & Code Ingestion**:
   - Ingests raw PDFs, structured Markdown, plain text, and complete **Code Repositories (`.zip` archives, `.py`, `.ipynb`)**.
   - Extracts code libraries (PyTorch, Transformers, JAX), model definitions, and referenced datasets.

3. **Hybrid AI Extraction & Embeddings (Cloud + Local Fallback)**:
   - **OpenRouter Mode**: Evidence-grounded google/gemma-4-31b-it structured extraction.
   - **Local Fallback Mode**: High-precision academic taxonomy and deterministic 768-dimensional normalized dense vectors.

4. **Cross-Disciplinary Collaboration Discovery**:
   - Multi-factor synergy scoring based on shared datasets, complementary methods, and semantic vector distance.
   - Generates actionable collaboration proposals and joint grant rationales.

5. **Research Redundancy Detection**:
   - Compares abstract embeddings, methodologies, and datasets.
   - Highlights overlap risk levels (High / Moderate / Domain Parallelism) and suggests joint benchmarking.

6. **Interactive Cytoscape Knowledge Graph**:
   - Dynamic force-directed physics layout with color-coded entity types (Paper, Researcher, Department, Dataset, Method, Topic, Technology).
   - Entity type filtering, node search, and full side-drawer Entity Inspector.

---

## ⚙️ Quick Start (Local Demo Mode)

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API Documentation will be live at: [http://localhost:8000/docs](http://localhost:8000/docs).

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173).

---

## ☁️ Google Cloud Deployment

### 1. Configure Environment Variables
Set the following server-side variables in `.env` or in Cloud Run:
```bash
export AI_PROVIDER="openrouter"
export OPENROUTER_API_KEY="your_openrouter_api_key"
export AI_MODEL="google/gemma-4-31b-it"
export MOCK_AI=false
# Optional: AlloyDB connection string
export DATABASE_URL="postgresql://postgres:PASSWORD@ALLOYDB_IP:5432/research_nexus"
```

### 2. Deploy to Cloud Run
```bash
gcloud builds submit --tag gcr.io/$GOOGLE_CLOUD_PROJECT/research-nexus:latest backend/

gcloud run deploy research-nexus \
  --image gcr.io/$GOOGLE_CLOUD_PROJECT/research-nexus:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AI_PROVIDER=openrouter,AI_MODEL=google/gemma-4-31b-it,MOCK_AI=false
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health, active OpenRouter / mock mode, DB engine |
| `GET` | `/api/stats` | Document, entity, relationship, and dataset metric counts |
| `GET` | `/api/datasets` | **First-class dataset matching & cross-department reuse intelligence** |
| `GET` | `/api/graph` | Knowledge graph nodes and edges for Cytoscape (supports `?type=...`) |
| `GET` | `/api/search?q=...` | Semantic vector search across papers, datasets, and methods |
| `GET` | `/api/collaborations` | Cross-disciplinary collaboration opportunities and synergy scores |
| `GET` | `/api/redundancy` | Research overlap and redundancy detection with recommendations |
| `GET` | `/api/documents` | List all ingested research documents |
| `GET` | `/api/entities/{id}` | Detailed entity inspector with direct links and connected papers |
| `POST` | `/api/upload` | Upload PDF, Markdown, TXT, or Code Repository ZIP |
| `POST` | `/api/analyze/{id}` | Run entity extraction, vector embedding, and update graph |
| `POST` | `/api/seed` | Reset and seed benchmark research papers |

---

## 🎬 2-Minute Demo Script

1. **System Health & GCP Mode**:
   - Point out the active mode badges in the top header: `OpenRouter (google/gemma-4-31b-it)` and `AlloyDB / pgvector` (or Local Fallback).
2. **First-Class Dataset Matching**:
   - Highlight the **Dataset Matching Hub**: show **"MIMIC-IV is being used by research projects across 2 departments (Computer Science, Biomedical Engineering)"**.
   - Show how Dr. Alice Smith (CS) and Dr. Brian Lee (Biomedical Engineering) are both leveraging the same data asset.
3. **Interactive Knowledge Graph**:
   - Filter graph by `Dataset` and `Paper`. Click on `MIMIC-IV` or `Landsat` to view the Entity Inspector drawer with direct relationships.
4. **Semantic Vector Search**:
   - Click the search pill `"federated learning medical imaging"` or type a natural language query.
   - Show ranked cosine similarity matches with extracted topic, method, and dataset tags.
5. **Cross-Disciplinary Collaboration**:
   - Review the Computer Science ↔ Biomedical Engineering collaboration card (95% synergy) detailing joint grant rationale.
6. **Redundancy Detection**:
   - Review the redundancy card highlighting overlapping methodologies between decentralized imaging studies.
7. **Live Document / Code Ingestion**:
   - Click "Ingest Research & Code", upload a research paper or code repository ZIP, and watch the knowledge graph dynamically expand!
