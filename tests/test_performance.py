import sys
from pathlib import Path
from time import perf_counter

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.performance
def test_search_scaling_synthetic_dataset(test_connection, mock_embed):
    from src import db

    project_id = db.add_project(test_connection, "perf-project", "/tmp/perf-project", "perf")
    session_ids = []
    for i in range(200):
        sid = db.add_session(test_connection, project_id, f"session {i}", [f"file_{i}.py"])
        session_ids.append(sid)

    concept_ids = []
    for i in range(400):
        title = f"concept-{i}"
        content = f"auth token refresh pattern {i}"
        emb = mock_embed(f"{title}: {content}")
        cid = db.add_concept(test_connection, title, content, ["auth", "token"], emb)
        concept_ids.append(cid)

    for i, sid in enumerate(session_ids):
        for j in range(2):
            db.link_concept_to_session(
                test_connection, concept_ids[(i * 2 + j) % len(concept_ids)], sid
            )

    query_emb = mock_embed("token refresh auth")
    concepts = db.get_all_concept_embeddings(test_connection)

    started = perf_counter()
    scored = []
    from src import embeddings

    for c in concepts:
        if c["embedding"]:
            scored.append(embeddings.cosine_similarity(query_emb, c["embedding"]))
    elapsed_ms = (perf_counter() - started) * 1000

    assert len(scored) > 0
    assert elapsed_ms < 1500


@pytest.mark.performance
def test_clustering_scaling_synthetic_dataset(test_connection, mock_embed):
    from src import db

    project_id = db.add_project(test_connection, "cluster-perf", "/tmp/cluster-perf", "perf")
    sid = db.add_session(test_connection, project_id, "cluster session", ["c.py"])

    for i in range(120):
        message = f"error pattern {i % 10} variant {i}"
        emb = mock_embed(message)
        db.add_error(test_connection, project_id, sid, message, "ctx", "c.py", emb)

    started = perf_counter()
    result = db.cluster_errors_by_similarity(test_connection, project_id, 0.92)
    elapsed_ms = (perf_counter() - started) * 1000

    assert "clusters" in result
    assert elapsed_ms < 2000
