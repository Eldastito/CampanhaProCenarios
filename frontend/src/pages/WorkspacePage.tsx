import { Component, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams, Link } from 'react-router-dom'
import { graphApi, simulationsApi } from '../api/client'
import type { GraphData, GraphNode, GraphProjectSummary, SimulationStep, SimulationView } from '../api/client'
import Layout from '../components/Layout'
import GraphViewer from '../components/GraphViewer'
import ScreenRecorder from '../components/ScreenRecorder'
import { useAuth } from '../contexts/AuthContext'

type ViewMode = 'graph' | 'split' | 'workbench'

const VIEW_MODES: { id: ViewMode; icon: string; label: string; desc: string }[] = [
  { id: 'graph', icon: '🕸', label: 'Gráfico', desc: 'Grafo + opiniões' },
  { id: 'split', icon: '⚌', label: 'Dividir', desc: 'Grafo + simulação' },
  { id: 'workbench', icon: '🔬', label: 'Bancada', desc: 'Resultados' },
]

const ACTION_ICONS: Record<string, string> = {
  speak: '💬', react: '⚡', move: '🔀', announce: '📢',
}

const ACTION_COLORS: Record<string, string> = {
  speak: 'border-blue-500 bg-blue-900/30',
  react: 'border-yellow-500 bg-yellow-900/30',
  move: 'border-purple-500 bg-purple-900/30',
  announce: 'border-green-500 bg-green-900/30',
}

const TYPE_COLORS = ['#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#84cc16']

function getTypeColor(type: string, allTypes: string[]): string {
  return TYPE_COLORS[allTypes.indexOf(type) % TYPE_COLORS.length]
}

