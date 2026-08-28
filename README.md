# Research Nexus

**AI-Powered Research Workspace & University Knowledge Graph Platform**

An automated, cloud-ready research workspace that breaks down university research silos. It discovers cross-disciplinary papers, detects matching datasets across departments, surfaces hidden collaboration opportunities, and identifies potentially redundant studies — all powered by a hybrid AI extraction engine and a persistent Supabase PostgreSQL + pgvector knowledge graph.

> **Status**: Student/Hackathon Project — Actively maintained, production-capable backend, open for contributions.

---

## Problem Statement

University research is heavily siloed across disparate academic departments. Researchers struggle to discover:

- **Cross-disciplinary research & papers**
- **Matching benchmark datasets** used by adjacent labs (e.g. Computer Science and Biomedical Engineering both independently leveraging MIMIC-IV)
- **Hidden collaboration synergies** and co-authorship opportunities
- **Redundant or overlapping studies** duplicating compute and experimental effort

Research Nexus solves this by automatically extracting entities, relationships, and embeddings from research documents and building a live, queryable knowledge graph.

---

## Features

| Feature | Description |
|---------|-------------|
| **Document Ingestion** | Upload PDF, Markdown, plain text, or code repositories (ZIP). Automatic parsing and content extraction. |
| **AI Entity Extraction** | Hybrid engine: OpenRouter (google/gemma-4-31b-it) for cloud mode; deterministic rule-based NLP for local fallback. Extracts papers, researchers, departments, datasets, methods, technologies, and topics. |
| **Vector Embeddings** | 768-dimensional dense vectors for semantic search. Stored in pgvector for efficient cosine similarity (`<=>`). |
| **Knowledge Graph** | Interactive Cytoscape visualization with force-directed layout, entity type filtering, and side-drawer inspector. |
| **Dataset Matching Hub** | First-class detection of datasets shared across departments with applied methods, active researchers, and synergy scoring. |
| **Collaboration Discovery** | Multi-factor scoring (shared datasets, complementary methods, semantic proximity) to surface cross-disciplinary opportunities. |
| **Redundancy Detection** | Compares abstract embeddings, methodologies, and datasets; flags High/Moderate/Domain-Parallelism overlap with actionable recommendations. |
| **Obsidian-Style Notes** | Wikilink (`[[...]]`) support, bi-directional linking to entities, pinning, tagging, and graph visualization. |
| **Semantic Search** | Vector similarity + keyword boosting across papers, datasets, and methods. |
| **AI Workspace Actions** | Summarize, deep-analyze, methodology extraction, research ideas, questions, chat with sources, and document comparison — all evidence-grounded. |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | FastAPI (Python 3.11+), Uvicorn |
| **Database** | Supabase PostgreSQL + pgvector (vector similarity search) |
| **AI Provider** | OpenRouter (OpenAI-compatible API) — primary: `google/gemma-4-31b-it`; free-tier fallback models |
| **Local Fallback** | Deterministic rule-based NLP + 768-dim embeddings (no external API required) |
| **Frontend** | Vanilla ES6 + Vite, Cytoscape.js (graph), Tailwind CSS (styling) |
| **Deployment** | Docker, Cloud Run ready |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     RESEARCH NEXUS UI                           │
│  Knowledge Graph • Dataset Matching • Collaboration Hub        │
│  Redundancy Detection • Semantic Search • Notes Workspace      │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ REST API / CORS
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                              │
│  Ingestion Engine • Hybrid Entity Extractor • Embedding Gen    │
│  Graph Analytics • Dataset Matching • Redundancy Engine        │
└────────────────────────────┬─────────────────────┬──────────────┘
                             │                     │
              ┌──────────────┘                     └──────────────┐
              ▼                                                   ▼
┌─────────────────────────────────┐     ┌─────────────────────────────────┐
│      AI PROVIDER LAYER          │     │      DATABASE LAYER             │
│                                 │     │                                 │
│  [Cloud]: OpenRouter API        │     │  [Primary]: Supabase PostgreSQL │
│  - google/gemma-4-31b-it        │     │  - pgvector extension           │
│  - free-tier fallbacks          │     │  - Vector cosine search         │
│                                 │     │                                 │
│  [Local]: Rule-based NLP        │     │  [Dev]: SQLite (fallback only)  │
│  - Deterministic 768-dim vecs   │     │  - Vector cosine distance       │
└─────────────────────────────────┘     └─────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Supabase account (for PostgreSQL + pgvector)
- OpenRouter API key (for cloud AI mode)

### 1. Clone & Configure Environment

```bash
git clone https://github.com/your-username/research-nexus.git
cd research-nexus

# Copy example environment file
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Supabase (required for PostgreSQL + pgvector)
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=your_publishable_key
SUPABASE_SECRET_KEY=your_secret_key
SUPABASE_JWKS_URL=https://YOUR_PROJECT_REF.supabase.co/auth/v1/.well-known/jwks.json

# Database — use Supabase session pooler (port 6543)
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@YOUR_POOLER_HOST:6543/postgres

# AI Provider (OpenRouter)
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key
AI_MODEL=google/gemma-4-31b-it
MOCK_AI=false
```

> **Security**: Never commit `.env`. It is in `.gitignore`. Use `.env.example` as a template only.

### 2. Supabase Setup

