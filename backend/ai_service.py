import os
import re
from typing import Any, Dict, List, Optional, Tuple

import ai_prompts
from ai_engine import extract_entities_heuristic, cosine_similarity, generate_local_embedding
from google_ai_provider import (
    generate_text,
    get_last_model_used,
    get_last_provider_error,
    get_model_name,
    is_google_ai_configured,
    is_google_ai_model_supported,
)


def is_mock_ai_enabled() -> bool:
    """Return true only when development mock responses were explicitly requested.

    For safety, mock mode is never allowed when running in production. If
    NODE_ENV=production and MOCK_AI is true, this function will return False
    and a server startup check will raise an explicit error to avoid accidental
    use of mock responses in production environments.
    """
    mock_env = os.getenv("MOCK_AI", "").strip().lower()
    enabled = mock_env in ("true", "1", "yes")
    if enabled and os.getenv("NODE_ENV", "").strip().lower() == "production":
        # Do not enable mock in production; caller should surface this during startup
        logger = __import__("logging").getLogger(__name__)
        logger.error("MOCK_AI is set to true but NODE_ENV=production — disabling mock mode for safety.")
        return False
    return enabled


# Simple per-process rate limiter to avoid runaway AI calls (token-bucket like).
# This is intentionally lightweight and in-memory; for production use a distributed
# limiter (Redis, Cloud Memorystore) to coordinate across instances.
_last_reset = None
_request_count = 0


def _invoke(system_instruction: str, user_content: str) -> Tuple[Optional[str], str]:
    """
    Returns (text, mode) where mode is openrouter | mock | unavailable.
    Provider failures never silently masquerade as production success.
    Also enforces a simple per-process rate limit based on AI_MAX_REQUESTS_PER_MINUTE.
    """
    global _last_reset, _request_count
    from datetime import datetime, timedelta

    # Mock first: explicit opt-in only
    if is_mock_ai_enabled():
        return None, "mock"

    if not is_google_ai_configured():
        return None, "unavailable"
    if not is_google_ai_model_supported():
        return None, "unsupported_model"

    now = datetime.utcnow()
    if _last_reset is None or (now - _last_reset) > timedelta(minutes=1):
        _last_reset = now
        _request_count = 0

    try:
        from config import max_ai_requests_per_minute
        limit = max_ai_requests_per_minute()
    except Exception:
        limit = 60

    if _request_count >= limit:
        return None, "unavailable"

    _request_count += 1

    try:
        text = generate_text(system_instruction, user_content)
    except Exception:
        text = None
    if text:
        return text, "openrouter"
    return None, "unavailable"


def _envelope(
    markdown: str,
    provider: str,
    status: str,
    structured: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "markdown": markdown or "",
        "provider": provider,
        "status": status,
        "structured": structured or {},
        "mock": status == "success" and "Mock" in provider,
    }
    if title:
        payload["title"] = title
    if error:
        payload["error"] = error
        payload["markdown"] = payload["markdown"] or f"### AI analysis is temporarily unavailable.\n\n{error}"
    return payload


def _unavailable(error: Optional[str] = None) -> Dict[str, Any]:
    default_error = (
        "OpenRouter is unavailable for the configured model. "
        "Check the OPENROUTER_API_KEY and AI_MODEL values in the server environment."
    )
    actual_error = error or get_last_provider_error() or default_error
    return _envelope(
        "",
        "OpenRouter (unavailable)",
        "unavailable",
        error=actual_error,
    )


def _extract_key_sentences(text: str, max_sentences: int = 5) -> List[str]:
    clean = re.sub(r"#.*?\n", "", text)
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", clean)
        if len(s.strip()) > 30 and not s.strip().startswith(("http", "Author:", "Keywords:"))
    ]
    return sentences[:max_sentences]


def _names(heuristic: Dict[str, Any], typ: str) -> List[str]:
    return [e["name"] for e in heuristic.get("entities", []) if e.get("type") == typ]