export default function WorkspacePage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const preselectedProject = searchParams.get('project')

  const [mode, setMode] = useState<ViewMode>('graph')
  const [projects, setProjects] = useState<GraphProjectSummary[]>([])
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [simulation, setSimulation] = useState<SimulationView | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [currentStep, setCurrentStep] = useState(-1)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1500)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const [simName, setSimName] = useState('')
  const [simPrompt, setSimPrompt] = useState('')
  const [numSteps, setNumSteps] = useState(12)
  const [filterEntityType, setFilterEntityType] = useState<string>('all')
  const [populatingOpinions, setPopulatingOpinions] = useState(false)
  const [opinionHint, setOpinionHint] = useState('')
  const [simulationStartedAt, setSimulationStartedAt] = useState<Date | null>(null)
  const [streamingStatus, setStreamingStatus] = useState<'idle' | 'generating' | 'streaming'>('idle')

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (user) loadProjects()
  }, [user]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (preselectedProject) loadGraph(preselectedProject)
  }, [preselectedProject]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [currentStep])

  useEffect(() => {
    if (playing && simulation) {
      const maxStep = simulation.steps.length - 1
      if (currentStep >= maxStep) {
        setPlaying(false)
        return
      }
      timerRef.current = setTimeout(() => {
        setCurrentStep((prev) => prev + 1)
      }, speed)
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [playing, currentStep, simulation, speed])

  async function loadProjects() {
    if (!user) return
    try {
      const data = await graphApi.list(user.organization_id)
      setProjects(data.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar projetos.')
    }
  }

  async function loadGraph(projectId: string) {
    try {
      const g = await graphApi.get(projectId)
      setGraph(g)
      setSelectedNode(null)
      setSimulation(null)
      setCurrentStep(-1)
      if (!simName) setSimName(`Simulação — ${g.name}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar grafo.')
    }
  }

  async function handleRunSimulation() {
    if (!user || !graph) return
    setRunning(true)
    setError(null)
    setCurrentStep(-1)
    setPlaying(false)
    setSimulationStartedAt(new Date())
    setStreamingStatus('generating')

    try {
      const created = await simulationsApi.create({
        project_id: graph.project_id,
        organization_id: user.organization_id,
        name: simName || `Simulação ${new Date().toLocaleDateString('pt-BR')}`,
        prompt: simPrompt || undefined,
      })

      // Seed an empty simulation so the UI shows "running" state immediately
      setSimulation({
        simulation_id: created.simulation_id,
        project_id: graph.project_id,
        name: created.name,
        status: 'running',
        summary: null,
        steps: [],
      })

      setStreamingStatus('streaming')

      for await (const event of simulationsApi.streamRun(created.simulation_id, numSteps)) {
        if (event.type === 'step') {
          const step: SimulationStep = event
          setSimulation((prev) => {
            if (!prev) return prev
            const steps = [...prev.steps, step]
            return { ...prev, steps }
          })
          setCurrentStep((prev) => prev + 1)
        } else if (event.type === 'done') {
          setSimulation((prev) =>
            prev ? { ...prev, status: 'completed', summary: event.summary } : prev,
          )
        } else if (event.type === 'error') {
          setError(event.message)
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao executar simulação.')
    } finally {
      setRunning(false)
      setStreamingStatus('idle')
    }
  }

  async function handlePopulateOpinions(): Promise<
    { ok: true; added_nodes: number; added_edges: number; total_nodes: number } | { ok: false; error: string }
  > {
    if (!graph) return { ok: false, error: 'Selecione um projeto de grafo antes.' }
    setPopulatingOpinions(true)
    setError(null)
    try {
      const result = await graphApi.populateOpinions(graph.project_id, opinionHint)
      const refreshed = await graphApi.get(graph.project_id)
      setGraph(refreshed)
      return { ok: true, ...result }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erro desconhecido ao popular opiniões.'
      setError(msg)
      return { ok: false, error: msg }
    } finally {
      setPopulatingOpinions(false)
    }
  }

  const activeStep = simulation?.steps[currentStep]
  const activeNodeId = activeStep?.agent_node_id ?? null
  const highlightedLabels = activeStep?.affected_nodes ?? []
  const visibleSteps = simulation ? simulation.steps.slice(0, currentStep + 1) : []
  const allTypes = graph ? [...new Set(graph.nodes.map((n) => n.entity_type))] : []
  const filteredNodes = graph
    ? (filterEntityType === 'all' ? graph.nodes : graph.nodes.filter((n) => n.entity_type === filterEntityType))
    : []

  return (
    <Layout wide={mode === 'graph'}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bancada de Agentes</h1>
          <p className="text-gray-500 text-sm mt-1">Análise visual de cenários, opiniões e simulações.</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={graph?.project_id ?? ''}
            onChange={(e) => e.target.value && loadGraph(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
          >
            <option value="">Selecione um projeto…</option>
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>{p.name}</option>
            ))}
          </select>
          <Link
            to="/graph"
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg text-gray-600 hover:border-brand-300"
          >
            + Novo Grafo
          </Link>
          <ScreenRecorder />
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      {graph?.description && graph.description.startsWith('AVISO IA') && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
          ⚠ {graph.description}
        </div>
      )}

      {/* Workspace: mode sidebar + main content */}
      <div
        className="flex gap-4"
        style={mode === 'graph' ? { height: 'calc(100vh - 180px)' } : { minHeight: '600px' }}
      >
        {/* Mode sidebar */}
        <aside className="w-40 shrink-0 space-y-2">
          {VIEW_MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={`w-full text-left p-3 rounded-xl border transition-all ${
                mode === m.id
                  ? 'border-brand-500 bg-brand-50 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-brand-300'
              }`}
            >
              <div className="text-2xl mb-1">{m.icon}</div>
              <p className={`text-sm font-semibold ${mode === m.id ? 'text-brand-700' : 'text-gray-800'}`}>
                {m.label}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">{m.desc}</p>
            </button>
          ))}
        </aside>

        {/* Main content */}
        <div className={`flex-1 min-w-0 ${mode === 'graph' ? 'h-full min-h-0' : ''}`}>
          {!graph ? (
            <div className="bg-white border border-dashed border-gray-300 rounded-xl p-16 text-center text-gray-400">
              <p className="text-4xl mb-3">🕸</p>
              <p className="text-sm">Selecione um projeto acima para começar.</p>
              <Link to="/graph" className="text-brand-600 text-sm hover:underline mt-2 inline-block">
                Criar novo grafo →
              </Link>
            </div>
          ) : mode === 'graph' ? (
            <GraphMode
              graph={graph}
              selectedNode={selectedNode}
              onSelectNode={setSelectedNode}
              filterEntityType={filterEntityType}
              onSetFilter={setFilterEntityType}
              filteredNodes={filteredNodes}
              allTypes={allTypes}
            />
          ) : mode === 'split' ? (
            <SplitMode
              graph={graph}
              simulation={simulation}
              currentStep={currentStep}
              activeStep={activeStep}
              activeNodeId={activeNodeId}
              highlightedLabels={highlightedLabels}
              visibleSteps={visibleSteps}
              playing={playing}
              speed={speed}
              running={running}
              streamingStatus={streamingStatus}
              simName={simName}
              simPrompt={simPrompt}
              numSteps={numSteps}
              logRef={logRef}
              onSetSimName={setSimName}
              onSetSimPrompt={setSimPrompt}
              onSetNumSteps={setNumSteps}
              onRun={handleRunSimulation}
              onPlay={() => {
                if (simulation && currentStep >= simulation.steps.length - 1) setCurrentStep(0)
                setPlaying(true)
              }}
              onPause={() => setPlaying(false)}
              onReset={() => { setPlaying(false); setCurrentStep(-1) }}
              onSetSpeed={setSpeed}
              onClearSimulation={() => { setSimulation(null); setCurrentStep(-1) }}
            />
          ) : (
            <WorkbenchMode
              graph={graph}
              simulation={simulation}
              allTypes={allTypes}
              simulationStartedAt={simulationStartedAt}
              opinionHint={opinionHint}
              onOpinionHintChange={setOpinionHint}
              populatingOpinions={populatingOpinions}
              onPopulateOpinions={handlePopulateOpinions}
            />
          )}
        </div>
      </div>
    </Layout>
  )
}

// =====================================================================
// Graph Mode — knowledge graph with opinion cards
// =====================================================================

function GraphMode({
  graph, selectedNode, onSelectNode, filterEntityType, onSetFilter, filteredNodes, allTypes,
}: {
  graph: GraphData
  selectedNode: GraphNode | null
  onSelectNode: (n: GraphNode | null) => void
  filterEntityType: string
  onSetFilter: (t: string) => void
  filteredNodes: GraphNode[]
  allTypes: string[]
}) {
  return (
    <div className="h-full flex flex-col gap-2 min-h-0">
      {/* Header + filter chips inline */}
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-gray-900 shrink-0">{graph.name}</h2>
        <div className="text-xs text-gray-500 shrink-0">
          {graph.node_count} nós · {graph.edge_count} arestas
        </div>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs text-gray-500 font-medium mr-1">Filtrar:</span>
        <button
          onClick={() => onSetFilter('all')}
          className={`px-2.5 py-0.5 text-xs rounded-full border transition-colors ${
            filterEntityType === 'all'
              ? 'bg-gray-800 text-white border-gray-800'
              : 'bg-white border-gray-300 text-gray-600 hover:border-gray-500'
          }`}
        >
          Todos ({graph.nodes.length})
        </button>
        {allTypes.map((t) => {
          const count = graph.nodes.filter((n) => n.entity_type === t).length
          const color = getTypeColor(t, allTypes)
          return (
            <button
              key={t}
              onClick={() => onSetFilter(t)}
              className={`flex items-center gap-1.5 px-2.5 py-0.5 text-xs rounded-full border transition-colors ${
                filterEntityType === t
                  ? 'text-white border-transparent'
                  : 'bg-white border-gray-300 text-gray-600 hover:border-gray-500'
              }`}
              style={filterEntityType === t ? { backgroundColor: color } : {}}
            >
              <span
                className="w-2 h-2 rounded-full inline-block"
                style={{ backgroundColor: color }}
              />
              {t} ({count})
            </button>
          )
        })}
      </div>

      {/* Main split: graph (left, fills) + cards sidebar (right) */}
      <div className="flex gap-3 flex-1 min-h-0">
        <div className="flex-1 relative min-w-0">
          <GraphViewer
            nodes={graph.nodes}
            edges={graph.edges}
            activeNodeId={selectedNode?.id ?? null}
            height="100%"
            onNodeClick={(id) => {
              const node = graph.nodes.find((n) => n.id === id)
              onSelectNode(node ?? null)
            }}
            onBackgroundClick={() => onSelectNode(null)}
          />
          {selectedNode && (
            <NodeDetailCard
              node={selectedNode}
              graph={graph}
              color={getTypeColor(selectedNode.entity_type, allTypes)}
              onClose={() => onSelectNode(null)}
            />
          )}
        </div>

        <div className="w-72 shrink-0 overflow-y-auto space-y-2 pr-1">
          <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold sticky top-0 bg-white/80 backdrop-blur py-1">
            Entidades ({filteredNodes.length})
          </p>
          {filteredNodes.map((n) => {
            const color = getTypeColor(n.entity_type, allTypes)
            const isSelected = selectedNode?.id === n.id
            return (
              <button
                key={n.id}
                onClick={() => onSelectNode(isSelected ? null : n)}
                className={`w-full text-left bg-white border rounded-lg p-2.5 transition-all hover:shadow-sm ${
                  isSelected ? 'border-brand-500 ring-2 ring-brand-200' : 'border-gray-200'
                }`}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                  <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">
                    {n.entity_type}
                  </span>
                </div>
                <h3 className="font-semibold text-gray-900 text-sm leading-tight">{n.label}</h3>
              </button>
            )
          })}
          {filteredNodes.length === 0 && (
            <p className="text-center text-gray-400 text-xs py-6">
              Nenhuma entidade encontrada nesse filtro.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// Split Mode — graph + simulation player
// =====================================================================

function SplitMode({
  graph, simulation, currentStep, activeStep, activeNodeId, highlightedLabels, visibleSteps,
  playing, speed, running, streamingStatus, simName, simPrompt, numSteps, logRef,
  onSetSimName, onSetSimPrompt, onSetNumSteps, onRun, onPlay, onPause, onReset, onSetSpeed, onClearSimulation,
}: {
  graph: GraphData
  simulation: SimulationView | null
  currentStep: number
  activeStep: SimulationView['steps'][number] | undefined
  activeNodeId: string | null
  highlightedLabels: string[]
  visibleSteps: SimulationView['steps']
  playing: boolean
  speed: number
  running: boolean
  streamingStatus: 'idle' | 'generating' | 'streaming'
  simName: string
  simPrompt: string
  numSteps: number
  logRef: React.RefObject<HTMLDivElement>
  onSetSimName: (s: string) => void
  onSetSimPrompt: (s: string) => void
  onSetNumSteps: (n: number) => void
  onRun: () => void
  onPlay: () => void
  onPause: () => void
  onReset: () => void
  onSetSpeed: (n: number) => void
  onClearSimulation: () => void
}) {
  return (
    <div className="grid grid-cols-2 gap-4 h-full">
      {/* Left: graph */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">{graph.name}</span>
          {activeStep && (
            <span className="text-xs text-brand-600">
              {activeStep.agent_label} {activeStep.action === 'speak' ? 'falando' : 'agindo'}
            </span>
          )}
        </div>
        <GraphViewer
          nodes={graph.nodes}
          edges={graph.edges}
          activeNodeId={activeNodeId}
          highlightedNodeLabels={highlightedLabels}
          height="500px"
        />
      </div>

      {/* Right: simulation */}
      <div className="flex flex-col gap-3 min-h-0">
        {!simulation ? (
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <h3 className="font-semibold text-gray-900">Configurar Simulação</h3>
            <input
              value={simName}
              onChange={(e) => onSetSimName(e.target.value)}
              placeholder="Nome"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
            />
            <textarea
              value={simPrompt}
              onChange={(e) => onSetSimPrompt(e.target.value)}
              rows={4}
              placeholder="Descreva o cenário (ex: 'candidato sofre escândalo')"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none resize-none"
            />
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-600">Passos:</span>
              {[8, 12, 16, 20].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => onSetNumSteps(n)}
                  className={`px-2 py-1 text-xs rounded border ${numSteps === n ? 'bg-brand-600 text-white border-brand-600' : 'border-gray-300 text-gray-600'}`}
                >
                  {n}
                </button>
              ))}
            </div>
            <button
              onClick={onRun}
              disabled={running}
              className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-medium py-2.5 rounded-lg text-sm"
            >
              {streamingStatus === 'generating'
                ? '🤖 Gerando passos…'
                : streamingStatus === 'streaming'
                  ? '📡 Transmitindo ao vivo…'
                  : '▶ Gerar e Executar'}
            </button>
          </div>
        ) : (
          <>
            {simulation.summary && (
              <div className="bg-gray-800 rounded-xl p-3">
                <p className="text-xs text-gray-400 uppercase mb-1 tracking-wider">Resumo</p>
                <p className="text-xs text-gray-200">{simulation.summary}</p>
              </div>
            )}
            <div className="bg-white border border-gray-200 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-2">
                <button onClick={onPlay} disabled={playing} className="flex-1 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium py-1.5 rounded-lg">▶ Play</button>
                <button onClick={onPause} disabled={!playing} className="flex-1 bg-gray-200 hover:bg-gray-300 disabled:opacity-50 text-gray-700 text-sm font-medium py-1.5 rounded-lg">⏸</button>
                <button onClick={onReset} className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-sm">↩</button>
              </div>
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <span>Velocidade:</span>
                {[{label:'Lento', v:3000}, {label:'Normal', v:1500}, {label:'Rápido', v:700}].map(({label, v}) => (
                  <button
                    key={v}
                    onClick={() => onSetSpeed(v)}
                    className={`px-2 py-0.5 rounded border text-xs ${speed === v ? 'bg-brand-600 text-white border-brand-600' : 'border-gray-300 text-gray-500'}`}
                  >
                    {label}
                  </button>
                ))}
                <span className="ml-auto text-gray-400">
                  {Math.max(0, currentStep + 1)}/{simulation.steps.length}
                </span>
              </div>
            </div>
            <div ref={logRef} className="bg-gray-950 rounded-xl p-2 overflow-y-auto flex-1 space-y-2" style={{ minHeight: '200px', maxHeight: '350px' }}>
              {visibleSteps.length === 0 && streamingStatus === 'idle' && (
                <p className="text-gray-600 text-xs text-center py-4">Clique em ▶ para iniciar</p>
              )}
              {visibleSteps.length === 0 && streamingStatus !== 'idle' && (
                <p className="text-brand-400 text-xs text-center py-4 animate-pulse">
                  {streamingStatus === 'generating' ? '🤖 Aguardando IA gerar passos…' : '📡 Primeiro passo chegando…'}
                </p>
              )}
              {visibleSteps.map((step, i) => (
                <div
                  key={step.step_number}
                  className={`rounded-lg border-l-2 px-2 py-1.5 text-xs ${ACTION_COLORS[step.action] ?? 'border-gray-500 bg-gray-800'} ${i === currentStep ? 'ring-1 ring-white/20' : ''}`}
                >
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span>{ACTION_ICONS[step.action] ?? '▸'}</span>
                    <span className="font-bold text-white">{step.agent_label}</span>
                    <span className="ml-auto text-gray-600">#{step.step_number}</span>
                  </div>
                  <p className="text-gray-300 leading-snug">{step.content}</p>
                </div>
              ))}
            </div>
            <button onClick={onClearSimulation} className="text-xs text-gray-400 hover:text-gray-200 text-center">
              Nova simulação
            </button>
          </>
        )}
      </div>
    </div>
  )
}

// =====================================================================
// Circular Progress Widget — agent-bench style
// =====================================================================

function CircularProgress({ value, max, label, sublabel, acts, elapsed }: {
  value: number; max: number; label: string; sublabel: string; acts: number; elapsed: string
}) {
  const r = 46
  const circ = 2 * Math.PI * r
  const pct = max > 0 ? Math.min(value / max, 1) : 0
  const dash = pct * circ
  return (
    <div className="bg-gray-900 rounded-2xl p-5 flex flex-col items-center gap-2 border border-gray-700">
      <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold">{label}</p>
      <div className="relative w-28 h-28">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={r} fill="none" stroke="#374151" strokeWidth="6" />
          <circle
            cx="50" cy="50" r={r} fill="none"
            stroke="#6366f1" strokeWidth="6"
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.8s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-white text-lg font-bold leading-none">{value}</span>
          <span className="text-gray-500 text-xs">/{max}</span>
        </div>
      </div>
      <p className="text-gray-300 text-xs">{sublabel}</p>
      <div className="w-full border-t border-gray-700 pt-2 grid grid-cols-2 gap-1 text-center">
        <div>
          <p className="text-gray-500 text-xs">Tempo decorrido</p>
          <p className="text-gray-200 text-sm font-mono">{elapsed}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">ATOS</p>
          <p className="text-gray-200 text-sm font-bold">{acts}</p>
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// Report Panel — console-style animated report (no transform animations)
// =====================================================================

// Compute report content ONCE per panel mount, outside any render path
function buildReportLines(graph: GraphData, simulation: SimulationView | null, reportId: string): string[] {
  const types = [...new Set(graph.nodes.map((n) => n.entity_type))].join(', ') || 'nenhum'
  const candidates = graph.nodes.filter((n) => n.entity_type === 'Candidato').map((n) => n.label).join(', ') || 'N/A'
  const voters = graph.nodes.filter((n) => n.entity_type === 'Eleitor').length
  const support = graph.edges.filter((e) => e.relationship_type === 'APOIA').length
  const oppose  = graph.edges.filter((e) => e.relationship_type === 'OPÕE').length
  const media   = graph.edges.filter((e) => e.relationship_type === 'CONSOME').length

  return [
    `[CampanhaPro] Iniciando geração — ID: ${reportId}`,
    `[CampanhaPro] Carregando grafo: ${graph.name}`,
    `[CampanhaPro] Entidades encontradas: ${graph.node_count} nós, ${graph.edge_count} arestas`,
    `[SEÇÃO 1/3] Análise de Cenário`,
    `  → Tipos de entidade: ${types}`,
    `  → Candidatos identificados: ${candidates}`,
    `  → Eleitores simulados: ${voters}`,
    `[SEÇÃO 2/3] Análise de Opiniões`,
    `  → Relações de apoio: ${support}`,
    `  → Relações de oposição: ${oppose}`,
    `  → Influência de mídia: ${media} conexões`,
    simulation
      ? `[SEÇÃO 3/3] Simulação — ${simulation.steps.length} atos`
      : `[SEÇÃO 3/3] Simulação — nenhuma simulação disponível`,
    simulation?.summary ? `  → ${simulation.summary}` : '  → Execute uma simulação para análise dinâmica',
    `[FERRAMENTAS] GraphRAG ✓  PanoramaSearch ✓  InsightCampanha ✓`,
    `[CampanhaPro] Relatório concluído — ${reportId}`,
  ]
}

function ReportPanelInner({ graph, simulation, onClose }: {
  graph: GraphData; simulation: SimulationView | null; onClose: () => void
}) {
  // Stable identity across renders — useState lazy initializer runs only once
  const [reportId] = useState(() => `report_${Math.random().toString(36).slice(2, 14)}`)
  const [allLines] = useState(() => buildReportLines(graph, simulation, reportId))
  const [startTime] = useState(() => Date.now())

  const [visibleCount, setVisibleCount] = useState(0)
  const [now, setNow] = useState(Date.now())
  const logRef = useRef<HTMLDivElement>(null)

  // Drip lines in one at a time
  useEffect(() => {
    if (visibleCount >= allLines.length) return
    const id = setTimeout(() => setVisibleCount((c) => c + 1), 220)
    return () => clearTimeout(id)
  }, [visibleCount, allLines.length])

  // Tick the elapsed-time display
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  // Auto-scroll the log to the bottom as new lines arrive
  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [visibleCount])

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const visibleLines = allLines.slice(0, visibleCount)
  const phase = visibleLines.filter((l) => l.startsWith('[SEÇÃO')).length
  const done = visibleCount >= allLines.length
  const sec = Math.floor((now - startTime) / 1000)
  const elapsed = `${Math.floor(sec / 60)} min ${sec % 60} s`

  // Render via portal to escape parent stacking contexts
  return createPortal(
    <div
      className="fixed inset-0 z-[100] bg-black/75 animate-fadeIn flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="animate-panelIn bg-gray-950 rounded-2xl border border-gray-700 shadow-2xl flex flex-col w-full max-w-5xl"
        style={{ height: 'min(85vh, 720px)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3.5 border-b border-gray-800 shrink-0">
          <div className="min-w-0">
            <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">Relatório de Previsão</p>
            <p className="text-white font-bold font-mono text-sm truncate">ID: {reportId}</p>
          </div>
          <div className="hidden md:flex items-center gap-5 text-xs text-gray-400">
            <span>Seções <span className="text-white font-bold">{Math.min(phase, 3)}/3</span></span>
            <span>Tempo <span className="text-white font-mono">{elapsed}</span></span>
            {done && <span className="text-green-400 font-bold">✓ Concluído</span>}
          </div>
          <button
            onClick={onClose}
            aria-label="Fechar"
            className="ml-3 text-gray-400 hover:text-white text-xl shrink-0 leading-none"
          >
            ✕
          </button>
        </div>

        {/* Body — two columns */}
        <div className="flex flex-1 min-h-0">
          {/* Left: console */}
          <div
            ref={logRef}
            className="flex-1 min-w-0 min-h-0 overflow-y-auto p-4 font-mono text-xs space-y-1 bg-gray-950"
          >
            {visibleLines.map((line, i) => (
              <div
                key={i}
                className={`leading-relaxed ${
                  line.startsWith('[SEÇÃO') ? 'text-brand-400 font-bold' :
                  line.startsWith('[CampanhaPro]') ? 'text-green-400' :
                  line.startsWith('[FERRAMENTAS]') ? 'text-yellow-400' :
                  'text-gray-300'
                }`}
              >
                {line}
              </div>
            ))}
            {!done && <div className="text-gray-500 animate-pulse">▌</div>}
          </div>

          {/* Right: summary cards */}
          <div className="w-72 shrink-0 border-l border-gray-800 p-5 space-y-3 overflow-y-auto bg-gray-900">
            <h3 className="text-white font-semibold text-sm">Análise do Cenário</h3>
            <div className="bg-gray-800 rounded-lg p-3 text-xs text-gray-400">
              <p className="text-gray-300 font-semibold mb-1">Grafo</p>
              <p>{graph.node_count} entidades · {graph.edge_count} relações</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 text-xs text-gray-400">
              <p className="text-gray-300 font-semibold mb-1">Eleitores</p>
              <p>{graph.nodes.filter((n) => n.entity_type === 'Eleitor').length} agentes simulados</p>
              <p className="mt-1">
                Apoio: {graph.edges.filter((e) => e.relationship_type === 'APOIA').length}
                {' / '}
                Oposição: {graph.edges.filter((e) => e.relationship_type === 'OPÕE').length}
              </p>
            </div>
            {simulation && (
              <div className="bg-gray-800 rounded-lg p-3 text-xs text-gray-400">
                <p className="text-gray-300 font-semibold mb-1">Simulação</p>
                <p>{simulation.steps.length} atos · {simulation.status}</p>
                {simulation.summary && (
                  <p className="mt-1 text-gray-500 leading-relaxed">
                    {simulation.summary.length > 140 ? simulation.summary.slice(0, 140) + '…' : simulation.summary}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

// Wrap the panel with a defensive boundary so a render error doesn't blank the app
class ReportErrorBoundary extends Component<
  { onClose: () => void; children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error) { console.error('ReportPanel crash:', error) }
  render() {
    if (this.state.error) {
      return createPortal(
        <div className="fixed inset-0 z-[100] bg-black/75 flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-gray-950 border border-red-700 rounded-xl p-6 max-w-md text-sm text-gray-200">
            <p className="text-red-400 font-bold mb-2">Erro ao gerar relatório</p>
            <p className="text-gray-400 text-xs mb-4 font-mono">{String(this.state.error?.message ?? this.state.error)}</p>
            <button
              onClick={this.props.onClose}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm"
            >
              Fechar
            </button>
          </div>
        </div>,
        document.body,
      )
    }
    return this.props.children
  }
}

function ReportPanel(props: { graph: GraphData; simulation: SimulationView | null; onClose: () => void }) {
  return (
    <ReportErrorBoundary onClose={props.onClose}>
      <ReportPanelInner {...props} />
    </ReportErrorBoundary>
  )
}

// =====================================================================
// Workbench Mode — agent-bench-style dashboard with plazas
// =====================================================================

function WorkbenchMode({
  graph, simulation, allTypes, simulationStartedAt,
  opinionHint, onOpinionHintChange, populatingOpinions, onPopulateOpinions,
}: {
  graph: GraphData
  simulation: SimulationView | null
  allTypes: string[]
  simulationStartedAt: Date | null
  opinionHint: string
  onOpinionHintChange: (v: string) => void
  populatingOpinions: boolean
  onPopulateOpinions: () => Promise<
    { ok: true; added_nodes: number; added_edges: number; total_nodes: number } | { ok: false; error: string }
  >
}) {
  const [showReport, setShowReport] = useState(false)
  const [elapsed, setElapsed] = useState('0h 0m')
  const [opinionFeedback, setOpinionFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)

  useEffect(() => {
    const tick = () => {
      if (!simulationStartedAt) { setElapsed('0h 0m'); return }
      const ms = Date.now() - simulationStartedAt.getTime()
      const totalMin = Math.floor(ms / 60000)
      setElapsed(`${Math.floor(totalMin / 60)}h ${totalMin % 60}m`)
    }
    tick()
    const id = setInterval(tick, 10000)
    return () => clearInterval(id)
  }, [simulationStartedAt])

  const actionCounts = simulation
    ? simulation.steps.reduce<Record<string, number>>((acc, s) => {
        acc[s.action] = (acc[s.action] || 0) + 1; return acc
      }, {})
    : {}

  const agentCounts = simulation
    ? simulation.steps.reduce<Record<string, number>>((acc, s) => {
        acc[s.agent_label] = (acc[s.agent_label] || 0) + 1; return acc
      }, {})
    : {}

  const topAgents = Object.entries(agentCounts).sort(([, a], [, b]) => b - a).slice(0, 5)
  const voterNodes = graph.nodes.filter(n => n.entity_type === 'Eleitor').length
  const totalActs = simulation?.steps.length ?? 0
  const topicCount = allTypes.length

  return (
    <div className="space-y-5">

      {/* agent-bench-style plaza row */}
      <div className="grid grid-cols-2 gap-5">
        <CircularProgress
          value={voterNodes}
          max={40}
          label="Praça de Informações"
          sublabel="Agentes eleitores no grafo"
          acts={graph.edge_count}
          elapsed={elapsed}
        />
        <CircularProgress
          value={topicCount}
          max={15}
          label="Comunidade de Tópicos"
          sublabel="Tipos de entidade ativos"
          acts={totalActs}
          elapsed={elapsed}
        />
      </div>

      {/* Populate opinions panel */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">Popular com Opiniões de Eleitores</h3>
          <span className="text-xs text-gray-400">{voterNodes} eleitores no grafo</span>
        </div>
        <div className="flex gap-3">
          <input
            value={opinionHint}
            onChange={(e) => onOpinionHintChange(e.target.value)}
            placeholder="Ex: Eleição para prefeito de São Paulo 2026…"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
          />
          <button
            onClick={async () => {
              setOpinionFeedback(null)
              try {
                const result = await onPopulateOpinions()
                if (result.ok) {
                  setOpinionFeedback({
                    type: 'success',
                    msg: `✓ +${result.added_nodes} eleitores e +${result.added_edges} opiniões adicionados. Total: ${result.total_nodes} nós no grafo.`,
                  })
                } else {
                  setOpinionFeedback({
                    type: 'error',
                    msg: `✗ Falha ao gerar eleitores: ${result.error}`,
                  })
                }
              } catch (err) {
                setOpinionFeedback({
                  type: 'error',
                  msg: `✗ Erro inesperado: ${err instanceof Error ? err.message : String(err)}`,
                })
              }
            }}
            disabled={populatingOpinions}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-medium px-4 py-2 rounded-lg text-sm transition-colors min-w-[150px]"
          >
            {populatingOpinions ? '🤖 Gerando… (até 3 min)' : '🧑‍🤝‍🧑 Gerar Eleitores'}
          </button>
        </div>
        {opinionFeedback && (
          <div className={`mt-2 px-3 py-2 rounded-lg text-xs font-medium ${opinionFeedback.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
            {opinionFeedback.msg}
          </div>
        )}
        <p className="text-xs text-gray-400 mt-2">
          A IA cria ~35 perfis de cidadãos (jovens, idosos, empresários, religiosos…) com opiniões sobre candidatos.
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Entidades</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{graph.node_count}</p>
          <p className="text-xs text-gray-400 mt-1">{allTypes.length} tipos</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Relações</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{graph.edge_count}</p>
          <p className="text-xs text-gray-400 mt-1">Conexões mapeadas</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Atos Simulados</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{totalActs}</p>
          <p className="text-xs text-gray-400 mt-1">{simulation ? simulation.status : 'sem simulação'}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Agentes Ativos</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{Object.keys(agentCounts).length}</p>
          <p className="text-xs text-gray-400 mt-1">No último cenário</p>
        </div>
      </div>

      {/* Two columns: summary + entity breakdown */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Resumo da Última Simulação</h3>
          {simulation ? (
            <>
              <p className="text-sm text-gray-700 mb-4 leading-relaxed">{simulation.summary || 'Sem resumo.'}</p>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Distribuição de Ações</p>
              <div className="space-y-2">
                {Object.entries(actionCounts).map(([action, count]) => {
                  const pct = Math.round((count / totalActs) * 100)
                  return (
                    <div key={action}>
                      <div className="flex items-center justify-between text-xs mb-0.5">
                        <span className="text-gray-700">{ACTION_ICONS[action] ?? '▸'} {action}</span>
                        <span className="text-gray-500">{count} ({pct}%)</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-brand-500" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-400">Vá para o modo "Dividir" e execute uma simulação.</p>
          )}
        </div>

        <div className="space-y-4">
          {topAgents.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Agentes Mais Ativos</h3>
              <div className="space-y-2">
                {topAgents.map(([agent, count]) => (
                  <div key={agent} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">{agent}</span>
                    <span className="px-2 py-0.5 bg-brand-100 text-brand-700 rounded-full text-xs font-medium">{count} ações</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Tipos de Entidades</h3>
            <div className="grid grid-cols-2 gap-2">
              {allTypes.map((t) => {
                const count = graph.nodes.filter((n) => n.entity_type === t).length
                const color = getTypeColor(t, allTypes)
                return (
                  <div key={t} className="flex items-center gap-2 text-sm">
                    <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-gray-700 truncate flex-1">{t}</span>
                    <span className="text-gray-500 text-xs">{count}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Gerar Relatório */}
      <div className="flex justify-center">
        <button
          onClick={() => setShowReport(true)}
          className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold px-8 py-3 rounded-xl shadow-lg transition-all text-sm"
        >
          📊 Gerar Relatório de Previsão
        </button>
      </div>

      {showReport && (
        <ReportPanel graph={graph} simulation={simulation} onClose={() => setShowReport(false)} />
      )}
    </div>
  )
}

// =====================================================================
// Node Detail Card — floating panel shown when a node is clicked
// =====================================================================

function NodeDetailCard({
  node, graph, color, onClose,
}: {
  node: GraphNode
  graph: GraphData
  color: string
  onClose: () => void
}) {
  const incomingEdges = graph.edges.filter((e) => e.target === node.id)
  const outgoingEdges = graph.edges.filter((e) => e.source === node.id)
  const labelOf = (id: string) => graph.nodes.find((n) => n.id === id)?.label ?? id
  const props = Object.entries(node.properties || {})

  return (
    <div className="absolute top-3 right-3 w-80 bg-white rounded-xl shadow-2xl border-2 border-gray-200 overflow-hidden z-10">
      <div
        className="px-4 py-3 flex items-start justify-between"
        style={{ backgroundColor: color }}
      >
        <div>
          <p className="text-xs uppercase tracking-wider text-white/80 font-medium">
            {node.entity_type}
          </p>
          <h3 className="text-lg font-bold text-white mt-0.5">{node.label}</h3>
        </div>
        <button
          onClick={onClose}
          className="text-white/80 hover:text-white text-xl leading-none"
          aria-label="Fechar"
        >
          ×
        </button>
      </div>

      <div className="p-4 max-h-80 overflow-y-auto space-y-4">
        {props.length > 0 ? (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Propriedades</p>
            <div className="space-y-1.5">
              {props.map(([k, v]) => (
                <div key={k} className="text-sm">
                  <span className="text-gray-500 capitalize">{k.replace(/_/g, ' ')}: </span>
                  <span className="text-gray-800">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-xs text-gray-400 italic">Sem propriedades adicionais.</p>
        )}

        {outgoingEdges.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Conexões de saída</p>
            <ul className="space-y-1">
              {outgoingEdges.map((e) => (
                <li key={e.id} className="text-sm text-gray-700">
                  <span className="text-brand-600 font-medium">{e.relationship_type}</span>
                  <span className="text-gray-400"> → </span>
                  <span>{labelOf(e.target)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {incomingEdges.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Conexões de entrada</p>
            <ul className="space-y-1">
              {incomingEdges.map((e) => (
                <li key={e.id} className="text-sm text-gray-700">
                  <span>{labelOf(e.source)}</span>
                  <span className="text-gray-400"> → </span>
                  <span className="text-brand-600 font-medium">{e.relationship_type}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {outgoingEdges.length === 0 && incomingEdges.length === 0 && (
          <p className="text-xs text-gray-400 italic">Sem conexões no grafo.</p>
        )}
      </div>
    </div>
  )
}
