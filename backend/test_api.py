import io
import zipfile
import os

# The AI test cases exercise deterministic development responses explicitly.
os.environ.setdefault("MOCK_AI", "true")
from fastapi.testclient import TestClient
from main import app
import ai_service
import google_ai_provider
from google_ai import _parse_extraction_response

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "mock_ai_mode" in data
    assert "capabilities" in data


def test_mock_ai_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("MOCK_AI", raising=False)
    assert ai_service.is_mock_ai_enabled() is False
    unavailable = ai_service.summarize_document("A study of MIMIC-IV.", "sample.txt", "Sample")
    assert unavailable["status"] == "unavailable"
    assert unavailable["mock"] is False


def test_gemma_provider_configuration_and_structured_validation(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "google/gemma-4-31b-it")
    assert google_ai_provider.is_google_ai_configured() is True
    assert google_ai_provider.get_model_name() == "google/gemma-4-31b-it"
    parsed = _parse_extraction_response('''{
      "title": "Paper",
      "researchers": [{"name": "Dr. Ada Lovelace", "department": "CS"}],
      "entities": [{"name": "MIMIC-IV", "type": "DATASET", "description": "benchmark"}],
      "relationships": [{"source": "Paper", "relation": "USES_DATASET", "target": "MIMIC-IV", "confidence": 0.9}]
    }''')
    assert parsed and parsed["entities"][0]["type"] == "DATASET"
    assert _parse_extraction_response("not-json") is None

def test_stats():
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["documents"] >= 5
    assert data["entities"] > 0
    assert data["relationships"] > 0
    assert data["notes"] >= 1
    assert data["total_datasets"] > 0

def test_dataset_matching():
    res = client.get("/api/datasets")
    assert res.status_code == 200
    data = res.json()
    assert "datasets" in data
    assert data["total_datasets"] > 0
    mimic = next((d for d in data["datasets"] if d["name"] == "MIMIC-IV"), None)
    assert mimic is not None
    assert mimic["is_cross_department"] is True

