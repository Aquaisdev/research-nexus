import io
import zipfile
import os
import httpx

# The AI test cases exercise deterministic development responses explicitly.
os.environ.setdefault("MOCK_AI", "true")
from fastapi.testclient import TestClient
from main import app
import ai_service
import google_ai_provider as gap
from google_ai import _parse_extraction_response
from unittest.mock import patch, MagicMock

client = TestClient(app)

# Helper to create a test document
def create_test_document(title="Test Research Paper", department="Computer Science", content=None):
    if content is None:
        content = """# Test Research Paper
Author: Dr. Test User
Keywords: Machine Learning, Neural Networks, Testing

## Abstract
This is a test research paper to verify the upload and analysis pipeline works correctly.

## Methodology
We use a simple neural network to test the document processing pipeline.
"""
    files = {'file': (f'{title.lower().replace(" ", "_")}.md', content.encode(), 'text/markdown')}
    data = {'department': department}
    res = client.post('/api/upload', files=files, data=data)
    assert res.status_code == 200
    return res.json()['id']

# Helper to create a second test document for comparison tests
def create_test_document_2():
    content = """# Second Test Paper
Author: Dr. Another User
Keywords: Deep Learning, Computer Vision, Testing

## Abstract
Another test paper for comparison and multi-document tests.

## Methodology
We use convolutional neural networks for image classification tasks.
"""
    return create_test_document("Second Test Paper", "Data Science", content)

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
    assert gap.is_google_ai_configured() is True
    assert gap.get_model_name() == "google/gemma-4-31b-it"
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
    assert "documents" in data
    assert "entities" in data
    assert "relationships" in data
    assert "notes" in data
    assert "total_datasets" in data
    assert isinstance(data["documents"], int)
    assert isinstance(data["entities"], int)

def test_dataset_matching():
    res = client.get("/api/datasets")
    assert res.status_code == 200
    data = res.json()
    assert "datasets" in data
    assert "total_datasets" in data
    assert "cross_department_matches_count" in data
    assert isinstance(data["datasets"], list)
    assert isinstance(data["total_datasets"], int)

