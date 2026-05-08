import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'

export interface GraphNode {
  id: string
  entity_type: string
  label: string
  properties: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  relationship_type: string
  properties: Record<string, unknown>
}

interface GraphViewerProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  activeNodeId?: string | null
  highlightedNodeLabels?: string[]
  height?: string
  realtimeStatus?: string | null
  onNodeClick?: (nodeId: string) => void
  onBackgroundClick?: () => void
}

const TYPE_COLORS = [
  '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6',
  '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#84cc16',
  '#06b6d4', '#a855f7', '#f43f5e', '#22c55e', '#eab308',
]

const DOTTED_BG: React.CSSProperties = {
  backgroundColor: '#0a0a14',
  backgroundImage: 'radial-gradient(rgba(148, 163, 184, 0.18) 1px, transparent 1px)',
  backgroundSize: '18px 18px',
}

function getTypeColor(type: string, allTypes: string[]): string {
  const idx = allTypes.indexOf(type)
  return TYPE_COLORS[idx % TYPE_COLORS.length]
}

export default function GraphViewer({
  nodes,
  edges,
  activeNodeId,
  highlightedNodeLabels = [],
  height = '500px',
  realtimeStatus = null,
  onNodeClick,
  onBackgroundClick,
}: GraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const onNodeClickRef = useRef(onNodeClick)
  const onBackgroundClickRef = useRef(onBackgroundClick)
  onNodeClickRef.current = onNodeClick
  onBackgroundClickRef.current = onBackgroundClick

  const [isMaximized, setIsMaximized] = useState(false)
  const [showEdgeLabels, setShowEdgeLabels] = useState(false)
  const [key, setKey] = useState(0)

  const allTypes = [...new Set(nodes.map((n) => n.entity_type))]

  useEffect(() => {
    if (!containerRef.current) return

    const cyNodes = nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.label,
        entity_type: n.entity_type,
        color: getTypeColor(n.entity_type, allTypes),
      },
    }))

    const cyEdges = edges.map((e) => ({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.relationship_type,
      },
    }))

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...cyNodes, ...cyEdges],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            label: 'data(label)',
            color: '#cbd5e1',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 6,
            'font-size': '10px',
            'font-weight': 500,
            width: 14,
            height: 14,
            'text-wrap': 'wrap',
            'text-max-width': '110px',
            'border-width': 0,
            'border-color': 'transparent',
            opacity: 0,
          },
        },
        {
          selector: 'node.active',
          style: {
            'border-color': '#a78bfa',
            'border-width': 3,
            width: 22,
            height: 22,
            color: '#ffffff',
            'font-weight': 700,
            'font-size': '11px',
          },
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#34d399',
            'border-width': 2,
            color: '#e5e7eb',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1,
            'line-color': 'rgba(148, 163, 184, 0.45)',
            'target-arrow-color': 'rgba(148, 163, 184, 0)',
            'target-arrow-shape': 'none',
            'curve-style': 'straight',
            label: showEdgeLabels ? 'data(label)' : '',
            'font-size': '9px',
            color: '#94a3b8',
            'text-background-opacity': 0,
            'text-rotation': 'autorotate',
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#a78bfa',
            'target-arrow-color': '#a78bfa',
            width: 2,
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 900,
        nodeRepulsion: () => 12000,
        idealEdgeLength: () => 140,
        gravity: 0.7,
      } as cytoscape.LayoutOptions,
    })

    cy.on('tap', 'node', (evt: cytoscape.EventObject) => {
      const id = evt.target.id() as string
      onNodeClickRef.current?.(id)
    })
    cy.on('tap', (evt: cytoscape.EventObject) => {
      if (evt.target === cy) onBackgroundClickRef.current?.()
    })

    cy.one('layoutstop', () => {
      cy.edges().style({ opacity: 0 })
      cy.nodes().forEach((node: cytoscape.NodeSingular, i: number) => {
        setTimeout(() => {
          node.animate({ style: { opacity: 1 } }, { duration: 350, easing: 'ease-in-out' as cytoscape.Css.TransitionTimingFunction })
        }, i * 40)
      })
      const nodeCount = cy.nodes().length
      setTimeout(() => {
        cy.edges().forEach((edge: cytoscape.EdgeSingular, i: number) => {
          setTimeout(() => {
            edge.animate({ style: { opacity: 1 } }, { duration: 250, easing: 'ease-in' as cytoscape.Css.TransitionTimingFunction })
          }, i * 20)
        })
      }, nodeCount * 40 + 100)
    })

    cyRef.current = cy
    return () => cy.destroy()
  }, [nodes, edges, key]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.style()
      .selector('edge')
      .style({ label: showEdgeLabels ? 'data(label)' : '' })
      .update()
  }, [showEdgeLabels])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().removeClass('active highlighted')
    cy.edges().removeClass('highlighted')

    if (activeNodeId) {
      const node = cy.getElementById(activeNodeId)
      node.addClass('active')
      node.connectedEdges().addClass('highlighted')
    }

    if (highlightedNodeLabels.length > 0) {
      cy.nodes().forEach((n: cytoscape.NodeSingular) => {
        if (highlightedNodeLabels.includes(n.data('label'))) {
          n.addClass('highlighted')
        }
      })
    }
  }, [activeNodeId, highlightedNodeLabels])

  const wrapperClass = isMaximized
    ? 'fixed inset-0 z-50 flex flex-col'
    : 'relative w-full rounded-xl overflow-hidden border border-gray-800/60'

  return (
    <div className={wrapperClass} style={isMaximized ? DOTTED_BG : { ...DOTTED_BG, height }}>
      {/* Toolbar */}
      <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
        <label
          className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-gray-900/80 backdrop-blur-sm text-xs text-gray-300 cursor-pointer select-none"
          title="Mostrar rótulos das arestas"
        >
          <span
            className={`relative inline-block w-7 h-3.5 rounded-full transition-colors ${
              showEdgeLabels ? 'bg-violet-500' : 'bg-gray-700'
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-2.5 h-2.5 rounded-full bg-white transition-transform ${
                showEdgeLabels ? 'translate-x-3.5' : ''
              }`}
            />
          </span>
          <input
            type="checkbox"
            className="sr-only"
            checked={showEdgeLabels}
            onChange={() => setShowEdgeLabels((v) => !v)}
          />
          Show Edge Labels
        </label>
        <button
          onClick={() => setKey((k) => k + 1)}
          title="Recarregar layout"
          className="px-2.5 py-1 rounded-full text-xs bg-gray-900/80 backdrop-blur-sm text-gray-300 hover:bg-gray-800 transition-colors flex items-center gap-1"
        >
          <span aria-hidden>↻</span> Refresh
        </button>
        <button
          onClick={() => setIsMaximized((v) => !v)}
          title={isMaximized ? 'Restaurar' : 'Tela cheia'}
          className="px-2 py-1 rounded-full text-xs bg-gray-900/80 backdrop-blur-sm text-gray-300 hover:bg-gray-800 transition-colors"
        >
          {isMaximized ? '⊡' : '⤢'}
        </button>
      </div>

      {isMaximized && (
        <div className="px-4 py-2 bg-gray-900/90 border-b border-gray-800 flex items-center gap-4 shrink-0">
          <span className="text-white font-semibold text-sm">Visualizador de Grafo</span>
          <span className="text-gray-400 text-xs">{nodes.length} nós · {edges.length} arestas</span>
        </div>
      )}

      <div ref={containerRef} className="w-full flex-1" style={isMaximized ? {} : { height: '100%' }} />

      {/* Realtime status pill */}
      {realtimeStatus && (
        <div className="absolute left-1/2 -translate-x-1/2 bottom-6 z-10 pointer-events-none">
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-gray-950/85 backdrop-blur-md border border-emerald-500/40 shadow-lg">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-70" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
            </span>
            <span className="text-xs text-gray-200 font-medium">{realtimeStatus}</span>
          </div>
        </div>
      )}

      {/* Legend */}
      {allTypes.length > 0 && (
        <div className="absolute bottom-3 left-3 bg-gray-950/85 backdrop-blur-sm border border-gray-800/60 rounded-lg p-2.5 max-w-xs">
          <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1.5">Entity Types</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {allTypes.map((t, i) => (
              <div key={t} className="flex items-center gap-1.5 text-xs text-gray-300">
                <span
                  className="inline-block w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: TYPE_COLORS[i % TYPE_COLORS.length] }}
                />
                {t}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
