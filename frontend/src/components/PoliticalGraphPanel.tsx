/**
 * PoliticalGraphPanel — visualização D3 do grafo político.
 *
 * Reimplementação independente, escrita do zero, baseada na ESPECIFICAÇÃO
 * funcional do PRD (não há código copiado de bibliotecas com licença
 * restritiva). Usa d3-force, d3-zoom e d3-drag.
 *
 * Recursos:
 *  - force simulation (link, charge, center, collide, x/y)
 *  - zoom/pan via d3-zoom
 *  - drag de nós com alphaTarget restart
 *  - arestas curvas: múltiplas relações entre o mesmo par recebem curvatura
 *    diferente para evitar sobreposição
 *  - self-loops: aresta do nó pra ele mesmo desenhada como arco
 *  - hover/selecione: realça o nó e suas arestas, esmaece o resto
 *  - clique abre drawer de detalhes (entidade ou relação)
 *  - toggle de labels de arestas
 *  - botão de refresh com spinner CSS
 *  - badge "atualizando em tempo real" com efeito breathing (placeholder
 *    para polling — ativado pelo prop `isLive`)
 *
 * Tipos de entidades coloridos pelo `colorForType` (paleta determinística).
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import * as d3 from 'd3'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export interface PoliticalGraphNodeIn {
  id: string
  entity_type: string
  label: string
  properties: Record<string, unknown>
}

export interface PoliticalGraphEdgeIn {
  id: string
  source: string
  target: string
  relationship_type: string
  properties: Record<string, unknown>
}

export interface PoliticalGraphPanelProps {
  nodes: PoliticalGraphNodeIn[]
  edges: PoliticalGraphEdgeIn[]
  height?: number
  isLive?: boolean
  onRefresh?: () => void
  refreshing?: boolean
}

// Versão "viva" usada pela simulação D3 (ela injeta x/y/vx/vy).
type SimNode = d3.SimulationNodeDatum & PoliticalGraphNodeIn

interface SimEdge extends d3.SimulationLinkDatum<SimNode> {
  id: string
  relationship_type: string
  properties: Record<string, unknown>
  // assigned at runtime: índice da curvatura entre o mesmo par (para múltiplas relações)
  curvatureIndex: number
  curvatureTotal: number
  isSelfLoop: boolean
}

// ---------------------------------------------------------------------------
// Paleta determinística por tipo de entidade
// ---------------------------------------------------------------------------

const TYPE_COLORS: Record<string, string> = {
  Candidato: '#a78bfa',
  Adversário: '#ec4899',
  Partido: '#f59e0b',
  'Federação/Coligação': '#10b981',
  Coligação: '#10b981',
  'Coordenador de Campanha': '#38bdf8',
  Eleitor: '#ef4444',
  'Segmento Eleitoral': '#fb7185',
  Território: '#fbbf24',
  Município: '#fbbf24',
  Bairro: '#facc15',
  'Zona Eleitoral': '#facc15',
  'Liderança Comunitária': '#22d3ee',
  'Influenciador Digital': '#84cc16',
  'Mídia Local': '#fb923c',
  'Mídia Nacional': '#f97316',
  'Pesquisa Eleitoral': '#a855f7',
  'Instituto de Pesquisa': '#c084fc',
  'Proposta/Pauta': '#06b6d4',
  Pauta: '#06b6d4',
  'Crise/Reputação': '#f43f5e',
  Aliança: '#34d399',
  'Evento de Campanha': '#fde047',
  'Rede Social': '#60a5fa',
  'Canal de Comunicação': '#93c5fd',
  'Grupo Religioso': '#e879f9',
  Sindicato: '#fb7185',
  'Associação Comercial': '#fde047',
  'Movimento Social': '#86efac',
  'Órgão Público': '#cbd5e1',
  'Justiça Eleitoral': '#94a3b8',
  'Fonte de Informação': '#7dd3fc',
}
const FALLBACK_COLOR = '#9ca3af'

function colorForType(type: string): string {
  return TYPE_COLORS[type] ?? FALLBACK_COLOR
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Calcula curvatura para arestas paralelas entre o mesmo par de nós.
 * Distribui as curvas em torno da reta direta para evitar sobreposição.
 */
