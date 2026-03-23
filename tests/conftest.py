import pytest
import kuzu
import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path for testing."""
    db_file = tmp_path / "test.graph.db"
    yield db_file
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture
def test_connection(temp_db_path):
    """Create a test database connection with schema initialized."""
    from src import db

    original_get_db_path = db.get_db_path

    def mock_get_db_path():
        return temp_db_path

    db._close_db_singleton()
    db._SCHEMA_READY_PATHS.clear()
    db.get_db_path = mock_get_db_path

    conn = db.get_connection()

    yield conn

    db._close_db_singleton()
    db._SCHEMA_READY_PATHS.clear()
    db.get_db_path = original_get_db_path


@pytest.fixture
def mock_embed():
    """Mock embedding function that returns fixed vectors."""
    import numpy as np

    def _embed(text):
        np.random.seed(hash(text) % (2**32))
        return np.random.rand(384).tolist()

    return _embed


@pytest.fixture
def sample_project(test_connection):
    """Create a sample project for testing."""
    from src import db

    project_id = db.add_project(test_connection, "test-project", "/tmp/test", "Test project")
    return project_id


@pytest.fixture
def sample_session(test_connection, sample_project):
    """Create a sample session for testing."""
    from src import db

    session_id = db.add_session(
        test_connection, sample_project, "Test session", ["file1.py", "file2.py"]
    )
    return session_id


@pytest.fixture
def sample_error(test_connection, sample_session, sample_project, mock_embed):
    """Create a sample error for testing."""
    from src import db

    embedding = mock_embed("Test error message")
    error_id = db.add_error(
        test_connection,
        sample_project,
        sample_session,
        "Test error message",
        "Test context",
        "test.py",
        embedding,
    )
    return error_id


@pytest.fixture
def sample_solution(test_connection, sample_error):
    """Create a sample solution for testing."""
    from src import db

    solution_id = db.add_solution(test_connection, sample_error, "Test solution", "print('fixed')")
    return solution_id


@pytest.fixture
def sample_concept(test_connection, mock_embed):
    """Create a sample concept for testing."""
    from src import db

    embedding = mock_embed("Test concept: A test concept for testing")
    concept_id = db.add_concept(
        test_connection,
        "Test concept",
        "A test concept for testing",
        ["test", "concept"],
        embedding,
    )
    return concept_id
