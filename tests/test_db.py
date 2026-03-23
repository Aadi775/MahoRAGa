import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSchema:
    def test_schema_initialization(self, test_connection):
        """Test that schema is created correctly."""
        from src import db

        result = test_connection.execute("CALL SHOW_TABLES() RETURN *")
        tables = []
        while result.has_next():
            row = result.get_next()
            if row[2] == "NODE":
                tables.append(row[1])

        assert "Project" in tables
        assert "Session" in tables
        assert "Error" in tables
        assert "Solution" in tables
        assert "Concept" in tables
        assert "DailyActivity" in tables

    def test_relationship_tables_created(self, test_connection):
        """Test that relationship tables are created."""
        from src import db

        result = test_connection.execute("CALL SHOW_TABLES() RETURN *")
        rel_tables = []
        while result.has_next():
            row = result.get_next()
            if row[2] == "REL":
                rel_tables.append(row[1])

        assert "HAS_PROJECT" in rel_tables
        assert "OCCURRED_IN" in rel_tables
        assert "SOLVES" in rel_tables
        assert "REFERENCES" in rel_tables
        assert "CONTRIBUTES_TO" in rel_tables
        assert "BELONGS_TO" in rel_tables


class TestProjectOperations:
    def test_add_project(self, test_connection):
        """Test adding a project."""
        from src import db

        project_id = db.add_project(
            test_connection, "my-project", "/path/to/project", "Test description"
        )
        assert project_id is not None
        assert len(project_id) == 36  # UUID format

    def test_get_project_by_name(self, test_connection, sample_project):
        """Test retrieving a project by name."""
        from src import db

        project = db.get_project_by_name(test_connection, "test-project")
        assert project is not None
        assert project["name"] == "test-project"
        assert project["path"] == "/tmp/test"

    def test_get_project_by_id(self, test_connection, sample_project):
        """Test retrieving a project by ID."""
        from src import db

        project = db.get_project_by_id(test_connection, sample_project)
        assert project is not None
        assert project["id"] == sample_project

    def test_list_projects(self, test_connection, sample_project):
        """Test listing all projects."""
        from src import db

        projects = db.list_projects(test_connection)
        assert len(projects) >= 1
        assert any(p["id"] == sample_project for p in projects)


class TestSessionOperations:
    def test_add_session(self, test_connection, sample_project):
        """Test adding a session."""
        from src import db

        session_id = db.add_session(test_connection, sample_project, "Test session", ["file1.py"])
        assert session_id is not None

    def test_get_session_by_id(self, test_connection, sample_session):
        """Test retrieving a session."""
        from src import db

        session = db.get_session_by_id(test_connection, sample_session)
        assert session is not None
        assert session["summary"] == "Test session"
        assert "file1.py" in session["files_touched"]

    def test_close_session(self, test_connection, sample_session):
        """Test closing a session."""
        from src import db

        result = db.close_session(test_connection, sample_session)
        assert result["closed"] is True

        session = db.get_session_by_id(test_connection, sample_session)
        assert session["ended_at"] != ""

    def test_get_recent_sessions(self, test_connection, sample_session):
        """Test getting recent sessions."""
        from src import db

        sessions = db.get_recent_sessions(test_connection, 10)
        assert len(sessions) >= 1
        assert any(s["id"] == sample_session for s in sessions)


class TestErrorOperations:
    def test_add_error(self, test_connection, sample_session, sample_project, mock_embed):
        """Test adding an error."""
        from src import db

        embedding = mock_embed("Test error")
        error_id = db.add_error(
            test_connection,
            sample_project,
            sample_session,
            "Test error",
            "Context",
            "test.py",
            embedding,
        )
        assert error_id is not None

    def test_get_errors_for_session(self, test_connection, sample_error, sample_session):
        """Test getting errors for a session."""
        from src import db

        errors = db.get_errors_for_session(test_connection, sample_session)
        assert len(errors) >= 1
        assert any(e["id"] == sample_error for e in errors)

    def test_get_all_error_embeddings(self, test_connection, sample_error):
        """Test getting all error embeddings."""
        from src import db

        errors = db.get_all_error_embeddings(test_connection)
        assert len(errors) >= 1
        assert any(e["id"] == sample_error for e in errors)


class TestSolutionOperations:
    def test_add_solution(self, test_connection, sample_error):
        """Test adding a solution."""
        from src import db

        solution_id = db.add_solution(test_connection, sample_error, "Test solution", "code")
        assert solution_id is not None

    def test_get_solutions_for_errors(self, test_connection, sample_solution, sample_error):
        """Test getting solutions for errors."""
        from src import db

        solutions = db.get_solutions_for_errors(test_connection, [sample_error])
        assert len(solutions) >= 1
        assert any(s["id"] == sample_solution for s in solutions)

    def test_add_solution_requires_existing_error(self, test_connection):
        from src import db

        with pytest.raises(ValueError):
            db.add_solution(test_connection, "missing-error", "nope", "")


class TestConceptOperations:
    def test_add_concept(self, test_connection, mock_embed):
        """Test adding a concept."""
        from src import db

        embedding = mock_embed("Test concept")
        concept_id = db.add_concept(test_connection, "Test", "Content", ["tag1"], embedding)
        assert concept_id is not None

    def test_get_concept_by_id(self, test_connection, sample_concept):
        """Test getting a concept."""
        from src import db

        concept = db.get_concept_by_id(test_connection, sample_concept)
        assert concept is not None
        assert concept["title"] == "Test concept"
        assert "test" in concept["tags"]

    def test_update_concept(self, test_connection, sample_concept, mock_embed):
        """Test updating a concept."""
        from src import db

        new_embedding = mock_embed("Updated content")
        result = db.update_concept(
            test_connection, sample_concept, "Updated content", new_embedding
        )
        assert result["updated"] is True

        concept = db.get_concept_by_id(test_connection, sample_concept)
        assert concept["content"] == "Updated content"

    def test_delete_concept(self, test_connection, sample_concept):
        """Test deleting a concept."""
        from src import db

        result = db.delete_concept(test_connection, sample_concept)
        assert result["deleted"] is True

        concept = db.get_concept_by_id(test_connection, sample_concept)
        assert concept is None

    def test_delete_concept_not_found(self, test_connection):
        from src import db

        result = db.delete_concept(test_connection, "missing-concept")
        assert "error" in result

    def test_search_concepts_by_tag(self, test_connection, sample_concept):
        """Test searching concepts by tag."""
        from src import db

        concepts = db.search_concepts_by_tag(test_connection, "test")
        assert len(concepts) >= 1


class TestConceptSessionLinking:
    def test_link_concept_to_session(self, test_connection, sample_concept, sample_session):
        """Test linking a concept to a session."""
        from src import db

        result = db.link_concept_to_session(test_connection, sample_concept, sample_session)
        assert result["linked"] is True

    def test_link_concept_to_session_is_idempotent(
        self, test_connection, sample_concept, sample_session
    ):
        from src import db

        db.link_concept_to_session(test_connection, sample_concept, sample_session)
        db.link_concept_to_session(test_connection, sample_concept, sample_session)

        result = test_connection.execute(
            """MATCH (s:Session {id: $sid})-[r:REFERENCES]->(c:Concept {id: $cid})
               RETURN count(r)""",
            {"sid": sample_session, "cid": sample_concept},
        )
        count = result.get_next()[0] if result.has_next() else 0
        assert count == 1

    def test_get_concepts_for_session(self, test_connection, sample_concept, sample_session):
        """Test getting concepts for a session."""
        from src import db

        db.link_concept_to_session(test_connection, sample_concept, sample_session)
        concepts = db.get_concepts_for_session(test_connection, sample_session)
        assert len(concepts) >= 1

    def test_unlink_concept_from_session(self, test_connection, sample_concept, sample_session):
        """Test unlinking a concept from a session."""
        from src import db

        db.link_concept_to_session(test_connection, sample_concept, sample_session)
        result = db.unlink_concept_from_session(test_connection, sample_concept, sample_session)
        assert result["unlinked"] is True

        concepts = db.get_concepts_for_session(test_connection, sample_session)
        assert not any(c["id"] == sample_concept for c in concepts)