def _structured(heuristic: Dict[str, Any], key_sents: List[str]) -> Dict[str, Any]:
    return {
        "summary": " ".join(key_sents[:2]),
        "key_findings": key_sents[:4],
        "research_questions": [],
        "methodology": _names(heuristic, "METHOD"),
        "datasets": _names(heuristic, "DATASET"),
        "technologies": _names(heuristic, "TECHNOLOGY"),
        "limitations": [],
        "future_work": [],
        "entities": heuristic.get("entities", []),
        "relationships": heuristic.get("relationships", []),
        "research_ideas": [],
    }


def _doc_prompt(title: str, filename: str, text: str) -> str:
    return f"Document Title: {title}\nFilename: {filename}\n\nDocument Text:\n{text[:30000]}"


def _maybe_google_ai(prompt_name: str, user_prompt: str) -> Dict[str, Any]:
    system = getattr(ai_prompts, prompt_name)
    llm, mode = _invoke(system, user_prompt)
    if mode == "openrouter":
        actual_model = get_last_model_used() or get_model_name()
        return _envelope(llm, f"OpenRouter ({actual_model})", "success")
    if mode in {"unavailable", "unsupported_model"}:
        return _unavailable(get_last_provider_error() or "OpenRouter is unavailable for the configured model.")
    return {}


def summarize_document(text: str, filename: str, title: str) -> Dict[str, Any]:
    hit = _maybe_google_ai("SUMMARY_PROMPT", _doc_prompt(title, filename, text))
    if hit:
        return hit

    heuristic = extract_entities_heuristic(text, filename)
    key_sents = _extract_key_sentences(text, 4)
    topics = _names(heuristic, "TOPIC")
    methods = _names(heuristic, "METHOD")
    datasets = _names(heuristic, "DATASET")

    md = f"""### Executive Summary
This research presents a novel study in **{', '.join(topics) or 'Applied Machine Learning'}**. {key_sents[0] if key_sents else 'The work addresses critical algorithmic challenges using empirical benchmarks.'} By leveraging **{', '.join(methods) or 'modern neural representations'}**, the authors demonstrate significant performance and scalability improvements.

### Core Contributions
- **Primary Innovation**: Implementation of {methods[0] if methods else 'an advanced algorithmic architecture'} tailored for {topics[0] if topics else 'complex data distributions'}.
- **Empirical Validation**: Benchmarked against **{', '.join(datasets) or 'standard domain benchmarks'}** to verify generalizability and robustness.
- **Interdisciplinary Utility**: Provides reusable pipelines applicable across {heuristic.get('department', 'academic research labs')}.

### Key Takeaway
Demonstrates that {methods[0] if methods else 'decentralized modeling'} combined with rigorous evaluation provides a reproducible foundation for future cross-disciplinary studies.
"""
    return _envelope(md, "Mock AI (development)", "success", _structured(heuristic, key_sents))