1. Create a new Supabase project
2. Enable the **pgvector** extension: `CREATE EXTENSION IF NOT EXISTS vector;`
3. Run the schema from `backend/migrations/001_initial_schema.sql` in the Supabase SQL editor
4. Get your database password from Settings → Database
5. Get the **Session Pooler** connection string from Settings → Database → Connection pooling (port 6543)
6. Update `DATABASE_URL` in `.env` with the pooler host and your password

### 3. Run Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 4. Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Yes | Supabase anon/public key |
| `SUPABASE_SECRET_KEY` | Yes | Supabase service role key |
| `SUPABASE_JWKS_URL` | Yes | JWKS endpoint for auth |
| `DATABASE_URL` | Yes | PostgreSQL connection string (use pooler port 6543) |
| `AI_PROVIDER` | No | `openrouter` (default) |
| `OPENROUTER_API_KEY` | For cloud mode | OpenRouter API key |
| `AI_MODEL` | No | Model ID (default: `google/gemma-4-31b-it`) |
| `MOCK_AI` | No | `true`/`false` — forces local deterministic engine |
| `NODE_ENV` | No | `development` / `production` |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Service health, DB engine, AI mode |
| `GET` | `/api/stats` | Document, entity, relationship, dataset counts |
| `GET` | `/api/datasets` | Dataset matching & cross-department reuse |
| `GET` | `/api/graph` | Knowledge graph (nodes/edges for Cytoscape) |
| `GET` | `/api/search?q=...` | Semantic vector search |
| `GET` | `/api/collaborations` | Cross-disciplinary opportunities |
| `GET` | `/api/redundancy` | Research overlap detection |
| `GET` | `/api/documents` | List all documents |
| `GET` | `/api/documents/{id}` | Document with entities |
| `POST` | `/api/upload` | Upload PDF/MD/TXT/ZIP |
| `POST` | `/api/analyze/{id}` | Run AI extraction + embeddings |
| `GET` | `/api/entities` | List all entities |
| `GET` | `/api/entities/{id}` | Entity details with linked papers |
| `GET` | `/api/notes` | List all notes |
| `POST` | `/api/notes` | Create note (supports wikilinks) |
| `PATCH` | `/api/notes/{id}` | Update note |
| `DELETE` | `/api/notes/{id}` | Delete note |
| `POST` | `/api/ai/summarize` | AI summary of document |
| `POST` | `/api/ai/analyze` | Deep analysis with entities |
| `POST` | `/api/ai/methodology` | Extract methodology |
| `POST` | `/api/ai/research-ideas` | Generate research ideas |
| `POST` | `/api/ai/questions` | Generate research questions |
| `POST` | `/api/ai/chat` | Chat with document sources |
| `POST` | `/api/ai/compare` | Compare two documents |

---

## Project Structure

```
research-nexus/
├── backend/
│   ├── main.py                 # FastAPI app, routes, startup
│   ├── database.py             # PostgreSQL/SQLite abstraction, schema, CRUD
│   ├── ai_engine.py            # Hybrid entity extraction + embeddings
│   ├── ai_service.py           # AI workspace actions (summarize, analyze, etc.)
│   ├── ai_prompts.py           # Structured prompts for OpenRouter
│   ├── analytics.py            # Dataset matching, collaborations, redundancy, graph
│   ├── ingestion.py            # PDF/MD/TXT/ZIP parsing
│   ├── config.py               # Settings management
│   ├── test_api.py             # Backend test suite (23 tests)
│   ├── migrations/
│   │   └── 001_initial_schema.sql  # Supabase schema with pgvector
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Container build
├── frontend/
│   ├── src/
│   │   ├── main.jsx            # App entry, routing, state
│   │   ├── components/         # React-like components (vanilla)
│   │   └── styles.css          # Tailwind + custom styles
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── deploy/                     # Deployment configs (if any)
├── .env.example                # Environment template
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## Testing

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest test_api.py -v
```

**Expected**: 23/23 tests pass against Supabase PostgreSQL.

---

## Security

- **Never commit `.env`** — it contains Supabase keys, database passwords, and OpenRouter API keys.
- `.env` is in `.gitignore` with `!.env.example` to allow the template.
- No secrets are hardcoded in source code.
- Supabase RLS (Row Level Security) can be enabled for production multi-tenant use.
- `MOCK_AI=true` forces the deterministic local engine (no external API calls).

---

## Deployment

### Docker

```bash
docker-compose up --build
```

### Cloud Run (GCP)

```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/research-nexus:latest backend/
gcloud run deploy research-nexus \
  --image gcr.io/$PROJECT_ID/research-nexus:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="AI_PROVIDER=openrouter,OPENROUTER_API_KEY=...,AI_MODEL=google/gemma-4-31b-it,MOCK_AI=false,DATABASE_URL=..."
```

---

## License

MIT License — Free for personal, educational, and commercial use.

```
MIT License

Copyright (c) 2025 Research Nexus Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Acknowledgments

- **Supabase** for PostgreSQL + pgvector hosting
- **OpenRouter** for unified LLM API access
- **Cytoscape.js** for graph visualization
- **FastAPI** for the modern Python web framework
- **Vite** for lightning-fast frontend tooling

---

*Built for researchers, by researchers. 🧪📊🔬*