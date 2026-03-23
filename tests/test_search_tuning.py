import pytest
from fastmcp import FastMCP

from src.tools import register_tools


async def _call_tool_fn(mcp: FastMCP, name: str, *args, **kwargs):
    tool = await mcp.get_tool(name)
    assert tool is not None
    return tool.fn(*args, **kwargs)


@pytest.mark.asyncio
async def test_search_prefers_title_keyword_match(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "tuning-title", "/tmp/tuning-title", "desc")
    session = await _call_tool_fn(mcp, "add_session", "tuning-title", "session", ["a.py"])

    strong = await _call_tool_fn(
        mcp,
        "add_concept",
        "JWT refresh token strategy",
        "auth flow details",
        ["auth"],
    )
    weak = await _call_tool_fn(
        mcp,
        "add_concept",
        "Authentication notes",
        "this mentions jwt refresh token in passing",
        ["auth"],
    )

    await _call_tool_fn(mcp, "link_concept_to_session", strong["concept_id"], session["session_id"])
    await _call_tool_fn(mcp, "link_concept_to_session", weak["concept_id"], session["session_id"])

    result = await _call_tool_fn(mcp, "search", "jwt refresh token", 2)
    assert len(result["concepts"]) == 2
    assert result["concepts"][0]["id"] == strong["concept_id"]


@pytest.mark.asyncio
async def test_search_uses_candidate_expansion_then_trims(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "tuning-candidates", "/tmp/tuning-candidates", "desc")
    session = await _call_tool_fn(mcp, "add_session", "tuning-candidates", "session", ["a.py"])

    target = await _call_tool_fn(
        mcp,
        "add_concept",
        "Token rotation pipeline",
        "rotation for refresh token with audit",
        ["auth"],
    )
    await _call_tool_fn(mcp, "link_concept_to_session", target["concept_id"], session["session_id"])

    for i in range(20):
        concept = await _call_tool_fn(
            mcp,
            "add_concept",
            f"Noise concept {i}",
            "misc notes unrelated to auth token rotation",
            ["misc"],
        )
        await _call_tool_fn(
            mcp, "link_concept_to_session", concept["concept_id"], session["session_id"]
        )

    result = await _call_tool_fn(mcp, "search", "token rotation refresh", 3)
    assert len(result["concepts"]) == 3
    ids = {c["id"] for c in result["concepts"]}
    assert target["concept_id"] in ids


@pytest.mark.asyncio
async def test_search_returns_weight_metadata(test_connection):
    mcp = FastMCP("test")
    register_tools(mcp)

    await _call_tool_fn(mcp, "add_project", "tuning-meta", "/tmp/tuning-meta", "desc")
    session = await _call_tool_fn(mcp, "add_session", "tuning-meta", "session", ["a.py"])
    concept = await _call_tool_fn(
        mcp,
        "add_concept",
        "Database migration rollback",
        "safe rollback strategy for failed migrations",
        ["db"],
    )
    await _call_tool_fn(
        mcp, "link_concept_to_session", concept["concept_id"], session["session_id"]
    )

    result = await _call_tool_fn(mcp, "search", "migration rollback strategy", 1)
    assert result["concepts"]

    top = result["concepts"][0]
    assert "title_score" in top
    assert "keyword_score" in top
    assert "rank_score" in top
    assert "metrics" in result
    assert result["metrics"]["concept_results"] == 1
