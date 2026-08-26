-- ============================================================================
-- RESEARCH NEXUS: Target AlloyDB / PostgreSQL + pgvector Schema
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core Research Documents
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    department TEXT NOT NULL,
    document_type TEXT NOT NULL, -- PDF, MARKDOWN, CODE_REPO, CODE_SCRIPT, TEXT
    content TEXT NOT NULL,
    abstract TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Extracted Knowledge Graph Entities
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    entity_type TEXT NOT NULL, -- RESEARCHER, DEPARTMENT, TOPIC, METHOD, DATASET, TECHNOLOGY, INSTITUTION, PAPER
    description TEXT
);

-- Document <-> Entity Many-to-Many Linking
CREATE TABLE IF NOT EXISTS document_entities (
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, entity_id)
);

-- Knowledge Graph Directed Relationships
CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL, -- AUTHORED, STUDIES, USES_METHOD, USES_DATASET, USES_TECHNOLOGY, BELONGS_TO, AFFILIATED_WITH, RELATED_TO, EXTENDS, CITES, EVALUATES_ON
    confidence REAL NOT NULL DEFAULT 0.85,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE
);

-- Dense Vector Embedding Chunks (768-dim local semantic fallback)
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    embedding vector(768)
);

-- Researchers & Affiliated Departments Directory
CREATE TABLE IF NOT EXISTS researchers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL
);

-- Obsidian-Style Connected Research Notes
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_pinned INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    tags TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Note Links & [[wikilinks]]
CREATE TABLE IF NOT EXISTS note_links (
    id TEXT PRIMARY KEY,
    source_note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL, -- NOTE, DOCUMENT, ENTITY, WIKILINK
    target_id TEXT NOT NULL,
    link_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for High-Performance Queries & Graph Traversal
CREATE INDEX IF NOT EXISTS idx_doc_entities_doc ON document_entities(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_entities_ent ON document_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_src ON relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_tgt ON relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_documents_dept ON documents(department);
CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(is_pinned);
CREATE INDEX IF NOT EXISTS idx_note_links_src ON note_links(source_note_id);
