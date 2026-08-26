"""Gemma structured extraction adapter used by the document graph pipeline."""

import json
import os
import re
from typing import Any, Dict, Optional

from google_ai_provider import generate_text, is_google_ai_configured

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "ai_prompt.txt")
PROMPT = open(PROMPT_PATH).read() if os.path.exists(PROMPT_PATH) else ""

ALLOWED_ENTITY_TYPES = {"RESEARCHER", "DEPARTMENT", "TOPIC", "METHOD", "DATASET", "TECHNOLOGY", "INSTITUTION", "PAPER"}
ALLOWED_RELATIONSHIP_TYPES = {"AUTHORED", "STUDIES", "USES_METHOD", "USES_DATASET", "USES_TECHNOLOGY", "BELONGS_TO", "AFFILIATED_WITH", "RELATED_TO", "EXTENDS", "CITES"}

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "researchers": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "department": {"type": "string"}}, "required": ["name", "department"]}},
        "entities": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string", "enum": sorted(ALLOWED_ENTITY_TYPES)}, "description": {"type": "string"}}, "required": ["name", "type", "description"]}},
        "relationships": {"type": "array", "items": {"type": "object", "properties": {"source": {"type": "string"}, "relation": {"type": "string", "enum": sorted(ALLOWED_RELATIONSHIP_TYPES)}, "target": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["source", "relation", "target", "confidence"]}},
    },
    "required": ["title", "researchers", "entities", "relationships"],
}


def _parse_extraction_response(raw: str) -> Optional[Dict[str, Any]]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    entities = []
    for item in data.get("entities", []):
        if not isinstance(item, dict):
            continue
        name, kind = str(item.get("name", "")).strip(), str(item.get("type", "")).upper().strip()
        if name and kind in ALLOWED_ENTITY_TYPES:
            entities.append({"name": name, "type": kind, "description": str(item.get("description", "")).strip()})

    researchers = [
        {"name": str(item["name"]).strip(), "department": str(item.get("department", "")).strip()}
        for item in data.get("researchers", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    relationships = []
    for item in data.get("relationships", []):
        if not isinstance(item, dict):
            continue
        source, target = str(item.get("source", "")).strip(), str(item.get("target", "")).strip()
        relation = str(item.get("relation", "")).upper().strip()
        if source and target and relation in ALLOWED_RELATIONSHIP_TYPES:
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0.7))))
            except (TypeError, ValueError):
                confidence = 0.7
            relationships.append({"source": source, "target": target, "relation": relation, "confidence": confidence})
    if not entities and not researchers:
        return None
    return {"title": str(data.get("title", "")).strip(), "researchers": researchers, "entities": entities, "relationships": relationships}


def analyze_with_google_ai(text: str) -> Optional[Dict[str, Any]]:
    if not is_google_ai_configured():
        return None
    return _parse_extraction_response(generate_text(PROMPT, text, EXTRACTION_SCHEMA) or "")