def deep_analyze_document(text: str, filename: str, title: str) -> Dict[str, Any]:
    hit = _maybe_google_ai("DEEP_ANALYSIS_PROMPT", _doc_prompt(title, filename, text))
    if hit:
        return hit

    heuristic = extract_entities_heuristic(text, filename)
    topics = _names(heuristic, "TOPIC")
    methods = _names(heuristic, "METHOD")
    datasets = _names(heuristic, "DATASET")
    techs = _names(heuristic, "TECHNOLOGY")
    key_sents = _extract_key_sentences(text, 6)

    md = f"""### Overview & Core Problem
The paper addresses scalability and validation constraints in **{', '.join(topics) or 'Data-Intensive AI'}**. {key_sents[0] if key_sents else 'Traditional centralized methods suffer from data fragmentation and domain shifts.'}

### Key Findings
1. **Algorithmic Convergence**: The proposed {methods[0] if methods else 'pipeline'} achieves high fidelity without requiring centralized data pooling.
2. **Benchmark Superiority**: Outperforms conventional baselines on **{', '.join(datasets) or 'standard evaluation suites'}**.
3. **Reproducibility**: Standardized execution utilizing {', '.join(techs) or 'PyTorch and modern ML stacks'}.

### Methodology & System Architecture
- **Algorithmic Approach**: Combines **{', '.join(methods) or 'deep neural representations'}** with targeted loss optimization and regularization.
- **Experimental Setup**: Multi-round cross-validation against domain-specific test cohorts.

### Datasets & Benchmarks
- **Primary Datasets**: {', '.join(datasets) or 'Curated academic benchmarks'}
- **Modality**: High-dimensional structured/multimodal feature representations.

### Limitations & Potential Weaknesses
- **Compute Overhead**: Increased communication rounds or memory footprint during large-scale scaling.
- **Domain Shift**: Extreme distribution shifts across heterogeneous institutional splits require calibration.

### Future Research Directions
- **Cross-Domain Transfer**: Evaluating the framework on complementary multi-omics and multimodal sensor streams.
- **Privacy & Verification Bounds**: Incorporating formal mathematical verification protocols.
"""
    structured = _structured(heuristic, key_sents)
    structured["limitations"] = ["Compute overhead at scale", "Domain shift across institutions"]
    structured["future_work"] = ["Cross-domain transfer", "Formal verification of privacy bounds"]
    return _envelope(md, "Mock AI (development)", "success", structured)


def explain_document(text: str, filename: str, title: str) -> Dict[str, Any]:
    hit = _maybe_google_ai("EXPLAIN_PROMPT", _doc_prompt(title, filename, text))
    if hit:
        return hit

    heuristic = extract_entities_heuristic(text, filename)
    methods = _names(heuristic, "METHOD")
    topics = _names(heuristic, "TOPIC")
    key_sents = _extract_key_sentences(text, 3)

    md = f"""### The Big Picture (In Plain English)
Imagine trying to solve a puzzle where different labs each hold only a few pieces—and policy or privacy rules forbid sending the raw pieces to a central room.

This paper addresses that dilemma in **{topics[0] if topics else 'collaborative science'}** using **{methods[0] if methods else 'modern learning architectures'}**. {key_sents[0] if key_sents else ''}

### How It Actually Works
1. **Local computation**: Each site works on its own data using **{methods[0] if methods else 'deep learning architectures'}**.
2. **Shared scientific signal**: Insights (not necessarily raw records) are compared against **{', '.join(_names(heuristic, 'DATASET')) or 'public or institutional benchmarks'}**.
3. **Iterative refinement**: The approach is evaluated for robustness across sites and departments.

### Why It Matters Across Fields
- Enables collaboration without collapsing every dataset into one warehouse.
- Makes methods reusable across adjacent university departments.
"""
    return _envelope(md, "Mock AI (development)", "success", _structured(heuristic, key_sents))


def analyze_methodology(text: str, filename: str, title: str) -> Dict[str, Any]:
    hit = _maybe_google_ai("METHODOLOGY_PROMPT", _doc_prompt(title, filename, text))
    if hit:
        return hit

    heuristic = extract_entities_heuristic(text, filename)
    methods = _names(heuristic, "METHOD")
    techs = _names(heuristic, "TECHNOLOGY")
    datasets = _names(heuristic, "DATASET")
    key_sents = _extract_key_sentences(text, 4)

    md = f"""### Algorithmic Formulation
- **Approach**: {', '.join(methods) or 'Deep neural representation learning'} applied to the research problem.
- **Evidence in text**: {key_sents[0] if key_sents else 'The paper describes an empirical training and evaluation pipeline.'}

### Implementation Stack & Frameworks
- **Primary Frameworks**: {', '.join(techs) or 'PyTorch, CUDA, Scikit-learn'}

### Validation & Benchmark Metrics
- **Evaluated On**: **{', '.join(datasets) or 'Multi-institutional test cohorts'}**
"""
    return _envelope(md, "Mock AI (development)", "success", _structured(heuristic, key_sents))