def test_notes_crud_and_wikilinks():
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

    get_res = client.get(f"/api/notes/{note_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == note_id

    up_res = client.put(f"/api/notes/{note_id}", json={
        "title": "Quantum AI Synthesis Updated",
        "content": "# Updated with [[Differential Privacy]]",
        "tags": ["quantum", "privacy"]
    })
    assert up_res.status_code == 200
    assert up_res.json()["title"] == "Quantum AI Synthesis Updated"
    assert "Differential Privacy" in up_res.json()["wikilinks"]

    dup_res = client.post(f"/api/notes/{note_id}/duplicate")
    assert dup_res.status_code == 200
    dup_note = dup_res.json()
    assert "Copy" in dup_note["title"]

    ng_res = client.get(f"/api/graph/note/{note_id}")
    assert ng_res.status_code == 200
    assert len(ng_res.json()["nodes"]) > 0

    del_res = client.delete(f"/api/notes/{note_id}")
    assert del_res.status_code == 200
    client.delete(f"/api/notes/{dup_note['id']}")

def test_ai_workspace_actions():
    doc_id = create_test_document()
    
    sum_res = client.post("/api/ai/summarize", json={"document_id": doc_id})
    assert sum_res.status_code == 200
    assert "markdown" in sum_res.json()

    an_res = client.post("/api/ai/analyze", json={"document_id": doc_id})
    assert an_res.status_code == 200
    assert "markdown" in an_res.json()

    exp_res = client.post("/api/ai/explain", json={"document_id": doc_id})
    assert exp_res.status_code == 200
    assert "markdown" in exp_res.json()

    meth_res = client.post("/api/ai/methodology", json={"document_id": doc_id})
    assert meth_res.status_code == 200
    assert "markdown" in meth_res.json()

    idea_res = client.post("/api/ai/research-ideas", json={"document_id": doc_id})
    assert idea_res.status_code == 200
    assert "markdown" in idea_res.json()

    q_res = client.post("/api/ai/questions", json={"document_id": doc_id})
    assert q_res.status_code == 200
    assert "markdown" in q_res.json()

    note_gen_res = client.post("/api/ai/generate-note", json={"document_id": doc_id})
    assert note_gen_res.status_code == 200
    assert "markdown" in note_gen_res.json()
    assert "[[" in note_gen_res.json()["markdown"]

    secondary_res = client.post("/api/ai/action", json={"document_id": doc_id, "action": "findings"})
    assert secondary_res.status_code == 200
    assert "markdown" in secondary_res.json()

def test_ai_compare():
    doc_id_a = create_test_document()
    doc_id_b = create_test_document_2()
    
    comp_res = client.post("/api/ai/compare", json={
        "document_id_a": doc_id_a,
        "document_id_b": doc_id_b
    })
    assert comp_res.status_code == 200
    assert "markdown" in comp_res.json()

def test_ai_chat_with_sources():
    doc_id = create_test_document()
    chat_res = client.post("/api/ai/chat", json={
        "query": "What methodology is used in this paper?",
        "document_ids": [doc_id]
    })
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert "response" in data
    assert "sources" in data

def test_document_and_global_graphs():
    doc_id = create_test_document()
    
    dg_res = client.get(f"/api/graph/document/{doc_id}")
    assert dg_res.status_code == 200
    assert len(dg_res.json()["nodes"]) > 0

    gg_res = client.get("/api/graph")
    assert gg_res.status_code == 200
    assert len(gg_res.json()["nodes"]) > 0

def test_delete_document():
    doc_id = create_test_document()
    
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
    doc_id = create_test_document("Original Title")
    
    res = client.patch(f"/api/documents/{doc_id}", json={"title": "Renamed Test Document"})
    assert res.status_code == 200
    assert res.json()["title"] == "Renamed Test Document"

    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.json()["document"]["title"] == "Renamed Test Document"

def test_rename_document_empty_title():
    doc_id = create_test_document("Original Title")
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

def _success_body(text: str = "Fallback response from free model."):
    return {"choices": [{"message": {"content": text}}]}

# 1. Free fallback list excludes primary and only includes :free models
def test_free_fallback_models_excludes_primary_and_nonfree(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    fake_models = [
        "minimax/minimax-m3:free",
        "nvidia/nemotron-3.5-lightning:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
    ]

    def fake_list_available_models():
        return fake_models

    with patch("google_ai_provider.list_available_models", fake_list_available_models):
        fallbacks = gap._get_free_fallback_models()
        assert "minimax/minimax-m3:free" not in fallbacks
        assert "openai/gpt-4o" not in fallbacks
        assert "anthropic/claude-3.5-sonnet" not in fallbacks
        assert all(":free" in m for m in fallbacks)


class MockResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data
        self.headers = {"content-type": "application/json"}
        self.text = str(json_data)
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=None, response=self)

# 2. generate_text tries primary, on 429 tries fallbacks, returns first success
def test_generate_text_429_falls_back_and_reports_model(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    call_count = {"n": 0}
    fallback_model_used = {"name": None}

    def fake_list_available_models():
        return ["minimax/minimax-m3:free", "nvidia/nemotron-3.5-lightning:free"]

    def fake_post(self, url, json=None, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return MockResponse(429, {"error": {"message": "Rate limit"}})
        fallback_model_used["name"] = json.get("model", "unknown")
        return MockResponse(200, _success_body("fallback ok"))

    with patch("google_ai_provider.list_available_models", fake_list_available_models):
        with patch("httpx.Client.post", fake_post):
            from google_ai_provider import generate_text
            result = generate_text("test prompt", "test")
            assert "fallback ok" in result
            assert call_count["n"] == 2
            assert fallback_model_used["name"] == "nvidia/nemotron-3.5-lightning:free"

# 3. Non-429 error does NOT trigger fallback
def test_non_429_error_does_not_trigger_fallback(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_list_available_models():
        return ["minimax/minimax-m3:free", "nvidia/nemotron-3.5-lightning:free"]

    class MockResponse500:
        status_code = 500
        headers = {"content-type": "application/json"}
        text = '{"error": {"message": "Server error"}}'
        def json(self):
            return {"error": {"message": "Server error"}}
        def raise_for_status(self):
            raise httpx.HTTPStatusError("500", request=None, response=self)

    def fake_post_fail(self, url, json=None, headers=None, timeout=None):
        return MockResponse500()

    with patch("google_ai_provider.list_available_models", fake_list_available_models):
        with patch("httpx.Client.post", fake_post_fail):
            from google_ai_provider import generate_text
            result = generate_text("test prompt", "test")
            assert result is None

# 4. All fallbacks rate-limited -> returns None
def test_all_fallbacks_rate_limited_returns_none(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_list_available_models():
        return ["minimax/minimax-m3:free", "nvidia/nemotron-3.5-lightning:free"]

    def fake_post_always_429(self, url, json=None, headers=None, timeout=None):
        return MockResponse(429, {"error": {"message": "Rate limit"}})

    with patch("google_ai_provider.list_available_models", fake_list_available_models):
        with patch("httpx.Client.post", fake_post_always_429):
            from google_ai_provider import generate_text
            result = generate_text("test prompt", "test")
            assert result is None

# 5. Last model used tracking
def test_get_last_model_used_reports_primary_on_success(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_list_available_models():
        return ["minimax/minimax-m3:free", "nvidia/nemotron-3.5-lightning:free"]

    def fake_post_ok(self, url, json=None, headers=None, timeout=None):
        return MockResponse(200, _success_body("primary ok"))

    with patch("google_ai_provider.list_available_models", fake_list_available_models):
        with patch("httpx.Client.post", fake_post_ok):
            from google_ai_provider import generate_text, get_last_model_used
            generate_text("test prompt", "test")
            assert get_last_model_used() == "minimax/minimax-m3:free"

# 6. AI Service provider string shows fallback model
def test_ai_service_provider_string_shows_fallback_model(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "minimax/minimax-m3:free")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    call_count = {"n": 0}

    def fake_list_available_models():
        return ["minimax/minimax-m3:free", "nvidia/nemotron-3.5-lightning:free"]

    def fake_post(self, url, json=None, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return MockResponse(429, {"error": {"message": "Rate limit"}})
        return MockResponse(200, _success_body("fallback ok"))

    with patch("google_ai_provider.list_available_models", fake_list_available_models):
        with patch("httpx.Client.post", fake_post):
            from ai_service import summarize_document
            result = summarize_document("test content", "test.txt", "Test")
            assert result.get("provider") is not None