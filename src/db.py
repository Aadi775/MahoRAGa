import json
import kuzu
import uuid
import atexit
from . import embeddings as emb
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

EMBEDDING_DIM = emb.EMBEDDING_DIM
_DB_SINGLETON: Optional[kuzu.Database] = None
_DB_SINGLETON_PATH: Optional[str] = None
_SCHEMA_READY_PATHS: set[str] = set()


def _close_db_singleton() -> None:
    global _DB_SINGLETON
    if _DB_SINGLETON is not None:
        _DB_SINGLETON.close()
        _DB_SINGLETON = None


atexit.register(_close_db_singleton)


def get_db_path() -> Path:
    db_path = Path.home() / ".config" / "mahoraga" / "graph.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_connection() -> kuzu.Connection:
    global _DB_SINGLETON, _DB_SINGLETON_PATH

    db_path = str(get_db_path())

    if _DB_SINGLETON is not None and _DB_SINGLETON_PATH != db_path:
        _DB_SINGLETON.close()
        _DB_SINGLETON = None

    if _DB_SINGLETON is None:
        _DB_SINGLETON = kuzu.Database(db_path)
        _DB_SINGLETON_PATH = db_path

    conn = kuzu.Connection(_DB_SINGLETON)
    if db_path not in _SCHEMA_READY_PATHS:
        init_schema(conn)
        _SCHEMA_READY_PATHS.add(db_path)

    return conn


def init_schema(conn: kuzu.Connection) -> None:
    existing_node_tables = set()
    existing_rel_tables = set()
    try:
        result = conn.execute("CALL SHOW_TABLES() RETURN *")
        while result.has_next():
            row = result.get_next()
            table_name = row[1]
            table_type = row[2]
            if table_type == "NODE":
                existing_node_tables.add(table_name)
            elif table_type == "REL":
                existing_rel_tables.add(table_name)
    except Exception:
        pass

    if "Project" not in existing_node_tables:
        conn.execute("""
            CREATE NODE TABLE Project(
                id STRING,
                name STRING,
                path STRING,
                description STRING,
                created_at STRING,
                PRIMARY KEY (id)
            )
        """)

    if "Session" not in existing_node_tables:
        conn.execute("""
            CREATE NODE TABLE Session(
                id STRING,
                project_id STRING,
                summary STRING,
                files_touched STRING,
                started_at STRING,
                ended_at STRING,
                PRIMARY KEY (id)
            )
        """)

    if "Error" not in existing_node_tables:
        conn.execute(f"""
            CREATE NODE TABLE Error(
                id STRING,
                project_id STRING,
                session_id STRING,
                message STRING,
                context STRING,
                file STRING,
                timestamp STRING,
                message_embedding FLOAT[{EMBEDDING_DIM}],
                PRIMARY KEY (id)
            )
        """)

    if "Solution" not in existing_node_tables:
        conn.execute("""
            CREATE NODE TABLE Solution(
                id STRING,
                error_id STRING,
                description STRING,
                code_snippet STRING,
                timestamp STRING,
                PRIMARY KEY (id)
            )
        """)

    if "Concept" not in existing_node_tables:
        conn.execute(f"""
            CREATE NODE TABLE Concept(
                id STRING,
                title STRING,
                content STRING,
                tags STRING,
                embedding FLOAT[{EMBEDDING_DIM}],
                PRIMARY KEY (id)
            )
        """)

    if "DailyActivity" not in existing_node_tables:
        conn.execute("""
            CREATE NODE TABLE DailyActivity(
                id STRING,
                date STRING,
                project_id STRING,
                summary STRING,
                session_ids STRING,
                errors_count INT64,
                PRIMARY KEY (id)
            )
        """)

    if "HAS_PROJECT" not in existing_rel_tables:
        conn.execute("CREATE REL TABLE HAS_PROJECT(FROM Session TO Project)")

    if "OCCURRED_IN" not in existing_rel_tables:
        conn.execute("CREATE REL TABLE OCCURRED_IN(FROM Error TO Session)")

    if "SOLVES" not in existing_rel_tables:
        conn.execute("CREATE REL TABLE SOLVES(FROM Solution TO Error)")

    if "REFERENCES" not in existing_rel_tables:
        conn.execute("CREATE REL TABLE REFERENCES(FROM Session TO Concept)")

    if "CONTRIBUTES_TO" not in existing_rel_tables:
        conn.execute("CREATE REL TABLE CONTRIBUTES_TO(FROM Session TO DailyActivity)")

    if "BELONGS_TO" not in existing_rel_tables:
        conn.execute("CREATE REL TABLE BELONGS_TO(FROM DailyActivity TO Project)")


def _result_to_dicts(result) -> list[dict]:
    rows = []
    columns = result.get_column_names()
    base_counts: dict[str, int] = {}
    for col in columns:
        base = col.split(".")[-1] if "." in col else col
        base_counts[base] = base_counts.get(base, 0) + 1

    while result.has_next():
        row = result.get_next()
        row_dict = {}
        for i, col in enumerate(columns):
            base = col.split(".")[-1] if "." in col else col
            key = col if base_counts.get(base, 0) > 1 else base
            row_dict[key] = row[i]
        rows.append(row_dict)
    return rows


def _parse_json_field(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def add_project(conn: kuzu.Connection, name: str, path: str, description: str = "") -> str:
    project_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "CREATE (:Project {id: $id, name: $name, path: $path, description: $description, created_at: $created_at})",
        {
            "id": project_id,
            "name": name,
            "path": path,
            "description": description,
            "created_at": created_at,
        },
    )
    return project_id


def get_project_by_name(conn: kuzu.Connection, name: str) -> Optional[dict]:
    result = conn.execute("MATCH (p:Project {name: $name}) RETURN p.*", {"name": name})
    rows = _result_to_dicts(result)
    if rows:
        return rows[0]
    return None


