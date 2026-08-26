import json
from typing import List, Dict, Any, Optional
from ai_engine import generate_local_embedding, cosine_similarity


def get_dataset_matching(conn) -> List[Dict[str, Any]]:
    """
    FIRST-CLASS FEATURE:
    Discovers all datasets used across research projects, detects cross-department usage,
    and highlights multi-department dataset synergies (e.g. MIMIC-IV in CS & Biomedical Engineering).
    """
    cur = conn.cursor() if hasattr(conn, "cursor") and callable(getattr(conn, "cursor")) else conn
    
    query = """
    SELECT 
        e.id AS dataset_id,
        e.name AS dataset_name,
        e.description AS dataset_description,
        d.id AS document_id,
        d.title AS document_title,
        d.department AS department,
        d.document_type AS document_type
    FROM entities e
    JOIN document_entities de ON de.entity_id = e.id
    JOIN documents d ON d.id = de.document_id
    WHERE e.entity_type = 'DATASET'
    ORDER BY e.name, d.title
    """
    rows = conn.execute(query).fetchall() if hasattr(conn, "execute") else cur.execute(query).fetchall()
    
    datasets_map: Dict[str, Dict[str, Any]] = {}
    
    for r in rows:
        ds_name = r["dataset_name"]
        if ds_name not in datasets_map:
            datasets_map[ds_name] = {
                "id": r["dataset_id"],
                "name": ds_name,
                "description": r["dataset_description"] or f"Research dataset: {ds_name}",
                "departments": set(),
                "documents": [],
                "document_ids": set(),
                "methods_applied": set(),
                "researchers": set()
            }
        datasets_map[ds_name]["departments"].add(r["department"])
        if r["document_id"] not in datasets_map[ds_name]["document_ids"]:
            datasets_map[ds_name]["document_ids"].add(r["document_id"])
            datasets_map[ds_name]["documents"].append({
                "id": r["document_id"],
                "title": r["document_title"],
                "department": r["department"],
                "document_type": r["document_type"]
            })

    # For each dataset, find associated methods and researchers
    result = []
    for ds_name, ds_info in datasets_map.items():
        doc_ids = list(ds_info["document_ids"])
        if doc_ids:
            placeholders = ",".join(["?"] * len(doc_ids))
            ent_query = f"""
            SELECT e.name, e.entity_type, de.document_id, d.department
            FROM entities e
            JOIN document_entities de ON de.entity_id = e.id
            JOIN documents d ON d.id = de.document_id
            WHERE de.document_id IN ({placeholders}) AND e.entity_type IN ('METHOD', 'RESEARCHER', 'TECHNOLOGY')
            """
            ent_rows = conn.execute(ent_query, doc_ids).fetchall()
            for er in ent_rows:
                if er["entity_type"] == "METHOD":
                    ds_info["methods_applied"].add(er["name"])
                elif er["entity_type"] == "RESEARCHER":
                    ds_info["researchers"].add(er["name"])

        depts_list = sorted(list(ds_info["departments"]))
        num_depts = len(depts_list)
        num_docs = len(ds_info["documents"])
        
        # Build punchline highlight
        if num_depts >= 2:
            highlight = f"{ds_name} is being used by research projects across {num_depts} departments ({', '.join(depts_list)})."
            cross_department = True
            synergy_tier = "High Multi-Department Reuse"
        elif num_docs >= 2:
            highlight = f"{ds_name} is shared across {num_docs} research studies within {depts_list[0]}."
            cross_department = False
            synergy_tier = "Department-Wide Standard"
        else:
            highlight = f"{ds_name} is currently utilized in {ds_info['documents'][0]['title']} ({depts_list[0] if depts_list else 'Unassigned'})."
            cross_department = False
            synergy_tier = "Specialized Benchmark"

        result.append({
            "id": ds_info["id"],
            "name": ds_name,
            "description": ds_info["description"],
            "total_papers": num_docs,
            "total_departments": num_depts,
            "departments": depts_list,
            "is_cross_department": cross_department,
            "highlight": highlight,
            "synergy_tier": synergy_tier,
            "papers": ds_info["documents"],
            "methods_applied": sorted(list(ds_info["methods_applied"])),
            "researchers": sorted(list(ds_info["researchers"]))
        })

    return sorted(result, key=lambda x: (x["total_departments"], x["total_papers"]), reverse=True)


