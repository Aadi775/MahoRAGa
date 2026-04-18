import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import gsap from 'gsap'
import './App.css'

// Types - matching backend response (entity_type, not type)
interface GraphNode {
  id: string
  entity_id: string
  entity_type: string
  label: string
  x?: number
  y?: number
  vx?: number
  vy?: number
  metadata?: Record<string, unknown>
}

interface GraphLink {
  source: string
  target: string
  type: string
}

interface Filters {
  project_id: string
  max_nodes: number
  max_links: number
}

// Normalized response shape (UI works with this internally)
interface GraphSummary {
  nodes: GraphNode[]
  links: GraphLink[]
  projects: { id: string; name: string }[]
  counts?: {
    nodes: number
    links: number
  }
}

interface RawGraphSummaryResponse {
  nodes?: RawNode[]
  links?: GraphLink[]
  counts?: {
    nodes?: number
    links?: number
  }
}

// API
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8090'

async function fetchGraphSummary(filters: Filters): Promise<RawGraphSummaryResponse> {
  const params = new URLSearchParams()
  if (filters.project_id) params.append('project_id', filters.project_id)
  if (filters.max_nodes) params.append('max_nodes', String(filters.max_nodes))
  if (filters.max_links) params.append('max_links', String(filters.max_links))

  await fetch(`${API_BASE}/v1/graph/refresh-snapshot`).catch(() => null)
  const res = await fetch(`${API_BASE}/v1/graph/summary?${params}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return (await res.json()) as RawGraphSummaryResponse
}

// Node colors - matching backend entity_type values
const nodeColors: Record<string, string> = {
  Session: '#a371f7',
  Concept: '#58a6ff',
  Error: '#f85149',
  Artifact: '#3fb950',
  Project: '#d29922',
  Solution: '#8b949e',
  DailyActivity: '#6e7681',
}

// Map backend entity_type to UI type (normalize to lowercase)
function normalizeNodeType(entityType: string): string {
  const mapping: Record<string, string> = {
    Session: 'session',
    Concept: 'concept',
    Error: 'error',
    Artifact: 'artifact',
    Project: 'project',
    Solution: 'solution',
    DailyActivity: 'dailyactivity',
  }
  return mapping[entityType] || entityType.toLowerCase()
}

// Normalize backend response to UI format
// Backend returns: { id, entity_id, entity_type, label }
// Backend does NOT return: projects list
// Also handles: labels-only fallback
interface RawNode {
  id: string
  entity_id?: string
  entity_type?: string
  type?: string
  label: string
  metadata?: Record<string, unknown>
}

interface DetailItem {
  label: string
  value: string
}

interface CameraState {
  x: number
  y: number
  scale: number
}

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))

function normalizeResponse(data: RawGraphSummaryResponse): GraphSummary {
  const rawNodes = data.nodes || []
  const rawLinks = data.links || []

  // Extract projects from nodes with entity_type === 'Project'
  const projectNodes = rawNodes.filter(
    (n) => (n.entity_type || n.type) === 'Project'
  )
  const projects = projectNodes.map((n) => ({
    id: n.entity_id || n.id.replace(/^Project:/, ''),
    name: n.label || n.entity_id || n.id,
  }))

  // Normalize node types (entity_type or type field)
  const nodes: GraphNode[] = rawNodes.map((n) => ({
    id: n.id,
    entity_id: n.entity_id || n.id,
    entity_type: n.entity_type || n.type || 'Unknown',
    label: n.label,
    metadata: n.metadata,
  }))

  return {
    nodes,
    links: rawLinks,
    projects,
    counts: {
      nodes: data.counts?.nodes ?? nodes.length,
      links: data.counts?.links ?? rawLinks.length,
    },
  }
}

function computeComponentCenters(
  nodes: GraphNode[],
  links: GraphLink[],
  width: number,
  height: number
): Map<string, { x: number; y: number }> {
  const parent = new Map<string, string>()

  const find = (id: string): string => {
    const p = parent.get(id)
    if (!p) {
      parent.set(id, id)
      return id
    }
    if (p === id) return id
    const root = find(p)
    parent.set(id, root)
    return root
  }

  const union = (a: string, b: string) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent.set(rb, ra)
  }

  nodes.forEach((node) => {
    parent.set(node.id, node.id)
  })

  links.forEach((link) => {
    if (parent.has(link.source) && parent.has(link.target)) {
      union(link.source, link.target)
    }
  })

  const groups = new Map<string, string[]>()
  nodes.forEach((node) => {
    const root = find(node.id)
    const arr = groups.get(root) || []
    arr.push(node.id)
    groups.set(root, arr)
  })

  const groupEntries = Array.from(groups.entries())
  const centers = new Map<string, { x: number; y: number }>()
  const count = Math.max(1, groupEntries.length)
  const radius = Math.min(width, height) * 0.28

  groupEntries.forEach(([_, ids], index) => {
    const angle = (index / count) * Math.PI * 2
    const cx = width / 2 + Math.cos(angle) * radius
    const cy = height / 2 + Math.sin(angle) * radius
    ids.forEach((id) => centers.set(id, { x: cx, y: cy }))
  })

  return centers
}

function getDetailItems(node: GraphNode): DetailItem[] {
  const meta = node.metadata || {}
  const entries: DetailItem[] = []

  const push = (label: string, key: string) => {
    const value = meta[key]
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) {
      entries.push({ label, value: value.join(', ') })
      return
    }
    entries.push({ label, value: String(value) })
  }

  if (node.entity_type === 'Concept') {
    push('Title', 'title')
    push('Tags', 'tags')
    push('Content', 'content')
  } else if (node.entity_type === 'Session') {
    push('Summary', 'summary')
    push('Files', 'files_touched')
    push('Started', 'started_at')
    push('Ended', 'ended_at')
  } else if (node.entity_type === 'Error') {
    push('Message', 'message')
    push('Context', 'context')
    push('File', 'file')
    push('Timestamp', 'timestamp')
  } else if (node.entity_type === 'Solution') {
    push('Description', 'description')
    push('Code Snippet', 'code_snippet')
    push('Timestamp', 'timestamp')
  } else if (node.entity_type === 'Artifact') {
    push('Type', 'type')
    push('Description', 'description')
    push('Tags', 'tags')
    push('Content', 'content')
    push('File Path', 'file_path')
  } else if (node.entity_type === 'Project') {
    push('Path', 'path')
    push('Description', 'description')
    push('Created', 'created_at')
  } else if (node.entity_type === 'DailyActivity') {
    push('Date', 'date')
    push('Summary', 'summary')
    push('Session IDs', 'session_ids')
    push('Errors', 'errors_count')
    push('Resolved Errors', 'resolved_errors_count')
  }

  return entries
}

// App Component
export default function App() {
  const [graphData, setGraphData] = useState<GraphSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters>({
    project_id: '',
    max_nodes: 100,
    max_links: 200,
  })
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [introComplete, setIntroComplete] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)
  const [camera, setCamera] = useState<CameraState>({ x: 0, y: 0, scale: 1 })

  // Track reduced motion preference
  const prefersReducedMotion = useRef(false)

  const canvasRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const nodesRef = useRef<GraphNode[]>([])
  const animationRef = useRef<number>()
  const cameraRef = useRef<CameraState>({ x: 0, y: 0, scale: 1 })
  const panningRef = useRef(false)
  const panStartRef = useRef({ x: 0, y: 0 })
  const cameraStartRef = useRef({ x: 0, y: 0 })
  const draggedNodeRef = useRef<string | null>(null)
  const draggedWorldRef = useRef({ x: 0, y: 0 })

  const closePanel = useCallback(() => {
    if (prefersReducedMotion.current) {
      if (panelRef.current) {
        gsap.set(panelRef.current, { x: 320, opacity: 0 })
      }
      setPanelOpen(false)
      setSelectedNode(null)
      return
    }

    if (panelRef.current) {
      gsap.to(panelRef.current, {
        x: 320,
        opacity: 0,
        duration: 0.25,
        ease: 'power2.in',
        onComplete: () => {
          setPanelOpen(false)
          setSelectedNode(null)
        },
      })
      return
    }

    setPanelOpen(false)
    setSelectedNode(null)
  }, [])

  const toWorldPoint = useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current
    const cam = cameraRef.current
    if (!canvas) {
      return { x: clientX, y: clientY }
    }
    const rect = canvas.getBoundingClientRect()
    return {
      x: (clientX - rect.left - cam.x) / cam.scale,
      y: (clientY - rect.top - cam.y) / cam.scale,
    }
  }, [])

  // Detect reduced motion preference
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    prefersReducedMotion.current = mediaQuery.matches
    const handler = (e: MediaQueryListEvent) => {
      prefersReducedMotion.current = e.matches
    }
    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  useEffect(() => {
    cameraRef.current = camera
  }, [camera])

  const matchedNodeIds = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()
    if (!term || !graphData) return new Set<string>()

    const matches = new Set<string>()
    graphData.nodes.forEach((node) => {
      const haystacks = [
        node.label,
        node.entity_type,
        node.entity_id,
        JSON.stringify(node.metadata || {}),
      ]
      if (haystacks.some((value) => value.toLowerCase().includes(term))) {
        matches.add(node.id)
      }
    })

    return matches
  }, [graphData, searchTerm])

  // Force simulation
  const runSimulation = useCallback(() => {
    if (!graphData || !canvasRef.current) return

    const nodes = [...graphData.nodes]
    const links = graphData.links
    const width = canvasRef.current!.clientWidth
    const height = canvasRef.current!.clientHeight

    const centersByNode = computeComponentCenters(nodes, links, width, height)

    // Initialize positions near component centers
    nodes.forEach((node) => {
      const center = centersByNode.get(node.id) || { x: width / 2, y: height / 2 }
      if (node.x === undefined) {
        node.x = center.x + (Math.random() - 0.5) * 140
        node.y = center.y + (Math.random() - 0.5) * 140
      }
      node.vx = 0
      node.vy = 0
    })

    const simulate = () => {
      const draggedNodeId = draggedNodeRef.current
      const draggedTarget = draggedNodeId ? nodes.find((node) => node.id === draggedNodeId) : undefined
      if (draggedTarget) {
        draggedTarget.x = draggedWorldRef.current.x
        draggedTarget.y = draggedWorldRef.current.y
        draggedTarget.vx = 0
        draggedTarget.vy = 0
      }

      // Pairwise repulsion
      for (let i = 0; i < nodes.length; i += 1) {
        const a = nodes[i]
        if (a.x === undefined || a.y === undefined) continue
        for (let j = i + 1; j < nodes.length; j += 1) {
          const b = nodes[j]
          if (b.x === undefined || b.y === undefined) continue
          const dx = a.x - b.x
          const dy = a.y - b.y
          const distSq = Math.max(dx * dx + dy * dy, 120)
          const dist = Math.sqrt(distSq)
          const force = Math.min(5.5, 1200 / distSq)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          a.vx! += fx
          a.vy! += fy
          b.vx! -= fx
          b.vy! -= fy
        }
      }

      // Pull each node to its component center (keeps disconnected groups separated)
      nodes.forEach((node) => {
        if (draggedNodeId && node.id === draggedNodeId) return
        if (node.x === undefined || node.y === undefined) return
        const target = centersByNode.get(node.id) || { x: width / 2, y: height / 2 }
        node.vx! += (target.x - node.x) * 0.0025
        node.vy! += (target.y - node.y) * 0.0025
      })

      const nodeById = new Map(nodes.map((node) => [node.id, node]))

      // Link attraction
      links.forEach((link) => {
        const source = nodeById.get(link.source)
        const target = nodeById.get(link.target)
        if (!source || !target || !source.x || !target.x || !source.y || !target.y) return

        const dx = target.x - source.x
        const dy = target.y - source.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const desiredDistance = 130
        const force = ((dist - desiredDistance) / dist) * 0.04

        source.vx! += dx * force
        source.vy! += dy * force
        target.vx! -= dx * force
        target.vy! -= dy * force
      })

      // Apply velocities with damping
      nodes.forEach((node) => {
        if (node.vx === undefined || node.vy === undefined || node.x === undefined || node.y === undefined) return
        if (draggedNodeId && node.id === draggedNodeId) return
        node.vx *= 0.88
        node.vy *= 0.88
        node.x += node.vx
        node.y += node.vy

        // Bounds with soft bounce
        if (node.x < 28) {
          node.x = 28
          node.vx *= -0.35
        } else if (node.x > width - 28) {
          node.x = width - 28
          node.vx *= -0.35
        }
        if (node.y < 28) {
          node.y = 28
          node.vy *= -0.35
        } else if (node.y > height - 28) {
          node.y = height - 28
          node.vy *= -0.35
        }
      })

      nodesRef.current = nodes

      if (canvasRef.current) {
        const nodeElements = canvasRef.current.querySelectorAll('.graph-node')
        nodes.forEach((node, i) => {
          const el = nodeElements[i] as HTMLElement
          if (el && node.x !== undefined && node.y !== undefined) {
            el.style.transform = `translate(${node.x}px, ${node.y}px)`
          }
        })

        // Update links
          const linkElements = canvasRef.current.querySelectorAll('.graph-link')
          links.forEach((link, i) => {
            const source = nodeById.get(link.source)
            const target = nodeById.get(link.target)
            if (!source || !target || !source.x || !target.x || !source.y || !target.y) return

          const el = linkElements[i] as SVGLineElement
          if (el) {
            el.setAttribute('x1', String(source.x))
            el.setAttribute('y1', String(source.y))
            el.setAttribute('x2', String(target.x))
            el.setAttribute('y2', String(target.y))
          }
        })
      }

      animationRef.current = requestAnimationFrame(simulate)
    }

    simulate()
  }, [graphData])

  // Load data
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rawData = await fetchGraphSummary(filters)
      // Normalize backend response to UI format
      // Handles: entity_type field, no projects list, labels-only fallbacks
      const normalized = normalizeResponse(rawData)
      setGraphData(normalized)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph')
    } finally {
      setLoading(false)
    }
  }, [filters])

  // Initial load
  useEffect(() => {
    loadData()
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // Run simulation when data changes
  useEffect(() => {
    if (graphData?.nodes?.length) {
      runSimulation()
      setTimeout(() => setIntroComplete(true), prefersReducedMotion.current ? 0 : 1200)
    }
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [graphData, runSimulation])

  // Handle filter changes
  const handleFilterChange = (key: keyof Filters, value: string | number) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const applyFilters = () => {
    loadData()
  }

  const onCanvasMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest('.graph-node')) {
      return
    }
    panningRef.current = true
    panStartRef.current = { x: event.clientX, y: event.clientY }
    cameraStartRef.current = { x: cameraRef.current.x, y: cameraRef.current.y }
  }

  const onCanvasWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const cursorX = event.clientX - rect.left
    const cursorY = event.clientY - rect.top
    const current = cameraRef.current
    const nextScale = clamp(current.scale * (event.deltaY < 0 ? 1.08 : 0.92), 0.45, 2.8)
    const worldX = (cursorX - current.x) / current.scale
    const worldY = (cursorY - current.y) / current.scale

    setCamera({
      x: cursorX - worldX * nextScale,
      y: cursorY - worldY * nextScale,
      scale: nextScale,
    })
  }

  const onNodeMouseDown = (event: React.MouseEvent<HTMLDivElement>, nodeId: string) => {
    event.stopPropagation()
    draggedNodeRef.current = nodeId
    draggedWorldRef.current = toWorldPoint(event.clientX, event.clientY)
  }

  useEffect(() => {
    const onPointerMove = (event: MouseEvent) => {
      if (panningRef.current) {
        const dx = event.clientX - panStartRef.current.x
        const dy = event.clientY - panStartRef.current.y
        setCamera((prev) => ({ ...prev, x: cameraStartRef.current.x + dx, y: cameraStartRef.current.y + dy }))
      }

      if (draggedNodeRef.current) {
        draggedWorldRef.current = toWorldPoint(event.clientX, event.clientY)
      }
    }

    const onPointerUp = () => {
      panningRef.current = false
      draggedNodeRef.current = null
    }

    window.addEventListener('mousemove', onPointerMove)
    window.addEventListener('mouseup', onPointerUp)
    return () => {
      window.removeEventListener('mousemove', onPointerMove)
      window.removeEventListener('mouseup', onPointerUp)
    }
  }, [toWorldPoint])

  // Node click handler
  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node)
    setPanelOpen(true)
  }

  // Panel animations - respect reduced motion
  useEffect(() => {
    if (panelOpen && panelRef.current) {
      if (prefersReducedMotion.current) {
        // Instant state for reduced motion - no animation
        gsap.set(panelRef.current, { x: 0, opacity: 1 })
      } else {
        gsap.fromTo(
          panelRef.current,
          { x: 320, opacity: 0 },
          { x: 0, opacity: 1, duration: 0.35, ease: 'power2.out' }
        )
      }
    }
  }, [panelOpen])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && panelOpen) {
        closePanel()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [panelOpen, closePanel])

  // Intro animation - respect reduced motion
  useEffect(() => {
    if (introComplete && canvasRef.current) {
      if (prefersReducedMotion.current) {
        // Instant visible for reduced motion - no animation
        gsap.set('.graph-node', { scale: 1, opacity: 1 })
        gsap.set('.graph-link', { opacity: 0.4 })
      } else {
        gsap.fromTo(
          '.graph-node',
          { scale: 0, opacity: 0 },
          {
            scale: 1,
            opacity: 1,
            duration: 0.5,
            stagger: 0.03,
            ease: 'back.out(1.5)',
          }
        )
        gsap.fromTo(
          '.graph-link',
          { opacity: 0 },
          { opacity: 0.4, duration: 0.4, stagger: 0.02, delay: 0.2 }
        )
      }
    }
  }, [introComplete])

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <h1 className="title">Knowledge Graph</h1>
          <span className="subtitle">Viewer</span>
        </div>

        <div className="filters">
          <div className="filter-group search-group">
            <label>Search</label>
            <input
              type="text"
              value={searchTerm}
              placeholder="Label, concept text, tags..."
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>Project</label>
            <select
              value={filters.project_id}
              onChange={(e) => handleFilterChange('project_id', e.target.value)}
            >
              <option value="">All Projects</option>
              {graphData?.projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>Max Nodes</label>
            <input
              type="number"
              min="10"
              max="500"
              value={filters.max_nodes}
              onChange={(e) => handleFilterChange('max_nodes', parseInt(e.target.value) || 100)}
            />
          </div>

          <div className="filter-group">
            <label>Max Links</label>
            <input
              type="number"
              min="10"
              max="1000"
              value={filters.max_links}
              onChange={(e) => handleFilterChange('max_links', parseInt(e.target.value) || 200)}
            />
          </div>

          <button className="apply-btn" onClick={applyFilters} disabled={loading}>
            {loading ? (
              <span className="loading-spin">⟳</span>
            ) : (
              'Apply'
            )}
          </button>
        </div>
      </header>

      {/* Main canvas */}
      <main className="main">
        {error && (
          <div className="error-banner">
            <span className="error-icon">⚠</span>
            {error}
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        {!error && !graphData && !loading && (
          <div className="empty-state">
            <p>No data loaded. Adjust filters and click Apply.</p>
          </div>
        )}

        <div className="canvas" ref={canvasRef} onMouseDown={onCanvasMouseDown} onWheel={onCanvasWheel}>
          <div
            ref={stageRef}
            className="graph-stage"
            style={{ transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})` }}
          >
            {graphData?.links?.length && (
              <svg className="links-layer">
                {graphData.links.map((link, i) => {
                  const source = graphData.nodes.find((n) => n.id === link.source)
                  const target = graphData.nodes.find((n) => n.id === link.target)
                  return (
                    <line
                      key={i}
                      className="graph-link"
                      x1={source?.x || 0}
                      y1={source?.y || 0}
                      x2={target?.x || 0}
                      y2={target?.y || 0}
                      stroke="var(--text-secondary)"
                      strokeWidth={1.5}
                      strokeOpacity={0.3}
                    />
                  )
                })}
              </svg>
            )}

            {graphData?.nodes?.map((node) => {
              const nodeType = normalizeNodeType(node.entity_type)
              const hasSearch = searchTerm.trim().length > 0
              const isMatch = !hasSearch || matchedNodeIds.has(node.id)

              return (
                <div
                  key={node.id}
                  className={`graph-node node-${nodeType} ${
                    selectedNode?.id === node.id ? 'selected' : ''
                  } ${hasSearch ? (isMatch ? 'search-match' : 'search-dim') : ''}`}
                  style={{
                    '--node-color': nodeColors[node.entity_type] || '#58a6ff',
                  } as React.CSSProperties}
                  onMouseDown={(event) => onNodeMouseDown(event, node.id)}
                  onClick={() => handleNodeClick(node)}
                >
                  <div className="node-dot" />
                  <span className="node-label">{node.label}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Details panel */}
        {panelOpen && selectedNode && (
          <aside className="details-panel" ref={panelRef}>
            <div className="panel-header">
              <span className="panel-type" style={{ color: nodeColors[selectedNode.entity_type] }}>
                {normalizeNodeType(selectedNode.entity_type)}
              </span>
              <button className="close-btn" onClick={closePanel}>
                ✕
              </button>
            </div>

            <h2 className="panel-title">{selectedNode.label}</h2>

            <div className="panel-id">
              <span className="label">Entity ID</span>
              <code>{selectedNode.entity_id}</code>
            </div>

            <div className="panel-metadata">
              <span className="label">Details</span>
              {getDetailItems(selectedNode).length > 0 ? (
                <div className="details-grid">
                  {getDetailItems(selectedNode).map((item) => (
                    <div key={`${item.label}-${item.value.slice(0, 12)}`} className="detail-row">
                      <div className="detail-key">{item.label}</div>
                      <div className="detail-value">{item.value}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="detail-empty">No additional details available.</div>
              )}

              {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
                <details className="raw-json-block">
                  <summary>Raw metadata JSON</summary>
                  <pre>{JSON.stringify(selectedNode.metadata, null, 2)}</pre>
                </details>
              )}
            </div>
          </aside>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        <div className="stats">
          {graphData && (
            <>
              <span className="stat">
                <span className="stat-value">{graphData.counts?.nodes || graphData.nodes?.length || 0}</span>
                <span className="stat-label">nodes</span>
              </span>
              <span className="stat-divider">•</span>
              <span className="stat">
                <span className="stat-value">{graphData.counts?.links || graphData.links?.length || 0}</span>
                <span className="stat-label">links</span>
              </span>
            </>
          )}
        </div>
      </footer>
    </div>
  )
}