def test_notes_crud_and_wikilinks():
    # 1. Create note
    create_res = client.post("/api/notes", json={
        "title": "Quantum AI Synthesis",
        "content": "# Notes on [[Federated Learning]] and [[MIMIC-IV]]\nInvestigating cross-department synergy.",
        "tags": ["quantum", "ai"],
        "is_pinned": True
    })
    assert create_res.status_code == 200
    note = create_res.json()
    note_id = note["id"]
    assert note["title"] == "Quantum AI Synthesis"
    assert "Federated Learning" in note["wikilinks"]
    assert "MIMIC-IV" in note["wikilinks"]

    # 2. Get note by ID
    get_res = client.get(f"/api/notes/{note_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == note_id

    # 3. Update note
    up_res = client.put(f"/api/notes/{note_id}", json={
        "title": "Quantum AI Synthesis Updated",
        "content": "# Updated with [[Differential Privacy]]",
        "tags": ["quantum", "privacy"]
    })
    assert up_res.status_code == 200
    assert up_res.json()["title"] == "Quantum AI Synthesis Updated"
    assert "Differential Privacy" in up_res.json()["wikilinks"]

    # 4. Duplicate note
    dup_res = client.post(f"/api/notes/{note_id}/duplicate")
    assert dup_res.status_code == 200
    dup_note = dup_res.json()
    assert "Copy" in dup_note["title"]

    # 5. Note Graph
    ng_res = client.get(f"/api/graph/note/{note_id}")
    assert ng_res.status_code == 200
    assert len(ng_res.json()["nodes"]) > 0

    # 6. Delete notes
    del_res = client.delete(f"/api/notes/{note_id}")
    assert del_res.status_code == 200
    client.delete(f"/api/notes/{dup_note['id']}")

def test_ai_workspace_actions():
    # Get a document ID
    docs = client.get("/api/documents").json()
    assert len(docs) > 0
    doc_id = docs[0]["id"]

    # Summarize
    sum_res = client.post("/api/ai/summarize", json={"document_id": doc_id})
    assert sum_res.status_code == 200
    assert "markdown" in sum_res.json()

    # Deep Analyze
    an_res = client.post("/api/ai/analyze", json={"document_id": doc_id})
    assert an_res.status_code == 200
    assert "markdown" in an_res.json()

    # Explain
    exp_res = client.post("/api/ai/explain", json={"document_id": doc_id})
    assert exp_res.status_code == 200
    assert "markdown" in exp_res.json()

    # Methodology
    meth_res = client.post("/api/ai/methodology", json={"document_id": doc_id})
    assert meth_res.status_code == 200
    assert "markdown" in meth_res.json()

    # Research Ideas
    idea_res = client.post("/api/ai/research-ideas", json={"document_id": doc_id})
    assert idea_res.status_code == 200
    assert "markdown" in idea_res.json()

    # Questions
    q_res = client.post("/api/ai/questions", json={"document_id": doc_id})
    assert q_res.status_code == 200
    assert "markdown" in q_res.json()

    # Generate Note
    note_gen_res = client.post("/api/ai/generate-note", json={"document_id": doc_id})
    assert note_gen_res.status_code == 200
    assert "markdown" in note_gen_res.json()
    assert "[[" in note_gen_res.json()["markdown"]

    secondary_res = client.post("/api/ai/action", json={"document_id": doc_id, "action": "findings"})
    assert secondary_res.status_code == 200
    assert "markdown" in secondary_res.json()

def test_ai_compare():
    docs = client.get("/api/documents").json()
    assert len(docs) >= 2
    comp_res = client.post("/api/ai/compare", json={
        "document_id_a": docs[0]["id"],
        "document_id_b": docs[1]["id"]
    })
    assert comp_res.status_code == 200
    assert "markdown" in comp_res.json()

def test_ai_chat_with_sources():
    docs = client.get("/api/documents").json()
    chat_res = client.post("/api/ai/chat", json={
        "query": "What dataset is used for medical imaging in this paper?",
        "document_ids": [docs[0]["id"]]
    })
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert "response" in data
    assert "sources" in data
    assert len(data["sources"]) > 0

def test_document_and_global_graphs():
    docs = client.get("/api/documents").json()
    doc_id = docs[0]["id"]
    
    # Document Graph
    dg_res = client.get(f"/api/graph/document/{doc_id}")
    assert dg_res.status_code == 200
    assert len(dg_res.json()["nodes"]) > 0

    # Global Graph
    gg_res = client.get("/api/graph")
    assert gg_res.status_code == 200
    assert len(gg_res.json()["nodes"]) > 0


def test_delete_document():
    docs = client.get("/api/documents").json()
    assert len(docs) > 0
    doc_id = docs[0]["id"]

    res = client.delete(f"/api/documents/{doc_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "deleted"

    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 404


def test_delete_document_404():
    res = client.delete("/api/documents/nonexistent-id-00000000")
    assert res.status_code == 404


def test_delete_note_404():
    res = client.delete("/api/notes/nonexistent-id-00000000")
    assert res.status_code == 404


def test_rename_document():
    docs = client.get("/api/documents").json()
    assert len(docs) > 0
    doc_id = docs[0]["id"]

    res = client.patch(f"/api/documents/{doc_id}", json={"title": "Renamed Test Document"})
    assert res.status_code == 200
    assert res.json()["title"] == "Renamed Test Document"

    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.json()["document"]["title"] == "Renamed Test Document"

    client.patch(f"/api/documents/{doc_id}", json={"title": docs[0]["title"]})


def test_rename_document_empty_title():
    docs = client.get("/api/documents").json()
    doc_id = docs[0]["id"]
    res = client.patch(f"/api/documents/{doc_id}", json={"title": "  "})
    assert res.status_code == 400


def test_rename_document_404():
    res = client.patch("/api/documents/nonexistent-id-00000000", json={"title": "Test"})
    assert res.status_code == 404


def test_reset_routes():
    rejected = client.post("/api/reset/workspace")
    assert rejected.status_code == 400

    res_ws = client.post("/api/reset/workspace", json={"confirm": True})
    assert res_ws.status_code == 200

    res_demo = client.post("/api/reset/demo")
    assert res_demo.status_code == 200


# --------------------------------------------------------------------------- #
#  429 Free-Model Fallback Tests                                              #
# --------------------------------------------------------------------------- #

from unittest.mock import patch, MagicMock
import google_ai_provider as gap


def _make_openrouter_response(status_code: int, body: dict = None, content_type: str = "application/json"):
    """Helper to create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"content-type": content_type}
    resp.text = str(body or {})
    resp.json.return_value = body or {}
    return resp


def _success_body(text: str = "Fallback response from free model."):
    return {"choices": [{"message": {"content": text}}]}


def _rate_limit_body():
    return {"error": {"code": "429", "message": "Rate limit exceeded"}}


class _FakeHTTP429(Exception):
    """Simulates httpx.HTTPStatusError with status 429."""
    def __init__(self):
        self.response = MagicMock()
        self.response.status_code = 429


# 1. Free fallback list excludes primary and only includes :free models
def test_free_fallback_models_excludes_primary_and_nonfree(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    fake_models = [
        "minimax/minimax-m3:free",          # primary — excluded
        "nvidia/nemotron-3.5-lightning:free",
        "meta-llama/llama-4-scout:free",
        "google/gemma-4-31b-it",             # paid — excluded
        "anthropic/claude-3-haiku",          # paid — excluded
        "deepseek/deepseek-r1:free",
    ]
    monkeypatch.setattr(gap, "list_available_models", lambda: fake_models)

    fallbacks = gap._get_free_fallback_models()

    assert all(m.endswith(":free") for m in fallbacks), "Only :free models allowed"
    assert "minimax/minimax-m3:free" not in fallbacks, "Primary must not appear in fallbacks"
    assert "google/gemma-4-31b-it" not in fallbacks, "Paid model must not appear"
    assert "anthropic/claude-3-haiku" not in fallbacks, "Paid model must not appear"
    assert len(fallbacks) == 3


# 2. On 429, generate_text falls back to a free model and reports it via get_last_model_used
def test_generate_text_429_falls_back_and_reports_model(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    fake_models = [
        "minimax/minimax-m3:free",
        "nvidia/nemotron-3.5-lightning:free",
        "deepseek/deepseek-r1:free",
    ]
    monkeypatch.setattr(gap, "list_available_models", lambda: fake_models)

    call_log = []

    def fake_post(*args, **kwargs):
        model_used = (kwargs.get("json") or {}).get("model", "")
        call_log.append(model_used)
        if model_used == "minimax/minimax-m3:free":
            return _make_openrouter_response(429, _rate_limit_body())
        return _make_openrouter_response(200, _success_body(f"OK from {model_used}"))

    monkeypatch.setattr("httpx.Client.post", fake_post)

    result = gap.generate_text("system", "user content")
    gap._last_provider_error = ""  # reset for other tests

    assert result is not None, "Expected text from fallback"
    assert "OK from" in result
    assert call_log[0] == "minimax/minimax-m3:free", "Primary tried first"
    assert call_log[1] != "minimax/minimax-m3:free", "Fallback model was tried"
    assert call_log[1].endswith(":free"), "Fallback must be a :free model"
    assert gap.get_last_model_used() == call_log[1], "get_last_model_used must report fallback"


# 3. API response provider string includes fallback model name
def test_ai_service_provider_string_shows_fallback_model(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("MOCK_AI", "")

    fake_models = [
        "minimax/minimax-m3:free",
        "nvidia/nemotron-3.5-lightning:free",
    ]
    monkeypatch.setattr(gap, "list_available_models", lambda: fake_models)

    def fake_post(*args, **kwargs):
        model_used = (kwargs.get("json") or {}).get("model", "")
        if model_used == "minimax/minimax-m3:free":
            return _make_openrouter_response(429, _rate_limit_body())
        return _make_openrouter_response(200, _success_body("Fallback OK"))

    monkeypatch.setattr("httpx.Client.post", fake_post)

    result = ai_service.summarize_document("Some text.", "file.txt", "Title")
    gap._last_provider_error = ""

    assert result["status"] == "success"
    assert "OpenRouter" in result["provider"]
    assert "nvidia/nemotron-3.5-lightning:free" in result["provider"], \
        f"Provider string should contain fallback model, got: {result['provider']}"
    assert "minimax/minimax-m3:free" not in result["provider"], \
        "Provider string must NOT show the rate-limited primary model"


# 4. Non-429 error does NOT trigger fallback
def test_non_429_error_does_not_trigger_fallback(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    fake_models = ["minimax/minimax-m3:free", "nvidia/nemotron-3.5-lightning:free"]
    monkeypatch.setattr(gap, "list_available_models", lambda: fake_models)

    call_log = []

    def fake_post(*args, **kwargs):
        model_used = (kwargs.get("json") or {}).get("model", "")
        call_log.append(model_used)
        return _make_openrouter_response(500, {"error": {"message": "Server error"}})

    monkeypatch.setattr("httpx.Client.post", fake_post)

    result = gap.generate_text("system", "user content")
    gap._last_provider_error = ""

    assert result is None
    assert len(call_log) == 1, f"Only primary should be called on 500, got calls: {call_log}"
    assert call_log[0] == "minimax/minimax-m3:free"


# 5. When all fallbacks are also 429, result is None and error is set
def test_all_fallbacks_rate_limited_returns_none(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    fake_models = [
        "minimax/minimax-m3:free",
        "nvidia/nemotron-3.5-lightning:free",
        "deepseek/deepseek-r1:free",
    ]
    monkeypatch.setattr(gap, "list_available_models", lambda: fake_models)

    def fake_post(*args, **kwargs):
        return _make_openrouter_response(429, _rate_limit_body())

    monkeypatch.setattr("httpx.Client.post", fake_post)

    result = gap.generate_text("system", "user content")
    gap._last_provider_error = ""

    assert result is None
    assert gap.get_last_model_used() == "", "No model succeeded"


# 6. get_last_model_used reports primary on normal success
def test_get_last_model_used_reports_primary_on_success(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        return _make_openrouter_response(200, _success_body("Primary OK"))

    monkeypatch.setattr("httpx.Client.post", fake_post)

    result = gap.generate_text("system", "user content")
    assert result == "Primary OK"
    assert gap.get_last_model_used() == "minimax/minimax-m3:free"