def get_collaborations(conn) -> List[Dict[str, Any]]:
    """
    Detects cross-disciplinary collaboration opportunities by scoring shared datasets,
    shared methods, semantic embedding closeness, and complementary topics across departments.
    """
    docs = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    if len(docs) < 2:
        return []

    doc_entities = {}
    doc_embeddings = {}
    
    for d in docs:
        did = d["id"]
        ents = conn.execute("""
            SELECT e.id, e.name, e.entity_type 
            FROM entities e 
            JOIN document_entities de ON de.entity_id = e.id 
            WHERE de.document_id = ?
        """, (did,)).fetchall()
        doc_entities[did] = ents
        
        # Load embedding chunk
        chunk = conn.execute("SELECT embedding FROM document_chunks WHERE document_id = ? LIMIT 1", (did,)).fetchone()
        emb = None
        if chunk and chunk["embedding"]:
            try:
                raw_emb = json.loads(chunk["embedding"]) if isinstance(chunk["embedding"], str) else chunk["embedding"]
                if isinstance(raw_emb, list) and len(raw_emb) > 0 and isinstance(raw_emb[0], (int, float)):
                    emb = [float(x) for x in raw_emb]
            except Exception:
                emb = None
        if not emb:
            emb = generate_local_embedding(d["content"])
        doc_embeddings[did] = emb

    collaborations = []
    
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            a, b = docs[i], docs[j]
            # Prioritize cross-department collaborations
            if a["department"] == b["department"]:
                continue

            ea = doc_entities[a["id"]]
            eb = doc_entities[b["id"]]

            def get_names(typ, elist):
                return {e["name"] for e in elist if e["entity_type"] == typ}

            datasets_a = get_names("DATASET", ea)
            datasets_b = get_names("DATASET", eb)
            shared_datasets = list(datasets_a & datasets_b)

            methods_a = get_names("METHOD", ea)
            methods_b = get_names("METHOD", eb)
            shared_methods = list(methods_a & methods_b)

            topics_a = get_names("TOPIC", ea)
            topics_b = get_names("TOPIC", eb)
            shared_topics = list(topics_a & topics_b)

            tech_a = get_names("TECHNOLOGY", ea)
            tech_b = get_names("TECHNOLOGY", eb)
            shared_tech = list(tech_a & tech_b)

            res_a = list(get_names("RESEARCHER", ea))
            res_b = list(get_names("RESEARCHER", eb))
            researcher_a = res_a[0] if res_a else f"Faculty ({a['department']})"
            researcher_b = res_b[0] if res_b else f"Faculty ({b['department']})"

            # Vector similarity
            vec_sim = cosine_similarity(doc_embeddings.get(a["id"], []), doc_embeddings.get(b["id"], []))

            # Multi-variable collaboration synergy calculation
            dataset_boost = 0.35 if shared_datasets else 0.0
            method_boost = 0.25 * min(1.0, len(shared_methods) * 0.5)
            topic_boost = 0.20 * min(1.0, len(shared_topics) * 0.5)
            vector_boost = 0.20 * vec_sim

            total_score = dataset_boost + method_boost + topic_boost + vector_boost
            
            if total_score >= 0.15 or shared_datasets or shared_methods:
                final_score = round(min(0.98, max(0.40, total_score + 0.20)), 2)
                
                reasons = []
                if shared_datasets:
                    reasons.append(f"Jointly utilizing the **{', '.join(shared_datasets)}** dataset across {a['department']} and {b['department']}")
                if shared_methods:
                    reasons.append(f"Applying complementary **{', '.join(shared_methods)}** methodologies")
                if shared_topics:
                    reasons.append(f"Investigating shared research questions in **{', '.join(shared_topics)}**")
                if not reasons:
                    reasons.append(f"High semantic overlap in algorithmic design ({int(vec_sim*100)}% conceptual closeness)")

                explanation = f"Cross-disciplinary synergy between {a['department']} and {b['department']}: " + "; ".join(reasons) + ". High potential for joint grant proposals and unified benchmark publications."

                collaborations.append({
                    "id": f"{a['id']}_{b['id']}",
                    "researcher_a": researcher_a,
                    "department_a": a["department"],
                    "paper_a": a["title"],
                    "paper_a_id": a["id"],
                    "researcher_b": researcher_b,
                    "department_b": b["department"],
                    "paper_b": b["title"],
                    "paper_b_id": b["id"],
                    "score": final_score,
                    "shared_datasets": shared_datasets,
                    "shared_methods": shared_methods,
                    "shared_topics": shared_topics,
                    "shared_technologies": shared_tech,
                    "semantic_similarity": round(vec_sim, 3),
                    "explanation": explanation
                })

    return sorted(collaborations, key=lambda x: (len(x["shared_datasets"]) > 0, x["score"]), reverse=True)[:10]


