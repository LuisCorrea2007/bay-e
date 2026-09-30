"""
BAY-E · Capa de datos SQLite (memoria persistente).

Tablas:
  memories   -> todas las memorias (episódica, semántica, personas, objetos, espacial, rutinas)
  messages   -> historial persistente del chat
  tasks      -> tareas y rutinas programadas
  settings   -> configuración (JSON por sección)
  logs       -> log técnico de eventos
  history    -> series temporales de estados internos (gráficas emocionales)

Nota de diseño: usamos sqlite3 de la stdlib con un lock, ya que el acceso es
de baja concurrencia (una app local). Para producción multi-proceso se puede
sustituir por aiosqlite manteniendo esta misma interfaz pública.
"""
import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

from .config import DB_PATH

_LOCK = threading.RLock()

# ----------------------------------------------------------------- esquema
SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,               -- episodic | semantic | person | object | spatial | routine
    content TEXT NOT NULL,
    detail TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    source TEXT DEFAULT 'system',     -- user | vision | audio | chat | system | sensor
    confidence REAL DEFAULT 0.8,      -- 0..1
    tags TEXT DEFAULT '[]',           -- JSON array
    relations TEXT DEFAULT '[]',      -- JSON array de ids
    last_used REAL DEFAULT 0,
    use_count INTEGER DEFAULT 0,
    pinned INTEGER DEFAULT 0,
    archived INTEGER DEFAULT 0,
    merged_into TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_mem_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_mem_updated ON memories(updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,               -- user | baye
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    emotion TEXT DEFAULT '',
    is_memory INTEGER DEFAULT 0,      -- "recordar" -> generado memoria
    fixed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',    -- pending | running | done | paused | failed
    scheduled_at REAL DEFAULT 0,
    repeat TEXT DEFAULT '',           -- '', daily, weekly, ...
    room TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    done_log TEXT DEFAULT '[]'        -- historial de cumplimiento (fechas ISO)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL               -- JSON
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    level TEXT DEFAULT 'info',        -- debug | info | warn | error | sensitive
    module TEXT DEFAULT 'core',
    human TEXT DEFAULT '',            -- texto legible
    technical TEXT DEFAULT ''         -- detalle técnico / payload
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    data TEXT NOT NULL                -- JSON snapshot de emociones/estado
);

CREATE TABLE IF NOT EXISTS world_entities (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    label_key TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    attrs TEXT NOT NULL DEFAULT '{}',
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    UNIQUE(kind, label_key)
);
CREATE INDEX IF NOT EXISTS idx_world_entity_kind ON world_entities(kind);
CREATE INDEX IF NOT EXISTS idx_world_entity_seen ON world_entities(last_seen DESC);

CREATE TABLE IF NOT EXISTS world_relations (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_id TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    attrs TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(subject_id, predicate, object_id)
);