def get_project_by_id(conn: kuzu.Connection, project_id: str) -> Optional[dict]:
    result = conn.execute("MATCH (p:Project {id: $id}) RETURN p.*", {"id": project_id})
    rows = _result_to_dicts(result)
    if rows:
        return rows[0]
    return None


def list_projects(conn: kuzu.Connection) -> list[dict]:
    result = conn.execute("MATCH (p:Project) RETURN p.* ORDER BY p.created_at DESC")
    return _result_to_dicts(result)


def update_project(
    conn: kuzu.Connection,
    project_id: str,
    name: Optional[str] = None,
    path: Optional[str] = None,
    description: Optional[str] = None,
    merge_project_id: Optional[str] = None,
) -> dict:
    if merge_project_id:
        merge_target = get_project_by_id(conn, merge_project_id)
        if not merge_target:
            return {"error": f"Target project {merge_project_id} not found"}

        result = conn.execute(
            "MATCH (s:Session {project_id: $old_id}) RETURN s.id",
            {"old_id": project_id},
        )
        session_ids = [row["id"] for row in _result_to_dicts(result)]

        conn.execute(
            "MATCH (s:Session {project_id: $old_id}) SET s.project_id = $new_id",
            {"old_id": project_id, "new_id": merge_project_id},
        )

        conn.execute(
            """MATCH (s:Session {project_id: $new_id})-[r:HAS_PROJECT]->(p:Project {id: $old_id})
               DELETE r""",
            {"old_id": project_id, "new_id": merge_project_id},
        )

        conn.execute(
            """MATCH (s:Session {project_id: $new_id}), (p:Project {id: $new_id})
               MERGE (s)-[:HAS_PROJECT]->(p)""",
            {"new_id": merge_project_id},
        )

        conn.execute(
            "MATCH (e:Error {project_id: $old_id}) SET e.project_id = $new_id",
            {"old_id": project_id, "new_id": merge_project_id},
        )

        conn.execute(
            "MATCH (da:DailyActivity {project_id: $old_id}) SET da.project_id = $new_id",
            {"old_id": project_id, "new_id": merge_project_id},
        )

        conn.execute(
            """MATCH (da:DailyActivity {project_id: $new_id})-[r:BELONGS_TO]->(p:Project {id: $old_id})
               DELETE r""",
            {"old_id": project_id, "new_id": merge_project_id},
        )

        conn.execute(
            """MATCH (da:DailyActivity {project_id: $new_id}), (p:Project {id: $new_id})
               MERGE (da)-[:BELONGS_TO]->(p)""",
            {"new_id": merge_project_id},
        )

        conn.execute("MATCH (p:Project {id: $id}) DELETE p", {"id": project_id})

        return {
            "merged": True,
            "into": merge_project_id,
            "sessions_moved": len(session_ids),
        }

    updates = []
    params = {"id": project_id}
    if name is not None:
        updates.append("p.name = $name")
        params["name"] = name
    if path is not None:
        updates.append("p.path = $path")
        params["path"] = path
    if description is not None:
        updates.append("p.description = $description")
        params["description"] = description

    if updates:
        query = f"MATCH (p:Project {{id: $id}}) SET {', '.join(updates)}"
        conn.execute(query, params)

    return {"updated": True}


def add_session(
    conn: kuzu.Connection, project_id: str, summary: str, files_touched: list[str]
) -> str:
    session_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    files_json = json.dumps(files_touched)

    conn.execute(
        """CREATE (:Session {
            id: $id, 
            project_id: $project_id, 
            summary: $summary, 
            files_touched: $files_touched, 
            started_at: $started_at, 
            ended_at: ""
        })""",
        {
            "id": session_id,
            "project_id": project_id,
            "summary": summary,
            "files_touched": files_json,
            "started_at": started_at,
        },
    )

    conn.execute(
        "MATCH (s:Session {id: $sid}), (p:Project {id: $pid}) CREATE (s)-[:HAS_PROJECT]->(p)",
        {"sid": session_id, "pid": project_id},
    )

    return session_id


def close_session(conn: kuzu.Connection, session_id: str, ended_at: Optional[str] = None) -> dict:
    if ended_at is None:
        ended_at = datetime.now(timezone.utc).isoformat()
    else:
        ended_at = _to_utc_iso(_parse_iso_datetime(ended_at))

    conn.execute(
        "MATCH (s:Session {id: $id}) SET s.ended_at = $ended_at",
        {"id": session_id, "ended_at": ended_at},
    )

    session = get_session_by_id(conn, session_id)
    if session:
        _update_or_create_daily_activity(conn, session)

    return {"closed": True, "ended_at": ended_at}


def get_session_by_id(conn: kuzu.Connection, session_id: str) -> Optional[dict]:
    result = conn.execute("MATCH (s:Session {id: $id}) RETURN s.*", {"id": session_id})
    rows = _result_to_dicts(result)
    if rows:
        session = rows[0]
        session["files_touched"] = _parse_json_field(session.get("files_touched"))
        return session
    return None


def _update_or_create_daily_activity(conn: kuzu.Connection, session: dict) -> None:
    session_id = session["id"]
    project_id = session["project_id"]
    started_at = session["started_at"]
    date = started_at[:10]

    result = conn.execute(
        "MATCH (da:DailyActivity {date: $date, project_id: $project_id}) RETURN da.*",
        {"date": date, "project_id": project_id},
    )
    existing = _result_to_dicts(result)

    if existing:
        da = existing[0]
        da_id = da["id"]
        session_ids = _parse_json_field(da.get("session_ids", "[]"))
        session_added = False
        if session_id not in session_ids:
            session_ids.append(session_id)
            session_added = True

        error_result = conn.execute(
            "MATCH (e:Error {session_id: $sid}) RETURN count(e)", {"sid": session_id}
        )
        error_count = 0
        if error_result.has_next():
            error_count = error_result.get_next()[0]

        error_delta = error_count if session_added else 0

        conn.execute(
            "MATCH (da:DailyActivity {id: $id}) SET da.session_ids = $session_ids, da.errors_count = da.errors_count + $error_count",
            {
                "id": da_id,
                "session_ids": json.dumps(session_ids),
                "error_count": error_delta,
            },
        )
    else:
        da_id = str(uuid.uuid4())
        summary = session.get("summary", "")
        session_ids = [session_id]
        error_result = conn.execute(
            "MATCH (e:Error {session_id: $sid}) RETURN count(e)", {"sid": session_id}
        )
        initial_error_count = error_result.get_next()[0] if error_result.has_next() else 0

        conn.execute(
            """CREATE (:DailyActivity {
                id: $id,
                date: $date,
                project_id: $project_id,
                summary: $summary,
                session_ids: $session_ids,
                errors_count: $errors_count
            })""",
            {
                "id": da_id,
                "date": date,
                "project_id": project_id,
                "summary": summary,
                "session_ids": json.dumps(session_ids),
                "errors_count": initial_error_count,
            },
        )

        conn.execute(
            "MATCH (da:DailyActivity {id: $da_id}), (p:Project {id: $pid}) CREATE (da)-[:BELONGS_TO]->(p)",
            {"da_id": da_id, "pid": project_id},
        )


