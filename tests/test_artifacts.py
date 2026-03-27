"""Tests for the Artifact feature — schema, DB layer, tools, and search integration."""

import pytest
from src import db


# ── DB-layer tests ───────────────────────────────────────────────────


class TestArtifactSchema:
    def test_artifact_table_created(self, test_connection):
        result = test_connection.execute("CALL SHOW_TABLES() RETURN *")
        tables = set()
        while result.has_next():
            row = result.get_next()
            tables.add(row[1])
        assert "Artifact" in tables
        assert "USES_ARTIFACT" in tables
        assert "ILLUSTRATES" in tables
        assert "ATTACHED_TO" in tables


class TestArtifactCRUD:
    def test_add_artifact(self, test_connection, mock_embed):
        emb = mock_embed("test artifact")
        aid = db.add_artifact(
            test_connection,
            artifact_type="config",
            title="DB Config",
            description="Database configuration file",
            content="host=localhost\nport=5432",
            embedding=emb,
            created_by="user",
            tags=["database", "config"],
            file_path="/etc/db.conf",
        )
        assert aid is not None

        artifact = db.get_artifact_by_id(test_connection, aid)
        assert artifact is not None
        assert artifact["title"] == "DB Config"
        assert artifact["type"] == "config"
        assert artifact["created_by"] == "user"
        assert artifact["content"] == "host=localhost\nport=5432"
        assert artifact["file_path"] == "/etc/db.conf"
        assert "database" in artifact["tags"]
        assert "config" in artifact["tags"]

    def test_get_artifact_not_found(self, test_connection):
        result = db.get_artifact_by_id(test_connection, "nonexistent")
        assert result is None

    def test_update_artifact(self, test_connection, mock_embed):
        emb = mock_embed("original")
        aid = db.add_artifact(
            test_connection, "note", "Original Title", "desc", "original content", emb
        )

        new_emb = mock_embed("updated content")
        result = db.update_artifact(
            test_connection,
            aid,
            title="Updated Title",
            content="updated content",
            new_embedding=new_emb,
            tags=["updated"],
        )
        assert result == {"updated": True}

        artifact = db.get_artifact_by_id(test_connection, aid)
        assert artifact is not None
        assert artifact["title"] == "Updated Title"
        assert artifact["content"] == "updated content"
        assert "updated" in artifact["tags"]

    def test_update_artifact_not_found(self, test_connection):
        result = db.update_artifact(test_connection, "nonexistent", title="x")
        assert "error" in result

    def test_delete_artifact(self, test_connection, mock_embed):
        emb = mock_embed("to delete")
        aid = db.add_artifact(test_connection, "log", "Delete Me", "desc", "content", emb)
        result = db.delete_artifact(test_connection, aid)
        assert result == {"deleted": True}
        assert db.get_artifact_by_id(test_connection, aid) is None

    def test_delete_artifact_not_found(self, test_connection):
        result = db.delete_artifact(test_connection, "nonexistent")
        assert "error" in result