def get_redundancy(conn) -> List[Dict[str, Any]]:
    """
    Identifies potentially overlapping or redundant research studies across the university.
    Evaluates semantic vector distance, shared datasets, identical methods, and topic alignment.
    """
    docs = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    if len(docs) < 2:
        return []

    doc_entities = {}
    doc_embeddings = {}
    for d in docs:
        did = d["id"]
        ents = conn.execute("""
            SELECT e.name, e.entity_type 
            FROM entities e 
            JOIN document_entities de ON de.entity_id = e.id 
            WHERE de.document_id = ?
        """, (did,)).fetchall()
        doc_entities[did] = ents
        
        chunk = conn.execute("SELECT embedding FROM document_chunks WHERE document_id = ? LIMIT 1", (did,)).fetchone()
        emb = None
        if chunk and chunk["embedding"]:
            try:
                raw_emb = json.loads(chunk["embedding"]) if isinstance(chunk["embedding"], str) else chunk["embedding"]
                if isinstance(raw_emb, list) and len(raw_emb) > 0 and isinstance(raw_emb[0], (int, float)):
                    emb = [float(x) for x in raw_emb]
            except Exception:
                emb = None
        if not emb:
            emb = generate_local_embedding(d["content"])
        doc_embeddings[did] = emb

    redundancies = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            a, b = docs[i], docs[j]
            ea = doc_entities[a["id"]]
            eb = doc_entities[b["id"]]

            def get_set(typ, elist): return {e["name"] for e in elist if e["entity_type"] == typ}
            
            common_datasets = list(get_set("DATASET", ea) & get_set("DATASET", eb))
            common_methods = list(get_set("METHOD", ea) & get_set("METHOD", eb))
            common_topics = list(get_set("TOPIC", ea) & get_set("TOPIC", eb))

            vec_sim = cosine_similarity(doc_embeddings.get(a["id"], []), doc_embeddings.get(b["id"], []))

            overlap_score = (vec_sim * 0.40) + (0.25 if common_datasets else 0.0) + (0.20 if common_methods else 0.0) + (0.15 if common_topics else 0.0)
            
            if overlap_score >= 0.30 or (common_datasets and common_methods):
                sim_pct = round(min(0.96, max(0.45, overlap_score + 0.15)), 2)
                
                if sim_pct >= 0.70:
                    risk_level = "High Potential Redundancy"
                    recommendation = "High methodological and dataset duplication. Consolidate experimental benchmarking to eliminate redundant compute and labor."
                elif sim_pct >= 0.50:
                    risk_level = "Moderate Methodological Overlap"
                    recommendation = "Parallel exploration of identical datasets with similar architectures. Recommend joint evaluation on unified test splits."
                else:
                    risk_level = "Domain Parallelism"
                    recommendation = "Cross-domain study with common methodological foundation. Share baseline code pipelines."

                redundancies.append({
                    "id": f"{a['id']}_{b['id']}",
                    "paper_a": a["title"],
                    "paper_a_id": a["id"],
                    "department_a": a["department"],
                    "paper_b": b["title"],
                    "paper_b_id": b["id"],
                    "department_b": b["department"],
                    "similarity": sim_pct,
                    "shared_datasets": common_datasets,
                    "shared_methods": common_methods,
                    "shared_topics": common_topics,
                    "risk_level": risk_level,
                    "explanation": f"Both studies address related objectives in {', '.join(common_topics) or 'adjacent fields'} utilizing {', '.join(common_methods) or 'similar deep learning architectures'}" + (f" on the **{', '.join(common_datasets)}** dataset." if common_datasets else "."),
                    "recommendation": recommendation
                })

    return sorted(redundancies, key=lambda x: x["similarity"], reverse=True)[:10]


