# MahoRAGa Architecture & Features

MahoRAGa is an agentic Knowledge Graph system designed to give AI agents (like Claude via MCP) a persistent, queryable, and highly structured memory. It uses Kùzu graph database, vector embeddings, and FastMCP to provide an unmatched semantic reasoning layer.

## What's in our Database?

The MahoRAGa database is built on a strict, ontology-driven schema that tracks the lifecycle of code, errors, and abstractions.

### Nodes (Entities)

- **Project**: The top-level logical container for a codebase or goal.
- **Session**: A discrete unit of work or investigation. Sessions track which files were touched and when the work occurred.
- **Error**: Exceptions, bugs, or problems encountered during a session.
- **Solution**: The fix or workaround applied to resolve an Error.
- **Concept**: Free-form semantic knowledge nodes, insights, or design patterns. Concepts are cross-project and represent the "learning" of the agent.
- **Artifact**: Physical resources like code snippets, configuration files, or logs.
- **DailyActivity**: Roll-up nodes that aggregate statistics (sessions run, errors hit, errors resolved) by date to track velocity and learning curves.

### Edges (Relationships)

The power of MahoRAGa comes from how these nodes connect:

- `(Session)-[:HAS_PROJECT]->(Project)`
- `(Error)-[:OCCURRED_IN]->(Session)`
- `(Solution)-[:SOLVES]->(Error)`
- `(Session)-[:REFERENCES]->(Concept)`
- `(DailyActivity)-[:BELONGS_TO]->(Project)`
- `(Artifact)-[:ILLUSTRATES]->(Concept)`
- `(Session)-[:USES_ARTIFACT]->(Artifact)`
- `(Artifact)-[:ATTACHED_TO]->(Error)`

---

## How it Works

1. **Agent Integration via MCP**: The system exposes over 20+ specialized tools to the agent natively via the Model Context Protocol (stdio transport). When an agent encounters an error, it calls `log_error`. When it figures out a fix, it calls `log_solution`.
2. **Real-time Semantic Embedding**: Every text-heavy node (Concept, Error, Artifact) is automatically embedded using `sentence-transformers` (`all-MiniLM-L6-v2`, 384 dimensions) before being inserted into Kùzu.
3. **Compound Queries**: Because relationships are tracked explicitly, questions like "What errors occurred in sessions that referenced the concept 'Authentication' but remain unsolved?" are O(1) graph traversals rather than massive JOINs.
4. **Lifecycle Management**: Cascade deletes are carefully implemented to prune orphaned nodes without leaving dangling DB references.

---

## What makes MahoRAGa Unique?

### 1. Hybrid Vector-Graph Search

Traditional RAG relies solely on vector similarity (nearest neighbor search). Traditional graph DBs rely solely on exact relationships.
MahoRAGa combines both. When an agent searches for "jwt refresh token", the system:

1. Performs a highly optimized, completely vectorized NumPy dot-product across all embeddings to find initial candidates.
2. Traverses the graph to expand candidates (e.g., finding the sessions that reference those concepts, and the errors that occurred in those sessions).
3. Applies a sophisticated multi-factor ranking algorithm:
   - **Similarity** (55%): How semantically close the node is.
   - **Recency** (20%): Time decay favoring newer sessions.
   - **Context** (15%): Graph centrality and density (does this node connect to the current active session or files?).
   - **Keyword** (10%): Exact lexical matches using custom stop-word filtering.

### 2. Auto-Deduplication of Memory

Agents often hit the same error repeatedly across different files or days. MahoRAGa intercepts `log_error` calls, computes the vector similarity against recent errors in the same session, and if it exceeds a 99.5% threshold, it silently deduplicates the error rather than bloating the graph.

### 3. "Daily Activity" Rollups

Unlike standard memory logs, MahoRAGa acts like a fitness tracker for coding. It maintains idempotent `DailyActivity` nodes using Kùzu's `MERGE` properties. It automatically recalibrates error and resolution counts precisely as sessions are added, updated, or deleted, giving agents the ability to analyze velocity over time via `get_project_stats` and `get_concept_growth_over_time`.

### 4. Cross-Pollination of Knowledge

Because `Concepts` and `Artifacts` sit outside the strict `Project` hierarchy, an agent solving a problem in one codebase (e.g., a tricky Postgres connection pool issue) creates a `Concept`. Months later, working in a completely different `Project`, the agent's contextual search will pull in that exact `Concept` and the `Solution` linked to it, creating true cross-project agentic memory.
