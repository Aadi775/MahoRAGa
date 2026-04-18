# MahoRAGa Viewer (Frontend)

This is the browser UI for exploring your MahoRAGa knowledge graph.

It is built as a separate app (not docs, not MCP) so you can inspect nodes visually, drag them around, zoom/pan, and search through what the memory graph contains.

## What it does

- Renders graph nodes and edges with a force layout
- Lets you zoom and pan around the canvas
- Lets you drag nodes to inspect clusters manually
- Includes search that highlights matches and dims non-matches
- Opens a detail panel on click (including concept content/tags when available)

## Requirements

- Node.js 18+
- Viewer backend API running at `http://127.0.0.1:8090`

## Run locally

From `viewer_ui/`:

```bash
npm install
npm run dev
```

Then open:

`http://127.0.0.1:5173`

## Build

```bash
npm run build
npm run preview
```

## Optional config

You can point the UI at another API URL:

```bash
VITE_API_BASE=http://127.0.0.1:8090 npm run dev
```

## Quick troubleshooting

If the graph is empty or stale:

1. Make sure backend is running.
2. Keep Project = **All Projects**.
3. Increase max nodes/links.
4. Refresh the page (UI triggers snapshot refresh automatically before fetch).