def generate_research_ideas(text: str, filename: str, title: str) -> Dict[str, Any]:
    hit = _maybe_google_ai("RESEARCH_IDEAS_PROMPT", _doc_prompt(title, filename, text))
    if hit:
        return hit

    heuristic = extract_entities_heuristic(text, filename)
    topics = _names(heuristic, "TOPIC")
    methods = _names(heuristic, "METHOD")
    datasets = _names(heuristic, "DATASET")
    key_sents = _extract_key_sentences(text, 3)

    md = f"""### Novel Research Extensions & Grant Ideas

1. **Idea 1: Interdisciplinary Synergy**
   - **Concept**: Combine **{methods[0] if methods else 'the core method'}** with adjacent-domain evaluation on **{datasets[0] if datasets else 'shared benchmarks'}**.
   - **Collaborating Departments**: {heuristic.get('department', 'Computer Science')} + a complementary school
   - **Impact**: Joint NSF/NIH-style validation across sites.

2. **Idea 2: Architecture Unification**
   - **Concept**: Multimodal fusion of the paper's signals with complementary sensors or records.
   - **Proposed Modification**: Cross-attention between existing extractors and a sequence/transformer head.

3. **Idea 3: Edge / Low-Resource Adaptation**
   - **Concept**: Transfer **{topics[0] if topics else 'the learned representation'}** to smaller clinics or field devices.
"""
    structured = _structured(heuristic, key_sents)
    structured["research_ideas"] = ["Interdisciplinary synergy", "Architecture unification", "Edge adaptation"]
    return _envelope(md, "Mock AI (development)", "success", structured)


def generate_questions(text: str, filename: str, title: str) -> Dict[str, Any]:
    hit = _maybe_google_ai("QUESTIONS_PROMPT", _doc_prompt(title, filename, text))
    if hit:
        return hit

    heuristic = extract_entities_heuristic(text, filename)
    topics = _names(heuristic, "TOPIC")
    methods = _names(heuristic, "METHOD")
    key_sents = _extract_key_sentences(text, 3)

    md = f"""### Critical Peer-Review Questions
1. **Methodological Scalability**: How does **{methods[0] if methods else 'the proposed model'}** scale as data silos become more heterogeneous?
2. **Data Bias & Fairness**: What mechanisms prevent majority cohorts from dominating minority updates?
3. **Robustness**: How sensitive are reported results to distribution shift?

### Seminar Discussion Topics
- **Topic A**: Trade-offs between accuracy and privacy/compute in {topics[0] if topics else 'this domain'}.
- **Topic B**: How university governance should treat co-trained models across departments.
"""
    structured = _structured(heuristic, key_sents)
    structured["research_questions"] = [
        f"How does {methods[0] if methods else 'the model'} scale under non-IID silos?",
        "What fairness mitigations are in place?",
        "How robust is the result to domain shift?",
    ]
    return _envelope(md, "Mock AI (development)", "success", structured)


def generate_research_note(text: str, filename: str, title: str, department: str, researcher: str) -> Dict[str, Any]:
    prompt = f"Document Title: {title}\nAuthor: {researcher}\nDepartment: {department}\nFilename: {filename}\n\nDocument Text:\n{text[:30000]}"
    hit = _maybe_google_ai("NOTE_GENERATION_PROMPT", prompt)
    if hit:
        hit["title"] = f"Note: {title}"
        return hit

    heuristic = extract_entities_heuristic(text, filename, department)
    topics = _names(heuristic, "TOPIC")
    methods = _names(heuristic, "METHOD")
    datasets = _names(heuristic, "DATASET")
    key_sents = _extract_key_sentences(text, 4)

    md = f"""# Research Summary

## Overview
[[{title}]] by [[{researcher}]] ([[{department}]]). {key_sents[0] if key_sents else ''}

## Research Question
How can [[{topics[0] if topics else 'this research area'}]] be advanced using [[{methods[0] if methods else 'the proposed methodology'}]]?

## Methodology
- Utilizes [[{methods[0] if methods else 'deep learning'}]]
- Implemented with [[{_names(heuristic, 'TECHNOLOGY')[0] if _names(heuristic, 'TECHNOLOGY') else 'PyTorch'}]]

## Dataset
- [[{datasets[0] if datasets else 'Primary benchmark'}]]

## Key Findings
{chr(10).join(f'- {s}' for s in key_sents[:3]) or '- Empirical results support the proposed approach.'}

## Limitations
- Scaling, domain shift, and compute cost remain open constraints.

## Related Research
- Connected to [[{topics[0] if topics else 'adjacent topics'}]]

## Potential Research Ideas
- Joint evaluation with labs already using the same datasets or methods.
"""
    return _envelope(md, "Mock AI (development)", "success", _structured(heuristic, key_sents), title=f"Note: {title}")


