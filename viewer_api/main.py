from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any, TypedDict

import kuzu
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.db import get_db_path


DEFAULT_MAX_NODES = 1000
DEFAULT_MAX_LINKS = 3000
MAX_NODES_CAP = 5000
MAX_LINKS_CAP = 15000

NODE_TYPES = [
    "Project",
    "Session",
    "Error",
    "Solution",
    "Concept",
    "Artifact",
    "DailyActivity",
]

REL_TYPES = [
    "HAS_PROJECT",
    "OCCURRED_IN",
    "SOLVES",
    "REFERENCES",
    "CONTRIBUTES_TO",
    "BELONGS_TO",
    "USES_ARTIFACT",
    "ILLUSTRATES",
    "ATTACHED_TO",
]

SOURCE_DB_PATH = Path(os.getenv("MAHORAGA_SOURCE_DB_PATH", str(get_db_path()))).expanduser()
SNAPSHOT_DB_PATH = Path(__file__).with_name("graph_snapshot.db")
SNAPSHOT_WAL_PATH = SNAPSHOT_DB_PATH.with_suffix(SNAPSHOT_DB_PATH.suffix + ".wal")
_SNAPSHOT_LOCK = threading.Lock()


class GraphNode(TypedDict):
    id: str
    entity_id: str
    entity_type: str
    label: str
    metadata: dict[str, Any]


class GraphLink(TypedDict):
    source: str
    target: str
    type: str