class TestDailyActivity:
    def test_daily_activity_created_on_session_close(
        self, test_connection, sample_session, sample_project
    ):
        """Test that daily activity is created when session is closed."""
        from src import db

        db.close_session(test_connection, sample_session)

        session = db.get_session_by_id(test_connection, sample_session)
        date = session["started_at"][:10]

        activity = db.get_daily_activity_by_date(test_connection, date, sample_project)
        assert activity is not None
        assert sample_session in activity["session_ids"]

    def test_get_daily_activities_for_project(
        self, test_connection, sample_session, sample_project
    ):
        """Test getting daily activities for a project."""
        from src import db

        db.close_session(test_connection, sample_session)

        activities = db.get_daily_activities_for_project(test_connection, sample_project)
        assert len(activities) >= 1

    def test_close_session_is_idempotent_for_error_counts(
        self, test_connection, sample_session, sample_project, mock_embed
    ):
        """Closing the same session repeatedly should not double-count errors in daily activity."""
        from src import db

        embedding = mock_embed("idempotent error")
        db.add_error(
            test_connection,
            sample_project,
            sample_session,
            "idempotent error",
            "context",
            "file.py",
            embedding,
        )

        db.close_session(test_connection, sample_session)
        db.link_session_to_daily_activity(test_connection, sample_session)
        db.close_session(test_connection, sample_session)
        db.link_session_to_daily_activity(test_connection, sample_session)

        session = db.get_session_by_id(test_connection, sample_session)
        date = session["started_at"][:10]
        activity = db.get_daily_activity_by_date(test_connection, date, sample_project)

        assert activity is not None
        assert activity["errors_count"] == 1


class TestProjectHistory:
    def test_get_project_history(
        self, test_connection, sample_project, sample_session, sample_error, sample_solution
    ):
        """Test getting project history."""
        from src import db

        history = db.get_project_history(test_connection, "test-project")
        assert "project" in history
        assert "sessions" in history
        assert "errors" in history
        assert "solutions" in history


class TestBatchOperations:
    def test_batch_add_concepts(self, test_connection, mock_embed):
        """Test batch adding concepts."""
        from src import db

        concepts_data = [
            {"title": "Concept 1", "content": "Content 1", "tags": ["tag1"]},
            {"title": "Concept 2", "content": "Content 2", "tags": ["tag2"]},
        ]

        result = db.batch_add_concepts(test_connection, concepts_data, mock_embed)
        assert result["count"] == 2
        assert len(result["concept_ids"]) == 2

    def test_batch_link_concepts(self, test_connection, sample_session, mock_embed):
        """Test batch linking concepts to session."""
        from src import db

        concept_ids = []
        for i in range(3):
            embedding = mock_embed(f"Concept {i}")
            cid = db.add_concept(test_connection, f"Concept {i}", f"Content {i}", [], embedding)
            concept_ids.append(cid)

        result = db.batch_link_concepts_to_session(test_connection, concept_ids, sample_session)
        assert result["count"] == 3


class TestStatistics:
    def test_get_project_statistics(
        self, test_connection, sample_project, sample_session, sample_error, sample_solution
    ):
        """Test getting project statistics."""
        from src import db

        stats = db.get_project_statistics(test_connection, sample_project)
        assert "session_count" in stats
        assert "error_count" in stats
        assert "solution_count" in stats
        assert "resolution_rate" in stats


class TestDeleteOperations:
    def test_delete_session_cascade(self, test_connection, sample_session, sample_error):
        """Test deleting a session cascades to errors."""
        from src import db

        result = db.delete_session_cascade(test_connection, sample_session)
        assert result["deleted"] is True
        assert result["deleted_errors"] >= 1

        session = db.get_session_by_id(test_connection, sample_session)
        assert session is None

    def test_delete_project_cascade(self, test_connection, sample_project, sample_session):
        """Test deleting a project cascades correctly."""
        from src import db

        result = db.delete_project_cascade(test_connection, sample_project)
        assert result["deleted"] is True

        project = db.get_project_by_id(test_connection, sample_project)
        assert project is None
