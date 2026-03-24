<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/MCP-Compatible-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/database-Kuzu%20Graph-00b4d8?style=for-the-badge" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" />
</p>

<h1 align="center">🧠 MahoRAGa</h1>

<p align="center">
  <b>Persistent, graph-powered memory for AI agents.</b><br>
  <sub>A production-ready MCP server that gives Claude, Cursor, and any agentic framework long-term semantic recall.</sub>
</p>

---

## Why MahoRAGa?

Every AI agent session starts **cold** — no memory of past errors, solutions, or project context. MahoRAGa fixes that by providing a **local graph database** that agents can read and write to across sessions, creating a living knowledge base that grows smarter over time.

- 🔁 **Never solve the same bug twice.** Errors and solutions are persisted and semantically searchable.
- 🧩 **Cross-project knowledge.** Concepts learned in one project are instantly available in others.
- 📊 **Activity intelligence.** Daily summaries, session histories, and project timelines — all queryable.
- 🔒 **100% local.** Your data never leaves your machine. No API keys, no cloud dependencies.

---

## Features

| Category            | Highlights                                                                                    |
| ------------------- | --------------------------------------------------------------------------------------------- |
| **Graph Engine**    | Kuzu embedded graph DB with strict referential integrity and cascade-safe deletes             |
| **Semantic Search** | `all-MiniLM-L6-v2` embeddings with hybrid ranking (similarity + recency + context + keywords) |
| **MCP Protocol**    | 25+ tools exposed via FastMCP over stdio — plug into Claude Code, Cursor, or any MCP client   |
| **Artifacts**       | Attach datasheets, configs, logs, and code snippets to sessions and errors                    |
| **Daily Activity**  | Automatic aggregation of sessions into daily summaries with garbage collection                |
| **Performance**     | Vectorized clustering, batched Cypher queries, pagination on all list endpoints               |
| **Reliability**     | Input validation, safe limit clamping, thread-safe connections, and comprehensive test suite  |

---

## Quick Start

### Linux / macOS

```bash
git clone https://github.com/Aadi775/MahoRAGa.git
cd MahoRAGa
chmod +x setup.sh && ./setup.sh
```

### Windows

```cmd
git clone https://github.com/Aadi775/MahoRAGa.git
cd MahoRAGa
setup.bat
```

Both scripts create a `.venv`, install all dependencies, and configure the MCP server entry automatically.

---

## Connect to Your Agent

You can run MahoRAGa in two different modes depending on whether you want one agent, or multiple agents/windows sharing the same brain.

### Mode 1: Single Client (stdio)

If you only use one AI coding agent (e.g., just Claude Desktop), you can let the client spawn MahoRAGa directly. Add this to your MCP config (`.mcp.json` or `~/.claude.json`):

```json
{
  "mcpServers": {
    "mahoraga": {
      "command": "/path/to/MahoRAGa/.venv/bin/mahoraga-kg"
    }
  }
}
```

### Mode 2: Multi-Client Shared Brain (SSE)

KùzuDB uses file-level locking, meaning if you try to open MahoRAGa in Cursor _and_ OpenCode at the same time using `stdio`, they will crash fighting over the lock. Instead, start MahoRAGa as a shared HTTP server in the background:

```bash
# Start the shared server manually in a terminal
mahoraga-kg --transport sse --port 8000
```

Then, configure all your MCP clients to connect to this shared endpoint instead of launching their own process:

```json
{
  "mcpServers": {
    "mahoraga-remote": {
      "type": "remote",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Any MCP-Compatible Client

MahoRAGa speaks **standard MCP**. Point your client to either the CLI executable or the SSE endpoint and you're set.

---

## MCP Tools Reference

### 🗂️ Projects

| Tool             | Description                           |
| ---------------- | ------------------------------------- |
| `add_project`    | Create a new project node             |
| `update_project` | Update metadata or merge two projects |
| `list_projects`  | Paginated list of all projects        |

### 📝 Sessions

| Tool                  | Description                                      |
| --------------------- | ------------------------------------------------ |
| `add_session`         | Start a session (auto-creates project if needed) |
| `close_session`       | Close and generate daily activity                |
| `get_recent_sessions` | Fetch recent sessions across projects            |
| `delete_session`      | Cascade-delete with DailyActivity sync           |

### 🐛 Errors & Solutions

| Tool                  | Description                                  |
| --------------------- | -------------------------------------------- |
| `log_error`           | Log an error with semantic embedding         |
| `log_solution`        | Attach a fix to a logged error               |
| `get_error_solutions` | Find similar past errors and their solutions |
| `cluster_errors`      | Group related errors by vector similarity    |

### 🧠 Knowledge

| Tool                      | Description                             |
| ------------------------- | --------------------------------------- |
| `add_concept`             | Add a semantic knowledge entry          |
| `update_concept`          | Update and re-embed a concept           |
| `link_concept_to_session` | Associate a concept with a session      |
| `batch_link_concepts`     | Bulk-link multiple concepts efficiently |
| `search`                  | Hybrid semantic + keyword search        |

### 📎 Artifacts

| Tool                       | Description                         |
| -------------------------- | ----------------------------------- |
| `add_artifact`             | Attach a file/document to the graph |
| `link_artifact_to_session` | Connect artifact to a session       |
| `link_artifact_to_error`   | Connect artifact to an error        |
| `get_project_artifacts`    | List artifacts for a project        |
| `search_artifacts_by_tag`  | Tag-based artifact search           |

### 📊 Analytics

| Tool                           | Description                          |
| ------------------------------ | ------------------------------------ |
| `get_project_history`          | Full session/error/solution timeline |
| `get_daily_summary`            | Aggregated stats for a specific date |
| `get_learning_progress`        | Error resolution trends over time    |
| `get_project_daily_activities` | Paginated daily activity feed        |

### 🔧 Admin

| Tool                    | Description                                              |
| ----------------------- | -------------------------------------------------------- |
| `delete_old_sessions`   | Prune sessions older than N days (with DailyActivity GC) |
| `delete_project`        | Full cascade delete of a project                         |
| `get_unlinked_concepts` | Find orphaned concepts                                   |

---

## Search Algorithm

MahoRAGa uses a **hybrid ranking** algorithm that blends four signals:

| Weight  | Signal              | Description                                                    |
| ------- | ------------------- | -------------------------------------------------------------- |
| **55%** | Semantic Similarity | Cosine similarity between query and content embeddings         |
| **20%** | Recency             | Exponential decay favoring recent knowledge                    |
| **15%** | Context Richness    | Bonus for concepts with linked errors, solutions, and sessions |
| **10%** | Keyword Overlap     | Title-boosted keyword matching for precision                   |

---

## Graph Schema

```
Project ← HAS_PROJECT ← Session → CONTRIBUTES_TO → DailyActivity → BELONGS_TO → Project
                              ↑
                     OCCURRED_IN
                              |
                           Error ← SOLVES ← Solution
                              ↑
                        ATTACHED_TO
                              |
                          Artifact ← USES_ARTIFACT ← Session
                              ↑
                         ILLUSTRATES
                              |
                           Concept ← REFERENCES ← Session
```

**Nodes:** `Project` · `Session` · `Error` · `Solution` · `Concept` · `DailyActivity` · `Artifact`

---

## Data Storage

All data is stored locally in an embedded Kuzu database:

```
~/.config/mahoraga/graph.db
```

No external services, no network calls, no cloud sync. Fully offline-capable.

---

## Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the full test suite (87 tests)
pytest tests/ -v

# Run performance benchmarks
pytest tests/test_performance.py -v

# Run search tuning tests
pytest tests/test_search_tuning.py -v
```

---

## Documentation

A full interactive documentation site is included in the `docs/` directory, built with React, Vite, TailwindCSS, GSAP, and Framer Motion.

```bash
cd docs && npm install && npm run dev
```

Then open [http://localhost:5173](http://localhost:5173).

---

## Demos — How Agents Use MahoRAGa

### 🟢 Demo 1: Basic Agent Session

When an agent starts working on your project, it opens a session and logs everything it does:

```
Agent → add_session(project_name="my-api", summary="Fix auth middleware", files_touched=["src/auth.ts"])
       ↳ Returns: { session_id: "abc-123" }

Agent → log_error(session_id="abc-123", message="JWT expired during refresh", context="Token TTL was 0", file="src/auth.ts")
       ↳ Returns: { error_id: "err-456" }

Agent → log_solution(error_id="err-456", description="Set TTL to 3600s in config", code_snippet="config.jwt.ttl = 3600")
       ↳ Returns: { solution_id: "sol-789" }

Agent → add_concept(title="JWT Refresh Flow", content="Always check token expiry before API calls. Default TTL should be 1hr.", tags=["auth", "jwt"])
       ↳ Returns: { concept_id: "con-012" }

Agent → link_concept_to_session(concept_id="con-012", session_id="abc-123")
Agent → close_session(session_id="abc-123")
```

The graph now holds a permanent record: **what went wrong, how it was fixed, and what was learned**.

---

### 🔍 Demo 2: Agent Recalls Past Knowledge

A week later, the same (or different) agent hits a similar issue. Instead of starting from scratch:

```
Agent → search(query="JWT token expiry authentication")
       ↳ Returns:
         concepts: [{ title: "JWT Refresh Flow", similarity: 0.94, recency_score: 0.98 }]
         sessions: [{ summary: "Fix auth middleware", files: ["src/auth.ts"] }]
         errors:   [{ message: "JWT expired during refresh" }]
         solutions:[{ description: "Set TTL to 3600s in config", code: "config.jwt.ttl = 3600" }]

Agent → get_error_solutions(error_message="token has expired")
       ↳ Returns 3 similar past errors ranked by semantic similarity, each with their solution
```

The agent immediately knows the fix without re-debugging. **Zero wasted time.**

---

### 📎 Demo 3: Attaching Artifacts

Agents can persist files, logs, and configs as searchable artifacts:

```
Agent → add_artifact(
          artifact_type="config",
          title="Production JWT Config",
          content="{ jwt: { ttl: 3600, algorithm: 'RS256', issuer: 'api.example.com' } }",
          description="Auth service JWT configuration",
          tags=["production", "auth", "config"]
        )
       ↳ Returns: { artifact_id: "art-345" }

Agent → link_artifact_to_session(artifact_id="art-345", session_id="abc-123")
Agent → search_artifacts_by_tag(tag="auth")
       ↳ Returns: [{ title: "Production JWT Config", type: "config", ... }]
```

---

### 📊 Demo 4: Project Analytics

Agents (or you) can query high-level project intelligence:

```
Agent → get_project_history(project_name="my-api", limit=10)
       ↳ Returns: last 10 sessions with all errors and solutions

Agent → get_daily_summary(date="2026-03-24")
       ↳ Returns: { total_sessions: 5, total_errors: 12, projects: [...] }

Agent → get_learning_progress(project_name="my-api")
       ↳ Returns: { errors_logged: 47, errors_resolved: 41, resolution_rate: 0.87 }
```

---

### 🧹 Demo 5: Maintenance & Cleanup

Keep the graph lean over time:

```
Agent → delete_old_sessions(days=30)
       ↳ Deletes sessions older than 30 days
       ↳ Automatically garbage-collects orphaned DailyActivity nodes
       ↳ Preserves all Concepts (knowledge is never lost)

Agent → get_unlinked_concepts(limit=20)
       ↳ Find concepts not linked to any session (candidates for cleanup or review)
```

---

## License

MIT — use it however you want.
