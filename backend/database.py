import os
import json
import sqlite3
import uuid
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB_PATH = Path(os.getenv("SQLITE_PATH", BASE_DIR / "research_nexus.db"))
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("ALLOYDB_DATABASE_URL")

USE_POSTGRES = False

if DATABASE_URL:
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(DATABASE_URL, connect_timeout=3, prepare_threshold=None) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        USE_POSTGRES = True
    except Exception as e:
        USE_POSTGRES = False
        print(f"[DB] PostgreSQL / AlloyDB connection failed ({e}). Falling back to local SQLite.")


class DBConnection:
    def __init__(self):
        self.is_postgres = USE_POSTGRES
        self.sqlite_path = SQLITE_DB_PATH

    @property
    def ph(self):
        return "%s" if self.is_postgres else "?"

    def get_sqlite_conn(self):
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_pg_conn(self):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None)

    def init_db(self):
        if self.is_postgres:
            try:
                with self.get_pg_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                        cur.execute("""
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
                        CREATE TABLE IF NOT EXISTS entities (
                            id TEXT PRIMARY KEY,
                            name TEXT UNIQUE NOT NULL,
                            entity_type TEXT NOT NULL,
                            description TEXT
                        );
                        CREATE TABLE IF NOT EXISTS document_entities (
                            document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                            entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
                            PRIMARY KEY (document_id, entity_id)
                        );
                        CREATE TABLE IF NOT EXISTS relationships (
                            id TEXT PRIMARY KEY,
                            source_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
                            target_entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
                            relation_type TEXT NOT NULL,
                            confidence REAL NOT NULL,
                            document_id TEXT REFERENCES documents(id) ON DELETE CASCADE
                        );
                        CREATE TABLE IF NOT EXISTS document_chunks (
                            id TEXT PRIMARY KEY,
                            document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                            chunk_text TEXT NOT NULL,
                            embedding vector(768)
                        );
                        CREATE TABLE IF NOT EXISTS researchers (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            department TEXT NOT NULL
                        );
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
                        CREATE TABLE IF NOT EXISTS note_links (
                            id TEXT PRIMARY KEY,
                            source_note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
                            target_type TEXT NOT NULL,
                            target_id TEXT NOT NULL,
                            link_text TEXT,
                            created_at TIMESTAMPTZ NOT NULL
                        );
                        """)
                    conn.commit()
                return
            except Exception as e:
                print(f"[DB] PostgreSQL init failed: {e}. Falling back to SQLite.")
                self.is_postgres = False

        # SQLite Fallback schema
        conn = self.get_sqlite_conn()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            department TEXT NOT NULL,
            document_type TEXT NOT NULL,
            content TEXT NOT NULL,
            abstract TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            entity_type TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS document_entities (
            document_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            PRIMARY KEY(document_id, entity_id),
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS relationships (
            id TEXT PRIMARY KEY,
            source_entity_id TEXT NOT NULL,
            target_entity_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            document_id TEXT,
            FOREIGN KEY(source_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(target_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS researchers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            tags TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS note_links (
            id TEXT PRIMARY KEY,
            source_note_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            link_text TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(source_note_id) REFERENCES notes(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_doc_entities_doc ON document_entities(document_id);
        CREATE INDEX IF NOT EXISTS idx_doc_entities_ent ON document_entities(entity_id);
        CREATE INDEX IF NOT EXISTS idx_relationships_src ON relationships(source_entity_id);
        CREATE INDEX IF NOT EXISTS idx_relationships_tgt ON relationships(target_entity_id);
        CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
        CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
        CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(is_pinned);
        CREATE INDEX IF NOT EXISTS idx_note_links_src ON note_links(source_note_id);
        """)
        
        # Migrations for existing DB instances
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN abstract TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, is_pinned INTEGER DEFAULT 0, is_archived INTEGER DEFAULT 0, tags TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS note_links (id TEXT PRIMARY KEY, source_note_id TEXT NOT NULL, target_type TEXT NOT NULL, target_id TEXT NOT NULL, link_text TEXT, created_at TEXT NOT NULL)")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_postgres": self.is_postgres,
            "engine": "AlloyDB / PostgreSQL + pgvector" if self.is_postgres else "SQLite (Local Fallback)",
            "database_url_configured": bool(DATABASE_URL),
            "sqlite_file": str(self.sqlite_path),
        }


db = DBConnection()
db.init_db()


def get_db_conn():
    if db.is_postgres:
        return db.get_pg_conn()
    return db.get_sqlite_conn()


def add_entity(conn, name: str, entity_type: str, description: str = "") -> Optional[str]:
    if not name or not name.strip():
        return None
    clean_name = name.strip()
    
    if db.is_postgres:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM entities WHERE lower(name) = lower(%s)", (clean_name,))
            row = cur.fetchone()
            if row:
                return row["id"]
            eid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO entities (id, name, entity_type, description) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO UPDATE SET entity_type = EXCLUDED.entity_type RETURNING id",
                (eid, clean_name, entity_type, description),
            )
            ret = cur.fetchone()
            return ret["id"] if ret else eid
    else:
        row = conn.execute("SELECT id FROM entities WHERE lower(name) = lower(?)", (clean_name,)).fetchone()
        if row:
            return row["id"]
        eid = str(uuid.uuid4())
        try:
            conn.execute("INSERT INTO entities (id, name, entity_type, description) VALUES (?, ?, ?, ?)",
                         (eid, clean_name, entity_type, description))
            return eid
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT id FROM entities WHERE lower(name) = lower(?)", (clean_name,)).fetchone()
            return row["id"] if row else eid


def link_doc_entity(conn, doc_id: str, entity_id: str):
    if not doc_id or not entity_id:
        return
    if db.is_postgres:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO document_entities (document_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (doc_id, entity_id),
            )
    else:
        conn.execute("INSERT OR IGNORE INTO document_entities (document_id, entity_id) VALUES (?, ?)",
                     (doc_id, entity_id))


def add_relationship(conn, source_id: str, target_id: str, relation_type: str, confidence: float, doc_id: Optional[str] = None):
    if not source_id or not target_id or not relation_type:
        return None
    rid = str(uuid.uuid4())
    if db.is_postgres:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO relationships (id, source_entity_id, target_entity_id, relation_type, confidence, document_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (rid, source_id, target_id, relation_type, confidence, doc_id),
            )
    else:
        conn.execute(
            "INSERT INTO relationships (id, source_entity_id, target_entity_id, relation_type, confidence, document_id) VALUES (?, ?, ?, ?, ?, ?)",
            (rid, source_id, target_id, relation_type, confidence, doc_id),
        )
    return rid


def save_chunk(conn, doc_id: str, chunk_text: str, embedding_vector: Optional[List[float]] = None):
    cid = str(uuid.uuid4())
    if db.is_postgres:
        with conn.cursor() as cur:
            emb_val = embedding_vector if embedding_vector else None
            cur.execute(
                "INSERT INTO document_chunks (id, document_id, chunk_text, embedding) VALUES (%s, %s, %s, %s)",
                (cid, doc_id, chunk_text, emb_val),
            )
    else:
        emb_json = json.dumps(embedding_vector) if embedding_vector else None
        conn.execute(
            "INSERT INTO document_chunks (id, document_id, chunk_text, embedding) VALUES (?, ?, ?, ?)",
            (cid, doc_id, chunk_text, emb_json),
        )
    return cid


# ============================================================================
# OBSIDIAN-STYLE NOTES REPOSITORY FUNCTIONS
# ============================================================================

def auto_detect_wikilinks(content: str) -> List[str]:
    """
    Extracts Obsidian [[wikilinks]] from markdown content.
    """
    return re.findall(r'\[\[(.*?)\]\]', content)


def create_note(conn, title: str, content: str = "", tags: Optional[List[str]] = None, is_pinned: bool = False) -> Dict[str, Any]:
    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    tags_json = json.dumps(tags or [])
    
    ph = db.ph
    conn.execute(
        f"INSERT INTO notes (id, title, content, is_pinned, is_archived, tags, created_at, updated_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
        (note_id, title.strip() or "Untitled Note", content, 1 if is_pinned else 0, 0, tags_json, now, now)
    )

    # Auto-link wikilinks
    wikilinks = auto_detect_wikilinks(content)
    for link in wikilinks:
        target_name = link.strip()
        if target_name:
            conn.execute(
                f"INSERT INTO note_links (id, source_note_id, target_type, target_id, link_text, created_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                (str(uuid.uuid4()), note_id, "WIKILINK", target_name, target_name, now)
            )

    return get_note_by_id(conn, note_id)


def get_notes(conn, query: Optional[str] = None, include_archived: bool = False) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM notes WHERE 1=1"
    params = []
    
    if not include_archived:
        sql += " AND is_archived = 0"
    if query and query.strip():
        sql += " AND (lower(title) LIKE ? OR lower(content) LIKE ?)"
        q_wild = f"%{query.strip().lower()}%"
        params.extend([q_wild, q_wild])
        
    sql += " ORDER BY is_pinned DESC, updated_at DESC"
    rows = conn.execute(sql, params).fetchall()
    
    notes = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d.get("tags") else []
        d["wikilinks"] = auto_detect_wikilinks(d.get("content", ""))
        notes.append(d)
    return notes


def get_note_by_id(conn, note_id: str) -> Optional[Dict[str, Any]]:
    ph = db.ph
    row = conn.execute(f"SELECT * FROM notes WHERE id = {ph}", (note_id,)).fetchone()
    if not row:
        return None
    note = dict(row)
    note["tags"] = json.loads(note["tags"]) if note.get("tags") else []
    note["wikilinks"] = auto_detect_wikilinks(note.get("content", ""))
    
    # Fetch links
    links = conn.execute(f"SELECT * FROM note_links WHERE source_note_id = {ph}", (note_id,)).fetchall()
    note["links"] = [dict(l) for l in links]
    return note


def update_note(conn, note_id: str, title: Optional[str] = None, content: Optional[str] = None, tags: Optional[List[str]] = None, is_pinned: Optional[bool] = None, is_archived: Optional[bool] = None) -> Optional[Dict[str, Any]]:
    existing = get_note_by_id(conn, note_id)
    if not existing:
        return None
        
    new_title = title.strip() if title is not None else existing["title"]
    new_content = content if content is not None else existing["content"]
    new_tags = json.dumps(tags) if tags is not None else json.dumps(existing["tags"])
    new_pinned = 1 if is_pinned else (0 if is_pinned is False else existing["is_pinned"])
    new_archived = 1 if is_archived else (0 if is_archived is False else existing["is_archived"])
    now = datetime.now(timezone.utc).isoformat()
    
    ph = db.ph
    conn.execute(
        f"UPDATE notes SET title = {ph}, content = {ph}, tags = {ph}, is_pinned = {ph}, is_archived = {ph}, updated_at = {ph} WHERE id = {ph}",
        (new_title, new_content, new_tags, new_pinned, new_archived, now, note_id)
    )

    # Refresh wikilinks if content changed
    if content is not None:
        conn.execute(f"DELETE FROM note_links WHERE source_note_id = {ph}", (note_id,))
        for link in auto_detect_wikilinks(new_content):
            target_name = link.strip()
            if target_name:
                conn.execute(
                    f"INSERT INTO note_links (id, source_note_id, target_type, target_id, link_text, created_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                    (str(uuid.uuid4()), note_id, "WIKILINK", target_name, target_name, now)
                )

    return get_note_by_id(conn, note_id)


def delete_note(conn, note_id: str) -> bool:
    ph = db.ph
    row = conn.execute(f"SELECT id FROM notes WHERE id = {ph}", (note_id,)).fetchone()
    if not row:
        return False
    conn.execute(f"DELETE FROM note_links WHERE source_note_id = {ph}", (note_id,))
    conn.execute(f"DELETE FROM notes WHERE id = {ph}", (note_id,))
    return True


def delete_document(conn, doc_id: str) -> bool:
    ph = db.ph
    row = conn.execute(f"SELECT id FROM documents WHERE id = {ph}", (doc_id,)).fetchone()
    if not row:
        return False
    if db.is_postgres:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM relationships WHERE document_id = %s", (doc_id,))
            cur.execute("DELETE FROM document_entities WHERE document_id = %s", (doc_id,))
            cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    else:
        conn.execute("DELETE FROM relationships WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM document_entities WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    return True


def duplicate_note(conn, note_id: str) -> Optional[Dict[str, Any]]:
    original = get_note_by_id(conn, note_id)
    if not original:
        return None
    return create_note(conn, f"{original['title']} (Copy)", original["content"], original["tags"], False)


def get_note_graph_data(conn, note_id: str) -> Dict[str, Any]:
    note = get_note_by_id(conn, note_id)
    if not note:
        return {"nodes": [], "edges": []}

    nodes = [{
        "id": note["id"],
        "label": note["title"],
        "type": "NOTE",
        "description": "Obsidian Research Note",
        "degree": len(note["wikilinks"]) + 1
    }]
    edges = []

    for link in note["wikilinks"]:
        target_name = link.strip()
        # Find if entity exists
        ph = db.ph
        ent_row = conn.execute(f"SELECT id, name, entity_type FROM entities WHERE lower(name) = lower({ph})", (target_name,)).fetchone()
        if ent_row:
            target_id = ent_row["id"]
            nodes.append({
                "id": target_id,
                "label": ent_row["name"],
                "type": ent_row["entity_type"],
                "description": f"Extracted {ent_row['entity_type']}",
                "degree": 2
            })
        else:
            target_id = f"virtual_{target_name}"
            nodes.append({
                "id": target_id,
                "label": target_name,
                "type": "TOPIC",
                "description": "Referenced Concept",
                "degree": 1
            })
        edges.append({
            "id": f"link_{note['id']}_{target_id}",
            "source": note["id"],
            "target": target_id,
            "label": "REFERENCES",
            "confidence": 1.0
        })

    return {"nodes": nodes, "edges": edges}


def get_document_graph_data(conn, document_id: str) -> Dict[str, Any]:
    ph = db.ph
    doc = conn.execute(f"SELECT * FROM documents WHERE id = {ph}", (document_id,)).fetchone()
    if not doc:
        return {"nodes": [], "edges": []}

    nodes = [{
        "id": doc["id"],
        "label": doc["title"],
        "type": "PAPER",
        "description": doc["abstract"] or doc["title"],
        "degree": 4
    }]
    edges = []

    ents = conn.execute("""
        SELECT e.id, e.name, e.entity_type, e.description
        FROM entities e
        JOIN document_entities de ON de.entity_id = e.id
        WHERE de.document_id = ?
    """, (document_id,)).fetchall()

    for e in ents:
        nodes.append({
            "id": e["id"],
            "label": e["name"],
            "type": e["entity_type"],
            "description": e["description"] or "",
            "degree": 2
        })
        edges.append({
            "id": f"doc_rel_{doc['id']}_{e['id']}",
            "source": doc["id"],
            "target": e["id"],
            "label": "MENTIONS",
            "confidence": 0.95
        })

    return {"nodes": nodes, "edges": edges}