def link_session_to_daily_activity(conn: kuzu.Connection, session_id: str) -> None:
    session = get_session_by_id(conn, session_id)
    if session:
        result = conn.execute(
            "MATCH (da:DailyActivity {date: $date, project_id: $project_id}) RETURN da.id",
            {"date": session["started_at"][:10], "project_id": session["project_id"]},
        )
        da_rows = _result_to_dicts(result)
        if da_rows:
            da_id = da_rows[0]["id"]
            existing_rel = conn.execute(
                """MATCH (s:Session {id: $sid})-[r:CONTRIBUTES_TO]->(da:DailyActivity {id: $da_id})
                   RETURN count(r)""",
                {"sid": session_id, "da_id": da_id},
            )
            rel_count = existing_rel.get_next()[0] if existing_rel.has_next() else 0
            if rel_count > 0:
                return
            conn.execute(
                "MATCH (s:Session {id: $sid}), (da:DailyActivity {id: $da_id}) CREATE (s)-[:CONTRIBUTES_TO]->(da)",
                {"sid": session_id, "da_id": da_id},
            )


def add_error(
    conn: kuzu.Connection,
    project_id: str,
    session_id: str,
    message: str,
    context: str,
    file: str,
    message_embedding: list[float],
) -> str:
    exact_result = conn.execute(
        """MATCH (e:Error {
               project_id: $project_id,
               session_id: $session_id,
               message: $message,
               context: $context,
               file: $file
           })
           RETURN e.id LIMIT 1""",
        {
            "project_id": project_id,
            "session_id": session_id,
            "message": message,
            "context": context,
            "file": file,
        },
    )
    if exact_result.has_next():
        return exact_result.get_next()[0]

    near_result = conn.execute(
        """MATCH (e:Error {project_id: $project_id, file: $file})
           RETURN e.id, e.message_embedding""",
        {"project_id": project_id, "file": file},
    )
    while near_result.has_next():
        row = near_result.get_next()
        existing_embedding = list(row[1]) if row[1] else []
        if (
            existing_embedding
            and emb.cosine_similarity(message_embedding, existing_embedding) >= 0.995
        ):
            return row[0]

    error_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    conn.execute(
        f"""CREATE (:Error {{
            id: $id,
            project_id: $project_id,
            session_id: $session_id,
            message: $message,
            context: $context,
            file: $file,
            timestamp: $timestamp,
            message_embedding: $embedding
        }})""",
        {
            "id": error_id,
            "project_id": project_id,
            "session_id": session_id,
            "message": message,
            "context": context,
            "file": file,
            "timestamp": timestamp,
            "embedding": message_embedding,
        },
    )

    conn.execute(
        "MATCH (e:Error {id: $eid}), (s:Session {id: $sid}) CREATE (e)-[:OCCURRED_IN]->(s)",
        {"eid": error_id, "sid": session_id},
    )

    conn.execute(
        """MATCH (s:Session {id: $sid})-[:CONTRIBUTES_TO]->(da:DailyActivity {project_id: $pid})
           WITH da
           MATCH (s2:Session)-[:CONTRIBUTES_TO]->(da)
           OPTIONAL MATCH (e:Error)-[:OCCURRED_IN]->(s2)
           WITH da, count(DISTINCT e) as err_count
           SET da.errors_count = err_count""",
        {"pid": project_id, "sid": session_id},
    )

    return error_id


def add_solution(
    conn: kuzu.Connection, error_id: str, description: str, code_snippet: str = ""
) -> str:
    error_result = conn.execute("MATCH (e:Error {id: $id}) RETURN e.id", {"id": error_id})
    if not error_result.has_next():
        raise ValueError(f"Error {error_id} not found")

    solution_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """CREATE (:Solution {
            id: $id,
            error_id: $error_id,
            description: $description,
            code_snippet: $code_snippet,
            timestamp: $timestamp
        })""",
        {
            "id": solution_id,
            "error_id": error_id,
            "description": description,
            "code_snippet": code_snippet,
            "timestamp": timestamp,
        },
    )

    conn.execute(
        "MATCH (sol:Solution {id: $sol_id}), (e:Error {id: $eid}) CREATE (sol)-[:SOLVES]->(e)",
        {"sol_id": solution_id, "eid": error_id},
    )

    return solution_id


def add_concept(
    conn: kuzu.Connection,
    title: str,
    content: str,
    tags: list[str],
    embedding: list[float],
) -> str:
    concept_id = str(uuid.uuid4())
    tags_json = json.dumps(tags)

    conn.execute(
        f"""CREATE (:Concept {{
            id: $id,
            title: $title,
            content: $content,
            tags: $tags,
            embedding: $embedding
        }})""",
        {
            "id": concept_id,
            "title": title,
            "content": content,
            "tags": tags_json,
            "embedding": embedding,
        },
    )

    return concept_id