class TestArtifactLinking:
    @pytest.fixture
    def setup_data(self, test_connection, mock_embed):
        pid = db.add_project(test_connection, "artifact_test_proj", "/tmp/test")
        sid = db.add_session(test_connection, pid, "test session", ["a.py"])
        emb = mock_embed("concept for artifact")
        cid = db.add_concept(test_connection, "Test Concept", "content", ["tag"], emb)
        err_emb = mock_embed("test error for artifact")
        eid = db.add_error(test_connection, pid, sid, "TestError", "ctx", "a.py", err_emb)
        art_emb = mock_embed("test artifact")
        aid = db.add_artifact(
            test_connection,
            "code",
            "Test Artifact",
            "desc",
            "print('hello')",
            art_emb,
        )
        return {"pid": pid, "sid": sid, "cid": cid, "eid": eid, "aid": aid}

    def test_link_artifact_to_session(self, test_connection, setup_data):
        result = db.link_artifact_to_session(test_connection, setup_data["aid"], setup_data["sid"])
        assert result == {"linked": True}

        artifacts = db.get_artifacts_for_session(test_connection, setup_data["sid"])
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == setup_data["aid"]

    def test_link_artifact_to_session_idempotent(self, test_connection, setup_data):
        db.link_artifact_to_session(test_connection, setup_data["aid"], setup_data["sid"])
        db.link_artifact_to_session(test_connection, setup_data["aid"], setup_data["sid"])
        artifacts = db.get_artifacts_for_session(test_connection, setup_data["sid"])
        assert len(artifacts) == 1

    def test_unlink_artifact_from_session(self, test_connection, setup_data):
        db.link_artifact_to_session(test_connection, setup_data["aid"], setup_data["sid"])
        result = db.unlink_artifact_from_session(
            test_connection, setup_data["aid"], setup_data["sid"]
        )
        assert result == {"unlinked": True}
        artifacts = db.get_artifacts_for_session(test_connection, setup_data["sid"])
        assert len(artifacts) == 0

    def test_link_artifact_to_concept(self, test_connection, setup_data):
        result = db.link_artifact_to_concept(test_connection, setup_data["aid"], setup_data["cid"])
        assert result == {"linked": True}

        artifacts = db.get_artifacts_for_concept(test_connection, setup_data["cid"])
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == setup_data["aid"]

    def test_link_artifact_to_error(self, test_connection, setup_data):
        result = db.link_artifact_to_error(test_connection, setup_data["aid"], setup_data["eid"])
        assert result == {"linked": True}

        artifacts = db.get_artifacts_for_error(test_connection, setup_data["eid"])
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == setup_data["aid"]

    def test_link_artifact_invalid_targets(self, test_connection, mock_embed):
        emb = mock_embed("orphan artifact")
        aid = db.add_artifact(test_connection, "note", "Orphan", "desc", "content", emb)

        result = db.link_artifact_to_session(test_connection, aid, "nonexistent")
        assert "error" in result

        result = db.link_artifact_to_concept(test_connection, aid, "nonexistent")
        assert "error" in result

        result = db.link_artifact_to_error(test_connection, aid, "nonexistent")
        assert "error" in result

    def test_delete_artifact_with_links(self, test_connection, setup_data):
        """Verify DETACH DELETE properly cleans up all relationships."""
        db.link_artifact_to_session(test_connection, setup_data["aid"], setup_data["sid"])
        db.link_artifact_to_concept(test_connection, setup_data["aid"], setup_data["cid"])
        db.link_artifact_to_error(test_connection, setup_data["aid"], setup_data["eid"])

        result = db.delete_artifact(test_connection, setup_data["aid"])
        assert result == {"deleted": True}

        assert db.get_artifacts_for_session(test_connection, setup_data["sid"]) == []
        assert db.get_artifacts_for_concept(test_connection, setup_data["cid"]) == []
        assert db.get_artifacts_for_error(test_connection, setup_data["eid"]) == []


