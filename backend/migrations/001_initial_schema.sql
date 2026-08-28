-- =============================================================================
-- Research Nexus — Supabase PostgreSQL Schema Migration 001
-- =============================================================================
-- This migration creates all tables required by Research Nexus for persistent
-- storage of documents, entities, relationships, notes, and more.
-- Run via: psql "$DATABASE_URL" -f backend/migrations/001_initial_schema.sql
-- =============================================================================

-- Enable the pgvector extension for AI embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- Documents table
-- Stores uploaded/document research papers and their metadata.
-- =============================================================================
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    department TEXT NOT NULL,
    document_type TEXT NOT NULL,
    content TEXT NOT NULL,
    abstract TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

-- =============================================================================
-- Entities table
-- Academic entities: PAPER, RESEARCHER, DEPARTMENT, METHOD, TOPIC, TECHNOLOGY, DATASET
-- =============================================================================
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT
);

-- =============================================================================
-- document_entities junction table
-- Many-to-many relationship between documents and entities.
-- Cascading delete: removing a document removes its entity links.
-- =============================================================================
CREATE TABLE IF NOT EXISTS document_entities (
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, entity_id)
);

-- =============================================================================
-- relationships table
-- Directed relationships between entities with confidence scores.
-- Cascading delete: removing a document or its entities cleanup relationships.
-- =============================================================================
CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE
);

-- =============================================================================
-- document_chunks table
-- Stores text chunks and their vector embeddings for semantic search.
-- =============================================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    embedding vector(768)
);

-- =============================================================================
-- researchers table
-- Faculty/researcher metadata.
-- =============================================================================
CREATE TABLE IF NOT EXISTS researchers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL
);

-- =============================================================================
-- notes table
-- Obsidian-style connected notes with wikilink support.
-- =============================================================================
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_pinned INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    tags TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- =============================================================================
-- note_links table
-- Wikilinks/references between notes.
-- Cascading delete: removing a note removes its links.
-- =============================================================================
CREATE TABLE IF NOT EXISTS note_links (
    id TEXT PRIMARY KEY,
    source_note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    link_text TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

-- =============================================================================
-- Indexes for query performance
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_doc_entities_doc ON document_entities(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_entities_ent ON document_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_src ON relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_tgt ON relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(is_pinned);
CREATE INDEX IF NOT EXISTS idx_note_links_src ON note_links(source_note_id);

-- =============================================================================
-- End of migration
-- =============================================================================