function buildSimEdges(edges: PoliticalGraphEdgeIn[]): SimEdge[] {
  // Agrupa por par não-direcionado {min,max}
  const buckets = new Map<string, PoliticalGraphEdgeIn[]>()
  for (const e of edges) {
    const a = e.source < e.target ? e.source : e.target
    const b = e.source < e.target ? e.target : e.source
    const key = `${a}__${b}`
    const arr = buckets.get(key)
    if (arr) arr.push(e)
    else buckets.set(key, [e])
  }

  const out: SimEdge[] = []
  for (const [, group] of buckets) {
    const total = group.length
    group.forEach((e, idx) => {
      out.push({
        id: e.id,
        source: e.source,
        target: e.target,
        relationship_type: e.relationship_type,
        properties: e.properties,
        curvatureIndex: idx,
        curvatureTotal: total,
        isSelfLoop: e.source === e.target,
      })
    })
  }
  return out
}

/**
 * Caminho SVG para uma aresta. Self-loop = arco circular.
 * Aresta normal com 1 ocorrência = linha reta. Múltiplas ocorrências =
 * curvas Bezier quadráticas com offset perpendicular.
 */
function edgePath(e: SimEdge): string {
  const s = e.source as SimNode
  const t = e.target as SimNode
  const sx = s.x ?? 0
  const sy = s.y ?? 0
  const tx = t.x ?? 0
  const ty = t.y ?? 0

  if (e.isSelfLoop) {
    // arco circular saindo e voltando ao mesmo nó (acima)
    const r = 28
    return `M ${sx},${sy - 6} C ${sx - r * 1.6},${sy - r * 2}  ${sx + r * 1.6},${sy - r * 2}  ${sx},${sy - 6}`
  }

  if (e.curvatureTotal === 1) {
    return `M ${sx},${sy} L ${tx},${ty}`
  }

  // múltiplas relações: distribui curvaturas simétricas em torno da reta
  const dx = tx - sx
  const dy = ty - sy
  const dist = Math.sqrt(dx * dx + dy * dy) || 1
  // intensidade do desvio cresce linearmente com o índice
  const seq = e.curvatureIndex - (e.curvatureTotal - 1) / 2
  const offset = seq * 22 // px de afastamento da reta
  // ponto de controle ortogonal à direção da aresta
  const nx = -dy / dist
  const ny = dx / dist
  const mx = (sx + tx) / 2 + nx * offset
  const my = (sy + ty) / 2 + ny * offset
  return `M ${sx},${sy} Q ${mx},${my} ${tx},${ty}`
}

function edgeMidpoint(e: SimEdge): { x: number; y: number } {
  const s = e.source as SimNode
  const t = e.target as SimNode
  const sx = s.x ?? 0
  const sy = s.y ?? 0
  const tx = t.x ?? 0
  const ty = t.y ?? 0
  if (e.isSelfLoop) return { x: sx, y: sy - 52 }
  if (e.curvatureTotal === 1) return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
  const dx = tx - sx
  const dy = ty - sy
  const dist = Math.sqrt(dx * dx + dy * dy) || 1
  const seq = e.curvatureIndex - (e.curvatureTotal - 1) / 2
  const offset = seq * 22
  const nx = -dy / dist
  const ny = dx / dist
  return { x: (sx + tx) / 2 + nx * offset, y: (sy + ty) / 2 + ny * offset }
}

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

type Selected =
  | { kind: 'node'; node: PoliticalGraphNodeIn }
  | { kind: 'edge'; edge: PoliticalGraphEdgeIn; source: PoliticalGraphNodeIn; target: PoliticalGraphNodeIn }
  | null

