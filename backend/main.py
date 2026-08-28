import truststore
truststore.inject_into_ssl()
import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import (
    db, get_db_conn, add_entity, link_doc_entity, add_relationship, save_chunk,
    create_note, get_notes, get_note_by_id, update_note, delete_note, duplicate_note,
    get_note_graph_data, get_document_graph_data, delete_document
)
from ingestion import parse_document
from ai_engine import analyze_research_document, generate_local_embedding
import analytics
import ai_service

app = FastAPI(
    title="Research Nexus API",
    description="AI Research Workspace & University Knowledge Graph Platform",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers middleware: add conservative defaults to reduce XSS/iframe risks.
@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    # Content-Security-Policy: keep it restrictive; allow self and basic sources.
    csp = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval';" \
          "style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:;"
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return response


# Startup validation to prevent dangerous misconfiguration (e.g., MOCK_AI in prod).
@app.on_event("startup")
def validate_configuration():
    """Validate runtime environment and surface clear errors early.

    - Prevent MOCK_AI from being enabled when NODE_ENV=production.
    - Require the OpenRouter provider configuration for production-like usage.
    """
    node_env = os.getenv("NODE_ENV", "").strip().lower()
    mock_env = os.getenv("MOCK_AI", "").strip().lower()
    if node_env == "production" and mock_env in ("true", "1", "yes"):
        raise RuntimeError("MOCK_AI must not be enabled in production. Set MOCK_AI=false in your environment.")

    provider = os.getenv("AI_PROVIDER", "openrouter").strip().lower() or "openrouter"
    if provider not in ("", "openrouter"):
        raise RuntimeError("AI_PROVIDER must be set to 'openrouter'. This backend intentionally does not silently switch to Gemini or mock mode.")

    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        import logging

        logger = logging.getLogger(__name__)
        logger.warning("OPENROUTER_API_KEY is not set — OpenRouter will be unavailable.")


# Lightweight safe config endpoint so the frontend can detect mock mode without exposing secrets.
from google_ai_provider import is_google_ai_configured, is_google_ai_model_supported

@app.get("/api/config")
def get_config():
    from google_ai_provider import is_google_ai_model_supported, list_available_models, is_google_api_key_valid

    provider = os.getenv("AI_PROVIDER", "openrouter").strip().lower() or "openrouter"
    available_models = list_available_models()
    key_valid = is_google_api_key_valid()

    return {
        "mock_ai": ai_service.is_mock_ai_enabled(),
        "google_ai_configured": is_google_ai_configured(),
        "openrouter_configured": is_google_ai_configured(),
        "api_key_configured": is_google_ai_configured(),
        "google_api_key_valid": key_valid,
        "openrouter_api_key_valid": key_valid,
        "google_ai_model_supported": is_google_ai_model_supported(),
        "openrouter_model_supported": is_google_ai_model_supported(),
        "available_models": available_models,
        "provider_status": "configured" if is_google_ai_configured() else "missing",
        "model": ai_service.get_model_name(),
        "ai_provider": provider,
        "provider": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "compatibility_issue": None,
    }


# Pydantic Schemas for Requests
class NoteCreateReq(BaseModel):
    title: str
    content: str = ""
    tags: Optional[List[str]] = Field(default_factory=list)
    is_pinned: bool = False

class NoteUpdateReq(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None

class AIDocReq(BaseModel):
    document_id: Optional[str] = None
    text: Optional[str] = None
    title: Optional[str] = None

class AICompareReq(BaseModel):
    document_id_a: str
    document_id_b: str

class AIChatReq(BaseModel):
    query: str
    document_ids: Optional[List[str]] = Field(default_factory=list)


class AIActionReq(AIDocReq):
    action: str


class ResetWorkspaceReq(BaseModel):
    confirm: bool = False


def get_demo_research():
    return [
        {
            "title": "Federated Learning for Privacy-Preserving Medical Imaging",
            "filename": "federated_learning_medical_imaging.pdf",
            "department": "Computer Science",
            "researcher": "Dr. Alice Smith",
            "document_type": "PDF",
            "abstract": "We present a decentralized federated learning framework with differential privacy for multi-site clinical diagnostics on MRI scans, evaluated extensively on the MIMIC-IV medical imaging benchmark without sharing patient records.",
            "content": """# Federated Learning for Privacy-Preserving Medical Imaging
Author: Dr. Alice Smith (Department of Computer Science)
Keywords: Federated Learning, Differential Privacy, Medical Imaging, MIMIC-IV, CNN, PyTorch, Healthcare AI

## Abstract
Clinical institutions face stringent regulatory boundaries preventing the aggregation of patient records. We propose a decentralized federated learning framework using Differential Privacy and Convolutional Neural Networks for privacy-preserving medical imaging. Our experiments on the MIMIC-IV dataset and clinical MRI scans demonstrate robust diagnostic classification accuracy while guaranteeing patient privacy bounds under strict epsilon differential privacy budgets.

## Methodology
The framework integrates PyTorch distributed backends with secure aggregation protocols. Local model updates compute gradient perturbations evaluated against the MIMIC-IV benchmark. Convolutional Neural Networks serve as the primary feature extractor for diagnostic lesion segmentation.
"""
        },
        {
            "title": "Collaborative Clinical Diagnostics with Federated Models",
            "filename": "collaborative_clinical_diagnostics.pdf",
            "department": "Biomedical Engineering",
            "researcher": "Dr. Brian Lee",
            "document_type": "PDF",
            "abstract": "Investigating collaborative hospital diagnostic pipelines using federated neural networks on the MIMIC-IV clinical dataset. Evaluates diagnostic models for radiological triage across disparate hospital networks.",
            "content": """# Collaborative Clinical Diagnostics with Federated Models
Author: Dr. Brian Lee (Department of Biomedical Engineering)
Keywords: Federated Learning, Medical Imaging, MIMIC-IV, Diagnostic Models, CNN, Deep Learning

## Abstract
Collaborative medical image analysis enables multi-center clinical studies without centralizing sensitive patient imaging archives. We deploy deep learning diagnostic models trained across hospital nodes utilizing the MIMIC-IV clinical dataset and chest radiographs. 

## Experimental Evaluation
Using Convolutional Neural Networks and Federated Learning, we benchmark diagnostic accuracy for pulmonary abnormalities against centralized baselines on the MIMIC-IV ICU cohorts, confirming high generalizability across disparate clinical sites.
"""
        },
        {
            "title": "Deep Learning and Computer Vision for Crop Disease Diagnosis",
            "filename": "crop_disease_computer_vision.md",
            "department": "Agriculture",
            "researcher": "Dr. Carla Rao",
            "document_type": "MARKDOWN",
            "abstract": "Deploying convolutional computer vision models on the PlantVillage dataset for automated detection of agricultural leaf pathogens and crop health management.",
            "content": """# Deep Learning and Computer Vision for Crop Disease Diagnosis
Author: Dr. Carla Rao (Department of Agricultural & Life Sciences)
Keywords: Computer Vision, Plant Disease Detection, PlantVillage, Convolutional Neural Networks, Deep Learning

## Abstract
Early detection of foliar pathogens is essential for food security and crop yield preservation. We utilize deep Convolutional Neural Networks to classify visual crop leaf anomalies across thousands of images from the PlantVillage dataset. Our transfer learning approach achieves rapid diagnostic speed suitable for edge mobile deployment in field environments.
"""
        },
        {
            "title": "Satellite Remote Sensing and Earth Observation for Environmental Monitoring",
            "filename": "satellite_remote_sensing_environment.md",
            "department": "Environmental Science",
            "researcher": "Dr. David Kumar",
            "document_type": "MARKDOWN",
            "abstract": "Automated land cover classification and climate ecosystem monitoring using spectral analysis of Landsat and Sentinel-2 satellite imagery archives.",
            "content": """# Satellite Remote Sensing and Earth Observation for Environmental Monitoring
Author: Dr. David Kumar (Department of Environmental Science)
Keywords: Satellite Image Analysis, Remote Sensing, Environmental Monitoring, Landsat, Sentinel-2, Land Cover Classification

## Abstract
Environmental changes demand continuous planetary observation. We present an automated spectral analysis pipeline for multispectral satellite image analysis. Leveraging decades of Landsat earth observation data alongside Sentinel-2 high-resolution imagery, our system accurately tracks deforestation, urban sprawl, and watershed dynamics across fragile ecosystems.
"""
        },
        {
            "title": "Multimodal AI for Agricultural and Ecological Risk Prediction",
            "filename": "multimodal_agricultural_risk.pdf",
            "department": "Data Science",
            "researcher": "Dr. Elena Patel",
            "document_type": "PDF",
            "abstract": "Predictive ecological and agricultural risk forecasting combining Landsat satellite image analysis, climate weather telemetry, and multimodal neural networks.",
            "content": """# Multimodal AI for Agricultural and Ecological Risk Prediction
Author: Dr. Elena Patel (Department of Data Science)
Keywords: Multimodal AI, Satellite Image Analysis, Agricultural Risk, Landsat, PyTorch, Deep Learning

## Abstract
Agricultural productivity is exposed to escalating climate variability. We develop a Multimodal AI architecture integrating Landsat surface reflectance imagery with meteorological sensor streams. Built in PyTorch, the multimodal model predicts localized drought severity and regional crop yield vulnerabilities up to six weeks in advance.
"""
        },
        {
            "title": "High-Throughput Genomic Variant Analysis with Transformer Pipelines",
            "filename": "genomic_variant_transformer_pipeline.py",
            "department": "Genomics",
            "researcher": "Dr. Frank Chen",
            "document_type": "CODE_SCRIPT",
            "abstract": "Deep Transformer neural architecture implemented in PyTorch for high-throughput oncological variant prioritization on the TCGA cancer genomics dataset.",
            "content": """# High-Throughput Genomic Variant Analysis with Transformer Pipelines
Author: Dr. Frank Chen (Institute for Genomic Biology)
Keywords: Transformer, Genomics, TCGA, Oncology Informatics, PyTorch, Single-Cell RNA-Seq

\"\"\"
Genomic Variant Priority Pipeline using PyTorch Transformers.
Evaluates somatic and germline mutations against The Cancer Genome Atlas (TCGA) repository.
\"\"\"
import torch
import torch.nn as nn
from transformers import AutoModel

class GenomicTransformerModel(nn.Module):
    def __init__(self, d_model=768):
        super().__init__()
        self.transformer = AutoModel.from_pretrained("bert-base-uncased")
        self.oncology_head = nn.Linear(d_model, 10) # TCGA tumor classification
"""
        }
    ]


def get_demo_notes():
    return [
        {
            "title": "Cross-Department Medical Imaging Ideas",
            "content": """# Medical Imaging Research Connections

## Key Cross-Disciplinary Finding
Observed that [[Computer Science]] and [[Biomedical Engineering]] are both independently evaluating [[Federated Learning]] pipelines on the [[MIMIC-IV]] dataset!

## Joint Grant Proposal
- Combine Dr. Alice Smith's privacy-preserving gradient aggregation with Dr. Brian Lee's multi-hospital diagnostic triage metrics.
- Target NSF/NIH joint smart healthcare award.

## Follow-up Questions
- Does [[Differential Privacy]] degrade small lesion boundary segmentation?
- Can we evaluate [[Convolutional Neural Networks]] alongside [[Transformer]] sequence models?
""",
            "tags": ["healthcare", "federated_learning", "collaboration"],
            "is_pinned": True
        },
        {
            "title": "Earth Observation & Climate Risk",
            "content": """# Satellite Image Analytics Synthesis

## Notes on Datasets
- [[Landsat]] provides multi-decadal time-series surface reflectance.
- [[Sentinel-2]] provides high-resolution 10m bands for localized crop canopy health.

## Methodology
Both [[Environmental Science]] and [[Data Science]] utilize [[Satellite Image Analysis]] for [[Land Cover Classification]].
""",
            "tags": ["environmental", "remote_sensing", "earth_observation"],
            "is_pinned": False
        }
    ]


def seed_database():
    conn = get_db_conn()
    is_pg = db.is_postgres
    ph = "%s" if is_pg else "?"
    doc_count = conn.execute(f"SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
    if doc_count == 0:
        for p in get_demo_research():
            doc_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            
            conn.execute(
                f"INSERT INTO documents (id, title, filename, department, document_type, content, abstract, created_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                (doc_id, p["title"], p["filename"], p["department"], p["document_type"], p["content"], p["abstract"], created_at)
            )
            
            result, embedding_vec, _ = analyze_research_document(p["content"], p["filename"], p["department"])
            
            paper_id = add_entity(conn, p["title"], "PAPER", p["abstract"])
            link_doc_entity(conn, doc_id, paper_id)
            
            dept_id = add_entity(conn, p["department"], "DEPARTMENT", f"University department ({p['department']})")
            link_doc_entity(conn, doc_id, dept_id)
            add_relationship(conn, paper_id, dept_id, "BELONGS_TO", 0.95, doc_id)
            
            res_id = add_entity(conn, p["researcher"], "RESEARCHER", f"Faculty member in {p['department']}")
            link_doc_entity(conn, doc_id, res_id)
            add_relationship(conn, res_id, paper_id, "AUTHORED", 0.98, doc_id)
            add_relationship(conn, res_id, dept_id, "AFFILIATED_WITH", 0.95, doc_id)
            
            for ent in result.get("entities", []):
                if ent["type"] in ("PAPER", "RESEARCHER", "DEPARTMENT"):
                    continue
                eid = add_entity(conn, ent["name"], ent["type"], ent.get("description", ""))
                link_doc_entity(conn, doc_id, eid)
                
                rel_type = "RELATED_TO"
                if ent["type"] == "DATASET": rel_type = "USES_DATASET"
                elif ent["type"] == "METHOD": rel_type = "USES_METHOD"
                elif ent["type"] == "TECHNOLOGY": rel_type = "USES_TECHNOLOGY"
                elif ent["type"] == "TOPIC": rel_type = "STUDIES"
                
                add_relationship(conn, paper_id, eid, rel_type, 0.90, doc_id)

            save_chunk(conn, doc_id, p["content"][:4000], embedding_vec)

    # Seed Demo Notes if empty
    note_count = conn.execute("SELECT COUNT(*) AS n FROM notes").fetchone()["n"]
    if note_count == 0:
        for note in get_demo_notes():
            create_note(conn, note["title"], note["content"], note["tags"], note["is_pinned"])

    conn.commit()
    conn.close()


# seed_database()  # Disabled - start with empty workspace


# ============================================================================
# HEALTH & METRICS ROUTES
# ============================================================================

@app.get("/api/health")
def health():
    db_status = db.get_status()
    has_openrouter_key = bool(os.getenv("OPENROUTER_API_KEY"))
    mock_mode = ai_service.is_mock_ai_enabled()
    model_supported = is_google_ai_model_supported()
    provider_name = os.getenv("AI_PROVIDER", "openrouter").strip().lower() or "openrouter"

    return {
        "status": "healthy",
        "service": "Research Nexus Workspace API",
        "version": "2.1.0",
        "mock_ai_mode": mock_mode,
        "active_mode": (
            "Mock Development Mode" if mock_mode
            else "OpenRouter Gemma Mode" if has_openrouter_key and model_supported and provider_name == "openrouter"
            else "OpenRouter not configured or model unsupported"
        ),
        "ai_engine": {
            "mode": f"OpenRouter ({ai_service.get_model_name()})" if (has_openrouter_key and not mock_mode and model_supported and provider_name == "openrouter") else "Deterministic Local NLP & Semantic Engine",
            "openrouter_configured": has_openrouter_key,
            "provider": provider_name,
            "model": ai_service.get_model_name(),
            "model_supported": model_supported,
            "compatibility_issue": None,
        },
        "database_engine": {
            "mode": db_status["engine"],
            "is_postgres": db_status["is_postgres"],
            "has_pgvector": db_status["is_postgres"]
        },
        "capabilities": [
            "NotebookLM Document Workspace",
            "Obsidian Connected Notes & [[Wikilinks]]",
            "AI Summary, Methodology & Question Generation",
            "Grounded Chat with Document Citations",
            "Multi-Document Comparative Analysis",
            "First-Class Dataset Matching",
            "Multi-View Knowledge Graphs (Global / Note / Doc)"
        ]
    }


@app.get("/api/stats")
def stats():
    conn = get_db_conn()
    doc_count = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
    ent_count = conn.execute("SELECT COUNT(*) AS n FROM entities").fetchone()["n"]
    rel_count = conn.execute("SELECT COUNT(*) AS n FROM relationships").fetchone()["n"]
    note_count = conn.execute("SELECT COUNT(*) AS n FROM notes WHERE is_archived = 0").fetchone()["n"]
    
    datasets = analytics.get_dataset_matching(conn)
    cross_dept_datasets = len([d for d in datasets if d["is_cross_department"]])
    collabs = analytics.get_collaborations(conn)
    redundancies = analytics.get_redundancy(conn)
    
    conn.close()
    return {
        "documents": doc_count,
        "entities": ent_count,
        "relationships": rel_count,
        "notes": note_count,
        "total_datasets": len(datasets),
        "cross_department_datasets": cross_dept_datasets,
        "collaboration_opportunities": len(collabs),
        "redundancies_detected": len(redundancies)
    }


# ============================================================================
# DOCUMENTS REPOSITORY ROUTES
# ============================================================================

@app.get("/api/documents")
def get_documents():
    conn = get_db_conn()
    rows = conn.execute("SELECT id, title, filename, department, document_type, abstract, created_at FROM documents ORDER BY created_at DESC").fetchall()
    
    docs = []
    ph = db.ph
    for r in rows:
        d = dict(r)
        # Add entity count for card
        ent_count = conn.execute(f"SELECT COUNT(*) AS n FROM document_entities WHERE document_id = {ph}", (d["id"],)).fetchone()["n"]
        d["entities_count"] = ent_count
        d["status"] = "Analyzed"
        docs.append(d)
        
    conn.close()
    return docs


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    conn = get_db_conn()
    ph = db.ph
    doc = conn.execute(f"SELECT * FROM documents WHERE id = {ph}", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")
        
    ents = conn.execute(f"""
        SELECT e.id, e.name, e.entity_type, e.description 
        FROM entities e 
        JOIN document_entities de ON de.entity_id = e.id 
        WHERE de.document_id = {ph}
        ORDER BY e.entity_type, e.name
    """, (doc_id,)).fetchall()
    
    conn.close()
    return {
        "document": dict(doc),
        "entities": [dict(e) for e in ents]
    }


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    department: Optional[str] = Form(None)
):
    try:
        data = await file.read()
        parsed = parse_document(data, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File parsing error: {e}")

    conn = get_db_conn()
    ph = db.ph
    doc_id = str(uuid.uuid4())
    doc_dept = department or parsed.get("department") or "Interdisciplinary Research"
    created_at = datetime.now(timezone.utc).isoformat()

    conn.execute(
        f"INSERT INTO documents (id, title, filename, department, document_type, content, abstract, created_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
        (doc_id, parsed["title"], file.filename, doc_dept, parsed["document_type"], parsed["content"], parsed["abstract"], created_at)
    )
    conn.commit()
    conn.close()

    return {
        "id": doc_id,
        "title": parsed["title"],
        "document_type": parsed["document_type"],
        "filename": file.filename,
        "department": doc_dept,
        "status": "uploaded",
        "message": "Document parsed successfully."
    }


@app.post("/api/analyze/{doc_id}")
def analyze_document(doc_id: str):
    conn = get_db_conn()
    ph = db.ph
    doc = conn.execute(f"SELECT * FROM documents WHERE id = {ph}", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")

    result, embedding_vec, mode = analyze_research_document(doc["content"], doc["filename"], doc["department"])

    paper_id = add_entity(conn, doc["title"], "PAPER", doc["abstract"] or f"Research document: {doc['title']}")
    link_doc_entity(conn, doc_id, paper_id)

    dept_name = doc["department"] if doc["department"] != "Unassigned" else (result.get("department") or "Interdisciplinary Research")
    dept_id = add_entity(conn, dept_name, "DEPARTMENT", f"University department ({dept_name})")
    link_doc_entity(conn, doc_id, dept_id)
    add_relationship(conn, paper_id, dept_id, "BELONGS_TO", 0.95, doc_id)

    # Keep a name-to-ID index so a validated model relationship can be persisted
    # exactly as supplied, rather than being reduced to a generic paper link.
    entity_ids = {
        doc["title"].casefold(): paper_id,
        dept_name.casefold(): dept_id,
    }
    extracted_title = str(result.get("title", "")).strip()
    if extracted_title:
        entity_ids[extracted_title.casefold()] = paper_id

    for r in result.get("researchers", []):
        r_name = r.get("name") if isinstance(r, dict) else str(r)
        if r_name:
            res_id = add_entity(conn, r_name, "RESEARCHER", f"Researcher in {dept_name}")
            link_doc_entity(conn, doc_id, res_id)
            entity_ids[r_name.casefold()] = res_id
            add_relationship(conn, res_id, paper_id, "AUTHORED", 0.95, doc_id)
            add_relationship(conn, res_id, dept_id, "AFFILIATED_WITH", 0.90, doc_id)

    for ent in result.get("entities", []):
        ename = ent.get("name")
        etype = ent.get("type", "TOPIC")
        edesc = ent.get("description", "")
        if ename and etype not in ("PAPER", "RESEARCHER", "DEPARTMENT"):
            eid = add_entity(conn, ename, etype, edesc)
            link_doc_entity(conn, doc_id, eid)
            entity_ids[ename.casefold()] = eid

            rel_type = "RELATED_TO"
            if etype == "DATASET": rel_type = "USES_DATASET"
            elif etype == "METHOD": rel_type = "USES_METHOD"
            elif etype == "TECHNOLOGY": rel_type = "USES_TECHNOLOGY"
            elif etype == "TOPIC": rel_type = "STUDIES"

            add_relationship(conn, paper_id, eid, rel_type, 0.90, doc_id)

    # The provider's allowed relationship set is validated before persistence.
    # supported, resolvable relationships in addition to the baseline graph links.
    for rel in result.get("relationships", []):
        if not isinstance(rel, dict):
            continue
        source_id = entity_ids.get(str(rel.get("source", "")).strip().casefold())
        target_id = entity_ids.get(str(rel.get("target", "")).strip().casefold())
        relation = str(rel.get("relation", "")).strip().upper()
        if source_id and target_id and relation:
            try:
                confidence = max(0.0, min(1.0, float(rel.get("confidence", 0.7))))
            except (TypeError, ValueError):
                confidence = 0.7
            add_relationship(conn, source_id, target_id, relation, confidence, doc_id)

    save_chunk(conn, doc_id, doc["content"][:4000], embedding_vec)

    conn.commit()
    conn.close()

    return {
        "status": "analyzed",
        "document_id": doc_id,
        "title": doc["title"],
        "ai_engine_mode": mode,
        "entities_extracted": len(result.get("entities", [])),
        "researchers_found": len(result.get("researchers", [])),
        "extraction_summary": result
    }


@app.delete("/api/documents/{doc_id}")
def delete_document_route(doc_id: str):
    conn = get_db_conn()
    deleted = delete_document(conn, doc_id)
    conn.commit()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "id": doc_id}


class DocumentRenameReq(BaseModel):
    title: str


@app.patch("/api/documents/{doc_id}")
def rename_document(doc_id: str, payload: DocumentRenameReq):
    new_title = payload.title.strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    conn = get_db_conn()
    ph = db.ph
    existing = conn.execute(f"SELECT id FROM documents WHERE id = {ph}", (doc_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")
    conn.execute(f"UPDATE documents SET title = {ph} WHERE id = {ph}", (new_title, doc_id))
    conn.commit()
    conn.close()
    return {"status": "renamed", "id": doc_id, "title": new_title}


# ============================================================================
# OBSIDIAN-STYLE NOTES ROUTES
# ============================================================================

@app.get("/api/notes")
def list_notes(
    q: Optional[str] = Query(None),
    include_archived: bool = Query(False)
):
    conn = get_db_conn()
    notes = get_notes(conn, query=q, include_archived=include_archived)
    conn.close()
    return notes


@app.post("/api/notes")
def create_new_note(payload: NoteCreateReq):
    conn = get_db_conn()
    note = create_note(conn, payload.title, payload.content, payload.tags, payload.is_pinned)
    conn.commit()
    conn.close()
    return note


@app.get("/api/notes/{note_id}")
def get_single_note(note_id: str):
    conn = get_db_conn()
    note = get_note_by_id(conn, note_id)
    conn.close()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@app.put("/api/notes/{note_id}")
def update_existing_note(note_id: str, payload: NoteUpdateReq):
    conn = get_db_conn()
    updated = update_note(
        conn,
        note_id,
        title=payload.title,
        content=payload.content,
        tags=payload.tags,
        is_pinned=payload.is_pinned,
        is_archived=payload.is_archived
    )
    conn.commit()
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Note not found")
    return updated


@app.delete("/api/notes/{note_id}")
def delete_single_note(note_id: str):
    conn = get_db_conn()
    success = delete_note(conn, note_id)
    conn.commit()
    conn.close()
    if not success:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "deleted", "id": note_id}


@app.post("/api/notes/{note_id}/duplicate")
def duplicate_existing_note(note_id: str):
    conn = get_db_conn()
    dup = duplicate_note(conn, note_id)
    conn.commit()
    conn.close()
    if not dup:
        raise HTTPException(status_code=404, detail="Note not found")
    return dup


# ============================================================================
# NOTEBOOKLM-STYLE AI WORKSPACE ACTIONS
# ============================================================================

def _resolve_document_content(payload: AIDocReq) -> tuple[str, str, str, str, str]:
    """Helper to fetch document content by id or fallback to payload text."""
    if payload.document_id:
        conn = get_db_conn()
        ph = db.ph
        doc = conn.execute(f"SELECT * FROM documents WHERE id = {ph}", (payload.document_id,)).fetchone()
        conn.close()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc["content"], doc["filename"], doc["title"], doc["department"], "Dr. Lead Author"
    elif payload.text:
        return payload.text, "research_text.txt", payload.title or "Research Document", "Interdisciplinary", "Author"
    else:
        raise HTTPException(status_code=400, detail="Must provide either document_id or text")


@app.post("/api/ai/summarize")
def ai_summarize(payload: AIDocReq):
    text, filename, title, _, _ = _resolve_document_content(payload)
    return ai_service.summarize_document(text, filename, title)


@app.post("/api/ai/analyze")
def ai_analyze(payload: AIDocReq):
    text, filename, title, _, _ = _resolve_document_content(payload)
    return ai_service.deep_analyze_document(text, filename, title)


@app.post("/api/ai/explain")
def ai_explain(payload: AIDocReq):
    text, filename, title, _, _ = _resolve_document_content(payload)
    return ai_service.explain_document(text, filename, title)


@app.post("/api/ai/methodology")
def ai_methodology(payload: AIDocReq):
    text, filename, title, _, _ = _resolve_document_content(payload)
    return ai_service.analyze_methodology(text, filename, title)


@app.post("/api/ai/research-ideas")
def ai_research_ideas(payload: AIDocReq):
    text, filename, title, _, _ = _resolve_document_content(payload)
    return ai_service.generate_research_ideas(text, filename, title)


@app.post("/api/ai/questions")
def ai_questions(payload: AIDocReq):
    text, filename, title, _, _ = _resolve_document_content(payload)
    return ai_service.generate_questions(text, filename, title)


@app.post("/api/ai/generate-note")
def ai_generate_note(payload: AIDocReq):
    text, filename, title, department, researcher = _resolve_document_content(payload)
    return ai_service.generate_research_note(text, filename, title, department, researcher)


@app.post("/api/ai/action")
def ai_document_action(payload: AIActionReq):
    """Run a secondary, evidence-grounded document action through the AI service."""
    text, filename, title, department, researcher = _resolve_document_content(payload)
    return ai_service.run_document_action(
        payload.action, text, filename, title, department, researcher,
    )


@app.post("/api/ai/compare")
def ai_compare(payload: AICompareReq):
    conn = get_db_conn()
    ph = db.ph
    doc_a = conn.execute(f"SELECT * FROM documents WHERE id = {ph}", (payload.document_id_a,)).fetchone()
    doc_b = conn.execute(f"SELECT * FROM documents WHERE id = {ph}", (payload.document_id_b,)).fetchone()
    conn.close()
    if not doc_a or not doc_b:
        raise HTTPException(status_code=404, detail="One or both documents not found")
    return ai_service.compare_documents(dict(doc_a), dict(doc_b))


@app.post("/api/ai/chat")
def ai_chat(payload: AIChatReq):
    conn = get_db_conn()
    ph = db.ph
    documents = []
    if payload.document_ids:
        for did in payload.document_ids:
            row = conn.execute(f"SELECT * FROM documents WHERE id = {ph}", (did,)).fetchone()
            if row:
                documents.append(dict(row))
    else:
        # Fallback to all documents
        rows = conn.execute("SELECT * FROM documents LIMIT 3").fetchall()
        documents = [dict(r) for r in rows]
    conn.close()

    if not documents:
        raise HTTPException(status_code=404, detail="No source documents found for chat")
    return ai_service.chat_with_sources(payload.query, documents)


# ============================================================================
# MULTI-VIEW GRAPH ROUTES
# ============================================================================

@app.get("/api/graph")
def get_global_graph(type: Optional[str] = None):
    conn = get_db_conn()
    graph_data = analytics.get_graph_data(conn, type_filter=type)
    
    # Also attach Note nodes into the global graph if notes exist!
    notes = get_notes(conn)
    for n in notes:
        graph_data["nodes"].append({
            "id": n["id"],
            "label": n["title"],
            "type": "NOTE",
            "description": "Obsidian Research Note",
            "degree": len(n.get("wikilinks", [])) + 1
        })
        for link in n.get("wikilinks", []):
            ph = db.ph
            ent = conn.execute(f"SELECT id FROM entities WHERE lower(name) = lower({ph})", (link.strip(),)).fetchone()
            if ent:
                graph_data["edges"].append({
                    "id": f"note_edge_{n['id']}_{ent['id']}",
                    "source": n["id"],
                    "target": ent["id"],
                    "label": "REFERENCES",
                    "confidence": 1.0,
                    "source_name": n["title"],
                    "target_name": link
                })

    conn.close()
    return graph_data


@app.get("/api/graph/note/{note_id}")
def get_note_graph(note_id: str):
    conn = get_db_conn()
    g = get_note_graph_data(conn, note_id)
    conn.close()
    return g


@app.get("/api/graph/document/{doc_id}")
def get_document_graph(doc_id: str):
    conn = get_db_conn()
    g = get_document_graph_data(conn, doc_id)
    conn.close()
    return g


# ============================================================================
# DATASETS, INSIGHTS & SEARCH ROUTES
# ============================================================================

@app.get("/api/datasets")
@app.get("/api/datasets/matching")
def get_datasets_matching():
    conn = get_db_conn()
    datasets = analytics.get_dataset_matching(conn)
    cross_dept_count = len([d for d in datasets if d["is_cross_department"]])
    conn.close()
    
    return {
        "total_datasets": len(datasets),
        "cross_department_matches_count": cross_dept_count,
        "headline": f"{cross_dept_count} Cross-Department Dataset Connections Detected" if cross_dept_count > 0 else "Dataset Inventory Active",
        "datasets": datasets
    }


@app.get("/api/entities")
def get_entities(type: Optional[str] = None):
    conn = get_db_conn()
    ph = db.ph
    if type and type.upper() != "ALL":
        rows = conn.execute(f"SELECT * FROM entities WHERE entity_type = {ph} ORDER BY name", (type.upper(),)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM entities ORDER BY entity_type, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/entities/{entity_id}")
def get_entity_detail(entity_id: str):
    conn = get_db_conn()
    ph = db.ph
    entity = conn.execute(f"SELECT * FROM entities WHERE id = {ph}", (entity_id,)).fetchone()
    if not entity:
        conn.close()
        raise HTTPException(status_code=404, detail="Entity not found")

    docs = conn.execute("""
        SELECT d.id, d.title, d.department, d.document_type 
        FROM documents d 
        JOIN document_entities de ON de.document_id = d.id 
        WHERE de.entity_id = ?
    """, (entity_id,)).fetchall()

    relationships = conn.execute("""
        SELECT r.*, s.name as source_name, s.entity_type as source_type, t.name as target_name, t.entity_type as target_type
        FROM relationships r
        JOIN entities s ON s.id = r.source_entity_id
        JOIN entities t ON t.id = r.target_entity_id
        WHERE r.source_entity_id = ? OR r.target_entity_id = ?
    """, (entity_id, entity_id)).fetchall()

    conn.close()
    return {
        "entity": dict(entity),
        "documents": [dict(d) for d in docs],
        "relationships": [dict(r) for r in relationships]
    }


@app.get("/api/search")
def search(q: str = Query(..., min_length=1)):
    conn = get_db_conn()
    results = analytics.search_research(conn, query=q, limit=12)
    conn.close()
    return results


@app.get("/api/collaborations")
def get_collaborations():
    conn = get_db_conn()
    collaborations = analytics.get_collaborations(conn)
    conn.close()
    return collaborations


@app.get("/api/redundancy")
def get_redundancy():
    conn = get_db_conn()
    redundancies = analytics.get_redundancy(conn)
    conn.close()
    return redundancies


# ============================================================================
# RESET WORKSPACE & DEMO ROUTES
# ============================================================================

@app.post("/api/reset/workspace")
def reset_workspace(payload: ResetWorkspaceReq = Body(default=ResetWorkspaceReq())):
    """Acknowledge a confirmed client-workspace reset without deleting research data."""
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to reset the current workspace view.")
    return {"status": "ok", "message": "Workspace view reset. Stored research data was not changed."}


@app.post("/api/reset/demo")
@app.post("/api/seed")
def reset_demo_data():
    if not db.is_postgres and db.sqlite_path.exists():
        try:
            db.sqlite_path.unlink()
        except Exception:
            pass
    db.init_db()
    seed_database()
    return {"status": "ok", "message": "Benchmark research papers and demo notes successfully re-seeded."}
