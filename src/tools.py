from fastmcp import FastMCP
from . import db
from . import embeddings
from datetime import datetime, timezone
import math
import os
import re
import numpy as np
from time import perf_counter
from typing import Optional


SEARCH_WEIGHTS = {
    "similarity": 0.55,
    "recency": 0.2,
    "context": 0.15,
    "keyword": 0.1,
}

SEARCH_EMBEDDING_SCAN_LIMIT = 5000


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


MAX_ARTIFACT_CONTENT_BYTES = _env_int("MAHORAGA_MAX_ARTIFACT_CONTENT_BYTES", 1000000)

STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "what",
    "when",
    "where",
    "how",
    "why",
    "use",
    "using",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "does",
    "did",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
    "can",
    "could",
    "not",
    "but",
    "its",
    "also",
    "about",
    "than",
    "then",
    "just",
    "more",
    "some",
    "other",
    "all",
    "any",
    "each",
    "every",
    "such",
    "very",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _tokenize(value: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+", value.lower())
    return {t for t in tokens if len(t) >= 3 and t not in STOP_WORDS}


def _is_blank(value: Optional[str]) -> bool:
    return value is None or not value.strip()


def _validate_date(date: str) -> Optional[str]:
    """Return an error message if date is not YYYY-MM-DD, else None."""
    if not _DATE_RE.match(date):
        return f"Invalid date format '{date}'. Expected YYYY-MM-DD."
    return None


def _clamp_limit(value: int, default: int = 10, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(1, min(parsed, maximum))


def _empty_search_response(error: Optional[str] = None, metrics: Optional[dict] = None) -> dict:
    response = {
        "concepts": [],
        "sessions": [],
        "errors": [],
        "solutions": [],
        "artifacts": [],
        "metrics": metrics or {},
    }
    if error:
        response["error"] = error
    return response


def _validate_artifact_content_size(content: str) -> Optional[str]:
    content_size = len(content.encode("utf-8"))
    if content_size > MAX_ARTIFACT_CONTENT_BYTES:
        return (
            f"content exceeds maximum size of {MAX_ARTIFACT_CONTENT_BYTES} bytes "
            f"(got {content_size} bytes)"
        )
    return None


def _ensure_actor_context(actor_context: Optional[dict]) -> Optional[str]:
    return db.validate_provenance_context(actor_context)


def _safe_log_action_event(
    conn,
    actor_context: Optional[dict],
    operation: str,
    target_type: str,
    target_id: str,
    project_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[str]:
    try:
        if actor_context is None:
            return None
        return db.log_action_event(
            conn,
            actor_context=actor_context,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            metadata=metadata,
        )
    except Exception:
        return None


def _vectorized_cosine_scores(
    query_embedding: list[float], items: list[dict], embedding_key: str = "embedding"
) -> list[float]:
    """Compute cosine similarity between query and all item embeddings using vectorized NumPy.
    Returns a list of scores (0.0 for items with empty embeddings)."""
    if not items:
        return []
    query_vec = np.array(query_embedding, dtype=np.float32)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return [0.0] * len(items)
    query_vec = query_vec / query_norm

    scores = []
    # Collect items that have embeddings for batch processing
    valid_indices = []
    valid_embeddings = []
    for i, item in enumerate(items):
        emb = item.get(embedding_key)
        if emb:
            valid_indices.append(i)
            valid_embeddings.append(emb)

    if valid_embeddings:
        emb_matrix = np.array(valid_embeddings, dtype=np.float32)
        norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        emb_matrix = emb_matrix / norms
        sims = emb_matrix @ query_vec  # vectorized dot product

        score_map = {idx: float(sims[j]) for j, idx in enumerate(valid_indices)}
    else:
        score_map = {}

    return [score_map.get(i, 0.0) for i in range(len(items))]


def register_tools(mcp: FastMCP) -> None:

    def _validated_ctx(actor_context: Optional[dict]) -> tuple[dict, Optional[dict]]:
        ctx_err = _ensure_actor_context(actor_context)
        if ctx_err:
            return {}, {"error": ctx_err}
        return actor_context or {}, None

    def _log_event(
        conn,
        actor_context: Optional[dict],
        operation: str,
        target_type: str,
        target_id: str,
        project_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        if actor_context is None:
            raise ValueError("actor_context is required")
        db.log_action_event(
            conn,
            actor_context=actor_context,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            metadata=metadata,
        )

    @mcp.tool
    def add_project(
        name: str,
        path: str,
        description: str = "",
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Create a new project node in the knowledge graph.

        Args:
            name: Unique name for the project
            path: File system path to the project directory
            description: Optional description of the project

        Returns:
            dict with project_id on success, or error dict on failure
        """
        try:
            ctx_err = _ensure_actor_context(actor_context)
            if ctx_err:
                return {"error": ctx_err}
            if _is_blank(name):
                return {"error": "Project name cannot be empty"}
            if _is_blank(path):
                return {"error": "Project path cannot be empty"}

            conn = db.get_connection()
            existing = db.get_project_by_name(conn, name)
            if existing:
                return {
                    "error": f"Project '{name}' already exists",
                    "project_id": existing["id"],
                }
            project_id = db.add_project(conn, name, path, description)
            db.log_action_event(
                conn,
                actor_context=actor_context or {},
                operation="add_project",
                target_type="Project",
                target_id=project_id,
                project_id=project_id,
                metadata={"name": name, "path": path},
            )
            return {"project_id": project_id, "name": name, "path": path}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def add_session(
        project_name: str,
        summary: str,
        files_touched: list[str],
        project_path: Optional[str] = None,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Create a new session linked to a project.

        If the project doesn't exist, it will be auto-created.
        For new projects, project_path is required.

        Args:
            project_name: Name of the project (will be created if doesn't exist)
            summary: Brief summary of what happened in the session
            files_touched: List of file paths that were modified or accessed
            project_path: Required if project doesn't exist - path to project directory

        Returns:
            dict with session_id on success, or error dict on failure
        """
        try:
            ctx_err = _ensure_actor_context(actor_context)
            if ctx_err:
                return {"error": ctx_err}
            if _is_blank(project_name):
                return {"error": "project_name cannot be empty"}
            if _is_blank(summary):
                return {"error": "summary cannot be empty"}
            if not files_touched:
                return {"error": "files_touched cannot be empty"}

            conn = db.get_connection()
            project = db.get_project_by_name(conn, project_name)

            if not project:
                if not project_path:
                    return {
                        "error": f"Project '{project_name}' doesn't exist. Provide project_path to auto-create it."
                    }
                project_id = db.add_project(conn, project_name, project_path)
            else:
                project_id = project["id"]

            session_id = db.add_session(conn, project_id, summary, files_touched)
            db.log_action_event(
                conn,
                actor_context=actor_context or {},
                operation="add_session",
                target_type="Session",
                target_id=session_id,
                project_id=project_id,
                metadata={"project_name": project_name},
            )
            return {"session_id": session_id, "project_id": project_id}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def close_session(
        session_id: str,
        ended_at: Optional[str] = None,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Close a session and update its end timestamp.

        Also creates or updates the DailyActivity node for the session's date.

        Args:
            session_id: ID of the session to close
            ended_at: Optional ISO 8601 timestamp. If not provided, uses current time.

        Returns:
            dict with success status or error dict on failure
        """
        try:
            ctx_err = _ensure_actor_context(actor_context)
            if ctx_err:
                return {"error": ctx_err}
            conn = db.get_connection()
            session = db.get_session_by_id(conn, session_id)
            if not session:
                return {"error": f"Session '{session_id}' not found"}

            result = db.close_session(conn, session_id, ended_at)
            db.link_session_to_daily_activity(conn, session_id)
            db.log_action_event(
                conn,
                actor_context=actor_context or {},
                operation="close_session",
                target_type="Session",
                target_id=session_id,
                project_id=session.get("project_id"),
                metadata={"ended_at": result.get("ended_at")},
            )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def log_error(
        session_id: str,
        message: str,
        context: str,
        file: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Log an error that occurred during a session.

        Creates an Error node with embedded message for semantic search.

        Args:
            session_id: ID of the session where the error occurred
            message: The error message
            context: Additional context about what was happening
            file: The file where the error occurred

        Returns:
            dict with error_id on success, or error dict on failure
        """
        try:
            ctx_err = _ensure_actor_context(actor_context)
            if ctx_err:
                return {"error": ctx_err}
            if _is_blank(message):
                return {"error": "message cannot be empty"}
            if _is_blank(file):
                return {"error": "file cannot be empty"}

            conn = db.get_connection()
            session = db.get_session_by_id(conn, session_id)
            if not session:
                return {"error": f"Session '{session_id}' not found"}

            message_embedding = embeddings.embed(message)
            error_id = db.add_error(
                conn,
                session["project_id"],
                session_id,
                message,
                context,
                file,
                message_embedding,
            )
            db.log_action_event(
                conn,
                actor_context=actor_context or {},
                operation="log_error",
                target_type="Error",
                target_id=error_id,
                project_id=session.get("project_id"),
                metadata={"session_id": session_id, "file": file},
            )
            return {"error_id": error_id}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def log_solution(
        error_id: str,
        description: str,
        code_snippet: str = "",
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Log a solution for a previously logged error.

        Args:
            error_id: ID of the error this solution addresses
            description: Description of how the error was solved
            code_snippet: Optional code that was used to fix the issue

        Returns:
            dict with solution_id on success, or error dict on failure
        """
        try:
            ctx_err = _ensure_actor_context(actor_context)
            if ctx_err:
                return {"error": ctx_err}
            if _is_blank(description):
                return {"error": "description cannot be empty"}

            conn = db.get_connection()
            solution_id = db.add_solution(conn, error_id, description, code_snippet)
            error_rows = db._result_to_dicts(
                conn.execute("MATCH (e:Error {id: $id}) RETURN e.project_id", {"id": error_id})
            )
            project_id = error_rows[0].get("project_id") if error_rows else None
            db.log_action_event(
                conn,
                actor_context=actor_context or {},
                operation="log_solution",
                target_type="Solution",
                target_id=solution_id,
                project_id=project_id,
                metadata={"error_id": error_id},
            )
            return {"solution_id": solution_id}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def add_concept(
        title: str,
        content: str,
        tags: Optional[list[str]] = None,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Add a new concept to the knowledge graph.

        Concepts are semantic knowledge entries that can be linked to sessions.

        Args:
            title: Short title for the concept
            content: Detailed explanation of the concept
            tags: List of tags for categorization

        Returns:
            dict with concept_id on success, or error dict on failure
        """
        try:
            ctx_err = _ensure_actor_context(actor_context)
            if ctx_err:
                return {"error": ctx_err}
            if _is_blank(title):
                return {"error": "title cannot be empty"}
            if _is_blank(content):
                return {"error": "content cannot be empty"}

            conn = db.get_connection()
            concept_tags = tags or []
            embedding = embeddings.embed(f"{title}: {content}")
            concept_id = db.add_concept(conn, title, content, concept_tags, embedding)
            db.log_action_event(
                conn,
                actor_context=actor_context or {},
                operation="add_concept",
                target_type="Concept",
                target_id=concept_id,
                metadata={"title": title, "tags": concept_tags},
            )
            return {"concept_id": concept_id}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def link_concept_to_session(
        concept_id: str,
        session_id: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Link a concept to a session.

        Creates a REFERENCES relationship from session to concept.

        Args:
            concept_id: ID of the concept to link
            session_id: ID of the session to link

        Returns:
            dict with success status or error dict on failure
        """
        try:
            ctx_err = _ensure_actor_context(actor_context)
            if ctx_err:
                return {"error": ctx_err}
            conn = db.get_connection()
            result = db.link_concept_to_session(conn, concept_id, session_id)
            if "error" not in result:
                session = db.get_session_by_id(conn, session_id)
                db.log_action_event(
                    conn,
                    actor_context=actor_context or {},
                    operation="link_concept_to_session",
                    target_type="Concept",
                    target_id=concept_id,
                    project_id=session.get("project_id") if session else None,
                    metadata={"session_id": session_id},
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def search(query: str, top_k: int = 5) -> dict:
        """Search the knowledge graph for relevant information.

        Performs semantic search over concepts, then traverses the graph
        to find related sessions, errors, and solutions.

        Results are ranked by: 55% similarity, 20% recency,
        15% context richness, 10% keyword overlap.

        Args:
            query: Natural language search query
            top_k: Number of top results to return (default 5)

        Returns:
            dict with concepts, sessions, errors, and solutions
        """
        try:
            if _is_blank(query):
                return _empty_search_response(error="query cannot be empty")
            top_k = _clamp_limit(top_k, default=5, maximum=50)

            overall_start = perf_counter()
            conn = db.get_connection()
            query_embedding = embeddings.embed(query)
            query_words = _tokenize(query)

            all_concepts = db.get_all_concept_embeddings(conn, limit=SEARCH_EMBEDDING_SCAN_LIMIT)
            all_artifacts = db.get_all_artifact_embeddings(conn, limit=SEARCH_EMBEDDING_SCAN_LIMIT)
            if not all_concepts and not all_artifacts:
                return _empty_search_response(
                    metrics={
                        "query_ms": round((perf_counter() - overall_start) * 1000, 2),
                        "concept_candidates": 0,
                        "concept_results": 0,
                        "session_results": 0,
                        "error_results": 0,
                        "solution_results": 0,
                        "artifact_results": 0,
                    }
                )

            scored_concepts = []
            concept_scores = _vectorized_cosine_scores(query_embedding, all_concepts)
            for concept, sim in zip(all_concepts, concept_scores):
                if sim > 0:
                    scored_concepts.append(
                        {
                            "id": concept["id"],
                            "title": concept["title"],
                            "content": concept["content"],
                            "similarity": sim,
                        }
                    )

            scored_concepts.sort(key=lambda x: x["similarity"], reverse=True)
            candidate_k = min(max(top_k * 5, top_k), len(scored_concepts))
            top_concept_ids = [c["id"] for c in scored_concepts[:candidate_k]]

            concepts = db.get_concepts_by_ids(conn, top_concept_ids)
            sessions = db.get_sessions_referencing_concepts(conn, top_concept_ids)
            session_ids = [s["id"] for s in sessions]
            errors = db.get_errors_for_sessions(conn, session_ids)
            error_ids = [e["id"] for e in errors]
            solutions = db.get_solutions_for_errors(conn, error_ids)

            errors_by_session: dict[str, list[dict]] = {}
            for err in errors:
                errors_by_session.setdefault(err.get("session_id", ""), []).append(err)

            solutions_by_error: dict[str, list[dict]] = {}
            for sol in solutions:
                solutions_by_error.setdefault(sol.get("error_id", ""), []).append(sol)

            now = datetime.now(timezone.utc)
            session_recency: dict[str, float] = {}
            for session in sessions:
                if session.get("started_at"):
                    started = db._parse_iso_datetime(session["started_at"])
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    days_old = (now - started).days
                    score = math.exp(-max(0, days_old) / 365)
                    session["recency_score"] = score
                    session_recency[session["id"]] = score

            concept_session_map: dict[str, list[str]] = {}
            concept_session_result = conn.execute(
                """UNWIND $concept_ids AS concept_id
                   MATCH (s:Session)-[:REFERENCES]->(c:Concept {id: concept_id})
                   RETURN concept_id, s.id""",
                {"concept_ids": top_concept_ids},
            )
            while concept_session_result.has_next():
                row = concept_session_result.get_next()
                concept_id = row[0]
                session_id = row[1]
                concept_session_map.setdefault(concept_id, []).append(session_id)

            for concept in concepts:
                concept_obj = next((c for c in scored_concepts if c["id"] == concept["id"]), None)
                if concept_obj:
                    concept["similarity"] = concept_obj["similarity"]
                    session_match_ids = concept_session_map.get(concept["id"], [])
                    errors_for_concept = [
                        err for sid in session_match_ids for err in errors_by_session.get(sid, [])
                    ]
                    solutions_for_errors = [
                        sol
                        for err in errors_for_concept
                        for sol in solutions_by_error.get(err.get("id", ""), [])
                    ]

                    concept_recency = 0.0
                    if session_match_ids:
                        concept_recency = sum(
                            session_recency.get(sid, 0.0) for sid in session_match_ids
                        ) / len(session_match_ids)
                    concept["recency_score"] = concept_recency

                    keyword_score = 0.0
                    title_score = 0.0
                    if query_words:
                        title_tokens = _tokenize(concept.get("title", ""))
                        content_tokens = _tokenize(concept.get("content", ""))

                        if title_tokens:
                            title_overlap = len(query_words.intersection(title_tokens))
                            # Use min() so partial exact matches against long queries aren't penalized
                            title_score = min(
                                1.0,
                                title_overlap / max(1, min(len(query_words), len(title_tokens))),
                            )

                        content_overlap = len(query_words.intersection(content_tokens))
                        content_score = min(
                            1.0,
                            content_overlap / max(1, min(len(query_words), len(content_tokens))),
                        )
                        keyword_score = min(1.0, 0.7 * title_score + 0.3 * content_score)

                    concept["context_score"] = min(
                        1.0,
                        len(errors_for_concept) * 0.1 + len(solutions_for_errors) * 0.15,
                    )
                    concept["keyword_score"] = keyword_score
                    concept["title_score"] = title_score

            for concept in concepts:
                similarity = concept.get("similarity", 0.5)
                recency = concept.get("recency_score", 0.5)
                context = concept.get("context_score", 0)
                keyword = concept.get("keyword_score", 0)
                concept["rank_score"] = (
                    SEARCH_WEIGHTS["similarity"] * similarity
                    + SEARCH_WEIGHTS["recency"] * recency
                    + SEARCH_WEIGHTS["context"] * context
                    + SEARCH_WEIGHTS["keyword"] * keyword
                )

            concepts.sort(key=lambda x: x.get("rank_score", 0), reverse=True)
            concepts = concepts[:top_k]
            for concept in concepts:
                concept.pop("embedding", None)

            final_concept_ids = {c["id"] for c in concepts}
            final_session_ids_from_concepts = {
                sid
                for cid, sid_list in concept_session_map.items()
                if cid in final_concept_ids
                for sid in sid_list
            }
            sessions = [s for s in sessions if s["id"] in final_session_ids_from_concepts]
            final_session_ids = {s["id"] for s in sessions}
            errors = [e for e in errors if e.get("session_id") in final_session_ids]
            final_error_ids = {e["id"] for e in errors}
            solutions = [sol for sol in solutions if sol.get("error_id") in final_error_ids]

            scored_artifacts = []
            artifact_scores = _vectorized_cosine_scores(query_embedding, all_artifacts)
            for artifact, sim in zip(all_artifacts, artifact_scores):
                if sim > 0:
                    scored_artifacts.append(
                        {
                            "id": artifact["id"],
                            "title": artifact["title"],
                            "description": artifact["description"],
                            "type": artifact["type"],
                            "similarity": sim,
                        }
                    )
            scored_artifacts.sort(key=lambda x: x["similarity"], reverse=True)
            top_artifacts = scored_artifacts[:top_k]

            artifact_ids = [a["id"] for a in top_artifacts]
            artifact_details = []
            if artifact_ids:
                score_by_id = {a["id"]: a["similarity"] for a in top_artifacts}
                artifacts_by_id = {a["id"]: a for a in db.get_artifacts_by_ids(conn, artifact_ids)}
                for aid in artifact_ids:
                    a = artifacts_by_id.get(aid)
                    if not a:
                        continue
                    a["similarity"] = score_by_id.get(aid, 0)
                    a.pop("embedding", None)
                    artifact_details.append(a)

            metrics = {
                "query_ms": round((perf_counter() - overall_start) * 1000, 2),
                "concept_candidates": len(all_concepts),
                "concept_results": len(concepts),
                "session_results": len(sessions),
                "error_results": len(errors),
                "solution_results": len(solutions),
                "artifact_results": len(artifact_details),
            }

            return {
                "concepts": concepts,
                "sessions": sessions,
                "errors": errors,
                "solutions": solutions,
                "artifacts": artifact_details,
                "metrics": metrics,
            }
        except Exception as e:
            return _empty_search_response(error=str(e))

    @mcp.tool
    def get_project_history(project_name: str, limit: int = 50, offset: int = 0) -> dict:
        """Get all sessions, errors, and solutions for a project.

        Args:
            project_name: Name of the project to query
            limit: Maximum sessions to return (default 50)
            offset: Pagination offset

        Returns:
            dict with project info, sessions, errors, and solutions
        """
        try:
            conn = db.get_connection()
            return db.get_project_history(
                conn, project_name, _clamp_limit(limit, default=50, maximum=200), offset
            )
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_error_solutions(error_message: str, top_k: int = 5) -> dict:
        """Find similar errors and their solutions using semantic search.

        Args:
            error_message: Error message to search for
            top_k: Number of similar errors to return (default 5)

        Returns:
            dict with matching errors and their solutions
        """
        try:
            top_k = _clamp_limit(top_k, default=5, maximum=50)
            conn = db.get_connection()
            query_embedding = embeddings.embed(error_message)

            all_errors = db.get_all_error_embeddings(conn, limit=SEARCH_EMBEDDING_SCAN_LIMIT)
            if not all_errors:
                return {"errors": [], "solutions": []}

            scored_errors = []
            error_scores = _vectorized_cosine_scores(query_embedding, all_errors)
            for error, sim in zip(all_errors, error_scores):
                if sim > 0:
                    scored_errors.append(
                        {
                            "id": error["id"],
                            "message": error["message"],
                            "similarity": sim,
                        }
                    )

            scored_errors.sort(key=lambda x: x["similarity"], reverse=True)
            top_error_ids = [e["id"] for e in scored_errors[:top_k]]

            errors = db.get_errors_by_ids(conn, top_error_ids)

            solutions = db.get_solutions_for_errors(conn, top_error_ids)

            for error in errors:
                error_obj = next((e for e in scored_errors if e["id"] == error["id"]), None)
                if error_obj:
                    error["similarity"] = error_obj["similarity"]

            return {"errors": errors, "solutions": solutions}
        except Exception as e:
            return {"error": str(e), "errors": [], "solutions": []}

    @mcp.tool
    def update_concept(
        concept_id: str,
        new_content: str,
        new_title: Optional[str] = None,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Update a concept's content (re-embeds automatically).

        Args:
            concept_id: ID of the concept to update
            new_content: New content for the concept
            new_title: Optional new title for the concept

        Returns:
            dict with success status or error dict on failure
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            if _is_blank(new_content):
                return {"error": "new_content cannot be empty"}
            if new_title is not None and _is_blank(new_title):
                return {"error": "new_title cannot be empty"}

            conn = db.get_connection()
            concept = db.get_concept_by_id(conn, concept_id)
            if not concept:
                return {"error": f"Concept {concept_id} not found"}

            title = new_title or concept.get("title", "")
            new_embedding = embeddings.embed(f"{title}: {new_content}")
            result = db.update_concept(conn, concept_id, new_content, new_embedding, new_title)
            if "error" not in result:
                _log_event(
                    conn,
                    actor_context,
                    "update_concept",
                    "Concept",
                    concept_id,
                    metadata={"new_title": new_title},
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def delete_concept(concept_id: str, actor_context: Optional[dict] = None) -> dict:
        """Delete a concept from the knowledge graph.

        Also removes any REFERENCES relationships to sessions.

        Args:
            concept_id: ID of the concept to delete

        Returns:
            dict with success status
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            result = db.delete_concept(conn, concept_id)
            if "error" not in result:
                _log_event(conn, actor_context, "delete_concept", "Concept", concept_id)
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def list_projects(limit: int = 100, offset: int = 0) -> dict:
        """List all projects in the knowledge graph.

        Returns:
            dict with list of projects sorted by creation date
        """
        try:
            conn = db.get_connection()
            projects = db.list_projects(conn, _clamp_limit(limit, default=100, maximum=500), offset)
            return {"projects": projects}
        except Exception as e:
            return {"error": str(e), "projects": []}

    @mcp.tool
    def get_recent_sessions(limit: int = 10) -> dict:
        """Get the most recent sessions across all projects.

        Args:
            limit: Maximum number of sessions to return (default 10)

        Returns:
            dict with list of recent sessions
        """
        try:
            conn = db.get_connection()
            sessions = db.get_recent_sessions(conn, limit)
            return {"sessions": sessions}
        except Exception as e:
            return {"error": str(e), "sessions": []}

    @mcp.tool
    def update_project(
        project_id: str,
        name: Optional[str] = None,
        path: Optional[str] = None,
        description: Optional[str] = None,
        merge_project_id: Optional[str] = None,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Update a project's metadata or merge with another project.

        Args:
            project_id: ID of the project to update
            name: New name for the project
            path: New path for the project
            description: New description for the project
            merge_project_id: If provided, merge this project into another project

        Returns:
            dict with success status or error dict on failure
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            if merge_project_id and project_id == merge_project_id:
                return {"error": "Cannot merge a project into itself"}
            if name is not None and _is_blank(name):
                return {"error": "name cannot be empty"}
            if path is not None and _is_blank(path):
                return {"error": "path cannot be empty"}

            conn = db.get_connection()
            result = db.update_project(conn, project_id, name, path, description, merge_project_id)
            if "error" not in result:
                _log_event(
                    conn,
                    actor_context,
                    "update_project",
                    "Project",
                    project_id,
                    project_id=project_id,
                    metadata={"merge_project_id": merge_project_id},
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def delete_old_sessions(days_to_keep: int = 30, actor_context: Optional[dict] = None) -> dict:
        """Delete old sessions and their errors/solutions (keeps concepts).

        Smart cleanup that preserves learned concepts while removing old session data.

        Args:
            days_to_keep: Number of days of sessions to keep (default 30)

        Returns:
            dict with deletion statistics
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            if isinstance(days_to_keep, bool):
                return {"error": "days_to_keep must be an integer"}
            try:
                parsed_days = int(days_to_keep)
            except Exception:
                return {"error": "days_to_keep must be an integer"}
            days_to_keep = max(1, min(parsed_days, 3650))
            conn = db.get_connection()
            result = db.delete_old_sessions(conn, days_to_keep)
            if "error" not in result:
                _log_event(
                    conn,
                    actor_context,
                    "delete_old_sessions",
                    "Session",
                    "bulk",
                    metadata={"days_to_keep": days_to_keep},
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_session_details(session_id: str) -> dict:
        """Get full session info including errors, solutions, and linked concepts.

        Args:
            session_id: ID of the session to retrieve

        Returns:
            dict with session, errors, solutions, and concepts
        """
        try:
            conn = db.get_connection()
            return db.get_session_with_details(conn, session_id)
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_error_details(error_id: str) -> dict:
        """Get error with all its solutions.

        Args:
            error_id: ID of the error to retrieve

        Returns:
            dict with error and solutions
        """
        try:
            conn = db.get_connection()
            return db.get_error_with_solutions(conn, error_id)
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_concept_details(concept_id: str) -> dict:
        """Get concept with all sessions that reference it.

        Args:
            concept_id: ID of the concept to retrieve

        Returns:
            dict with concept and linked sessions
        """
        try:
            conn = db.get_connection()
            result = db.get_concept_with_sessions(conn, concept_id)
            if result.get("concept"):
                result["concept"].pop("embedding", None)
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_daily_activity(date: str, project_id: str) -> dict:
        """Get daily activity for a specific date and project.

        Args:
            date: Date in YYYY-MM-DD format
            project_id: ID of the project

        Returns:
            dict with daily activity or error if not found
        """
        try:
            date_err = _validate_date(date)
            if date_err:
                return {"error": date_err}
            conn = db.get_connection()
            activity = db.get_daily_activity_by_date(conn, date, project_id)
            if activity:
                return {"activity": activity}
            return {"error": f"No activity found for {date} in project {project_id}"}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def search_by_tag(tag: str) -> dict:
        """Find concepts by tag (non-semantic search).

        Args:
            tag: Tag to search for

        Returns:
            dict with list of matching concepts
        """
        try:
            conn = db.get_connection()
            concepts = db.search_concepts_by_tag(conn, tag)
            return {"concepts": concepts, "count": len(concepts)}
        except Exception as e:
            return {"error": str(e), "concepts": []}

    @mcp.tool
    def get_project_stats(project_id: str) -> dict:
        """Get comprehensive statistics for a project.

        Returns session count, error count, resolution rate, top files with errors, etc.

        Args:
            project_id: ID of the project

        Returns:
            dict with full project statistics
        """
        try:
            conn = db.get_connection()
            return db.get_project_statistics(conn, project_id)
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def update_session_summary(
        session_id: str,
        summary: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Update a session's summary.

        Args:
            session_id: ID of the session to update
            summary: New summary text

        Returns:
            dict with success status
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            if _is_blank(summary):
                return {"error": "summary cannot be empty"}
            conn = db.get_connection()
            result = db.update_session_summary(conn, session_id, summary)
            if "error" not in result:
                session = db.get_session_by_id(conn, session_id)
                _log_event(
                    conn,
                    actor_context,
                    "update_session_summary",
                    "Session",
                    session_id,
                    project_id=session.get("project_id") if session else None,
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def add_tag_to_concept(
        concept_id: str,
        tag: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Add a tag to a concept without re-embedding.

        Args:
            concept_id: ID of the concept
            tag: Tag to add

        Returns:
            dict with updated tags
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            result = db.add_tag_to_concept(conn, concept_id, tag)
            if "error" not in result:
                _log_event(conn, actor_context, "add_tag_to_concept", "Concept", concept_id)
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def remove_tag_from_concept(
        concept_id: str,
        tag: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Remove a tag from a concept without re-embedding.

        Args:
            concept_id: ID of the concept
            tag: Tag to remove

        Returns:
            dict with updated tags
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            result = db.remove_tag_from_concept(conn, concept_id, tag)
            if "error" not in result:
                _log_event(conn, actor_context, "remove_tag_from_concept", "Concept", concept_id)
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def delete_project(project_id: str, actor_context: Optional[dict] = None) -> dict:
        """Delete a project and all its sessions, errors, and solutions.

        Warning: This is a cascade delete and cannot be undone.

        Args:
            project_id: ID of the project to delete

        Returns:
            dict with deletion statistics
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            result = db.delete_project_cascade(conn, project_id)
            if "error" not in result:
                _log_event(
                    conn,
                    actor_context,
                    "delete_project",
                    "Project",
                    project_id,
                    project_id=project_id,
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def batch_add_concepts(concepts: list[dict], actor_context: Optional[dict] = None) -> dict:
        """Add multiple concepts at once.

        Each concept dict should have: title, content, and optionally tags.

        Args:
            concepts: List of concept dicts with title, content, tags

        Returns:
            dict with list of created concept IDs
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            if not concepts:
                return {"error": "concepts list cannot be empty"}
            for i, c in enumerate(concepts):
                if _is_blank(c.get("title")):
                    return {"error": f"Concept at index {i} has empty title"}
                if _is_blank(c.get("content")):
                    return {"error": f"Concept at index {i} has empty content"}

            conn = db.get_connection()
            result = db.batch_add_concepts(conn, concepts, embeddings.embed_batch)
            if "error" not in result:
                for concept_id in result.get("concept_ids", []):
                    _safe_log_action_event(
                        conn,
                        actor_context,
                        "batch_add_concept",
                        "Concept",
                        concept_id,
                    )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def batch_link_concepts(
        concept_ids: list[str],
        session_id: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Link multiple concepts to a session at once.

        Args:
            concept_ids: List of concept IDs to link
            session_id: ID of the session to link to

        Returns:
            dict with linked and failed lists
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            result = db.batch_link_concepts_to_session(conn, concept_ids, session_id)
            if "error" not in result:
                session = db.get_session_by_id(conn, session_id)
                for cid in result.get("linked", []):
                    _safe_log_action_event(
                        conn,
                        actor_context,
                        "batch_link_concept",
                        "Concept",
                        cid,
                        project_id=session.get("project_id") if session else None,
                        metadata={"session_id": session_id},
                    )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_unlinked_concepts(limit: int = 100, offset: int = 0) -> dict:
        """Find concepts that are not linked to any session.

        Returns:
            dict with list of unlinked concepts
        """
        try:
            conn = db.get_connection()
            concepts = db.get_unlinked_concepts(
                conn, _clamp_limit(limit, default=100, maximum=500), offset
            )
            return {"concepts": concepts, "count": len(concepts)}
        except Exception as e:
            return {"error": str(e), "concepts": []}

    @mcp.tool
    def get_concepts_by_project(project_id: str) -> dict:
        """Get all concepts linked to a project's sessions.

        Args:
            project_id: ID of the project

        Returns:
            dict with list of concepts
        """
        try:
            conn = db.get_connection()
            concepts = db.get_concepts_for_project(conn, project_id)
            return {"concepts": concepts, "count": len(concepts)}
        except Exception as e:
            return {"error": str(e), "concepts": []}

    @mcp.tool
    def get_project_errors_by_type(project_id: str, similarity_threshold: float = 0.85) -> dict:
        """Cluster project errors by similarity to find common error patterns.

        Args:
            project_id: ID of the project
            similarity_threshold: Minimum similarity to group errors (default 0.85)

        Returns:
            dict with error clusters
        """
        try:
            conn = db.get_connection()
            return db.cluster_errors_by_similarity(conn, project_id, similarity_threshold)
        except Exception as e:
            return {"error": str(e), "clusters": []}

    @mcp.tool
    def get_learning_progress(project_id: str) -> dict:
        """Track concept growth and activity over time for a project.

        Args:
            project_id: ID of the project

        Returns:
            dict with monthly data and totals
        """
        try:
            conn = db.get_connection()
            return db.get_concept_growth_over_time(conn, project_id)
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_most_referenced_concepts(limit: int = 10) -> dict:
        """Get the most referenced concepts across all sessions.

        Args:
            limit: Maximum number of concepts to return (default 10)

        Returns:
            dict with list of concepts and their reference counts
        """
        try:
            conn = db.get_connection()
            concepts = db.get_most_referenced_concepts(conn, limit)
            return {"concepts": concepts}
        except Exception as e:
            return {"error": str(e), "concepts": []}

    @mcp.tool
    def unlink_concept_from_session(
        concept_id: str,
        session_id: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Remove a concept reference from a session.

        Args:
            concept_id: ID of the concept
            session_id: ID of the session

        Returns:
            dict with success status
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            result = db.unlink_concept_from_session(conn, concept_id, session_id)
            if "error" not in result:
                session = db.get_session_by_id(conn, session_id)
                _log_event(
                    conn,
                    actor_context,
                    "unlink_concept_from_session",
                    "Concept",
                    concept_id,
                    project_id=session.get("project_id") if session else None,
                    metadata={"session_id": session_id},
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_session_errors(session_id: str) -> dict:
        """Get all errors for a specific session.

        Args:
            session_id: ID of the session

        Returns:
            dict with list of errors
        """
        try:
            conn = db.get_connection()
            errors = db.get_errors_for_session(conn, session_id)
            return {"errors": errors, "count": len(errors)}
        except Exception as e:
            return {"error": str(e), "errors": []}

    @mcp.tool
    def get_session_concepts(session_id: str) -> dict:
        """Get all concepts linked to a specific session.

        Args:
            session_id: ID of the session

        Returns:
            dict with list of concepts
        """
        try:
            conn = db.get_connection()
            concepts = db.get_concepts_for_session(conn, session_id)
            return {"concepts": concepts, "count": len(concepts)}
        except Exception as e:
            return {"error": str(e), "concepts": []}

    @mcp.tool
    def get_errors_without_solutions(project_id: Optional[str] = None) -> dict:
        """Find unresolved errors (errors without solutions).

        Args:
            project_id: Optional project ID to filter by

        Returns:
            dict with list of unresolved errors
        """
        try:
            conn = db.get_connection()
            errors = db.get_unresolved_errors(conn, project_id)
            return {"errors": errors, "count": len(errors)}
        except Exception as e:
            return {"error": str(e), "errors": []}

    @mcp.tool
    def get_recent_errors(limit: int = 10) -> dict:
        """Get the most recent errors across all projects.

        Args:
            limit: Maximum number of errors to return (default 10)

        Returns:
            dict with list of recent errors
        """
        try:
            conn = db.get_connection()
            errors = db.get_recent_errors(conn, limit)
            return {"errors": errors}
        except Exception as e:
            return {"error": str(e), "errors": []}

    @mcp.tool
    def get_agent_activity(
        agent_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Get action events performed by a specific agent.

        Args:
            agent_id: Agent ID
            start_date: Optional ISO/date lower bound
            end_date: Optional ISO/date upper bound

        Returns:
            dict with agent metadata and matching events
        """
        try:
            conn = db.get_connection()
            return db.get_agent_activity(conn, agent_id, start_date, end_date)
        except Exception as e:
            return {"error": str(e), "events": []}

    @mcp.tool
    def get_model_activity(
        model_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Get action events produced by a specific model."""
        try:
            conn = db.get_connection()
            return db.get_model_activity(conn, model_id, start_date, end_date)
        except Exception as e:
            return {"error": str(e), "events": []}

    @mcp.tool
    def get_action_timeline(
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        model_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Get filtered provenance timeline events."""
        try:
            conn = db.get_connection()
            return db.get_action_timeline(
                conn,
                project_id=project_id,
                agent_id=agent_id,
                model_id=model_id,
                since=since,
                until=until,
                limit=_clamp_limit(limit, default=100, maximum=1000),
                offset=offset,
            )
        except Exception as e:
            return {"error": str(e), "events": []}

    @mcp.tool
    def get_entity_provenance(target_type: str, target_id: str, limit: int = 100) -> dict:
        """Get action history for a specific entity."""
        try:
            conn = db.get_connection()
            return db.get_entity_provenance(
                conn,
                target_type=target_type,
                target_id=target_id,
                limit=_clamp_limit(limit, default=100, maximum=1000),
            )
        except Exception as e:
            return {"error": str(e), "events": []}

    @mcp.tool
    def delete_session(session_id: str, actor_context: Optional[dict] = None) -> dict:
        """Delete a session and all its errors and solutions.

        Warning: This is a cascade delete and cannot be undone.

        Args:
            session_id: ID of the session to delete

        Returns:
            dict with deletion statistics
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            session = db.get_session_by_id(conn, session_id)
            result = db.delete_session_cascade(conn, session_id)
            if "error" not in result:
                _log_event(
                    conn,
                    actor_context,
                    "delete_session",
                    "Session",
                    session_id,
                    project_id=session.get("project_id") if session else None,
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_project_daily_activities(project_id: str, limit: int = 100, offset: int = 0) -> dict:
        """Get all daily activities for a project.

        Args:
            project_id: ID of the project

        Returns:
            dict with list of daily activities
        """
        try:
            conn = db.get_connection()
            activities = db.get_daily_activities_for_project(
                conn,
                project_id,
                _clamp_limit(limit, default=100, maximum=500),
                offset,
            )
            return {"activities": activities, "count": len(activities)}
        except Exception as e:
            return {"error": str(e), "activities": []}

    @mcp.tool
    def get_daily_summary(date: str) -> dict:
        """Get aggregated summary for a specific date across all projects.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            dict with total sessions, errors, and per-project breakdown
        """
        try:
            date_err = _validate_date(date)
            if date_err:
                return {"error": date_err}
            conn = db.get_connection()
            return db.get_daily_summary(conn, date)
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def update_daily_activity(
        activity_id: str,
        summary: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Update a daily activity's summary.

        Args:
            activity_id: ID of the daily activity
            summary: New summary text

        Returns:
            dict with success status
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            if _is_blank(summary):
                return {"error": "summary cannot be empty"}
            conn = db.get_connection()
            result = db.update_daily_activity_summary(conn, activity_id, summary)
            if "error" not in result:
                _log_event(
                    conn,
                    actor_context,
                    "update_daily_activity",
                    "DailyActivity",
                    activity_id,
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    # ── Artifact tools ──────────────────────────────────────────────

    @mcp.tool
    def add_artifact(
        artifact_type: str,
        title: str,
        description: str,
        content: str,
        created_by: str = "agent",
        tags: Optional[list[str]] = None,
        file_path: Optional[str] = None,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Create a new artifact in the knowledge graph.

        Artifacts store files, configs, logs, code snippets, datasheets, etc.

        Args:
            artifact_type: Type of artifact (datasheet/config/log/code/snippet/diagram/note/reference/template/other)
            title: Short title for the artifact
            description: Description of the artifact's purpose
            content: The actual content (code, config text, log output, etc.)
            created_by: Who created it - 'agent' or 'user' (default 'agent')
            tags: Optional list of tags for categorization
            file_path: Optional path to associated file on disk

        Returns:
            dict with artifact_id on success, or error dict on failure
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            if _is_blank(title):
                return {"error": "title cannot be empty"}
            if _is_blank(content):
                return {"error": "content cannot be empty"}
            size_error = _validate_artifact_content_size(content)
            if size_error:
                return {"error": size_error}
            if artifact_type not in db.VALID_ARTIFACT_TYPES:
                return {
                    "error": f"Invalid artifact type '{artifact_type}'. Valid types: {', '.join(sorted(db.VALID_ARTIFACT_TYPES))}"
                }
            if created_by not in ("agent", "user"):
                return {"error": "created_by must be 'agent' or 'user'"}

            conn = db.get_connection()
            embed_text = f"{title}: {description or ''} {content[:500]}"
            embedding = embeddings.embed(embed_text)
            artifact_id = db.add_artifact(
                conn,
                artifact_type,
                title,
                description or "",
                content,
                embedding,
                created_by,
                tags,
                file_path,
            )
            _log_event(
                conn,
                actor_context,
                "add_artifact",
                "Artifact",
                artifact_id,
                metadata={"artifact_type": artifact_type, "title": title},
            )
            return {"artifact_id": artifact_id}
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def get_artifact_details(artifact_id: str) -> dict:
        """Get full details of an artifact.

        Args:
            artifact_id: ID of the artifact

        Returns:
            dict with artifact details and linked sessions/concepts
        """
        try:
            conn = db.get_connection()
            artifact = db.get_artifact_by_id(conn, artifact_id)
            if not artifact:
                return {"error": f"Artifact {artifact_id} not found"}
            artifact.pop("embedding", None)

            sessions = []
            session_result = conn.execute(
                "MATCH (s:Session)-[:USES_ARTIFACT]->(a:Artifact {id: $aid}) RETURN s.*",
                {"aid": artifact_id},
            )
            sessions = db._result_to_dicts(session_result)
            for s in sessions:
                s["files_touched"] = db._parse_json_field(s.get("files_touched"))

            concepts = []
            concept_result = conn.execute(
                "MATCH (c:Concept)-[:ILLUSTRATES]->(a:Artifact {id: $aid}) RETURN c.*",
                {"aid": artifact_id},
            )
            concepts = db._result_to_dicts(concept_result)
            for c in concepts:
                c["tags"] = db._parse_json_field(c.get("tags"))
                c.pop("embedding", None)

            errors = []
            error_result = conn.execute(
                "MATCH (a:Artifact {id: $aid})-[:ATTACHED_TO]->(e:Error) RETURN e.*",
                {"aid": artifact_id},
            )
            errors = db._result_to_dicts(error_result)

            return {
                "artifact": artifact,
                "linked_sessions": sessions,
                "linked_concepts": concepts,
                "linked_errors": errors,
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def update_artifact(
        artifact_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
        file_path: Optional[str] = None,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Update an artifact's metadata or content (re-embeds automatically).

        Args:
            artifact_id: ID of the artifact
            title: New title
            description: New description
            content: New content
            tags: New tags list
            file_path: New file path

        Returns:
            dict with success status
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            if title is not None and _is_blank(title):
                return {"error": "title cannot be empty"}
            if content is not None and _is_blank(content):
                return {"error": "content cannot be empty"}
            if content is not None:
                size_error = _validate_artifact_content_size(content)
                if size_error:
                    return {"error": size_error}

            conn = db.get_connection()
            artifact = db.get_artifact_by_id(conn, artifact_id)
            if not artifact:
                return {"error": f"Artifact {artifact_id} not found"}

            new_embedding = None
            if title is not None or description is not None or content is not None:
                t = title or artifact.get("title", "")
                d = description or artifact.get("description", "")
                c = content or artifact.get("content", "")
                new_embedding = embeddings.embed(f"{t}: {d} {c[:500]}")

            result = db.update_artifact(
                conn,
                artifact_id,
                title,
                description,
                content,
                new_embedding,
                tags,
                file_path,
            )
            if "error" not in result:
                _log_event(
                    conn,
                    actor_context,
                    "update_artifact",
                    "Artifact",
                    artifact_id,
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def delete_artifact(artifact_id: str, actor_context: Optional[dict] = None) -> dict:
        """Delete an artifact and all its relationships.

        Args:
            artifact_id: ID of the artifact to delete

        Returns:
            dict with success status
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            result = db.delete_artifact(conn, artifact_id)
            if "error" not in result:
                _log_event(conn, actor_context, "delete_artifact", "Artifact", artifact_id)
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def link_artifact(
        artifact_id: str,
        target_id: str,
        target_type: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Link an artifact to a session, concept, or error.

        Args:
            artifact_id: ID of the artifact
            target_id: ID of the session, concept, or error
            target_type: One of 'session', 'concept', or 'error'

        Returns:
            dict with success status
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            if target_type == "session":
                result = db.link_artifact_to_session(conn, artifact_id, target_id)
                if "error" not in result:
                    session = db.get_session_by_id(conn, target_id)
                    _log_event(
                        conn,
                        actor_context,
                        "link_artifact",
                        "Artifact",
                        artifact_id,
                        project_id=session.get("project_id") if session else None,
                        metadata={"target_type": target_type, "target_id": target_id},
                    )
                return result
            elif target_type == "concept":
                result = db.link_artifact_to_concept(conn, artifact_id, target_id)
                if "error" not in result:
                    _log_event(
                        conn,
                        actor_context,
                        "link_artifact",
                        "Artifact",
                        artifact_id,
                        metadata={"target_type": target_type, "target_id": target_id},
                    )
                return result
            elif target_type == "error":
                result = db.link_artifact_to_error(conn, artifact_id, target_id)
                if "error" not in result:
                    rows = db._result_to_dicts(
                        conn.execute(
                            "MATCH (e:Error {id: $id}) RETURN e.project_id", {"id": target_id}
                        )
                    )
                    _log_event(
                        conn,
                        actor_context,
                        "link_artifact",
                        "Artifact",
                        artifact_id,
                        project_id=rows[0].get("project_id") if rows else None,
                        metadata={"target_type": target_type, "target_id": target_id},
                    )
                return result
            else:
                return {
                    "error": f"Invalid target_type '{target_type}'. Use 'session', 'concept', or 'error'."
                }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def unlink_artifact_from_session(
        artifact_id: str,
        session_id: str,
        actor_context: Optional[dict] = None,
    ) -> dict:
        """Remove an artifact link from a session.

        Args:
            artifact_id: ID of the artifact
            session_id: ID of the session

        Returns:
            dict with success status
        """
        try:
            actor_context, err = _validated_ctx(actor_context)
            if err:
                return err
            conn = db.get_connection()
            result = db.unlink_artifact_from_session(conn, artifact_id, session_id)
            if "error" not in result:
                session = db.get_session_by_id(conn, session_id)
                _log_event(
                    conn,
                    actor_context,
                    "unlink_artifact_from_session",
                    "Artifact",
                    artifact_id,
                    project_id=session.get("project_id") if session else None,
                    metadata={"session_id": session_id},
                )
            return result
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool
    def list_artifacts(artifact_type: str, limit: int = 50, offset: int = 0) -> dict:
        """List artifacts filtered by type.

        Args:
            artifact_type: Type filter (datasheet/config/log/code/snippet/diagram/note/reference/template/other)
            limit: Max results (default 50)
            offset: Pagination offset

        Returns:
            dict with list of artifacts
        """
        try:
            if artifact_type not in db.VALID_ARTIFACT_TYPES:
                return {
                    "error": f"Invalid artifact type '{artifact_type}'. Valid types: {', '.join(sorted(db.VALID_ARTIFACT_TYPES))}",
                    "artifacts": [],
                }

            conn = db.get_connection()
            artifacts = db.list_artifacts_by_type(
                conn, artifact_type, _clamp_limit(limit, default=50, maximum=500), offset
            )
            for a in artifacts:
                a.pop("embedding", None)
            return {"artifacts": artifacts, "count": len(artifacts)}
        except Exception as e:
            return {"error": str(e), "artifacts": []}

    @mcp.tool
    def get_project_artifacts(project_id: str, limit: int = 50, offset: int = 0) -> dict:
        """Get all artifacts linked to a project's sessions.

        Args:
            project_id: ID of the project
            limit: Maximum artifacts to return (default 50)
            offset: Pagination offset

        Returns:
            dict with list of artifacts
        """
        try:
            conn = db.get_connection()
            artifacts = db.get_artifacts_for_project(
                conn, project_id, _clamp_limit(limit, default=50, maximum=200), offset
            )
            for a in artifacts:
                a.pop("embedding", None)
            return {"artifacts": artifacts, "count": len(artifacts)}
        except Exception as e:
            return {"error": str(e), "artifacts": []}

    @mcp.tool
    def search_artifacts_by_tag(tag: str, limit: int = 50, offset: int = 0) -> dict:
        """Find artifacts by tag.

        Args:
            tag: Tag to search for
            limit: Maximum artifacts to return (default 50)
            offset: Pagination offset

        Returns:
            dict with list of matching artifacts
        """
        try:
            conn = db.get_connection()
            artifacts = db.search_artifacts_by_tag(
                conn, tag, _clamp_limit(limit, default=50, maximum=200), offset
            )
            for a in artifacts:
                a.pop("embedding", None)
            return {"artifacts": artifacts, "count": len(artifacts)}
        except Exception as e:
            return {"error": str(e), "artifacts": []}
