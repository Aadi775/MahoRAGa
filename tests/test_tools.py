import pytest
from fastmcp import FastMCP

from src.tools import register_tools


async def _call_tool_fn(mcp: FastMCP, name: str, *args, **kwargs):
    tool = await mcp.get_tool(name)
    assert tool is not None
    return tool.fn(*args, **kwargs)


@pytest.mark.asyncio
async def test_tools_registered_count():
    mcp = FastMCP("test")
    register_tools(mcp)
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}
    required = {
        "add_project",
        "add_session",
        "search",
        "log_error",
        "log_solution",
        "get_project_history",
        "add_artifact",
        "link_artifact",
    }
    assert required.issubset(tool_names)


@pytest.mark.asyncio
async def test_project_session_error_solution_flow(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    project = await _call_tool_fn(mcp, "add_project", "proj-a", "/tmp/proj-a", "desc")
    assert "project_id" in project

    session = await _call_tool_fn(
        mcp,
        "add_session",
        "proj-a",
        "worked on setup",
        ["a.py", "b.py"],
    )
    assert "session_id" in session

    error = await _call_tool_fn(
        mcp,
        "log_error",
        session["session_id"],
        "TypeError: x is None",
        "while bootstrapping",
        "a.py",
    )
    assert "error_id" in error

    solution = await _call_tool_fn(
        mcp,
        "log_solution",
        error["error_id"],
        "added null check",
        "if x is None: return",
    )
    assert "solution_id" in solution


@pytest.mark.asyncio
async def test_input_validation_for_core_tools(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    bad_project = await _call_tool_fn(mcp, "add_project", "", "/tmp/x", "desc")
    assert "error" in bad_project

    good_project = await _call_tool_fn(mcp, "add_project", "proj-valid", "/tmp/proj-valid", "desc")
    assert "project_id" in good_project

    bad_session = await _call_tool_fn(mcp, "add_session", "proj-valid", "", ["a.py"])
    assert "error" in bad_session

    bad_search = await _call_tool_fn(mcp, "search", "", 5)
    assert "error" in bad_search
    assert {
        "concepts",
        "sessions",
        "errors",
        "solutions",
        "artifacts",
        "metrics",
    }.issubset(bad_search.keys())

    session = await _call_tool_fn(mcp, "add_session", "proj-valid", "summary", ["a.py"])
    bad_error = await _call_tool_fn(mcp, "log_error", session["session_id"], "", "ctx", "a.py")
    assert "error" in bad_error

    bad_concept = await _call_tool_fn(mcp, "add_concept", "", "valid content", ["x"])
    assert "error" in bad_concept

    bad_cleanup = await _call_tool_fn(mcp, "delete_old_sessions", "abc")
    assert "error" in bad_cleanup

    bad_artifact_type = await _call_tool_fn(mcp, "list_artifacts", "banana", 5, 0)
    assert "error" in bad_artifact_type


@pytest.mark.asyncio
async def test_concept_link_and_search_flow(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "proj-b", "/tmp/proj-b", "desc")
    session = await _call_tool_fn(
        mcp,
        "add_session",
        "proj-b",
        "worked on auth",
        ["auth.py"],
    )
    concept = await _call_tool_fn(
        mcp,
        "add_concept",
        "JWT refresh",
        "refresh token before expiry",
        ["auth", "jwt"],
    )
    assert "concept_id" in concept

    link = await _call_tool_fn(
        mcp, "link_concept_to_session", concept["concept_id"], session["session_id"]
    )
    assert link.get("linked") is True

    tag_search = await _call_tool_fn(mcp, "search_by_tag", "auth")
    assert "concepts" in tag_search

    semantic = await _call_tool_fn(mcp, "search", "jwt token refresh", 5)
    assert "concepts" in semantic
    assert "sessions" in semantic

    concept_details = await _call_tool_fn(mcp, "get_concept_details", concept["concept_id"])
    assert "concept" in concept_details
    assert "embedding" not in concept_details["concept"]


@pytest.mark.asyncio
async def test_daily_activity_tools(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    project = await _call_tool_fn(mcp, "add_project", "proj-c", "/tmp/proj-c", "desc")
    session = await _call_tool_fn(
        mcp,
        "add_session",
        "proj-c",
        "daily work",
        ["x.py"],
    )
    closed = await _call_tool_fn(mcp, "close_session", session["session_id"], None)
    assert closed.get("closed") is True

    activities = await _call_tool_fn(mcp, "get_project_daily_activities", project["project_id"])
    assert "activities" in activities

    if activities["activities"]:
        activity_id = activities["activities"][0]["id"]
        update = await _call_tool_fn(mcp, "update_daily_activity", activity_id, "updated")
        assert update.get("updated") is True


@pytest.mark.asyncio
async def test_batch_and_admin_tools(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "proj-d", "/tmp/proj-d", "desc")
    session = await _call_tool_fn(mcp, "add_session", "proj-d", "batch work", ["k.py"])

    batch = await _call_tool_fn(
        mcp,
        "batch_add_concepts",
        [
            {"title": "c1", "content": "content1", "tags": ["t1"]},
            {"title": "c2", "content": "content2", "tags": ["t2"]},
        ],
    )
    assert "concept_ids" in batch
    assert len(batch["concept_ids"]) == 2

    linked = await _call_tool_fn(
        mcp, "batch_link_concepts", batch["concept_ids"], session["session_id"]
    )
    assert linked.get("count") == 2

    recent_sessions = await _call_tool_fn(mcp, "get_recent_sessions", 5)
    assert "sessions" in recent_sessions

    recent_errors = await _call_tool_fn(mcp, "get_recent_errors", 5)
    assert "errors" in recent_errors


@pytest.mark.asyncio
async def test_update_and_delete_tools(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    project = await _call_tool_fn(mcp, "add_project", "proj-e", "/tmp/proj-e", "desc")
    session = await _call_tool_fn(mcp, "add_session", "proj-e", "initial", ["m.py"])
    concept = await _call_tool_fn(mcp, "add_concept", "title", "content", ["a"])

    upd_proj = await _call_tool_fn(
        mcp,
        "update_project",
        project["project_id"],
        "proj-e2",
        "/tmp/proj-e2",
        "new-desc",
        None,
    )
    assert upd_proj.get("updated") is True

    upd_sess = await _call_tool_fn(mcp, "update_session_summary", session["session_id"], "updated")
    assert upd_sess.get("updated") is True

    upd_concept = await _call_tool_fn(
        mcp, "update_concept", concept["concept_id"], "new content", None
    )
    assert upd_concept.get("updated") is True

    concepts_by_tag = await _call_tool_fn(mcp, "search_by_tag", "a")
    updated = next(c for c in concepts_by_tag["concepts"] if c["id"] == concept["concept_id"])
    assert updated["title"] == "title"

    delete_concept = await _call_tool_fn(mcp, "delete_concept", concept["concept_id"])
    assert delete_concept.get("deleted") is True

    delete_session = await _call_tool_fn(mcp, "delete_session", session["session_id"])
    assert delete_session.get("deleted") is True

    safe_cleanup = await _call_tool_fn(mcp, "delete_old_sessions", 0)
    assert "deleted_sessions" in safe_cleanup


@pytest.mark.asyncio
async def test_stats_and_history_tools(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    project = await _call_tool_fn(mcp, "add_project", "proj-f", "/tmp/proj-f", "desc")
    session = await _call_tool_fn(mcp, "add_session", "proj-f", "work", ["q.py"])
    error = await _call_tool_fn(
        mcp, "log_error", session["session_id"], "ValueError", "ctx", "q.py"
    )
    await _call_tool_fn(mcp, "log_solution", error["error_id"], "fix", "pass")

    stats = await _call_tool_fn(mcp, "get_project_stats", project["project_id"])
    assert "session_count" in stats

    history = await _call_tool_fn(mcp, "get_project_history", "proj-f")
    assert "sessions" in history
    assert "errors" in history
    assert "solutions" in history

    unresolved = await _call_tool_fn(mcp, "get_errors_without_solutions", project["project_id"])
    assert "errors" in unresolved
    if unresolved["errors"]:
        assert "message_embedding" not in unresolved["errors"][0]

    projects = await _call_tool_fn(mcp, "list_projects", 1, 0)
    assert len(projects["projects"]) <= 1

    activities = await _call_tool_fn(
        mcp, "get_project_daily_activities", project["project_id"], 1, 0
    )
    assert len(activities["activities"]) <= 1


@pytest.mark.asyncio
async def test_get_error_solutions_clamps_top_k(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "proj-clamp", "/tmp/proj-clamp", "desc")
    session = await _call_tool_fn(mcp, "add_session", "proj-clamp", "work", ["q.py"])

    for i in range(60):
        err = await _call_tool_fn(
            mcp,
            "log_error",
            session["session_id"],
            f"ClampError {i}",
            "ctx",
            "q.py",
        )
        await _call_tool_fn(mcp, "log_solution", err["error_id"], "fix", "pass")

    result = await _call_tool_fn(mcp, "get_error_solutions", "ClampError", 10000)
    assert len(result["errors"]) <= 50


@pytest.mark.asyncio
async def test_search_returns_recency_and_rank_scores(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "proj-rank", "/tmp/proj-rank", "desc")
    session = await _call_tool_fn(mcp, "add_session", "proj-rank", "auth work", ["auth.py"])
    concept = await _call_tool_fn(
        mcp,
        "add_concept",
        "JWT refresh token",
        "refresh token before expiry in authentication flows",
        ["auth", "jwt"],
    )
    await _call_tool_fn(
        mcp, "link_concept_to_session", concept["concept_id"], session["session_id"]
    )

    result = await _call_tool_fn(mcp, "search", "jwt refresh token auth", 5)
    assert result["concepts"]

    top = result["concepts"][0]
    assert "recency_score" in top
    assert "rank_score" in top
    assert "keyword_score" in top


@pytest.mark.asyncio
async def test_search_filters_sessions_and_errors_to_final_topk(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "proj-filter", "/tmp/proj-filter", "desc")
    s1 = await _call_tool_fn(mcp, "add_session", "proj-filter", "auth jwt refresh", ["a.py"])
    s2 = await _call_tool_fn(mcp, "add_session", "proj-filter", "noise session", ["b.py"])

    c1 = await _call_tool_fn(
        mcp,
        "add_concept",
        "JWT refresh strategy",
        "token refresh before expiry",
        ["auth"],
    )
    c2 = await _call_tool_fn(
        mcp,
        "add_concept",
        "Unrelated concept",
        "misc unrelated notes",
        ["misc"],
    )

    await _call_tool_fn(mcp, "link_concept_to_session", c1["concept_id"], s1["session_id"])
    await _call_tool_fn(mcp, "link_concept_to_session", c2["concept_id"], s2["session_id"])

    await _call_tool_fn(
        mcp,
        "log_error",
        s1["session_id"],
        "AuthError",
        "during token refresh",
        "a.py",
    )
    await _call_tool_fn(
        mcp,
        "log_error",
        s2["session_id"],
        "NoiseError",
        "unrelated",
        "b.py",
    )

    result = await _call_tool_fn(mcp, "search", "jwt refresh", 1)
    assert len(result["concepts"]) == 1
    assert result["concepts"][0]["id"] == c1["concept_id"]

    assert all(sess["id"] == s1["session_id"] for sess in result["sessions"])
    assert all(err["session_id"] == s1["session_id"] for err in result["errors"])


@pytest.mark.asyncio
async def test_search_uses_bounded_embedding_scans(test_connection, monkeypatch):
    from src import db as db_module
    from src.tools import SEARCH_EMBEDDING_SCAN_LIMIT

    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "proj-bound", "/tmp/proj-bound", "desc")
    await _call_tool_fn(mcp, "add_concept", "Bounded Concept", "content", ["bound"])
    await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="note",
        title="Bounded Artifact",
        description="desc",
        content="content",
    )
    s = await _call_tool_fn(mcp, "add_session", "proj-bound", "work", ["x.py"])
    await _call_tool_fn(mcp, "log_error", s["session_id"], "bounded error", "ctx", "x.py")

    calls = {"concept": None, "artifact": None, "error": None}
    orig_concepts = db_module.get_all_concept_embeddings
    orig_artifacts = db_module.get_all_artifact_embeddings
    orig_errors = db_module.get_all_error_embeddings

    def wrapped_concepts(conn, limit=None):
        calls["concept"] = limit
        return orig_concepts(conn, limit)

    def wrapped_artifacts(conn, limit=None):
        calls["artifact"] = limit
        return orig_artifacts(conn, limit)

    def wrapped_errors(conn, limit=None):
        calls["error"] = limit
        return orig_errors(conn, limit)

    monkeypatch.setattr(db_module, "get_all_concept_embeddings", wrapped_concepts)
    monkeypatch.setattr(db_module, "get_all_artifact_embeddings", wrapped_artifacts)
    monkeypatch.setattr(db_module, "get_all_error_embeddings", wrapped_errors)

    await _call_tool_fn(mcp, "search", "bounded", 5)
    await _call_tool_fn(mcp, "get_error_solutions", "bounded", 5)

    assert calls["concept"] == SEARCH_EMBEDDING_SCAN_LIMIT
    assert calls["artifact"] == SEARCH_EMBEDDING_SCAN_LIMIT
    assert calls["error"] == SEARCH_EMBEDDING_SCAN_LIMIT


@pytest.mark.asyncio
async def test_search_empty_db_has_normalized_response(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    result = await _call_tool_fn(mcp, "search", "anything", 5)
    assert {
        "concepts",
        "sessions",
        "errors",
        "solutions",
        "artifacts",
        "metrics",
    }.issubset(result.keys())
    assert result["concepts"] == []
    assert result["artifacts"] == []


@pytest.mark.asyncio
async def test_search_exception_path_has_normalized_response(test_connection, monkeypatch):
    from src import embeddings as embeddings_module

    mcp = FastMCP("test")
    register_tools(mcp)

    def boom(_query: str):
        raise RuntimeError("internal failure")

    monkeypatch.setattr(embeddings_module, "embed", boom)

    result = await _call_tool_fn(mcp, "search", "jwt refresh", 5)
    assert "error" in result
    assert {
        "concepts",
        "sessions",
        "errors",
        "solutions",
        "artifacts",
        "metrics",
    }.issubset(result.keys())


@pytest.mark.asyncio
async def test_update_project_missing_returns_error(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    result = await _call_tool_fn(
        mcp,
        "update_project",
        "missing-project-id",
        "new-name",
        None,
        None,
        None,
    )
    assert "error" in result
    assert result.get("updated") is False