def link_concept_to_session(conn: kuzu.Connection, concept_id: str, session_id: str) -> dict:
    concept = get_concept_by_id(conn, concept_id)
    session = get_session_by_id(conn, session_id)

    if not concept:
        return {"error": f"Concept {concept_id} not found"}
    if not session:
        return {"error": f"Session {session_id} not found"}

    conn.execute(
        "MATCH (s:Session {id: $sid}), (c:Concept {id: $cid}) MERGE (s)-[:REFERENCES]->(c)",
        {"sid": session_id, "cid": concept_id},
    )

    return {"linked": True}


def get_concept_by_id(conn: kuzu.Connection, concept_id: str) -> Optional[dict]:
    result = conn.execute("MATCH (c:Concept {id: $id}) RETURN c.*", {"id": concept_id})
    rows = _result_to_dicts(result)
    if rows:
        concept = rows[0]
        concept["tags"] = _parse_json_field(concept.get("tags"))
        return concept
    return None


def get_all_concept_embeddings(conn: kuzu.Connection) -> list[dict]:
    result = conn.execute("MATCH (c:Concept) RETURN c.id, c.embedding, c.title, c.content")
    concepts = []
    while result.has_next():
        row = result.get_next()
        concepts.append(
            {
                "id": row[0],
                "embedding": list(row[1]) if row[1] else [],
                "title": row[2],
                "content": row[3],
            }
        )
    return concepts


def get_all_error_embeddings(conn: kuzu.Connection) -> list[dict]:
    result = conn.execute("MATCH (e:Error) RETURN e.id, e.message_embedding, e.message")
    errors = []
    while result.has_next():
        row = result.get_next()
        errors.append(
            {
                "id": row[0],
                "embedding": list(row[1]) if row[1] else [],
                "message": row[2],
            }
        )
    return errors


def get_concepts_by_ids(conn: kuzu.Connection, concept_ids: list[str]) -> list[dict]:
    if not concept_ids:
        return []
    result = conn.execute(
        """UNWIND $concept_ids AS concept_id
           MATCH (c:Concept {id: concept_id})
           RETURN DISTINCT c.*""",
        {"concept_ids": concept_ids},
    )
    concepts = _result_to_dicts(result)
    for c in concepts:
        c["tags"] = _parse_json_field(c.get("tags"))
    return concepts


def get_sessions_referencing_concepts(conn: kuzu.Connection, concept_ids: list[str]) -> list[dict]:
    if not concept_ids:
        return []
    result = conn.execute(
        """UNWIND $concept_ids AS concept_id
           MATCH (s:Session)-[:REFERENCES]->(c:Concept {id: concept_id})
           RETURN DISTINCT s.*""",
        {"concept_ids": concept_ids},
    )
    sessions = _result_to_dicts(result)
    for s in sessions:
        s["files_touched"] = _parse_json_field(s.get("files_touched"))
    return sessions


def get_errors_for_sessions(conn: kuzu.Connection, session_ids: list[str]) -> list[dict]:
    if not session_ids:
        return []
    result = conn.execute(
        """UNWIND $session_ids AS session_id
           MATCH (e:Error)-[:OCCURRED_IN]->(s:Session {id: session_id})
           RETURN DISTINCT e.*""",
        {"session_ids": session_ids},
    )
    return _result_to_dicts(result)


def get_solutions_for_errors(conn: kuzu.Connection, error_ids: list[str]) -> list[dict]:
    if not error_ids:
        return []
    result = conn.execute(
        """UNWIND $error_ids AS error_id
           MATCH (sol:Solution)-[:SOLVES]->(e:Error {id: error_id})
           RETURN DISTINCT sol.*""",
        {"error_ids": error_ids},
    )
    return _result_to_dicts(result)


def get_project_history(conn: kuzu.Connection, project_name: str) -> dict:
    project = get_project_by_name(conn, project_name)
    if not project:
        return {"error": f"Project '{project_name}' not found"}

    project_id = project["id"]

    result = conn.execute(
        "MATCH (s:Session {project_id: $pid}) RETURN s.* ORDER BY s.started_at DESC",
        {"pid": project_id},
    )
    sessions = _result_to_dicts(result)
    for s in sessions:
        s["files_touched"] = _parse_json_field(s.get("files_touched"))

    session_ids = [s["id"] for s in sessions]

    errors = []
    if session_ids:
        result = conn.execute(
            """UNWIND $session_ids AS session_id
               MATCH (e:Error {session_id: session_id})
               RETURN e.* ORDER BY e.timestamp""",
            {"session_ids": session_ids},
        )
        errors = _result_to_dicts(result)

    error_ids = [e["id"] for e in errors]
    solutions = []
    if error_ids:
        result = conn.execute(
            """UNWIND $error_ids AS error_id
               MATCH (sol:Solution {error_id: error_id})
               RETURN sol.* ORDER BY sol.timestamp""",
            {"error_ids": error_ids},
        )
        solutions = _result_to_dicts(result)

    return {
        "project": project,
        "sessions": sessions,
        "errors": errors,
        "solutions": solutions,
    }


def get_recent_sessions(conn: kuzu.Connection, limit: int = 10) -> list[dict]:
    safe_limit = max(1, int(limit))
    result = conn.execute(
        "MATCH (s:Session) RETURN s.* ORDER BY s.started_at DESC LIMIT $limit",
        {"limit": safe_limit},
    )
    sessions = _result_to_dicts(result)
    for s in sessions:
        s["files_touched"] = _parse_json_field(s.get("files_touched"))
    return sessions


def update_concept(
    conn: kuzu.Connection,
    concept_id: str,
    new_content: str,
    new_embedding: list[float],
    new_title: Optional[str] = None,
) -> dict:
    concept = get_concept_by_id(conn, concept_id)
    if not concept:
        return {"error": f"Concept {concept_id} not found"}

    if new_title:
        conn.execute(
            "MATCH (c:Concept {id: $id}) SET c.content = $content, c.embedding = $embedding, c.title = $title",
            {
                "id": concept_id,
                "content": new_content,
                "embedding": new_embedding,
                "title": new_title,
            },
        )
    else:
        conn.execute(
            "MATCH (c:Concept {id: $id}) SET c.content = $content, c.embedding = $embedding",
            {"id": concept_id, "content": new_content, "embedding": new_embedding},
        )

    return {"updated": True}


def delete_concept(conn: kuzu.Connection, concept_id: str) -> dict:
    concept = get_concept_by_id(conn, concept_id)
    if not concept:
        return {"error": f"Concept {concept_id} not found"}

    conn.execute(
        "MATCH (s:Session)-[r:REFERENCES]->(c:Concept {id: $id}) DELETE r",
        {"id": concept_id},
    )
    conn.execute("MATCH (c:Concept {id: $id}) DELETE c", {"id": concept_id})
    return {"deleted": True}


def delete_old_sessions(conn: kuzu.Connection, days_to_keep: int = 30) -> dict:
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()

    result = conn.execute(
        "MATCH (s:Session) WHERE s.started_at < $cutoff RETURN s.id, s.project_id",
        {"cutoff": cutoff_date},
    )
    old_sessions = _result_to_dicts(result)
    session_ids = [s["id"] for s in old_sessions]

    deleted_errors = 0
    deleted_solutions = 0
    deleted_sessions = len(session_ids)

    if not session_ids:
        return {
            "deleted_sessions": 0,
            "deleted_errors": 0,
            "deleted_solutions": 0,
            "concepts_preserved": True,
        }

    error_result = conn.execute(
        """UNWIND $session_ids AS session_id
           MATCH (e:Error {session_id: session_id})
           RETURN e.id""",
        {"session_ids": session_ids},
    )
    error_ids = [row["id"] for row in _result_to_dicts(error_result)]
    deleted_errors = len(error_ids)

    if error_ids:
        solution_count_result = conn.execute(
            """UNWIND $error_ids AS error_id
               MATCH (sol:Solution {error_id: error_id})
               RETURN count(sol)""",
            {"error_ids": error_ids},
        )
        deleted_solutions = (
            solution_count_result.get_next()[0] if solution_count_result.has_next() else 0
        )

        conn.execute(
            """UNWIND $error_ids AS error_id
               MATCH (sol:Solution {error_id: error_id})
               DELETE sol""",
            {"error_ids": error_ids},
        )

        conn.execute(
            """UNWIND $session_ids AS session_id
               MATCH (e:Error {session_id: session_id})
               DETACH DELETE e""",
            {"session_ids": session_ids},
        )

    conn.execute(
        """UNWIND $session_ids AS session_id
           MATCH (s:Session {id: session_id})
           DETACH DELETE s""",
        {"session_ids": session_ids},
    )

    return {
        "deleted_sessions": deleted_sessions,
        "deleted_errors": deleted_errors,
        "deleted_solutions": deleted_solutions,
        "concepts_preserved": True,
    }


def get_session_with_details(conn: kuzu.Connection, session_id: str) -> dict:
    session = get_session_by_id(conn, session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}

    errors = get_errors_for_session(conn, session_id)
    error_ids = [e["id"] for e in errors]
    solutions = get_solutions_for_errors(conn, error_ids) if error_ids else []

    concepts = get_concepts_for_session(conn, session_id)

    return {
        "session": session,
        "errors": errors,
        "solutions": solutions,
        "concepts": concepts,
    }


def get_error_with_solutions(conn: kuzu.Connection, error_id: str) -> dict:
    result = conn.execute("MATCH (e:Error {id: $id}) RETURN e.*", {"id": error_id})
    errors = _result_to_dicts(result)
    if not errors:
        return {"error": f"Error {error_id} not found"}

    error = errors[0]
    solutions = get_solutions_for_errors(conn, [error_id])

    return {
        "error": error,
        "solutions": solutions,
    }


def get_concept_with_sessions(conn: kuzu.Connection, concept_id: str) -> dict:
    concept = get_concept_by_id(conn, concept_id)
    if not concept:
        return {"error": f"Concept {concept_id} not found"}

    result = conn.execute(
        "MATCH (s:Session)-[:REFERENCES]->(c:Concept {id: $cid}) RETURN s.*",
        {"cid": concept_id},
    )
    sessions = _result_to_dicts(result)
    for s in sessions:
        s["files_touched"] = _parse_json_field(s.get("files_touched"))

    return {
        "concept": concept,
        "sessions": sessions,
    }


def get_daily_activity_by_date(conn: kuzu.Connection, date: str, project_id: str) -> Optional[dict]:
    result = conn.execute(
        "MATCH (da:DailyActivity {date: $date, project_id: $project_id}) RETURN da.*",
        {"date": date, "project_id": project_id},
    )
    activities = _result_to_dicts(result)
    if activities:
        activity = activities[0]
        activity["session_ids"] = _parse_json_field(activity.get("session_ids"))
        return activity
    return None


def search_concepts_by_tag(conn: kuzu.Connection, tag: str) -> list[dict]:
    result = conn.execute(
        """MATCH (c:Concept)
           WHERE c.tags CONTAINS $quoted_tag
           RETURN c.*""",
        {"quoted_tag": f'"{tag}"'},
    )
    concepts = _result_to_dicts(result)
    matched = []
    for c in concepts:
        tags = _parse_json_field(c.get("tags"))
        c["tags"] = tags
        if isinstance(tags, list) and tag in tags:
            matched.append(c)
    return matched