def search_research(conn, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Performs semantic vector search across all indexed research documents and entities.
    Ranks results by cosine similarity vector distance and entity matching.
    """
    if not query or not query.strip():
        return []

    q_vec = generate_local_embedding(query)
    q_lower = query.lower()

    docs = conn.execute("SELECT * FROM documents").fetchall()
    results = []

    for d in docs:
        did = d["id"]
        d_dict = dict(d)
        
        # Fetch embedding
        chunk = conn.execute("SELECT embedding FROM document_chunks WHERE document_id = ? LIMIT 1", (did,)).fetchone()
        doc_vec = None
        if chunk and chunk["embedding"]:
            try:
                raw_emb = json.loads(chunk["embedding"]) if isinstance(chunk["embedding"], str) else chunk["embedding"]
                if isinstance(raw_emb, list) and len(raw_emb) > 0 and isinstance(raw_emb[0], (int, float)):
                    doc_vec = [float(x) for x in raw_emb]
            except Exception:
                doc_vec = None
        if not doc_vec:
            doc_vec = generate_local_embedding(d["content"])

        # Cosine distance
        v_sim = cosine_similarity(q_vec, doc_vec)

        # Keyword / token boost for exact queries
        title_boost = 0.25 if q_lower in d["title"].lower() else 0.0
        content_boost = 0.15 if q_lower in d["content"].lower() else 0.0

        total_sim = round(min(0.99, v_sim + title_boost + content_boost), 3)

        if total_sim > 0.08:
            ents = conn.execute("""
                SELECT e.name, e.entity_type 
                FROM entities e 
                JOIN document_entities de ON de.entity_id = e.id 
                WHERE de.document_id = ?
            """, (did,)).fetchall()

            topics = [e["name"] for e in ents if e["entity_type"] == "TOPIC"]
            methods = [e["name"] for e in ents if e["entity_type"] == "METHOD"]
            datasets = [e["name"] for e in ents if e["entity_type"] == "DATASET"]
            researchers = [e["name"] for e in ents if e["entity_type"] == "RESEARCHER"]
            technologies = [e["name"] for e in ents if e["entity_type"] == "TECHNOLOGY"]

            abstract_text = d_dict.get("abstract") or (d["content"][:240] + "...")

            results.append({
                "id": d["id"],
                "title": d["title"],
                "filename": d["filename"],
                "department": d["department"],
                "document_type": d["document_type"],
                "abstract": abstract_text,
                "similarity": total_sim,
                "topics": topics,
                "methods": methods,
                "datasets": datasets,
                "researchers": researchers,
                "technologies": technologies
            })

    return sorted(results, key=lambda x: x["similarity"], reverse=True)[:limit]


def get_graph_data(conn, type_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates structured graph nodes and edges for Cytoscape visualization.
    Calculates degree centrality and enriches entity metadata.
    """
    if type_filter and type_filter.upper() != "ALL":
        entities = conn.execute("SELECT * FROM entities WHERE entity_type = ? ORDER BY name", (type_filter.upper(),)).fetchall()
    else:
        entities = conn.execute("SELECT * FROM entities ORDER BY entity_type, name").fetchall()

    ent_ids = {e["id"] for e in entities}

    # Fetch relationships
    relationships = conn.execute("""
        SELECT r.*, s.name as source_name, s.entity_type as source_type, t.name as target_name, t.entity_type as target_type
        FROM relationships r
        JOIN entities s ON s.id = r.source_entity_id
        JOIN entities t ON t.id = r.target_entity_id
    """).fetchall()

    # Calculate degrees
    degrees = {}
    edges = []
    for r in relationships:
        src = r["source_entity_id"]
        tgt = r["target_entity_id"]
        if src in ent_ids or tgt in ent_ids:
            degrees[src] = degrees.get(src, 0) + 1
            degrees[tgt] = degrees.get(tgt, 0) + 1
            if src in ent_ids and tgt in ent_ids:
                edges.append({
                    "id": r["id"],
                    "source": src,
                    "target": tgt,
                    "label": r["relation_type"],
                    "confidence": r["confidence"],
                    "source_name": r["source_name"],
                    "target_name": r["target_name"],
                })

    nodes = []
    for e in entities:
        nodes.append({
            "id": e["id"],
            "label": e["name"],
            "type": e["entity_type"],
            "description": e["description"] or "",
            "degree": degrees.get(e["id"], 1)
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }
