# OpenCode Knowledge Graph MCP Server

A local Graph RAG knowledge base MCP server for OpenCode that provides persistent, structured memory across all sessions and projects.

## Purpose

Every OpenCode session starts cold with no memory. This system gives the agent persistent, structured, relational memory:

- Errors it hit and how it solved them
- What it knows about each project
- Files it touched in each session
- Concepts it learned along the way
- Daily activity tracking

## Features

- **Graph-based memory**: Uses Kuzu embedded graph database for structured knowledge storage
- **Semantic search**: Embeds content using `all-MiniLM-L6-v2` for intelligent retrieval
- **Hybrid ranking**: Combines semantic similarity with recency, context, and keyword overlap
- **Relationship traversal**: Finds related sessions, errors, solutions from concept queries
- **Daily activity tracking**: Automatically aggregates sessions into daily summaries
- **Thread-safe**: New connection per call for safe async operation
- **Fully local**: No external services required - everything runs on your machine
- **Search observability**: Returns lightweight timing and result-count metrics per query

## Installation

```bash
# Clone or download this repository
cd knowledge-graph

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Usage

### Running the MCP Server

```bash
# Test with FastMCP dev mode
fastmcp dev src/main.py

# Or run directly
python -m src.main

# Or use installed console script
opencode-kg
```

### Integration with OpenCode

Add to your OpenCode configuration:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "python",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/knowledge-graph"
    }
  }
}
```

## MCP Tools

### Project Management

| Tool | Description |
|------|-------------|
| `add_project` | Create a new project node |
| `update_project` | Update project metadata or merge projects |
| `list_projects` | List all known projects |

### Session Tracking

| Tool | Description |
|------|-------------|
| `add_session` | Create a session linked to a project |
| `close_session` | Close session and create daily activity |
| `get_recent_sessions` | Get recent sessions across projects |

### Error & Solution Logging

| Tool | Description |
|------|-------------|
| `log_error` | Log an error with semantic embedding |
| `log_solution` | Log a solution for an error |
| `get_error_solutions` | Semantic search for similar errors |

### Knowledge Management

| Tool | Description |
|------|-------------|
| `add_concept` | Add a concept with embedding |
| `link_concept_to_session` | Link concept to session |
| `update_concept` | Update and re-embed concept |
| `delete_concept` | Remove a concept |
| `search` | Semantic search over knowledge graph |

`search` now uses a hybrid rank score:
- 60% semantic similarity
- 20% recency
- 10% context richness (related errors/solutions)
- 10% keyword overlap

`search` responses also include a `metrics` object with timing and result counts.

### Project History

| Tool | Description |
|------|-------------|
| `get_project_history` | Get all sessions/errors/solutions for project |

### Cleanup

| Tool | Description |
|------|-------------|
| `delete_old_sessions` | Smart cleanup preserving concepts |

## Graph Schema

### Node Types

```
Project(id, name, path, description, created_at)
Session(id, project_id, summary, files_touched, started_at, ended_at)
Error(id, project_id, session_id, message, context, file, timestamp, message_embedding)
Solution(id, error_id, description, code_snippet, timestamp)
Concept(id, title, content, tags, embedding)
DailyActivity(id, date, project_id, summary, session_ids, errors_count)
```

### Relationships

```
Session -[:HAS_PROJECT]-> Project
Error -[:OCCURRED_IN]-> Session
Solution -[:SOLVES]-> Error
Session -[:REFERENCES]-> Concept
Session -[:CONTRIBUTES_TO]-> DailyActivity
DailyActivity -[:BELONGS_TO]-> Project
```

## Data Storage

All data is stored locally at:
```
~/.local/share/opencode-kg/graph.db
```

## Example Usage

```python
# Add a project
add_project(name="my-app", path="/home/user/projects/my-app")

# Start a session
result = add_session(
    project_name="my-app",
    summary="Fixed authentication bug",
    files_touched=["auth/login.py", "auth/utils.py"]
)
session_id = result["session_id"]

# Log an error
error_result = log_error(
    session_id=session_id,
    message="JWT token validation failed",
    context="Token expired during user login",
    file="auth/login.py"
)

# Log a solution
log_solution(
    error_id=error_result["error_id"],
    description="Added token refresh logic",
    code_snippet="refresh_token_if_expired(user_token)"
)

# Add a learned concept
concept_result = add_concept(
    title="JWT Token Refresh",
    content="Always refresh tokens before expiry to prevent auth failures",
    tags=["authentication", "jwt", "security"]
)

# Link concept to session
link_concept_to_session(concept_result["concept_id"], session_id)

# Close session
close_session(session_id)

# Search later
search("how to handle JWT token expiry")
```

## Development

```bash
# Run tests
pytest tests/

# Run synthetic performance benchmarks
pytest tests/ -m performance

# Format code
black src/

# Lint
ruff check src/
```

## Changelog

See `CHANGELOG.md` for a versioned history of changes.

## License

MIT