def get_project_statistics(conn: kuzu.Connection, project_id: str) -> dict:
    project = get_project_by_id(conn, project_id)
    if not project:
        return {"error": f"Project {project_id} not found"}

    session_result = conn.execute(
        "MATCH (s:Session {project_id: $pid}) RETURN count(s)", {"pid": project_id}
    )
    session_count = session_result.get_next()[0] if session_result.has_next() else 0

    error_result = conn.execute(
        "MATCH (e:Error {project_id: $pid}) RETURN count(e)", {"pid": project_id}
    )
    error_count = error_result.get_next()[0] if error_result.has_next() else 0

    solution_result = conn.execute(
        "MATCH (e:Error {project_id: $pid}) MATCH (sol:Solution)-[:SOLVES]->(e) RETURN count(DISTINCT e)",
        {"pid": project_id},
    )
    resolved_error_count = solution_result.get_next()[0] if solution_result.has_next() else 0

    sessions_with_concepts = conn.execute(
        "MATCH (s:Session {project_id: $pid})-[:REFERENCES]->(c:Concept) RETURN count(DISTINCT c)",
        {"pid": project_id},
    )
    concept_count = sessions_with_concepts.get_next()[0] if sessions_with_concepts.has_next() else 0

    unresolved_result = conn.execute(
        "MATCH (e:Error {project_id: $pid}) WHERE NOT EXISTS { MATCH (sol:Solution)-[:SOLVES]->(e) } RETURN count(e)",
        {"pid": project_id},
    )
    unresolved_count = unresolved_result.get_next()[0] if unresolved_result.has_next() else 0

    resolution_rate = resolved_error_count / error_count if error_count > 0 else 1.0
    avg_errors_per_session = error_count / session_count if session_count > 0 else 0.0

    first_session_result = conn.execute(
        "MATCH (s:Session {project_id: $pid}) RETURN s.started_at ORDER BY s.started_at ASC LIMIT 1",
        {"pid": project_id},
    )
    first_session = first_session_result.get_next()[0] if first_session_result.has_next() else None

    last_session_result = conn.execute(
        "MATCH (s:Session {project_id: $pid}) RETURN s.started_at ORDER BY s.started_at DESC LIMIT 1",
        {"pid": project_id},
    )
    last_session = last_session_result.get_next()[0] if last_session_result.has_next() else None

    file_error_result = conn.execute(
        "MATCH (e:Error {project_id: $pid}) RETURN e.file, count(e) as cnt ORDER BY cnt DESC LIMIT 5",
        {"pid": project_id},
    )
    top_files = []
    while file_error_result.has_next():
        row = file_error_result.get_next()
        top_files.append({"file": row[0], "count": row[1]})

    return {
        "session_count": session_count,
        "error_count": error_count,
        "solution_count": resolved_error_count,
        "concept_count": concept_count,
        "unresolved_count": unresolved_count,
        "resolution_rate": round(resolution_rate, 2),
        "avg_errors_per_session": round(avg_errors_per_session, 2),
        "time_range": {
            "first_session": first_session,
            "last_session": last_session,
        },
        "top_files_with_errors": top_files,
    }


def update_session_summary(conn: kuzu.Connection, session_id: str, summary: str) -> dict:
    session = get_session_by_id(conn, session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}

    conn.execute(
        "MATCH (s:Session {id: $id}) SET s.summary = $summary",
        {"id": session_id, "summary": summary},
    )
    return {"updated": True}


def add_tag_to_concept(conn: kuzu.Connection, concept_id: str, tag: str) -> dict:
    concept = get_concept_by_id(conn, concept_id)
    if not concept:
        return {"error": f"Concept {concept_id} not found"}

    tags = concept.get("tags", [])
    if tag not in tags:
        tags.append(tag)
        conn.execute(
            "MATCH (c:Concept {id: $id}) SET c.tags = $tags",
            {"id": concept_id, "tags": json.dumps(tags)},
        )
    return {"updated": True, "tags": tags}


def remove_tag_from_concept(conn: kuzu.Connection, concept_id: str, tag: str) -> dict:
    concept = get_concept_by_id(conn, concept_id)
    if not concept:
        return {"error": f"Concept {concept_id} not found"}

    tags = concept.get("tags", [])
    if tag in tags:
        tags.remove(tag)
        conn.execute(
            "MATCH (c:Concept {id: $id}) SET c.tags = $tags",
            {"id": concept_id, "tags": json.dumps(tags)},
        )
    return {"updated": True, "tags": tags}


def delete_project_cascade(conn: kuzu.Connection, project_id: str) -> dict:
    project = get_project_by_id(conn, project_id)
    if not project:
        return {"error": f"Project {project_id} not found"}

    session_result = conn.execute(
        "MATCH (s:Session {project_id: $pid}) RETURN s.id", {"pid": project_id}
    )
    session_ids = [row["id"] for row in _result_to_dicts(session_result)]

    deleted_errors = 0
    deleted_solutions = 0

    if session_ids:
        error_result = conn.execute(
            """UNWIND $session_ids AS session_id
               MATCH (e:Error {session_id: session_id})
               RETURN e.id""",
            {"session_ids": session_ids},
        )
        error_ids = [row["id"] for row in _result_to_dicts(error_result)]
        deleted_errors = len(error_ids)

        if error_ids:
            solution_count_result = conn.execute(
                """UNWIND $error_ids AS error_id
                   MATCH (sol:Solution {error_id: error_id})
                   RETURN count(sol)""",
                {"error_ids": error_ids},
            )
            deleted_solutions = (
                solution_count_result.get_next()[0] if solution_count_result.has_next() else 0
            )

            conn.execute(
                """UNWIND $error_ids AS error_id
                   MATCH (sol:Solution {error_id: error_id})
                   DELETE sol""",
                {"error_ids": error_ids},
            )

            conn.execute(
                """UNWIND $session_ids AS session_id
                   MATCH (e:Error {session_id: session_id})
                   DETACH DELETE e""",
                {"session_ids": session_ids},
            )

        conn.execute(
            """UNWIND $session_ids AS session_id
               MATCH (s:Session {id: session_id})
               DETACH DELETE s""",
            {"session_ids": session_ids},
        )

    conn.execute(
        "MATCH (da:DailyActivity {project_id: $pid}) DETACH DELETE da", {"pid": project_id}
    )
    conn.execute("MATCH (p:Project {id: $pid}) DETACH DELETE p", {"pid": project_id})

    return {
        "deleted": True,
        "deleted_sessions": len(session_ids),
        "deleted_errors": deleted_errors,
        "deleted_solutions": deleted_solutions,
    }


