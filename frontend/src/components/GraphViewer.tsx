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
  onNodeClick?: (nodeId: string) => void
  onBackgroundClick?: () => void
}

const TYPE_COLORS = [
  '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6',
  '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#84cc16',
  '#06b6d4', '#a855f7', '#f43f5e', '#22c55e', '#eab308',
]

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
            color: '#fff',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px',
            'font-weight': 'bold',
            width: 60,
            height: 60,
            'text-wrap': 'wrap',
            'text-max-width': '55px',
            'border-width': 2,
            'border-color': 'transparent',
            opacity: 0,
          },
        },
        {
          selector: 'node.active',
          style: {
            'border-color': '#fbbf24',
            'border-width': 4,
            width: 80,
            height: 80,
            'font-size': '13px',
          },
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#34d399',
            'border-width': 3,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': '#94a3b8',
            'target-arrow-color': '#94a3b8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: showEdgeLabels ? 'data(label)' : '',
            'font-size': '9px',
            color: '#64748b',
            'text-background-color': '#1e293b',
            'text-background-opacity': showEdgeLabels ? 0.7 : 0,
            'text-background-padding': '2px',
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#fbbf24',
            'target-arrow-color': '#fbbf24',
            width: 3,
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 900,
        nodeRepulsion: () => 10000,
        idealEdgeLength: () => 130,
        gravity: 0.8,
      } as cytoscape.LayoutOptions,
    })

    cy.on('tap', 'node', (evt: cytoscape.EventObject) => {
      const id = evt.target.id() as string
      onNodeClickRef.current?.(id)
    })
    cy.on('tap', (evt: cytoscape.EventObject) => {
      if (evt.target === cy) onBackgroundClickRef.current?.()
    })

    // Staggered fade-in after layout settles
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

  // Toggle edge labels live
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.style()
      .selector('edge')
      .style({
        label: showEdgeLabels ? 'data(label)' : '',
        'text-background-opacity': showEdgeLabels ? 0.7 : 0,
      })
      .update()
  }, [showEdgeLabels])

  // Update active/highlighted nodes without full re-render
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
    ? 'fixed inset-0 z-50 bg-gray-950 flex flex-col'
    : 'relative w-full bg-gray-950 rounded-xl overflow-hidden'

  return (
    <div className={wrapperClass} style={isMaximized ? {} : { height }}>
      {/* Toolbar */}
      <div className="absolute top-2 right-2 z-10 flex gap-1.5">
        <button
          onClick={() => setShowEdgeLabels((v) => !v)}
          title={showEdgeLabels ? 'Ocultar rótulos de aresta' : 'Mostrar rótulos de aresta'}
          className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
            showEdgeLabels
              ? 'bg-brand-600 text-white'
              : 'bg-gray-800/80 text-gray-300 hover:bg-gray-700'
          }`}
        >
          🏷 Rótulos
        </button>
        <button
          onClick={() => setKey((k) => k + 1)}
          title="Recarregar layout do grafo"
          className="px-2 py-1 rounded text-xs bg-gray-800/80 text-gray-300 hover:bg-gray-700 transition-colors"
        >
          ↻
        </button>
        <button
          onClick={() => setIsMaximized((v) => !v)}
          title={isMaximized ? 'Restaurar' : 'Tela cheia'}
          className="px-2 py-1 rounded text-xs bg-gray-800/80 text-gray-300 hover:bg-gray-700 transition-colors"
        >
          {isMaximized ? '⊡' : '⤢'}
        </button>
      </div>

      {isMaximized && (
        <div className="px-4 py-2 bg-gray-900 border-b border-gray-800 flex items-center gap-4 shrink-0">
          <span className="text-white font-semibold text-sm">Visualizador de Grafo</span>
          <span className="text-gray-400 text-xs">{nodes.length} nós · {edges.length} arestas</span>
        </div>
      )}

      <div ref={containerRef} className="w-full flex-1" style={isMaximized ? {} : { height: '100%' }} />

      {/* Legend */}
      {allTypes.length > 0 && (
        <div className="absolute bottom-3 left-3 bg-gray-900/90 rounded-lg p-2 flex flex-wrap gap-2 max-w-xs">
          {allTypes.map((t, i) => (
            <div key={t} className="flex items-center gap-1.5 text-xs text-gray-300">
              <span
                className="inline-block w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: TYPE_COLORS[i % TYPE_COLORS.length] }}
              />
              {t}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