export function PoliticalGraphPanel({
  nodes,
  edges,
  height = 600,
  isLive = false,
  onRefresh,
  refreshing = false,
}: PoliticalGraphPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [showLabels, setShowLabels] = useState(false)
  const [selected, setSelected] = useState<Selected>(null)
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 800, h: height })

  // Mantém referência viva às props pra usar dentro de handlers d3 sem stale closure
  const selectedRef = useRef<Selected>(null)
  selectedRef.current = selected

  // ResizeObserver para fit responsivo
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect
      if (r) setSize({ w: Math.max(320, Math.floor(r.width)), h: height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [height])

  const simEdges = useMemo(() => buildSimEdges(edges), [edges])

  const nodeById = useMemo(() => {
    const map = new Map<string, PoliticalGraphNodeIn>()
    for (const n of nodes) map.set(n.id, n)
    return map
  }, [nodes])

  // Conjunto de IDs vizinhos do nó selecionado, usado pra dim/highlight
  const neighborIds = useMemo(() => {
    if (!selected || selected.kind !== 'node') return null
    const out = new Set<string>([selected.node.id])
    for (const e of edges) {
      if (e.source === selected.node.id) out.add(e.target)
      if (e.target === selected.node.id) out.add(e.source)
    }
    return out
  }, [selected, edges])

  // ---------------------------------------------------------------------
  // Render D3 — efeito principal
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const w = size.w
    const h = size.h

    // Cópias mutáveis para a simulação (D3 atribui x/y in-place)
    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }))
    const idToSimNode = new Map(simNodes.map((n) => [n.id, n]))
    const links: SimEdge[] = simEdges.map((e) => ({
      ...e,
      source: idToSimNode.get(e.source as string) ?? (e.source as SimNode),
      target: idToSimNode.get(e.target as string) ?? (e.target as SimNode),
    }))

    // grupo raiz para zoom/pan
    const root = svg.append('g').attr('class', 'pg-root')

    // ----- defs: filtros e marcadores ------------------------------------
    const defs = svg.append('defs')

    // Glow padrão (gaussian blur + composite)
    const glow = defs.append('filter').attr('id', 'pg-glow').attr('x', '-60%').attr('y', '-60%').attr('width', '220%').attr('height', '220%')
    glow.append('feGaussianBlur').attr('stdDeviation', '3.2').attr('result', 'blur')
    const glowMerge = glow.append('feMerge')
    glowMerge.append('feMergeNode').attr('in', 'blur')
    glowMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    // Glow forte (usado no pulse do selecionado)
    const glowStrong = defs.append('filter').attr('id', 'pg-glow-strong').attr('x', '-100%').attr('y', '-100%').attr('width', '300%').attr('height', '300%')
    glowStrong.append('feGaussianBlur').attr('stdDeviation', '6').attr('result', 'blur')
    const glowStrongMerge = glowStrong.append('feMerge')
    glowStrongMerge.append('feMergeNode').attr('in', 'blur')
    glowStrongMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    // Marker de seta para arestas direcionadas
    defs
      .append('marker')
      .attr('id', 'pg-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 18)
      .attr('refY', 0)
      .attr('markerWidth', 7)
      .attr('markerHeight', 7)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'rgba(180, 192, 222, 0.7)')

    const linkGroup = root.append('g').attr('class', 'pg-edges')
    const haloGroup = root.append('g').attr('class', 'pg-halos')
    const linkLabelGroup = root.append('g').attr('class', 'pg-edge-labels')
    const nodeGroup = root.append('g').attr('class', 'pg-nodes')

    // Simulation — força centrípeta menor + repulsão moderada + colisão
    // generosa para evitar o look "aranha" com hub central radial.
    const simulation = d3
      .forceSimulation<SimNode>(simNodes)
      .alphaDecay(0.018) // mais lento = animação inicial dura ~3s
      .force(
        'link',
        d3
          .forceLink<SimNode, SimEdge>(links)
          .id((d) => d.id)
          .distance((e) => (e.isSelfLoop ? 60 : 130))
          .strength(0.85),
      )
      .force('charge', d3.forceManyBody<SimNode>().strength(-180).distanceMax(420))
      .force('center', d3.forceCenter(w / 2, h / 2).strength(0.6))
      .force('collide', d3.forceCollide<SimNode>().radius(40).strength(0.95))
      .force('x', d3.forceX<SimNode>(w / 2).strength(0.02))
      .force('y', d3.forceY<SimNode>(h / 2).strength(0.02))

    // Edges (paths)
    const edgePaths = linkGroup
      .selectAll<SVGPathElement, SimEdge>('path')
      .data(links, (d) => d.id)
      .join('path')
      .attr('class', 'pg-edge')
      .attr('marker-end', (d) => (d.isSelfLoop ? null : 'url(#pg-arrow)'))
      .attr('data-edge-id', (d) => d.id)
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation()
        const s = nodeById.get((d.source as SimNode).id)
        const t = nodeById.get((d.target as SimNode).id)
        if (s && t) {
          setSelected({
            kind: 'edge',
            edge: {
              id: d.id,
              source: s.id,
              target: t.id,
              relationship_type: d.relationship_type,
              properties: d.properties,
            },
            source: s,
            target: t,
          })
        }
      })

    // Edge labels
    const edgeLabelTexts = linkLabelGroup
      .selectAll<SVGTextElement, SimEdge>('text')
      .data(links, (d) => d.id)
      .join('text')
      .attr('class', 'pg-edge-label')
      .attr('text-anchor', 'middle')
      .style('display', showLabels ? 'block' : 'none')
      .text((d) => d.relationship_type)

    // Nodes
    const node = nodeGroup
      .selectAll<SVGGElement, SimNode>('g.pg-node')
      .data(simNodes, (d) => d.id)
      .join('g')
      .attr('class', 'pg-node')
      .attr('data-node-id', (d) => d.id)
      .style('cursor', 'pointer')
      // Cor da currentColor (usada por glow + halo) = cor do tipo da entidade
      .style('color', (d) => colorForType(d.entity_type))
      // Stagger de entrada: cada nó aparece com pequeno offset em cascata.
      // Variável CSS lida pelo @keyframes pgNodeEnter / pgNodeBreathe.
      .style('--enter-delay', (_, i) => `${Math.min(i * 28, 1100)}ms`)
      .on('click', (event, d) => {
        event.stopPropagation()
        const found = nodeById.get(d.id)
        if (found) setSelected({ kind: 'node', node: found })
      })

    node
      .append('circle')
      .attr('class', 'pg-node-body')
      .attr('r', 22)
      .attr('fill', (d) => colorForType(d.entity_type))
      .attr('stroke', 'rgba(7, 9, 26, 0.9)')
      .attr('stroke-width', 1.5)

    node
      .append('text')
      .attr('class', 'pg-node-label')
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .text((d) => truncateLabel(d.label, 12))

    // Drag
    node.call(
      d3
        .drag<SVGGElement, SimNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        }),
    )

    // Tick
    simulation.on('tick', () => {
      edgePaths.attr('d', (d) => edgePath(d))
      edgeLabelTexts
        .attr('x', (d) => edgeMidpoint(d).x)
        .attr('y', (d) => edgeMidpoint(d).y)
      node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
      // halos seguem o nó focado
      haloGroup
        .selectAll<SVGCircleElement, SimNode>('circle.pg-halo')
        .attr('cx', (d) => d.x ?? 0)
        .attr('cy', (d) => d.y ?? 0)
    })

    // Zoom/Pan
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        root.attr('transform', event.transform.toString())
      })
    svg.call(zoom)

    // Click no canvas = limpa seleção
    svg.on('click', () => setSelected(null))

    return () => {
      simulation.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, simEdges, size.w, size.h])

  // Atualiza visibilidade dos labels sem refazer a simulação
  useEffect(() => {
    if (!svgRef.current) return
    d3.select(svgRef.current)
      .selectAll<SVGTextElement, SimEdge>('text.pg-edge-label')
      .style('display', showLabels ? 'block' : 'none')
  }, [showLabels])

  // Aplica classes de highlight/dim + halo pulsante conforme seleção
  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    const sel = selectedRef.current

    svg.selectAll<SVGGElement, SimNode>('g.pg-node').classed('selected', false).classed('dimmed', false)
    svg.selectAll<SVGPathElement, SimEdge>('path.pg-edge').classed('highlighted', false).classed('dimmed', false)

    // limpa halos antigos
    const haloG = svg.select<SVGGElement>('g.pg-halos')
    haloG.selectAll('*').remove()

    if (!sel) return

    if (sel.kind === 'node') {
      const focused = sel.node.id
      const focusedNode = svg
        .selectAll<SVGGElement, SimNode>('g.pg-node')
        .filter((d) => d.id === focused)
        .datum()
      svg
        .selectAll<SVGGElement, SimNode>('g.pg-node')
        .classed('selected', (d) => d.id === focused)
        .classed('dimmed', (d) => !!neighborIds && !neighborIds.has(d.id))
      svg
        .selectAll<SVGPathElement, SimEdge>('path.pg-edge')
        .classed('highlighted', (d) => {
          const sId = (d.source as SimNode).id
          const tId = (d.target as SimNode).id
          return sId === focused || tId === focused
        })
        .classed('dimmed', (d) => {
          const sId = (d.source as SimNode).id
          const tId = (d.target as SimNode).id
          return sId !== focused && tId !== focused
        })

      // injeta 3 halos pulsantes (com delay diferente) atrás do nó focado
      if (focusedNode) {
        const color = colorForType(focusedNode.entity_type)
        for (const cls of ['', 'delay-1', 'delay-2']) {
          haloG
            .append('circle')
            .attr('class', `pg-halo ${cls}`.trim())
            .attr('r', 22)
            .attr('cx', focusedNode.x ?? 0)
            .attr('cy', focusedNode.y ?? 0)
            .style('color', color)
            .attr('stroke', color)
        }
      }
    } else if (sel.kind === 'edge') {
      const eId = sel.edge.id
      svg.selectAll<SVGPathElement, SimEdge>('path.pg-edge')
        .classed('highlighted', (d) => d.id === eId)
        .classed('dimmed', (d) => d.id !== eId)
    }
  }, [selected, neighborIds])

  // Legenda de tipos efetivamente presentes
  const legend = useMemo(() => {
    const types = new Map<string, number>()
    for (const n of nodes) types.set(n.entity_type, (types.get(n.entity_type) ?? 0) + 1)
    return Array.from(types.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([type, count]) => ({ type, count, color: colorForType(type) }))
  }, [nodes])

  return (
    <div className="relative">
      <div
        ref={containerRef}
        className="rounded-xl border border-slate-700 overflow-hidden relative pg-canvas"
        style={{ height }}
      >
        <svg ref={svgRef} width={size.w} height={size.h} className="block" />

        {/* Toolbar superior */}
        <div className="absolute top-3 right-3 flex items-center gap-2">
          <button
            onClick={() => setShowLabels((v) => !v)}
            className={`text-xs px-2 py-1 rounded border transition-colors ${
              showLabels
                ? 'bg-brand-600 border-brand-600 text-white'
                : 'bg-slate-800/80 border-slate-600 text-slate-200 hover:bg-slate-700'
            }`}
            title="Mostrar/ocultar rótulos das arestas"
          >
            🏷 Rótulos
          </button>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="text-xs px-2 py-1 rounded border border-slate-600 bg-slate-800/80 text-slate-200 hover:bg-slate-700 disabled:opacity-50 flex items-center gap-1"
              title="Recarregar grafo"
            >
              <span className={refreshing ? 'inline-block animate-spin-slow' : 'inline-block'}>↻</span>
              Atualizar
            </button>
          )}
        </div>

        {/* Hint "atualizando em tempo real" */}
        {isLive && (
          <div className="absolute top-3 left-3 flex items-center gap-2 text-xs text-emerald-200 bg-emerald-900/40 border border-emerald-700/60 rounded px-2 py-1">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-breathe" />
            atualizando memória política em tempo real
          </div>
        )}

        {/* Legenda inferior */}
        {legend.length > 0 && (
          <div className="absolute bottom-3 left-3 flex flex-wrap gap-1.5 max-w-[60%] bg-slate-900/70 backdrop-blur rounded-lg px-2 py-1.5 border border-slate-700">
            {legend.slice(0, 12).map((l) => (
              <span key={l.type} className="text-[10px] text-slate-200 flex items-center gap-1">
                <span
                  className="inline-block w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: l.color }}
                />
                {l.type} ({l.count})
              </span>
            ))}
            {legend.length > 12 && (
              <span className="text-[10px] text-slate-400">+{legend.length - 12} tipos</span>
            )}
          </div>
        )}

        {/* Métricas */}
        <div className="absolute bottom-3 right-3 text-[10px] text-slate-300 bg-slate-900/70 backdrop-blur rounded px-2 py-1 border border-slate-700">
          {nodes.length} nós · {edges.length} arestas
        </div>

        {/* Drawer de detalhes */}
        {selected && (
          <DetailDrawer
            selected={selected}
            onClose={() => setSelected(null)}
            colorOf={colorForType}
          />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------

function DetailDrawer({
  selected,
  onClose,
  colorOf,
}: {
  selected: NonNullable<Selected>
  onClose: () => void
  colorOf: (t: string) => string
}) {
  return (
    <div className="absolute top-0 right-0 h-full w-80 bg-slate-900/95 backdrop-blur border-l border-slate-700 shadow-xl animate-slide-in-right overflow-auto">
      <div className="flex items-start justify-between p-4 border-b border-slate-700">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-400">
            {selected.kind === 'node' ? 'Entidade' : 'Relação'}
          </p>
          <h3 className="text-sm font-semibold text-slate-100 mt-0.5">
            {selected.kind === 'node' ? selected.node.label : selected.edge.relationship_type}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 text-xl leading-none"
          aria-label="Fechar"
        >
          ×
        </button>
      </div>

      <div className="p-4 space-y-3 text-xs">
        {selected.kind === 'node' ? (
          <>
            <Row label="Tipo">
              <span
                className="inline-block px-2 py-0.5 rounded-full text-[10px]"
                style={{
                  backgroundColor: colorOf(selected.node.entity_type) + '33',
                  color: colorOf(selected.node.entity_type),
                  border: `1px solid ${colorOf(selected.node.entity_type)}80`,
                }}
              >
                {selected.node.entity_type}
              </span>
            </Row>
            <Row label="ID">
              <code className="text-slate-300 break-all">{selected.node.id}</code>
            </Row>
            <Row label="Propriedades">
              <PropDump obj={selected.node.properties} />
            </Row>
          </>
        ) : (
          <>
            <Row label="Origem">
              <span className="text-slate-200">{selected.source.label}</span>
              <span className="text-[10px] text-slate-400 ml-1">({selected.source.entity_type})</span>
            </Row>
            <Row label="Destino">
              <span className="text-slate-200">{selected.target.label}</span>
              <span className="text-[10px] text-slate-400 ml-1">({selected.target.entity_type})</span>
            </Row>
            <Row label="Tipo de relação">
              <code className="text-amber-300">{selected.edge.relationship_type}</code>
            </Row>
            <Row label="Propriedades">
              <PropDump obj={selected.edge.properties} />
            </Row>
          </>
        )}
      </div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">{label}</p>
      <div className="text-slate-200">{children}</div>
    </div>
  )
}

function PropDump({ obj }: { obj: Record<string, unknown> }) {
  const entries = Object.entries(obj || {})
  if (entries.length === 0) return <span className="text-slate-500 italic">vazio</span>
  return (
    <pre className="text-[10px] text-slate-300 bg-slate-950/60 border border-slate-700 rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap">
      {JSON.stringify(obj, null, 2)}
    </pre>
  )
}

function truncateLabel(s: string, max: number): string {
  if (s.length <= max) return s
  return s.slice(0, max - 1) + '…'
}

export default PoliticalGraphPanel