class TestArtifactQueries:
    def test_list_artifacts_by_type(self, test_connection, mock_embed):
        for i in range(3):
            emb = mock_embed(f"config {i}")
            db.add_artifact(test_connection, "config", f"Config {i}", "desc", f"content {i}", emb)
        emb = mock_embed("a log")
        db.add_artifact(test_connection, "log", "Log File", "desc", "log content", emb)

        configs = db.list_artifacts_by_type(test_connection, "config")
        assert len(configs) == 3

        logs = db.list_artifacts_by_type(test_connection, "log")
        assert len(logs) == 1

    def test_get_artifacts_for_project(self, test_connection, mock_embed):
        pid = db.add_project(test_connection, "proj_with_artifacts", "/tmp/p")
        sid = db.add_session(test_connection, pid, "sess", ["x.py"])
        emb = mock_embed("project artifact")
        aid = db.add_artifact(test_connection, "code", "Project Code", "desc", "code", emb)
        db.link_artifact_to_session(test_connection, aid, sid)

        artifacts = db.get_artifacts_for_project(test_connection, pid)
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == aid

    def test_search_artifacts_by_tag(self, test_connection, mock_embed):
        emb = mock_embed("tagged artifact")
        db.add_artifact(
            test_connection,
            "note",
            "Tagged",
            "desc",
            "content",
            emb,
            tags=["python", "testing"],
        )
        emb2 = mock_embed("other artifact")
        db.add_artifact(
            test_connection,
            "note",
            "Other",
            "desc",
            "content",
            emb2,
            tags=["rust"],
        )

        results = db.search_artifacts_by_tag(test_connection, "python")
        assert len(results) == 1
        assert results[0]["title"] == "Tagged"

    def test_get_all_artifact_embeddings(self, test_connection, mock_embed):
        for i in range(2):
            emb = mock_embed(f"emb artifact {i}")
            db.add_artifact(test_connection, "note", f"Note {i}", "desc", f"content {i}", emb)

        all_embs = db.get_all_artifact_embeddings(test_connection)
        assert len(all_embs) >= 2
        for e in all_embs:
            assert "embedding" in e
            assert "title" in e

    def test_get_artifacts_by_ids(self, test_connection, mock_embed):
        emb1 = mock_embed("artifact one")
        emb2 = mock_embed("artifact two")
        aid1 = db.add_artifact(test_connection, "note", "One", "desc", "content1", emb1)
        aid2 = db.add_artifact(test_connection, "note", "Two", "desc", "content2", emb2)

        artifacts = db.get_artifacts_by_ids(test_connection, [aid2, aid1])
        ids = {a["id"] for a in artifacts}

        assert ids == {aid1, aid2}


# ── Tool-layer tests ─────────────────────────────────────────────────


async def _call_tool_fn(mcp, tool_name, *args, **kwargs):
    """Helper to call a registered MCP tool function."""
    tool = await mcp.get_tool(tool_name)
    assert tool is not None
    return tool.fn(*args, **kwargs)


@pytest.mark.asyncio
async def test_artifact_tool_crud_flow(test_connection):
    from fastmcp import FastMCP
    from src.tools import register_tools

    mcp = FastMCP("test")
    register_tools(mcp)

    # Create artifact
    result = await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="config",
        title="Test Config",
        description="A test config",
        content="key=value\nother=123",
        created_by="user",
        tags=["test"],
        file_path="/tmp/test.conf",
    )
    assert "artifact_id" in result
    aid = result["artifact_id"]

    # Get details
    details = await _call_tool_fn(mcp, "get_artifact_details", aid)
    assert details["artifact"]["title"] == "Test Config"
    assert "embedding" not in details["artifact"]

    # Update
    update_result = await _call_tool_fn(
        mcp, "update_artifact", aid, title="Updated Config", content="new=content"
    )
    assert update_result == {"updated": True}

    updated = await _call_tool_fn(mcp, "get_artifact_details", aid)
    assert updated["artifact"]["title"] == "Updated Config"

    # Delete
    del_result = await _call_tool_fn(mcp, "delete_artifact", aid)
    assert del_result == {"deleted": True}


@pytest.mark.asyncio
async def test_artifact_tool_validation(test_connection):
    from fastmcp import FastMCP
    from src.tools import register_tools

    mcp = FastMCP("test")
    register_tools(mcp)

    # Empty title
    result = await _call_tool_fn(
        mcp, "add_artifact", artifact_type="note", title="", description="d", content="c"
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_artifact_content_size_guardrail_add_and_update(test_connection, monkeypatch):
    from fastmcp import FastMCP
    from src import tools as tools_module
    from src.tools import register_tools

    monkeypatch.setattr(tools_module, "MAX_ARTIFACT_CONTENT_BYTES", 16)

    mcp = FastMCP("test")
    register_tools(mcp)

    too_large = await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="note",
        title="too big",
        description="d",
        content="x" * 17,
    )
    assert "error" in too_large
    assert "maximum size" in too_large["error"]

    created = await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="note",
        title="ok",
        description="d",
        content="x" * 16,
    )
    assert "artifact_id" in created

    update_too_large = await _call_tool_fn(
        mcp,
        "update_artifact",
        created["artifact_id"],
        None,
        None,
        "y" * 17,
    )
    assert "error" in update_too_large
    assert "maximum size" in update_too_large["error"]