def batch_add_concepts(conn: kuzu.Connection, concepts_data: list[dict], embed_func) -> dict:
    if not concepts_data:
        return {"concept_ids": [], "count": 0}

    texts = [f"{cd.get('title', '')}: {cd.get('content', '')}" for cd in concepts_data]
    embeddings_batch = embed_func(texts)
    if not isinstance(embeddings_batch, list):
        raise TypeError("embed_func must return list[list[float]]")
    if len(embeddings_batch) != len(concepts_data):
        raise ValueError("embed_func returned mismatched batch size")
    if embeddings_batch and not isinstance(embeddings_batch[0], list):
        raise TypeError("embed_func must return batched embeddings")

    concept_ids = []
    for cd, embedding in zip(concepts_data, embeddings_batch):
        title = cd.get("title", "")
        content = cd.get("content", "")
        tags = cd.get("tags", [])
        concept_id = add_concept(conn, title, content, tags, embedding)
        concept_ids.append(concept_id)
    return {"concept_ids": concept_ids, "count": len(concept_ids)}


def batch_link_concepts_to_session(
    conn: kuzu.Connection, concept_ids: list[str], session_id: str
) -> dict:
    session = get_session_by_id(conn, session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}

    linked = []
    failed = []
    for cid in concept_ids:
        result = link_concept_to_session(conn, cid, session_id)
        if "error" in result:
            failed.append({"concept_id": cid, "error": result["error"]})
        else:
            linked.append(cid)

    return {"linked": linked, "failed": failed, "count": len(linked)}


def get_unlinked_concepts(conn: kuzu.Connection) -> list[dict]:
    result = conn.execute(
        "MATCH (c:Concept) WHERE NOT EXISTS { MATCH (s:Session)-[:REFERENCES]->(c) } RETURN c.*"
    )
    concepts = _result_to_dicts(result)
    for c in concepts:
        c["tags"] = _parse_json_field(c.get("tags"))
    return concepts


def get_concepts_for_project(conn: kuzu.Connection, project_id: str) -> list[dict]:
    result = conn.execute(
        "MATCH (s:Session {project_id: $pid})-[:REFERENCES]->(c:Concept) RETURN DISTINCT c.*",
        {"pid": project_id},
    )
    concepts = _result_to_dicts(result)
    for c in concepts:
        c["tags"] = _parse_json_field(c.get("tags"))
    return concepts


def cluster_errors_by_similarity(
    conn: kuzu.Connection, project_id: str, similarity_threshold: float = 0.85
) -> dict:
    result = conn.execute(
        """MATCH (e:Error {project_id: $pid})
           RETURN e.id, e.message_embedding, e.message""",
        {"pid": project_id},
    )
    project_errors = []
    while result.has_next():
        row = result.get_next()
        project_errors.append(
            {
                "id": row[0],
                "embedding": list(row[1]) if row[1] else [],
                "message": row[2],
            }
        )
    project_errors = [e for e in project_errors if e.get("embedding")]

    cluster_limit = 300
    cluster_warning = None
    if len(project_errors) > cluster_limit:
        original_size = len(project_errors)
        project_errors = project_errors[:cluster_limit]
        cluster_warning = (
            f"cluster input capped at {cluster_limit} errors from {original_size} candidates"
        )

    clusters = []
    used = set()

    for i, err in enumerate(project_errors):
        if err["id"] in used:
            continue

        cluster_members = [err["id"]]
        cluster_messages = [err["message"]]

        for j, other in enumerate(project_errors):
            if i != j and other["id"] not in used:
                sim = emb.cosine_similarity(err["embedding"], other["embedding"])
                if sim >= similarity_threshold:
                    cluster_members.append(other["id"])
                    cluster_messages.append(other["message"])
                    used.add(other["id"])

        used.add(err["id"])

        if len(cluster_members) > 1:
            clusters.append(
                {
                    "representative": err["message"],
                    "member_count": len(cluster_members),
                    "members": cluster_members,
                    "messages": cluster_messages,
                }
            )

    return {
        "clusters": clusters,
        "total_clustered": sum(c["member_count"] for c in clusters),
        "warning": cluster_warning,
        "input_size": len(project_errors),
    }


def get_concept_growth_over_time(conn: kuzu.Connection, project_id: str) -> dict:
    result = conn.execute(
        """MATCH (s:Session {project_id: $pid})-[:REFERENCES]->(c:Concept)
           WITH c, MIN(s.started_at) as first_seen
           RETURN substring(first_seen, 0, 7) as month, count(c) as count
           ORDER BY month""",
        {"pid": project_id},
    )

    monthly_data = []
    while result.has_next():
        row = result.get_next()
        monthly_data.append({"month": row[0], "concepts_added": row[1]})

    session_result = conn.execute(
        """MATCH (s:Session {project_id: $pid})
           WITH substring(s.started_at, 0, 7) as month, count(s) as sessions
           RETURN month, sessions ORDER BY month""",
        {"pid": project_id},
    )

    session_data = []
    while session_result.has_next():
        row = session_result.get_next()
        session_data.append({"month": row[0], "sessions_completed": row[1]})

    month_map = {}
    for m in monthly_data:
        month_map[m["month"]] = {
            "month": m["month"],
            "concepts_added": m["concepts_added"],
            "sessions_completed": 0,
            "errors_resolved": 0,
        }
    for s in session_data:
        if s["month"] in month_map:
            month_map[s["month"]]["sessions_completed"] = s["sessions_completed"]
        else:
            month_map[s["month"]] = {
                "month": s["month"],
                "concepts_added": 0,
                "sessions_completed": s["sessions_completed"],
                "errors_resolved": 0,
            }

    combined = sorted(month_map.values(), key=lambda x: x["month"])

    total_concepts = sum(m["concepts_added"] for m in combined)
    total_sessions = sum(m["sessions_completed"] for m in combined)

    return {
        "monthly": combined,
        "totals": {
            "total_concepts": total_concepts,
            "total_sessions": total_sessions,
        },
    }