app = FastAPI(title="knowledge-graph-viewer-api", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _node_ref(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def _safe_label(entity_type: str, row: dict[str, Any]) -> str:
    if entity_type == "Project":
        return row.get("name") or row["id"]
    if entity_type == "Session":
        return row.get("summary") or row["id"]
    if entity_type == "Error":
        return row.get("message") or row["id"]
    if entity_type == "Solution":
        return row.get("description") or row["id"]
    if entity_type == "Concept":
        return row.get("title") or row["id"]
    if entity_type == "Artifact":
        return row.get("title") or row["id"]
    if entity_type == "DailyActivity":
        return row.get("date") or row["id"]
    return row["id"]


def _safe_parse_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _refresh_snapshot() -> None:
    source_wal = SOURCE_DB_PATH.with_suffix(SOURCE_DB_PATH.suffix + ".wal")
    with _SNAPSHOT_LOCK:
        if SOURCE_DB_PATH.exists():
            shutil.copy2(SOURCE_DB_PATH, SNAPSHOT_DB_PATH)
        if source_wal.exists():
            shutil.copy2(source_wal, SNAPSHOT_WAL_PATH)


def _get_read_connection() -> kuzu.Connection:
    _refresh_snapshot()
    if not SNAPSHOT_DB_PATH.exists():
        raise RuntimeError(f"Snapshot DB not found at {SNAPSHOT_DB_PATH}")
    db = kuzu.Database(str(SNAPSHOT_DB_PATH))
    conn = kuzu.Connection(db)
    return conn


def _fetch_rows(
    conn: Any,
    query: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    result = conn.execute(query, params or {})
    columns = result.get_column_names()
    rows: list[dict[str, Any]] = []
    while result.has_next():
        row = result.get_next()
        rows.append({columns[i]: row[i] for i in range(len(columns))})
    return rows


def _fetch_nodes(
    conn: Any,
    entity_type: str,
    project_id: str | None,
    per_type_limit: int,
) -> list[GraphNode]:
    params: dict[str, Any] = {"limit": per_type_limit}
    if entity_type == "Project":
        if project_id:
            query = (
                "MATCH (n:Project {id: $project_id}) "
                "RETURN n.id AS id, n.name AS name, n.path AS path, "
                "n.description AS description, n.created_at AS created_at LIMIT $limit"
            )
            params["project_id"] = project_id
        else:
            query = (
                "MATCH (n:Project) "
                "RETURN n.id AS id, n.name AS name, n.path AS path, "
                "n.description AS description, n.created_at AS created_at LIMIT $limit"
            )
    elif entity_type == "Session":
        if project_id:
            query = (
                "MATCH (n:Session {project_id: $project_id}) "
                "RETURN n.id AS id, n.project_id AS project_id, n.summary AS summary, "
                "n.files_touched AS files_touched, n.started_at AS started_at, n.ended_at AS ended_at "
                "LIMIT $limit"
            )
            params["project_id"] = project_id
        else:
            query = (
                "MATCH (n:Session) "
                "RETURN n.id AS id, n.project_id AS project_id, n.summary AS summary, "
                "n.files_touched AS files_touched, n.started_at AS started_at, n.ended_at AS ended_at "
                "LIMIT $limit"
            )
    elif entity_type == "Error":
        if project_id:
            query = (
                "MATCH (n:Error {project_id: $project_id}) "
                "RETURN n.id AS id, n.project_id AS project_id, n.session_id AS session_id, "
                "n.message AS message, n.context AS context, n.file AS file, n.timestamp AS timestamp "
                "LIMIT $limit"
            )
            params["project_id"] = project_id
        else:
            query = (
                "MATCH (n:Error) "
                "RETURN n.id AS id, n.project_id AS project_id, n.session_id AS session_id, "
                "n.message AS message, n.context AS context, n.file AS file, n.timestamp AS timestamp "
                "LIMIT $limit"
            )
    elif entity_type == "Solution":
        if project_id:
            query = (
                "MATCH (n:Solution)-[:SOLVES]->(:Error)-[:OCCURRED_IN]->(:Session {project_id: $project_id}) "
                "RETURN DISTINCT n.id AS id, n.error_id AS error_id, n.description AS description, "
                "n.code_snippet AS code_snippet, n.timestamp AS timestamp LIMIT $limit"
            )
            params["project_id"] = project_id
        else:
            query = (
                "MATCH (n:Solution) "
                "RETURN n.id AS id, n.error_id AS error_id, n.description AS description, "
                "n.code_snippet AS code_snippet, n.timestamp AS timestamp LIMIT $limit"
            )
    elif entity_type == "Concept":
        if project_id:
            query = (
                "MATCH (:Session {project_id: $project_id})-[:REFERENCES]->(n:Concept) "
                "RETURN DISTINCT n.id AS id, n.title AS title, n.content AS content, n.tags AS tags LIMIT $limit"
            )
            params["project_id"] = project_id
        else:
            query = (
                "MATCH (n:Concept) "
                "RETURN n.id AS id, n.title AS title, n.content AS content, n.tags AS tags LIMIT $limit"
            )
    elif entity_type == "Artifact":
        if project_id:
            query = (
                "MATCH (:Session {project_id: $project_id})-[:USES_ARTIFACT]->(n:Artifact) "
                "RETURN DISTINCT n.id AS id, n.type AS type, n.title AS title, n.description AS description, "
                "n.created_by AS created_by, n.tags AS tags, n.timestamp AS timestamp, "
                "n.content AS content, n.file_path AS file_path LIMIT $limit"
            )
            params["project_id"] = project_id
        else:
            query = (
                "MATCH (n:Artifact) "
                "RETURN n.id AS id, n.type AS type, n.title AS title, n.description AS description, "
                "n.created_by AS created_by, n.tags AS tags, n.timestamp AS timestamp, "
                "n.content AS content, n.file_path AS file_path LIMIT $limit"
            )
    else:  # DailyActivity
        if project_id:
            query = (
                "MATCH (n:DailyActivity {project_id: $project_id}) "
                "RETURN n.id AS id, n.date AS date, n.project_id AS project_id, n.summary AS summary, "
                "n.session_ids AS session_ids, n.errors_count AS errors_count, "
                "n.resolved_errors_count AS resolved_errors_count LIMIT $limit"
            )
            params["project_id"] = project_id
        else:
            query = (
                "MATCH (n:DailyActivity) "
                "RETURN n.id AS id, n.date AS date, n.project_id AS project_id, n.summary AS summary, "
                "n.session_ids AS session_ids, n.errors_count AS errors_count, "
                "n.resolved_errors_count AS resolved_errors_count LIMIT $limit"
            )

    rows = _fetch_rows(conn, query, params)
    nodes: list[GraphNode] = []
    for row in rows:
        if not row.get("id"):
            continue

        metadata: dict[str, Any]
        if entity_type == "Project":
            metadata = {
                "path": row.get("path"),
                "description": row.get("description"),
                "created_at": row.get("created_at"),
            }
        elif entity_type == "Session":
            metadata = {
                "project_id": row.get("project_id"),
                "summary": row.get("summary"),
                "files_touched": _safe_parse_json(row.get("files_touched")),
                "started_at": row.get("started_at"),
                "ended_at": row.get("ended_at"),
            }
        elif entity_type == "Error":
            metadata = {
                "project_id": row.get("project_id"),
                "session_id": row.get("session_id"),
                "message": row.get("message"),
                "context": row.get("context"),
                "file": row.get("file"),
                "timestamp": row.get("timestamp"),
            }
        elif entity_type == "Solution":
            metadata = {
                "error_id": row.get("error_id"),
                "description": row.get("description"),
                "code_snippet": row.get("code_snippet"),
                "timestamp": row.get("timestamp"),
            }
        elif entity_type == "Concept":
            metadata = {
                "title": row.get("title"),
                "content": row.get("content"),
                "tags": _safe_parse_json(row.get("tags")),
            }
        elif entity_type == "Artifact":
            metadata = {
                "type": row.get("type"),
                "title": row.get("title"),
                "description": row.get("description"),
                "created_by": row.get("created_by"),
                "tags": _safe_parse_json(row.get("tags")),
                "timestamp": row.get("timestamp"),
                "content": row.get("content"),
                "file_path": row.get("file_path"),
            }
        else:
            metadata = {
                "date": row.get("date"),
                "project_id": row.get("project_id"),
                "summary": row.get("summary"),
                "session_ids": _safe_parse_json(row.get("session_ids")),
                "errors_count": row.get("errors_count"),
                "resolved_errors_count": row.get("resolved_errors_count"),
            }

        nodes.append(
            {
                "id": _node_ref(entity_type, str(row["id"])),
                "entity_id": str(row["id"]),
                "entity_type": entity_type,
                "label": _safe_label(entity_type, row),
                "metadata": metadata,
            }
        )

    return nodes


def _fetch_links(
    conn: Any, rel_type: str, project_id: str | None, per_rel_limit: int
) -> list[GraphLink]:
    params: dict[str, Any] = {"limit": per_rel_limit}
    if rel_type == "HAS_PROJECT":
        query = (
            "MATCH (s:Session)-[:HAS_PROJECT]->(p:Project) "
            "WHERE $project_id IS NULL OR p.id = $project_id "
            "RETURN s.id AS source_id, p.id AS target_id LIMIT $limit"
        )
    elif rel_type == "OCCURRED_IN":
        query = (
            "MATCH (e:Error)-[:OCCURRED_IN]->(s:Session) "
            "WHERE $project_id IS NULL OR s.project_id = $project_id "
            "RETURN e.id AS source_id, s.id AS target_id LIMIT $limit"
        )
    elif rel_type == "SOLVES":
        query = (
            "MATCH (sol:Solution)-[:SOLVES]->(e:Error)-[:OCCURRED_IN]->(s:Session) "
            "WHERE $project_id IS NULL OR s.project_id = $project_id "
            "RETURN DISTINCT sol.id AS source_id, e.id AS target_id LIMIT $limit"
        )
    elif rel_type == "REFERENCES":
        query = (
            "MATCH (s:Session)-[:REFERENCES]->(c:Concept) "
            "WHERE $project_id IS NULL OR s.project_id = $project_id "
            "RETURN s.id AS source_id, c.id AS target_id LIMIT $limit"
        )
    elif rel_type == "CONTRIBUTES_TO":
        query = (
            "MATCH (s:Session)-[:CONTRIBUTES_TO]->(da:DailyActivity) "
            "WHERE $project_id IS NULL OR s.project_id = $project_id "
            "RETURN s.id AS source_id, da.id AS target_id LIMIT $limit"
        )
    elif rel_type == "BELONGS_TO":
        query = (
            "MATCH (da:DailyActivity)-[:BELONGS_TO]->(p:Project) "
            "WHERE $project_id IS NULL OR p.id = $project_id "
            "RETURN da.id AS source_id, p.id AS target_id LIMIT $limit"
        )
    elif rel_type == "USES_ARTIFACT":
        query = (
            "MATCH (s:Session)-[:USES_ARTIFACT]->(a:Artifact) "
            "WHERE $project_id IS NULL OR s.project_id = $project_id "
            "RETURN s.id AS source_id, a.id AS target_id LIMIT $limit"
        )
    elif rel_type == "ILLUSTRATES":
        query = (
            "MATCH (c:Concept)-[:ILLUSTRATES]->(a:Artifact) "
            "WHERE $project_id IS NULL OR EXISTS { "
            "  MATCH (:Session {project_id: $project_id})-[:REFERENCES]->(c) "
            "} "
            "RETURN DISTINCT c.id AS source_id, a.id AS target_id LIMIT $limit"
        )
    else:  # ATTACHED_TO
        query = (
            "MATCH (a:Artifact)-[:ATTACHED_TO]->(e:Error)-[:OCCURRED_IN]->(s:Session) "
            "WHERE $project_id IS NULL OR s.project_id = $project_id "
            "RETURN DISTINCT a.id AS source_id, e.id AS target_id LIMIT $limit"
        )

    params["project_id"] = project_id
    rows = _fetch_rows(conn, query, params)

    source_type, target_type = {
        "HAS_PROJECT": ("Session", "Project"),
        "OCCURRED_IN": ("Error", "Session"),
        "SOLVES": ("Solution", "Error"),
        "REFERENCES": ("Session", "Concept"),
        "CONTRIBUTES_TO": ("Session", "DailyActivity"),
        "BELONGS_TO": ("DailyActivity", "Project"),
        "USES_ARTIFACT": ("Session", "Artifact"),
        "ILLUSTRATES": ("Concept", "Artifact"),
        "ATTACHED_TO": ("Artifact", "Error"),
    }[rel_type]

    return [
        {
            "source": _node_ref(source_type, str(row["source_id"])),
            "target": _node_ref(target_type, str(row["target_id"])),
            "type": rel_type,
        }
        for row in rows
        if row.get("source_id") and row.get("target_id")
    ]


def _fetch_unlinked_projects(conn: Any, limit: int) -> list[GraphNode]:
    rows = _fetch_rows(
        conn,
        """
        MATCH (p:Project)
        WHERE NOT EXISTS { MATCH (:Session)-[:HAS_PROJECT]->(p) }
          AND NOT EXISTS { MATCH (:DailyActivity)-[:BELONGS_TO]->(p) }
        RETURN p.id AS id, p.name AS name, p.path AS path,
               p.description AS description, p.created_at AS created_at
        LIMIT $limit
        """,
        {"limit": limit},
    )
    nodes: list[GraphNode] = []
    for row in rows:
        if not row.get("id"):
            continue
        nodes.append(
            {
                "id": _node_ref("Project", str(row["id"])),
                "entity_id": str(row["id"]),
                "entity_type": "Project",
                "label": row.get("name") or str(row["id"]),
                "metadata": {
                    "path": row.get("path"),
                    "description": row.get("description"),
                    "created_at": row.get("created_at"),
                },
            }
        )
    return nodes


def _fetch_unlinked_concepts(conn: Any, limit: int) -> list[GraphNode]:
    rows = _fetch_rows(
        conn,
        """
        MATCH (c:Concept)
        WHERE NOT EXISTS { MATCH (:Session)-[:REFERENCES]->(c) }
          AND NOT EXISTS { MATCH (c)-[:ILLUSTRATES]->(:Artifact) }
        RETURN c.id AS id, c.title AS title, c.content AS content, c.tags AS tags
        LIMIT $limit
        """,
        {"limit": limit},
    )
    nodes: list[GraphNode] = []
    for row in rows:
        if not row.get("id"):
            continue
        nodes.append(
            {
                "id": _node_ref("Concept", str(row["id"])),
                "entity_id": str(row["id"]),
                "entity_type": "Concept",
                "label": row.get("title") or str(row["id"]),
                "metadata": {
                    "title": row.get("title"),
                    "content": row.get("content"),
                    "tags": _safe_parse_json(row.get("tags")),
                },
            }
        )
    return nodes


def _project_exists(conn: Any, project_id: str) -> bool:
    rows = _fetch_rows(
        conn,
        "MATCH (p:Project {id: $project_id}) RETURN p.id AS id LIMIT 1",
        {"project_id": project_id},
    )
    return bool(rows)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/graph/refresh-snapshot")
def refresh_snapshot() -> dict[str, str]:
    _refresh_snapshot()
    return {"status": "ok", "snapshot_path": str(SNAPSHOT_DB_PATH)}


@app.get("/v1/graph/summary")
def graph_summary(
    project_id: str | None = Query(default=None),
    max_nodes: int = Query(default=DEFAULT_MAX_NODES, ge=1, le=MAX_NODES_CAP),
    max_links: int = Query(default=DEFAULT_MAX_LINKS, ge=1, le=MAX_LINKS_CAP),
) -> dict[str, Any]:
    conn = _get_read_connection()
    try:
        if project_id and not _project_exists(conn, project_id):
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

        per_type_limit = max(1, max_nodes // len(NODE_TYPES))
        per_rel_limit = max(1, max_links // len(REL_TYPES))

        node_map: dict[str, GraphNode] = {}
        for entity_type in NODE_TYPES:
            for node in _fetch_nodes(conn, entity_type, project_id, per_type_limit):
                if len(node_map) >= max_nodes:
                    break
                node_map[node["id"]] = node

        links: list[GraphLink] = []
        seen_links: set[tuple[str, str, str]] = set()
        for rel_type in REL_TYPES:
            for link in _fetch_links(conn, rel_type, project_id, per_rel_limit):
                if len(links) >= max_links:
                    break
                key = (link["source"], link["target"], link["type"])
                if key in seen_links:
                    continue
                seen_links.add(key)
                links.append(link)

                if link["source"] not in node_map and len(node_map) < max_nodes:
                    source_type, source_id = link["source"].split(":", 1)
                    node_map[link["source"]] = {
                        "id": link["source"],
                        "entity_id": source_id,
                        "entity_type": source_type,
                        "label": source_id,
                        "metadata": {},
                    }
                if link["target"] not in node_map and len(node_map) < max_nodes:
                    target_type, target_id = link["target"].split(":", 1)
                    node_map[link["target"]] = {
                        "id": link["target"],
                        "entity_id": target_id,
                        "entity_type": target_type,
                        "label": target_id,
                        "metadata": {},
                    }

        # Reserve room for isolated concepts/projects so unlinked nodes are visible by default.
        if project_id is None and len(node_map) < max_nodes:
            remaining = max_nodes - len(node_map)
            isolated_budget = max(1, min(remaining, max_nodes // 4, 25))

            for node in _fetch_unlinked_concepts(conn, max(1, isolated_budget // 2)):
                if len(node_map) >= max_nodes:
                    break
                node_map.setdefault(node["id"], node)

            remaining = max_nodes - len(node_map)
            if remaining > 0:
                for node in _fetch_unlinked_projects(conn, remaining):
                    if len(node_map) >= max_nodes:
                        break
                    node_map.setdefault(node["id"], node)

        nodes = list(node_map.values())
        node_counts = Counter(node["entity_type"] for node in nodes)
        link_counts = Counter(link["type"] for link in links)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": {
                "project_id": project_id,
                "max_nodes": max_nodes,
                "max_links": max_links,
            },
            "counts": {
                "nodes": len(nodes),
                "links": len(links),
                "node_types": dict(node_counts),
                "link_types": dict(link_counts),
            },
            "nodes": nodes,
            "links": links,
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass
