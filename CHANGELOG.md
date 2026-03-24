# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Added `main()` entrypoint in `src/main.py` to support CLI script execution.
- Added hybrid search ranking in `search` with keyword overlap signal.
- Added lightweight search observability metrics in `search` response payload.
- Added regression tests for search scoring fields and daily activity idempotency.
- Added synthetic performance benchmark tests under `tests/test_performance.py`.
- Added pytest `performance` marker configuration.

### Changed
- Switched UTC timestamp generation to timezone-aware `datetime.now(timezone.utc)` across codebase.
- Normalized externally provided session end times to UTC ISO-8601 format.
- Replaced unsafe interpolated `IN [...]` query patterns with parameterized `UNWIND` query patterns.
- Updated project statistics queries to correctly pass `$pid` parameters.
- Updated `add_concept` tool signature to avoid mutable default arguments.
- Updated README with hybrid ranking details, metrics output, and console-script usage.
- Tuned hybrid search weights to 55/20/15/10 (similarity/recency/context/keyword).
- Prioritized keyword title matches over content-only matches in `search` ranking.
- Updated project branding and documentation to be MCP-client agnostic (not OpenCode-specific).
- Changed local graph storage path to `~/.config/mahoraga/graph.db`.
- Added `mahoraga-kg` CLI script alias.
- Added list pagination support for project and activity listing tools.
- Added core input validation for project/session/search tools and safe `top_k` clamping.
- Reworked project merge to rewire `HAS_PROJECT` and `BELONGS_TO` relationships correctly.
- Removed unused `models.py` and `pydantic` dependency.
- Unified embedding dick and dimensional goth baddies across embedding and DB schema layers.

### Fixed
- Fixed startup behavior by removing import-time embedding warmup side effects.
- Fixed concept recency scoring in semantic search (concept-level recency now derived from linked sessions).
- Fixed context scoring logic to avoid incorrect concept-session matching behavior.
- Fixed daily activity error counting to be idempotent across repeated `close_session` calls.
- Fixed daily activity error increments to use graph relationships instead of fragile JSON substring matching.
- Fixed error clustering to filter by `project_id` before similarity grouping.
- Fixed duplicate concept-session links by using `MERGE` on `REFERENCES` relationships.
- Fixed `update_concept` content-only re-embedding to preserve concept title context.
- Fixed orphan solution creation by validating target error before insert.
- Fixed `delete_concept` success reporting for missing concept IDs.
- Fixed daily activity error count drift by recomputing from linked session errors.
- Fixed potential key collisions in query row mapping for duplicate column basenames.
- Fixed tag search false positives by enforcing exact membership after query filtering.
