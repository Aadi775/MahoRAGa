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
    assert len(tools) == 42


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

    delete_concept = await _call_tool_fn(mcp, "delete_concept", concept["concept_id"])
    assert delete_concept.get("deleted") is True

    delete_session = await _call_tool_fn(mcp, "delete_session", session["session_id"])
    assert delete_session.get("deleted") is True


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