def get_most_referenced_concepts(conn: kuzu.Connection, limit: int = 10) -> list[dict]:
    safe_limit = max(1, int(limit))
    result = conn.execute(
        """MATCH (s:Session)-[:REFERENCES]->(c:Concept)
           RETURN c.id, c.title, count(s) as ref_count
           ORDER BY ref_count DESC
           LIMIT $limit""",
        {"limit": safe_limit},
    )

    concepts = []
    while result.has_next():
        row = result.get_next()
        concepts.append(
            {
                "id": row[0],
                "title": row[1],
                "reference_count": row[2],
            }
        )
    return concepts


def unlink_concept_from_session(conn: kuzu.Connection, concept_id: str, session_id: str) -> dict:
    conn.execute(
        "MATCH (s:Session {id: $sid})-[r:REFERENCES]->(c:Concept {id: $cid}) DELETE r",
        {"sid": session_id, "cid": concept_id},
    )
    return {"unlinked": True}


def get_errors_for_session(conn: kuzu.Connection, session_id: str) -> list[dict]:
    result = conn.execute(
        "MATCH (e:Error {session_id: $sid}) RETURN e.* ORDER BY e.timestamp",
        {"sid": session_id},
    )
    return _result_to_dicts(result)


def get_concepts_for_session(conn: kuzu.Connection, session_id: str) -> list[dict]:
    result = conn.execute(
        "MATCH (s:Session {id: $sid})-[:REFERENCES]->(c:Concept) RETURN c.*",
        {"sid": session_id},
    )
    concepts = _result_to_dicts(result)
    for c in concepts:
        c["tags"] = _parse_json_field(c.get("tags"))
    return concepts


def get_unresolved_errors(conn: kuzu.Connection, project_id: Optional[str] = None) -> list[dict]:
    if project_id:
        result = conn.execute(
            """MATCH (e:Error {project_id: $pid})
               WHERE NOT EXISTS { MATCH (sol:Solution)-[:SOLVES]->(e) }
               RETURN e.* ORDER BY e.timestamp DESC""",
            {"pid": project_id},
        )
    else:
        result = conn.execute(
            """MATCH (e:Error)
               WHERE NOT EXISTS { MATCH (sol:Solution)-[:SOLVES]->(e) }
               RETURN e.* ORDER BY e.timestamp DESC"""
        )
    return _result_to_dicts(result)


def get_recent_errors(conn: kuzu.Connection, limit: int = 10) -> list[dict]:
    safe_limit = max(1, int(limit))
    result = conn.execute(
        "MATCH (e:Error) RETURN e.* ORDER BY e.timestamp DESC LIMIT $limit",
        {"limit": safe_limit},
    )
    return _result_to_dicts(result)


def delete_session_cascade(conn: kuzu.Connection, session_id: str) -> dict:
    session = get_session_by_id(conn, session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}

    error_result = conn.execute(
        "MATCH (e:Error {session_id: $sid}) RETURN e.id", {"sid": session_id}
    )
    error_ids = [row["id"] for row in _result_to_dicts(error_result)]

    deleted_solutions = 0
    if error_ids:
        solution_count_result = conn.execute(
            """UNWIND $error_ids AS error_id
               MATCH (sol:Solution {error_id: error_id})
               RETURN count(sol)""",
            {"error_ids": error_ids},
        )
        deleted_solutions = (
            solution_count_result.get_next()[0] if solution_count_result.has_next() else 0
        )

        conn.execute(
            """UNWIND $error_ids AS error_id
               MATCH (sol:Solution {error_id: error_id})
               DELETE sol""",
            {"error_ids": error_ids},
        )

    conn.execute("MATCH (e:Error {session_id: $sid}) DETACH DELETE e", {"sid": session_id})

    conn.execute("MATCH (s:Session {id: $sid})-[r:REFERENCES]->() DELETE r", {"sid": session_id})
    conn.execute("MATCH (s:Session {id: $sid})-[r:HAS_PROJECT]->() DELETE r", {"sid": session_id})
    conn.execute(
        "MATCH (s:Session {id: $sid})-[r:CONTRIBUTES_TO]->() DELETE r", {"sid": session_id}
    )
    conn.execute("MATCH (s:Session {id: $sid}) DETACH DELETE s", {"sid": session_id})

    return {
        "deleted": True,
        "deleted_errors": len(error_ids),
        "deleted_solutions": deleted_solutions,
    }


def get_daily_activities_for_project(conn: kuzu.Connection, project_id: str) -> list[dict]:
    result = conn.execute(
        "MATCH (da:DailyActivity {project_id: $pid}) RETURN da.* ORDER BY da.date DESC",
        {"pid": project_id},
    )
    activities = _result_to_dicts(result)
    for a in activities:
        a["session_ids"] = _parse_json_field(a.get("session_ids"))
    return activities


def get_daily_summary(conn: kuzu.Connection, date: str) -> dict:
    result = conn.execute(
        "MATCH (da:DailyActivity {date: $date}) RETURN da.*",
        {"date": date},
    )
    activities = _result_to_dicts(result)

    total_sessions = 0
    total_errors = 0
    projects = []

    for a in activities:
        a["session_ids"] = _parse_json_field(a.get("session_ids"))
        total_sessions += len(a.get("session_ids", []))
        total_errors += a.get("errors_count", 0)
        projects.append(
            {
                "project_id": a.get("project_id"),
                "sessions": len(a.get("session_ids", [])),
                "errors": a.get("errors_count", 0),
            }
        )

    return {
        "date": date,
        "total_sessions": total_sessions,
        "total_errors": total_errors,
        "projects": projects,
        "activities": activities,
    }


def update_daily_activity_summary(conn: kuzu.Connection, activity_id: str, summary: str) -> dict:
    conn.execute(
        "MATCH (da:DailyActivity {id: $id}) SET da.summary = $summary",
        {"id": activity_id, "summary": summary},
    )
    return {"updated": True}