def compare_documents(doc_a: Dict[str, Any], doc_b: Dict[str, Any]) -> Dict[str, Any]:
    content_a = doc_a.get("content", "")[:15000]
    content_b = doc_b.get("content", "")[:15000]
    prompt = (
        f"DOCUMENT A:\nTitle: {doc_a.get('title')}\nDepartment: {doc_a.get('department')}\nContent:\n{content_a}\n\n"
        f"DOCUMENT B:\nTitle: {doc_b.get('title')}\nDepartment: {doc_b.get('department')}\nContent:\n{content_b}"
    )
    hit = _maybe_google_ai("COMPARE_PROMPT", prompt)
    if hit:
        return hit

    ea = extract_entities_heuristic(content_a, doc_a.get("filename", "a.pdf"), doc_a.get("department"))
    eb = extract_entities_heuristic(content_b, doc_b.get("filename", "b.pdf"), doc_b.get("department"))

    def get_set(typ, elist):
        return {e["name"] for e in elist["entities"] if e["type"] == typ}

    shared_datasets = list(get_set("DATASET", ea) & get_set("DATASET", eb))
    shared_methods = list(get_set("METHOD", ea) & get_set("METHOD", eb))
    shared_topics = list(get_set("TOPIC", ea) & get_set("TOPIC", eb))

    md = f"""### Similarities
- **Shared Datasets**: {', '.join(shared_datasets) if shared_datasets else 'No identical named datasets detected; feature spaces may still be compatible.'}
- **Shared Methods**: {', '.join(shared_methods) if shared_methods else 'Both appear to rely on neural representation learning.'}
- **Common Themes**: {', '.join(shared_topics) if shared_topics else 'Applied predictive modeling.'}

### Differences
- **Institutional Context**: Document A is grounded in **{doc_a.get('department')}**; Document B in **{doc_b.get('department')}**.
- **Scope**: Distinct evaluation targets and reporting emphasis.

### Shared Methods
{', '.join(shared_methods) or 'No identical named methods extracted.'}

### Shared Datasets
{', '.join(shared_datasets) or 'No identical named datasets extracted.'}

### Different Results
Results are reported in different departmental contexts; treat numeric comparisons as suggestions until both full papers are aligned on the same split.

### Potential Research Overlap
{'High — same methods and datasets.' if shared_datasets and shared_methods else 'Moderate — adjacent questions or tools.'}

### Possible Collaboration
Unify ingestion, share evaluation splits, and co-author a cross-department benchmark.
"""
    return _envelope(md, "Mock AI (development)", "success")