CREATE TABLE IF NOT EXISTS health_measurements (
    id TEXT PRIMARY KEY,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    person_id TEXT DEFAULT '',
    quality REAL NOT NULL DEFAULT 1.0,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_health_metric_ts ON health_measurements(metric, ts DESC);

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    room TEXT DEFAULT '',
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_observation_ts ON observations(ts DESC);
CREATE INDEX IF NOT EXISTS idx_observation_pattern ON observations(kind, label, room, ts DESC);

CREATE TABLE IF NOT EXISTS face_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    embedding TEXT NOT NULL,
    consent_ts REAL NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_threads (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mind_rules (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 50,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS mobile_nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'android',
    last_seen REAL NOT NULL,
    capabilities TEXT NOT NULL DEFAULT '{}',
    telemetry TEXT NOT NULL DEFAULT '{}',
    token_hash TEXT NOT NULL DEFAULT '',
    paired_at REAL NOT NULL DEFAULT 0,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS learning_candidates (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    source_message_id TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.6,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    memory_id TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_status_created ON learning_candidates(status, created_at DESC);
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


_INIT_DB_DONE = False


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(r["name"]) for r in conn.execute("PRAGMA table_info(" + table + ")").fetchall()}


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Migraciones aditivas para bases locales existentes."""
    cols = _column_names(conn, "messages")
    if "thread_id" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN thread_id TEXT NOT NULL DEFAULT 'default'")
    if "updated_at" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN updated_at REAL NOT NULL DEFAULT 0")
        conn.execute("UPDATE messages SET updated_at=created_at WHERE updated_at=0")
    if "deleted" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0")

    mobile_cols = _column_names(conn, "mobile_nodes")
    if "token_hash" not in mobile_cols:
        conn.execute("ALTER TABLE mobile_nodes ADD COLUMN token_hash TEXT NOT NULL DEFAULT ''")
    if "paired_at" not in mobile_cols:
        conn.execute("ALTER TABLE mobile_nodes ADD COLUMN paired_at REAL NOT NULL DEFAULT 0")
    if "revoked" not in mobile_cols:
        conn.execute("ALTER TABLE mobile_nodes ADD COLUMN revoked INTEGER NOT NULL DEFAULT 0")

    now = time.time()
    conn.execute(
        "INSERT OR IGNORE INTO chat_threads (id,title,created_at,updated_at,archived) VALUES ('default','BAY-E',?,?,0)",
        (now, now),
    )
    row = conn.execute("SELECT MAX(created_at) AS ts FROM messages WHERE thread_id='default'").fetchone()
    if row and row["ts"]:
        conn.execute("UPDATE chat_threads SET updated_at=? WHERE id='default'", (float(row["ts"]),))


def init_db() -> None:
    """Crea esquema + siembra datos iniciales la primera vez."""
    global _INIT_DB_DONE
    with _LOCK:
        conn = _conn()
        conn.executescript(SCHEMA)
        _migrate_schema(conn)
        conn.commit()
        first = conn.execute("SELECT COUNT(*) c FROM memories").fetchone()["c"] == 0
        conn.close()
        if first and not get_setting("seeded"):
            set_setting("seeded", True)
            from .seed import _seed      # import diferido para evitar ciclo
            _seed()
        _INIT_DB_DONE = True


# ----------------------------------------------------------------- memorias
def _row_to_memory(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["relations"] = json.loads(d.get("relations") or "[]")
    d["pinned"] = bool(d["pinned"])
    d["archived"] = bool(d["archived"])
    return d


def add_memory(*, type: str, content: str, detail: str = "", source: str = "system",
               confidence: float = 0.8, tags: Optional[list] = None,
               relations: Optional[list] = None, pinned: bool = False) -> dict:
    now = time.time()
    mid = "m_" + uuid.uuid4().hex[:10]
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO memories (id,type,content,detail,created_at,updated_at,source,confidence,"
            "tags,relations,last_used,use_count,pinned,archived,merged_into) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,0,'')",
            (mid, type, content, detail, now, now, source, confidence,
             json.dumps(tags or []), json.dumps(relations or []), now, 1 if pinned else 0))
        conn.commit()
        row = conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        conn.close()
    return _row_to_memory(row)


def list_memories(*, q: str = "", type: str = "", tag: str = "",
                  include_archived: bool = False, include_pinned_first: bool = True) -> list[dict]:
    sql = "SELECT * FROM memories WHERE 1=1"
    args: list[Any] = []
    if not include_archived:
        sql += " AND archived=0"
    if type:
        sql += " AND type=?"
        args.append(type)
    if tag:
        sql += " AND tags LIKE ?"
        args.append(f'%"{tag}"%')
    if q:
        sql += " AND (content LIKE ? OR detail LIKE ? OR tags LIKE ?)"
        like = f"%{q}%"
        args += [like, like, like]
    order = " ORDER BY pinned DESC, updated_at DESC" if include_pinned_first else " ORDER BY updated_at DESC"
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql + order, args).fetchall()
        conn.close()
    return [_row_to_memory(r) for r in rows]


def get_memory(mid: str) -> Optional[dict]:
    with _LOCK:
        conn = _conn()
        r = conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        conn.close()
    return _row_to_memory(r) if r else None


def update_memory(mid: str, **fields: Any) -> Optional[dict]:
    allowed = {"content", "detail", "type", "source", "confidence", "pinned", "archived"}
    sets, args = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            args.append(1 if isinstance(v, bool) else v)
    if "tags" in fields:
        sets.append("tags=?"); args.append(json.dumps(fields["tags"]))
    if "relations" in fields:
        sets.append("relations=?"); args.append(json.dumps(fields["relations"]))
    if not sets:
        return get_memory(mid)
    sets.append("updated_at=?"); args.append(time.time())
    args.append(mid)
    with _LOCK:
        conn = _conn()
        conn.execute(f"UPDATE memories SET {','.join(sets)} WHERE id=?", args)
        conn.commit()
        r = conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        conn.close()
    return _row_to_memory(r) if r else None


def touch_memory(mid: str) -> None:
    """Registra uso (para 'última vez usada' y confianza asociativa)."""
    with _LOCK:
        conn = _conn()
        conn.execute("UPDATE memories SET last_used=?, use_count=use_count+1 WHERE id=?",
                     (time.time(), mid))
        conn.commit()
        conn.close()


def delete_memory(mid: str) -> bool:
    with _LOCK:
        conn = _conn()
        n = conn.execute("DELETE FROM memories WHERE id=?", (mid,)).rowcount
        conn.commit()
        conn.close()
    return n > 0


def merge_memories(primary_id: str, secondary_id: str) -> Optional[dict]:
    """Fusiona: el contenido de `secondary` pasa como relación/detalle a `primary`."""
    p, s = get_memory(primary_id), get_memory(secondary_id)
    if not p or not s:
        return None
    rel = list(set(p["relations"] + [secondary_id]))
    out = update_memory(primary_id,
                        detail=(p["detail"] + ("\n" if p["detail"] else "") + f"[fusionada] {s['content']}").strip(),
                        relations=rel,
                        confidence=min(1.0, p["confidence"] + 0.05))
    delete_memory(secondary_id)
    return out


def delete_memories_by(**crit: Any) -> int:
    """Borrado masivo por tipo / fuente / antes de fecha. Devuelve nº borrados."""
    sql = "DELETE FROM memories WHERE 1=1"
    args: list[Any] = []
    if crit.get("type"):
        sql += " AND type=?"; args.append(crit["type"])
    if crit.get("before"):
        sql += " AND created_at<?"; args.append(float(crit["before"]))
    if crit.get("person_content_like"):
        sql += " AND content LIKE ?"; args.append(f"%{crit['person_content_like']}%")
    with _LOCK:
        conn = _conn()
        n = conn.execute(sql, args).rowcount
        conn.commit()
        conn.close()
    return n


def export_memories() -> list[dict]:
    with _LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM memories").fetchall()
        conn.close()
    return [_row_to_memory(r) for r in rows]


def import_memories(items: list[dict]) -> int:
    n = 0
    for it in items:
        try:
            add_memory(type=it.get("type", "semantic"), content=it.get("content", ""),
                       detail=it.get("detail", ""), source=it.get("source", "import"),
                       confidence=float(it.get("confidence", 0.8)),
                       tags=it.get("tags", []), relations=it.get("relations", []),
                       pinned=bool(it.get("pinned")))
            n += 1
        except Exception:
            continue
    return n


# ----------------------------------------------------------------- conversaciones / mensajes
def create_thread(title: str = "Nuevo chat") -> dict:
    tid = "chat_" + uuid.uuid4().hex[:10]
    now = time.time()
    title = (title or "Nuevo chat").strip()[:120]
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO chat_threads (id,title,created_at,updated_at,archived) VALUES (?,?,?,?,0)",
            (tid, title, now, now),
        )
        conn.commit()
        conn.close()
    return {"id": tid, "title": title, "created_at": now, "updated_at": now, "archived": False}


def list_threads(include_archived: bool = False) -> list[dict]:
    sql = "SELECT * FROM chat_threads"
    if not include_archived:
        sql += " WHERE archived=0"
    sql += " ORDER BY updated_at DESC"
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql).fetchall()
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["archived"] = bool(d["archived"])
        out.append(d)
    return out


def get_thread(thread_id: str) -> Optional[dict]:
    with _LOCK:
        conn = _conn()
        r = conn.execute("SELECT * FROM chat_threads WHERE id=?", (thread_id,)).fetchone()
        conn.close()
    if not r:
        return None
    d = dict(r)
    d["archived"] = bool(d["archived"])
    return d


def update_thread(thread_id: str, *, title: Optional[str] = None, archived: Optional[bool] = None) -> Optional[dict]:
    sets, args = [], []
    if title is not None:
        sets.append("title=?")
        args.append((title or "Nuevo chat").strip()[:120])
    if archived is not None:
        sets.append("archived=?")
        args.append(1 if archived else 0)
    if not sets:
        return get_thread(thread_id)
    sets.append("updated_at=?")
    args.append(time.time())
    args.append(thread_id)
    with _LOCK:
        conn = _conn()
        conn.execute("UPDATE chat_threads SET " + ",".join(sets) + " WHERE id=?", args)
        conn.commit()
        conn.close()
    return get_thread(thread_id)


def delete_thread(thread_id: str) -> bool:
    if thread_id == "default":
        return False
    with _LOCK:
        conn = _conn()
        conn.execute("DELETE FROM messages WHERE thread_id=?", (thread_id,))
        n = conn.execute("DELETE FROM chat_threads WHERE id=?", (thread_id,)).rowcount
        conn.commit()
        conn.close()
    return n > 0


def _touch_thread(thread_id: str, preview: str = "") -> None:
    now = time.time()
    with _LOCK:
        conn = _conn()
        row = conn.execute("SELECT id,title FROM chat_threads WHERE id=?", (thread_id,)).fetchone()
        if not row:
            title = preview.strip().replace("\n", " ")[:48] or "Nuevo chat"
            conn.execute(
                "INSERT INTO chat_threads (id,title,created_at,updated_at,archived) VALUES (?,?,?,?,0)",
                (thread_id, title, now, now),
            )
        else:
            if row["title"] == "Nuevo chat" and preview.strip():
                title = preview.strip().replace("\n", " ")[:48]
                conn.execute("UPDATE chat_threads SET title=?,updated_at=? WHERE id=?", (title, now, thread_id))
            else:
                conn.execute("UPDATE chat_threads SET updated_at=? WHERE id=?", (now, thread_id))
        conn.commit()
        conn.close()


def add_message(role: str, content: str, emotion: str = "", thread_id: str = "default") -> dict:
    mid = "msg_" + uuid.uuid4().hex[:10]
    now = time.time()
    thread_id = thread_id or "default"
    _touch_thread(thread_id, content if role == "user" else "")
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO messages (id,role,content,created_at,emotion,is_memory,fixed,thread_id,updated_at,deleted) "
            "VALUES (?,?,?,?,?,0,0,?,?,0)",
            (mid, role, content, now, emotion, thread_id, now),
        )
        conn.commit()
        conn.close()
    return {
        "id": mid, "role": role, "content": content, "created_at": now, "updated_at": now,
        "emotion": emotion, "is_memory": False, "fixed": False, "thread_id": thread_id, "deleted": False
    }


def list_messages(limit: int = 200, thread_id: str = "") -> list[dict]:
    sql = "SELECT * FROM messages WHERE deleted=0"
    args = []
    if thread_id:
        sql += " AND thread_id=?"
        args.append(thread_id)
    sql += " ORDER BY created_at ASC LIMIT ?"
    args.append(limit)
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql, args).fetchall()
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["is_memory"] = bool(d.get("is_memory"))
        d["fixed"] = bool(d.get("fixed"))
        d["deleted"] = bool(d.get("deleted"))
        out.append(d)
    return out


def search_messages(q: str, limit: int = 50) -> list[dict]:
    q = " ".join((q or "").split()).strip()
    if not q:
        return []
    like = f"%{q}%"
    with _LOCK:
        conn = _conn()
        rows = conn.execute(
            "SELECT m.id,m.role,m.content,m.created_at,m.thread_id,t.title AS thread_title,t.archived "
            "FROM messages m LEFT JOIN chat_threads t ON t.id=m.thread_id "
            "WHERE m.deleted=0 AND m.content LIKE ? "
            "ORDER BY m.created_at DESC LIMIT ?",
            (like, max(1, min(200, int(limit)))),
        ).fetchall()
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["archived"] = bool(d.get("archived"))
        out.append(d)
    return out


def update_message(msg_id: str, content: str) -> Optional[dict]:
    content = (content or "").strip()
    if not content:
        return None
    with _LOCK:
        conn = _conn()
        conn.execute("UPDATE messages SET content=?,updated_at=? WHERE id=? AND deleted=0", (content, time.time(), msg_id))
        conn.commit()
        r = conn.execute("SELECT * FROM messages WHERE id=? AND deleted=0", (msg_id,)).fetchone()
        conn.close()
    return dict(r) if r else None


def delete_message(msg_id: str) -> bool:
    with _LOCK:
        conn = _conn()
        n = conn.execute("UPDATE messages SET deleted=1,updated_at=? WHERE id=?", (time.time(), msg_id)).rowcount
        conn.commit()
        conn.close()
    return n > 0


def set_message_flag(msg_id: str, field: str, value: bool) -> None:
    col = {"memory": "is_memory", "fixed": "fixed"}.get(field, "fixed")
    with _LOCK:
        conn = _conn()
        conn.execute("UPDATE messages SET " + col + "=?,updated_at=? WHERE id=?", (1 if value else 0, time.time(), msg_id))
        conn.commit()
        conn.close()


# ----------------------------------------------------------------- mente editable
MIND_KINDS = {"restriction", "principle", "goal", "belief", "note"}


def add_mind_rule(kind: str, content: str, *, priority: int = 50, enabled: bool = True) -> dict:
    kind = kind if kind in MIND_KINDS else "note"
    rid = "rule_" + uuid.uuid4().hex[:10]
    now = time.time()
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO mind_rules (id,kind,content,enabled,priority,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (rid, kind, content.strip(), 1 if enabled else 0, max(0, min(100, int(priority))), now, now),
        )
        conn.commit()
        r = conn.execute("SELECT * FROM mind_rules WHERE id=?", (rid,)).fetchone()
        conn.close()
    d = dict(r)
    d["enabled"] = bool(d["enabled"])
    return d


def list_mind_rules(kind: str = "", enabled_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM mind_rules WHERE 1=1"
    args = []
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    if enabled_only:
        sql += " AND enabled=1"
    sql += " ORDER BY priority DESC, updated_at DESC"
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql, args).fetchall()
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["enabled"] = bool(d["enabled"])
        out.append(d)
    return out


def update_mind_rule(rule_id: str, **fields: Any) -> Optional[dict]:
    sets, args = [], []
    if "kind" in fields:
        kind = fields["kind"] if fields["kind"] in MIND_KINDS else "note"
        sets.append("kind=?")
        args.append(kind)
    if "content" in fields:
        sets.append("content=?")
        args.append(str(fields["content"]).strip())
    if "enabled" in fields:
        sets.append("enabled=?")
        args.append(1 if fields["enabled"] else 0)
    if "priority" in fields:
        sets.append("priority=?")
        args.append(max(0, min(100, int(fields["priority"]))))
    if not sets:
        return None
    sets.append("updated_at=?")
    args.append(time.time())
    args.append(rule_id)
    with _LOCK:
        conn = _conn()
        conn.execute("UPDATE mind_rules SET " + ",".join(sets) + " WHERE id=?", args)
        conn.commit()
        r = conn.execute("SELECT * FROM mind_rules WHERE id=?", (rule_id,)).fetchone()
        conn.close()
    if not r:
        return None
    d = dict(r)
    d["enabled"] = bool(d["enabled"])
    return d


def delete_mind_rule(rule_id: str) -> bool:
    with _LOCK:
        conn = _conn()
        n = conn.execute("DELETE FROM mind_rules WHERE id=?", (rule_id,)).rowcount
        conn.commit()
        conn.close()
    return n > 0


# ----------------------------------------------------------------- aprendizaje propuesto
def _row_to_learning_candidate(r: sqlite3.Row) -> dict:
    return dict(r)


def add_learning_candidate(*, kind: str, content: str, source_message_id: str = "",
                           confidence: float = 0.6, reason: str = "") -> Optional[dict]:
    content = " ".join((content or "").split()).strip()
    if not content:
        return None
    with _LOCK:
        conn = _conn()
        duplicate = conn.execute(
            "SELECT * FROM learning_candidates WHERE lower(content)=lower(?) "
            "AND status IN ('pending','approved') ORDER BY created_at DESC LIMIT 1",
            (content,),
        ).fetchone()
        if duplicate:
            conn.close()
            return _row_to_learning_candidate(duplicate)
        existing_memory = conn.execute(
            "SELECT id FROM memories WHERE archived=0 AND lower(content)=lower(?) LIMIT 1",
            (content,),
        ).fetchone()
        if existing_memory:
            conn.close()
            return None
        now = time.time()
        cid = "learn_" + uuid.uuid4().hex[:10]
        conn.execute(
            "INSERT INTO learning_candidates "
            "(id,kind,content,source_message_id,confidence,reason,status,memory_id,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,'pending','',?,?)",
            (cid, kind, content, source_message_id, max(0.0, min(1.0, confidence)), reason, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM learning_candidates WHERE id=?", (cid,)).fetchone()
        conn.close()
    return _row_to_learning_candidate(row)


def list_learning_candidates(status: str = "pending", limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM learning_candidates"
    args: list[Any] = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(max(1, min(500, int(limit))))
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql, args).fetchall()
        conn.close()
    return [_row_to_learning_candidate(r) for r in rows]


def get_learning_candidate(candidate_id: str) -> Optional[dict]:
    with _LOCK:
        conn = _conn()
        row = conn.execute("SELECT * FROM learning_candidates WHERE id=?", (candidate_id,)).fetchone()
        conn.close()
    return _row_to_learning_candidate(row) if row else None


def resolve_learning_candidate(candidate_id: str, action: str) -> Optional[dict]:
    action = (action or "").strip().lower()
    if action not in {"approve", "reject"}:
        raise ValueError("acción de aprendizaje inválida")
    with _LOCK:
        conn = _conn()
        row = conn.execute("SELECT * FROM learning_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            conn.close()
            return None
        item = _row_to_learning_candidate(row)
        if item["status"] != "pending":
            conn.close()
            return item
        now = time.time()
        if action == "reject":
            conn.execute("DELETE FROM learning_candidates WHERE id=?", (candidate_id,))
            conn.commit()
            conn.close()
            return {**item, "status": "rejected", "memory_id": "", "updated_at": now}

        mid = "m_" + uuid.uuid4().hex[:10]
        conn.execute(
            "INSERT INTO memories (id,type,content,detail,created_at,updated_at,source,confidence,"
            "tags,relations,last_used,use_count,pinned,archived,merged_into) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,0,0,0,'')",
            (mid, item["kind"], item["content"], item["reason"], now, now, "learning-review",
             float(item["confidence"]), json.dumps(["learned","user-approved"]), "[]", now),
        )
        conn.execute(
            "UPDATE learning_candidates SET status='approved',memory_id=?,content='',reason='',"
            "source_message_id='',updated_at=? WHERE id=?",
            (mid, now, candidate_id),
        )
        conn.commit()
        out = conn.execute("SELECT * FROM learning_candidates WHERE id=?", (candidate_id,)).fetchone()
        conn.close()
    return _row_to_learning_candidate(out)


# ----------------------------------------------------------------- nodos móviles
def _row_to_mobile_node(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["capabilities"] = json.loads(d.get("capabilities") or "{}")
    d["telemetry"] = json.loads(d.get("telemetry") or "{}")
    d["paired"] = bool(d.get("token_hash")) and not bool(d.get("revoked"))
    d["revoked"] = bool(d.get("revoked"))
    d.pop("token_hash", None)
    return d


def upsert_mobile_node(node_id: str, *, name: str, platform: str = "android",
                       capabilities: Optional[dict] = None, telemetry: Optional[dict] = None) -> dict:
    """Actualiza telemetría sin tocar credenciales de emparejamiento."""
    now = time.time()
    capabilities = capabilities or {}
    telemetry = telemetry or {}
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO mobile_nodes (id,name,platform,last_seen,capabilities,telemetry) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,platform=excluded.platform,last_seen=excluded.last_seen,"
            "capabilities=excluded.capabilities,telemetry=excluded.telemetry",
            (node_id, name, platform, now, json.dumps(capabilities), json.dumps(telemetry)),
        )
        conn.commit()
        r = conn.execute("SELECT * FROM mobile_nodes WHERE id=?", (node_id,)).fetchone()
        conn.close()
    return _row_to_mobile_node(r)


def pair_mobile_node(node_id: str, *, name: str, platform: str, token_hash: str) -> dict:
    now = time.time()
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO mobile_nodes "
            "(id,name,platform,last_seen,capabilities,telemetry,token_hash,paired_at,revoked) "
            "VALUES (?,?,?,?, '{}', '{}', ?, ?, 0) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,platform=excluded.platform,"
            "last_seen=excluded.last_seen,token_hash=excluded.token_hash,paired_at=excluded.paired_at,revoked=0",
            (node_id, name, platform, now, token_hash, now),
        )
        conn.commit()
        r = conn.execute("SELECT * FROM mobile_nodes WHERE id=?", (node_id,)).fetchone()
        conn.close()
    return _row_to_mobile_node(r)


def get_mobile_node(node_id: str) -> Optional[dict]:
    with _LOCK:
        conn = _conn()
        r = conn.execute("SELECT * FROM mobile_nodes WHERE id=?", (node_id,)).fetchone()
        conn.close()
    return _row_to_mobile_node(r) if r else None


def get_mobile_auth(node_id: str) -> Optional[dict]:
    """Vista interna mínima; token_hash nunca se devuelve por endpoints públicos."""
    with _LOCK:
        conn = _conn()
        r = conn.execute(
            "SELECT id,token_hash,paired_at,revoked FROM mobile_nodes WHERE id=?",
            (node_id,),
        ).fetchone()
        conn.close()
    return dict(r) if r else None


def revoke_mobile_node(node_id: str) -> bool:
    with _LOCK:
        conn = _conn()
        n = conn.execute(
            "UPDATE mobile_nodes SET revoked=1,token_hash='' WHERE id=?",
            (node_id,),
        ).rowcount
        conn.commit()
        conn.close()
    return n > 0


def list_mobile_nodes() -> list[dict]:
    with _LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM mobile_nodes ORDER BY last_seen DESC").fetchall()
        conn.close()
    return [_row_to_mobile_node(r) for r in rows]


# ----------------------------------------------------------------- tareas
def add_task(title: str, description: str = "", scheduled_at: float = 0,
             repeat: str = "", room: str = "") -> dict:
    tid = "t_" + uuid.uuid4().hex[:8]
    now = time.time()
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO tasks (id,title,status,description,scheduled_at,repeat,room,created_at,updated_at,done_log) "
            "VALUES (?,?,'pending',?,?,?,?,?,?,?)",
            (tid, title, description, scheduled_at, repeat, room, now, now, "[]"))
        conn.commit()
        conn.close()
    return {"id": tid, "title": title, "description": description, "status": "pending",
            "scheduled_at": scheduled_at, "repeat": repeat, "room": room,
            "created_at": now, "updated_at": now, "done_log": []}


def list_tasks() -> list[dict]:
    with _LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM tasks ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'pending' THEN 1 WHEN 'paused' THEN 2 ELSE 3 END, scheduled_at ASC").fetchall()
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["done_log"] = json.loads(d.get("done_log") or "[]")
        out.append(d)
    return out


def update_task(tid: str, **fields: Any) -> Optional[dict]:
    allowed = {"title", "description", "status", "scheduled_at", "repeat", "room", "done_log"}
    sets, args = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            args.append(json.dumps(v) if k == "done_log" else v)
    if not sets:
        return None
    sets.append("updated_at=?"); args.append(time.time()); args.append(tid)
    with _LOCK:
        conn = _conn()
        conn.execute(f"UPDATE tasks SET {','.join(sets)} WHERE id=?", args)
        conn.commit()
        r = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        conn.close()
    if not r:
        return None
    d = dict(r); d["done_log"] = json.loads(d.get("done_log") or "[]")
    return d


def delete_task(tid: str) -> bool:
    with _LOCK:
        conn = _conn()
        n = conn.execute("DELETE FROM tasks WHERE id=?", (tid,)).rowcount
        conn.commit()
        conn.close()
    return n > 0


# ----------------------------------------------------------------- ajustes
def get_setting(key: str, default: Any = None) -> Any:
    with _LOCK:
        conn = _conn()
        r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        conn.close()
    return json.loads(r["value"]) if r else default


def set_setting(key: str, value: Any) -> None:
    with _LOCK:
        conn = _conn()
        conn.execute("INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (key, json.dumps(value)))
        conn.commit()
        conn.close()


# ----------------------------------------------------------------- logs
def log(level: str, module: str, human: str, technical: str = "") -> None:
    with _LOCK:
        conn = _conn()
        conn.execute("INSERT INTO logs (ts,level,module,human,technical) VALUES (?,?,?,?,?)",
                     (time.time(), level, module, human, technical))
        conn.commit()
        conn.close()


def list_logs(limit: int = 300, level: str = "", module: str = "", only_sensitive: bool = False) -> list[dict]:
    sql = "SELECT * FROM logs WHERE 1=1"
    args: list[Any] = []
    if level:
        sql += " AND level=?"; args.append(level)
    if module:
        sql += " AND module=?"; args.append(module)
    if only_sensitive:
        sql += " AND level='sensitive'"
    sql += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql, args).fetchall()
        conn.close()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------- histórico
def push_history(data: dict) -> None:
    with _LOCK:
        conn = _conn()
        conn.execute("INSERT INTO history (ts,data) VALUES (?,?)", (time.time(), json.dumps(data)))
        # retención: últimas 720 muestras (~36h a 30s)
        conn.execute("DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY ts DESC LIMIT 720)")
        conn.commit()
        conn.close()


def get_history(limit: int = 240) -> list[dict]:
    with _LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM history ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
    out = []
    for r in reversed(rows):
        d = dict(r)
        d["data"] = json.loads(d["data"])
        out.append(d)
    return out

# ----------------------------------------------------------------- world model
def world_upsert_entity(*, entity_id: Optional[str], kind: str, label: str, source: str,
                        confidence: float = 0.7, attrs: Optional[dict] = None) -> dict:
    now = time.time()
    label_key = label.strip().casefold()
    with _LOCK:
        conn = _conn()
        old = conn.execute(
            "SELECT * FROM world_entities WHERE kind=? AND label_key=?",
            (kind, label_key),
        ).fetchone()
        if old:
            merged_attrs = json.loads(old["attrs"] or "{}")
            merged_attrs.update(attrs or {})
            conf = max(float(old["confidence"]), float(confidence))
            conn.execute(
                "UPDATE world_entities SET source=?, confidence=?, attrs=?, last_seen=? WHERE id=?",
                (source, conf, json.dumps(merged_attrs), now, old["id"]),
            )
            eid = old["id"]
        else:
            eid = entity_id or ("e_" + uuid.uuid4().hex[:10])
            conn.execute(
                "INSERT INTO world_entities (id,kind,label,label_key,source,confidence,attrs,first_seen,last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (eid, kind, label, label_key, source, confidence, json.dumps(attrs or {}), now, now),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM world_entities WHERE id=?", (eid,)).fetchone()
        conn.close()
    out = dict(row)
    out["attrs"] = json.loads(out.get("attrs") or "{}")
    return out


def world_upsert_relation(*, relation_id: Optional[str], subject_id: str, predicate: str,
                          object_id: str, source: str, confidence: float = 0.7,
                          attrs: Optional[dict] = None) -> dict:
    now = time.time()
    with _LOCK:
        conn = _conn()
        old = conn.execute(
            "SELECT * FROM world_relations WHERE subject_id=? AND predicate=? AND object_id=?",
            (subject_id, predicate, object_id),
        ).fetchone()
        if old:
            merged_attrs = json.loads(old["attrs"] or "{}")
            merged_attrs.update(attrs or {})
            rid = old["id"]
            conn.execute(
                "UPDATE world_relations SET source=?,confidence=?,attrs=?,updated_at=? WHERE id=?",
                (source, max(float(old["confidence"]), float(confidence)), json.dumps(merged_attrs), now, rid),
            )
        else:
            rid = relation_id or ("r_" + uuid.uuid4().hex[:10])
            conn.execute(
                "INSERT INTO world_relations (id,subject_id,predicate,object_id,source,confidence,attrs,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (rid, subject_id, predicate, object_id, source, confidence, json.dumps(attrs or {}), now, now),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM world_relations WHERE id=?", (rid,)).fetchone()
        conn.close()
    out = dict(row)
    out["attrs"] = json.loads(out.get("attrs") or "{}")
    return out


def world_list_entities(kind: str = "", limit: int = 250) -> list[dict]:
    sql = "SELECT * FROM world_entities"
    args: list[Any] = []
    if kind:
        sql += " WHERE kind=?"
        args.append(kind)
    sql += " ORDER BY last_seen DESC LIMIT ?"
    args.append(limit)
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql, args).fetchall()
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["attrs"] = json.loads(d.get("attrs") or "{}")
        out.append(d)
    return out


def world_list_relations(limit: int = 500) -> list[dict]:
    with _LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM world_relations ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["attrs"] = json.loads(d.get("attrs") or "{}")
        out.append(d)
    return out


# ----------------------------------------------------------------- health measurements
def health_add_measurement(*, metric: str, value: float, unit: str, source: str,
                           person_id: str = "", quality: float = 1.0) -> dict:
    item = {
        "id": "hm_" + uuid.uuid4().hex[:10],
        "metric": metric,
        "value": float(value),
        "unit": unit,
        "source": source,
        "person_id": person_id,
        "quality": float(quality),
        "ts": time.time(),
    }
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO health_measurements (id,metric,value,unit,source,person_id,quality,ts) VALUES (?,?,?,?,?,?,?,?)",
            tuple(item[k] for k in ("id","metric","value","unit","source","person_id","quality","ts")),
        )
        conn.commit()
        conn.close()
    return item


def health_list_measurements(*, metric: str = "", person_id: str = "", limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM health_measurements WHERE 1=1"
    args: list[Any] = []
    if metric:
        sql += " AND metric=?"; args.append(metric)
    if person_id:
        sql += " AND person_id=?"; args.append(person_id)
    sql += " ORDER BY ts DESC LIMIT ?"; args.append(limit)
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql, args).fetchall()
        conn.close()
    return [dict(r) for r in rows]

# ----------------------------------------------------------------- observations / routine learning
def add_observation(*, kind: str, label: str, room: str = "", source: str = "sensor",
                    confidence: float = 0.5, ts: Optional[float] = None) -> dict:
    item = {
        "id": "obs_" + uuid.uuid4().hex[:10],
        "kind": kind,
        "label": label,
        "room": room,
        "source": source,
        "confidence": float(confidence),
        "ts": float(ts or time.time()),
    }
    with _LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO observations (id,kind,label,room,source,confidence,ts) VALUES (?,?,?,?,?,?,?)",
            tuple(item[k] for k in ("id","kind","label","room","source","confidence","ts")),
        )
        conn.commit()
        conn.close()
    return item


def list_observations(*, since: float = 0.0, kind: str = "", label: str = "",
                      room: str = "", limit: int = 1000) -> list[dict]:
    sql = "SELECT * FROM observations WHERE ts>=?"
    args: list[Any] = [float(since)]
    if kind:
        sql += " AND kind=?"; args.append(kind)
    if label:
        sql += " AND label=?"; args.append(label)
    if room:
        sql += " AND room=?"; args.append(room)
    sql += " ORDER BY ts DESC LIMIT ?"; args.append(limit)
    with _LOCK:
        conn = _conn()
        rows = conn.execute(sql, args).fetchall()
        conn.close()
    return [dict(r) for r in rows]

# ----------------------------------------------------------------- opt-in face identity profiles
def face_upsert_profile(*, name: str, embedding: list[float], consent_ts: float) -> dict:
    now = time.time()
    with _LOCK:
        conn = _conn()
        old = conn.execute("SELECT id,created_at FROM face_profiles WHERE name=?", (name,)).fetchone()
        if old:
            fid = old["id"]
            conn.execute(
                "UPDATE face_profiles SET embedding=?,consent_ts=?,updated_at=? WHERE id=?",
                (json.dumps(embedding), consent_ts, now, fid),
            )
        else:
            fid = "face_" + uuid.uuid4().hex[:10]
            conn.execute(
                "INSERT INTO face_profiles (id,name,embedding,consent_ts,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                (fid, name, json.dumps(embedding), consent_ts, now, now),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM face_profiles WHERE id=?", (fid,)).fetchone()
        conn.close()
    out = dict(row)
    out["embedding"] = json.loads(out["embedding"])
    return out


def face_list_profiles() -> list[dict]:
    with _LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM face_profiles ORDER BY name").fetchall()
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["embedding"] = json.loads(d["embedding"])
        out.append(d)
    return out


def face_delete_profile(profile_id: str) -> bool:
    with _LOCK:
        conn = _conn()
        n = conn.execute("DELETE FROM face_profiles WHERE id=?", (profile_id,)).rowcount
        conn.commit()
        conn.close()
    return n > 0


def face_delete_by_name(name: str) -> int:
    with _LOCK:
        conn = _conn()
        n = conn.execute("DELETE FROM face_profiles WHERE name LIKE ?", (name,)).rowcount
        conn.commit()
        conn.close()
    return n


def face_purge() -> int:
    with _LOCK:
        conn = _conn()
        n = conn.execute("DELETE FROM face_profiles").rowcount
        conn.commit()
        conn.close()
    return n