@pytest.mark.asyncio
async def test_artifact_content_size_guardrail_uses_utf8_bytes(test_connection, monkeypatch):
    from fastmcp import FastMCP
    from src import tools as tools_module
    from src.tools import register_tools

    monkeypatch.setattr(tools_module, "MAX_ARTIFACT_CONTENT_BYTES", 4)

    mcp = FastMCP("test")
    register_tools(mcp)

    ok = await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="note",
        title="utf8-ok",
        description="d",
        content="🚀",  # 4 bytes in UTF-8
    )
    assert "artifact_id" in ok

    too_large = await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="note",
        title="utf8-too-large",
        description="d",
        content="🚀🚀",  # 8 bytes in UTF-8
    )
    assert "error" in too_large
    assert "maximum size" in too_large["error"]

    # Empty content
    result = await _call_tool_fn(
        mcp, "add_artifact", artifact_type="note", title="t", description="d", content=""
    )
    assert "error" in result

    # Invalid type
    result = await _call_tool_fn(
        mcp, "add_artifact", artifact_type="invalid_type", title="t", description="d", content="c"
    )
    assert "error" in result

    # Invalid created_by
    result = await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="note",
        title="t",
        description="d",
        content="c",
        created_by="bot",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_artifact_link_tool(test_connection):
    from fastmcp import FastMCP
    from src.tools import register_tools

    mcp = FastMCP("test")
    register_tools(mcp)

    # Setup
    proj = await _call_tool_fn(mcp, "add_project", "link_test_proj", "/tmp/ltp")
    pid = proj["project_id"]
    sess = await _call_tool_fn(mcp, "add_session", "link_test_proj", "sess", ["a.py"])
    sid = sess["session_id"]
    art = await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="code",
        title="Link Test",
        description="d",
        content="print(1)",
    )
    aid = art["artifact_id"]

    # Link to session
    link_result = await _call_tool_fn(mcp, "link_artifact", aid, sid, "session")
    assert link_result == {"linked": True}

    # Invalid target_type
    bad_link = await _call_tool_fn(mcp, "link_artifact", aid, sid, "banana")
    assert "error" in bad_link

    # Get project artifacts
    proj_arts = await _call_tool_fn(mcp, "get_project_artifacts", pid)
    assert proj_arts["count"] == 1

    # Unlink
    unlink_result = await _call_tool_fn(mcp, "unlink_artifact_from_session", aid, sid)
    assert unlink_result == {"unlinked": True}


@pytest.mark.asyncio
async def test_search_includes_artifacts(test_connection):
    from fastmcp import FastMCP
    from src.tools import register_tools

    mcp = FastMCP("test")
    register_tools(mcp)

    # Create an artifact
    await _call_tool_fn(
        mcp,
        "add_artifact",
        artifact_type="config",
        title="Database Connection Pooling Config",
        description="PostgreSQL connection pool settings",
        content="max_connections=100\npool_size=20",
        tags=["database", "postgres"],
    )

    # Search should now return artifacts
    results = await _call_tool_fn(mcp, "search", "database connection pooling")
    assert "artifacts" in results
    assert len(results["artifacts"]) >= 1
    assert results["metrics"]["artifact_results"] >= 1
    # Verify embeddings are stripped
    for a in results["artifacts"]:
        assert "embedding" not in a