def chat_with_sources(query: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    context = ""
    sources_cited = []
    for d in documents:
        context += f"\n\n--- DOCUMENT: {d.get('title')} (File: {d.get('filename')}) ---\n{d.get('content', '')[:12000]}"
        sources_cited.append(d.get("filename"))

    prompt = f"USER QUERY: {query}\n\nCONTEXT DOCUMENTS:\n{context}"
    llm, mode = _invoke(ai_prompts.CHAT_PROMPT, prompt)
    if mode == "openrouter":
        actual_model = get_last_model_used() or get_model_name()
        return {"response": llm, "sources": sources_cited, "provider": f"OpenRouter ({actual_model})", "status": "success"}
    if mode == "unavailable":
        return {
            "response": "AI analysis is temporarily unavailable.",
            "sources": sources_cited,
            "provider": "OpenRouter (unavailable)",
            "status": "unavailable",
            "error": get_last_provider_error() or "AI analysis is temporarily unavailable.",
        }

    q_lower = query.lower()
    matched_sentences = []
    for d in documents:
        sents = _extract_key_sentences(d.get("content", ""), 8)
        for s in sents:
            if any(word in s.lower() for word in q_lower.split() if len(word) > 3):
                matched_sentences.append((s, d.get("filename")))

    if matched_sentences:
        answer_body = " ".join([m[0] for m in matched_sentences[:3]])
        cited_files = list(set([m[1] for m in matched_sentences[:3]]))
    else:
        doc = documents[0] if documents else {}
        answer_body = (
            f"Based on {doc.get('title', 'the provided research')}, the study explores "
            f"{doc.get('department', 'academic')} methodologies. Key findings focus on empirical validation."
        )
        cited_files = [documents[0].get("filename", "document.pdf")] if documents else []

    resp = f"{answer_body}\n\n**Source**: `{', '.join(cited_files)}`"
    return {"response": resp, "sources": cited_files, "provider": "Mock AI (development)", "status": "success"}


def section_focus(text: str, filename: str, title: str, action: str) -> Dict[str, Any]:
    prompt_map = {
        "findings": "FINDINGS_PROMPT",
        "contributions": "CONTRIBUTIONS_PROMPT",
        "research-questions": "RESEARCH_QUESTIONS_PROMPT",
        "datasets": "DATASETS_PROMPT",
        "technologies": "TECHNOLOGIES_PROMPT",
        "results": "RESULTS_PROMPT",
        "limitations": "LIMITATIONS_PROMPT",
        "future-work": "FUTURE_WORK_PROMPT",
        "concepts": "CONCEPTS_PROMPT",
        "entities": "ENTITY_FOCUS_PROMPT",
        "ideas": "RESEARCH_IDEAS_PROMPT",
        "extract": "ENTITY_FOCUS_PROMPT",
    }
    prompt_attr = prompt_map.get(action)
    if prompt_attr:
        hit = _maybe_google_ai(prompt_attr, _doc_prompt(title, filename, text))
        if hit:
            return hit

    heuristic = extract_entities_heuristic(text, filename)
    key_sents = _extract_key_sentences(text, 6)
    topics = _names(heuristic, "TOPIC")
    methods = _names(heuristic, "METHOD")
    datasets = _names(heuristic, "DATASET")
    techs = _names(heuristic, "TECHNOLOGY")
    ents = heuristic.get("entities", [])

    sections = {
        "findings": f"""### Key Findings
{chr(10).join(f'{i}. {s}' for i, s in enumerate(key_sents[:4], 1)) or '1. The work reports empirical improvements on its chosen benchmarks.'}
""",
        "contributions": f"""### Key Contributions
- Method: {', '.join(methods) or 'Novel modeling pipeline'}
- Domain: {', '.join(topics) or 'Applied research'}
- Evaluation: {', '.join(datasets) or 'Domain benchmarks'}
""",
        "research-questions": f"""### Research Questions
1. How can {topics[0] if topics else 'the target problem'} be solved with {methods[0] if methods else 'the proposed method'}?
2. What evidence does {', '.join(datasets) or 'the evaluation'} provide?
3. Where does the approach fail under shift or sparse data?
""",
        "datasets": f"""### Datasets
{chr(10).join(f'- **{n}**' for n in datasets) or '- No named public datasets were confidently extracted from the text.'}
""",
        "technologies": f"""### Technologies
{chr(10).join(f'- **{n}**' for n in techs) or '- Stack not explicitly listed; likely a standard scientific Python/ML toolchain.'}
""",
        "results": f"""### Important Results
{chr(10).join(f'- {s}' for s in key_sents[:4]) or '- Results are described qualitatively in the source text.'}
""",
        "limitations": """### Limitations
- Scaling and compute cost.
- Possible domain shift across sites.
- Incomplete reporting of negative results is common in short papers.
""",
        "future-work": """### Future Work
- Broader datasets and sites.
- Stronger privacy or robustness bounds.
- Cross-department replication.
""",
        "concepts": f"""### Extracted Concepts
{chr(10).join(f'- [[{n}]]' for n in (topics + methods)[:12]) or '- No taxonomy concepts matched.'}
""",
        "entities": f"""### Extracted Entities
{chr(10).join(f'- **{e["name"]}** ({e["type"]}) — {e.get("description") or ""}' for e in ents) or '- No entities extracted.'}
""",
        "extract": f"""### Extracted Concepts & Entities
**Concepts**: {', '.join(f'[[{n}]]' for n in topics) or 'n/a'}
**Methods**: {', '.join(f'[[{n}]]' for n in methods) or 'n/a'}
**Datasets**: {', '.join(f'[[{n}]]' for n in datasets) or 'n/a'}
**Technologies**: {', '.join(f'[[{n}]]' for n in techs) or 'n/a'}
""",
        "related": "",
        "similar": "",
        "redundant": "",
    }

    md = sections.get(action) or deep_analyze_document(text, filename, title)["markdown"]
    return _envelope(md, "Mock AI (development)", "success", _structured(heuristic, key_sents))


def related_or_similar(action: str, current: Dict[str, Any], others: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = (
        f"CURRENT PAPER: {current.get('title')}\n{current.get('content', '')[:12000]}\n\n"
        "CANDIDATES:\n"
        + "\n".join(f"- {d.get('title')} ({d.get('department')}): {d.get('abstract') or d.get('content', '')[:400]}" for d in others[:8])
    )
    attr = "RELATED_PROMPT" if action == "related" else "SIMILAR_PROMPT" if action == "similar" else "REDUNDANT_PROMPT"
    hit = _maybe_google_ai(attr, prompt)
    if hit:
        return hit

    cur_vec = generate_local_embedding(current.get("content") or current.get("title") or "")
    ranked = []
    for d in others:
        if d.get("id") == current.get("id"):
            continue
        sim = cosine_similarity(cur_vec, generate_local_embedding(d.get("content") or ""))
        ranked.append((sim, d))
    ranked.sort(key=lambda x: x[0], reverse=True)

    heading = {
        "related": "Find Related Research",
        "similar": "Find Similar Papers",
        "redundant": "Find Potentially Redundant Studies",
    }.get(action, "Related Research")

    lines = [f"### {heading}", ""]
    if not ranked:
        lines.append("No other documents are in the workspace yet.")
    for sim, d in ranked[:5]:
        lines.append(
            f"- **{d.get('title')}** ({d.get('department')}) — suggested similarity {int(sim * 100)}%. "
            f"Treat as a heuristic, not a citation."
        )
        lines.append(f"  - Source: `{d.get('filename')}`")
    return _envelope("\n".join(lines), "Mock AI (development)", "success")


def run_document_action(
    action: str,
    text: str,
    filename: str,
    title: str,
    department: str = "",
    researcher: str = "",
    current_doc: Optional[Dict[str, Any]] = None,
    other_docs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    action = (action or "").replace("_", "-")
    if action in ("summarize",):
        return summarize_document(text, filename, title)
    if action in ("analyze", "analysis"):
        return deep_analyze_document(text, filename, title)
    if action in ("explain",):
        return explain_document(text, filename, title)
    if action in ("methodology",):
        return analyze_methodology(text, filename, title)
    if action in ("research-ideas", "ideas"):
        return generate_research_ideas(text, filename, title)
    if action in ("questions", "generate-questions"):
        return generate_questions(text, filename, title)
    if action in ("generate-note", "note"):
        return generate_research_note(text, filename, title, department, researcher)
    if action in ("related", "similar", "redundant"):
        return related_or_similar(action, current_doc or {"title": title, "content": text, "filename": filename}, other_docs or [])
    return section_focus(text, filename, title, action)
