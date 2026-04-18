# MahoRaga Viewer API (Backend)

Small read-only API used by the MahoRaga browser viewer.

This service is intentionally separate from the MCP server. It reads graph data and returns visualization-friendly payloads (`nodes + links`) for the frontend.

## Endpoints

- `GET /health`
- `GET /v1/graph/refresh-snapshot`
- `GET /v1/graph/summary?project_id=&max_nodes=&max_links=`

`summary` returns:

- `generated_at`
- `filters`
- `counts`
- `nodes`
- `links`

## Why snapshot refresh exists

Kùzu uses file locking. Since your MCP server may hold the live DB lock, the viewer API reads from a refreshed local snapshot copy before serving data.

This keeps viewer reads stable without fighting the MCP process lock.

## Run locally

From repo root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r viewer_api/requirements.txt
uvicorn viewer_api.main:app --host 127.0.0.1 --port 8090 --reload
```

## Optional env

- `MAHORAGA_SOURCE_DB_PATH` → source DB to snapshot from

Default source path follows the same logic as core MahoRAGa DB path resolution.
