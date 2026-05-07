import { FormEvent, useEffect, useRef, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { graphApi, simulationsApi } from '../api/client'
import type { GraphData, SimulationView } from '../api/client'
import Layout from '../components/Layout'
import GraphViewer from '../components/GraphViewer'
import ScreenRecorder from '../components/ScreenRecorder'
import { useAuth } from '../contexts/AuthContext'

const ACTION_ICONS: Record<string, string> = {
  speak: '💬',
  react: '⚡',
  move: '🔀',
  announce: '📢',
}

const ACTION_COLORS: Record<string, string> = {
  speak: 'border-blue-500 bg-blue-900/30',
  react: 'border-yellow-500 bg-yellow-900/30',
  move: 'border-purple-500 bg-purple-900/30',
  announce: 'border-green-500 bg-green-900/30',
}

export default function SimulationPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const preselectedProject = searchParams.get('project')

  const [graph, setGraph] = useState<GraphData | null>(null)
  const [simulation, setSimulation] = useState<SimulationView | null>(null)
  const [currentStep, setCurrentStep] = useState(-1)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1500) // ms per step
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)

  // Form
  const [simName, setSimName] = useState('')
  const [simPrompt, setSimPrompt] = useState('')
  const [numSteps, setNumSteps] = useState(12)

  const logRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (preselectedProject) loadGraph(preselectedProject)
  }, [preselectedProject]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
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

  async function loadGraph(projectId: string) {
    try {
      const g = await graphApi.get(projectId)
      setGraph(g)
      if (!simName) setSimName(`Simulação — ${g.name}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar grafo.')
    }
  }

  async function handleCreateAndRun(e: FormEvent) {
    e.preventDefault()
    if (!user || !graph) return
    setCreating(true)
    setError(null)
    setCurrentStep(-1)
    setPlaying(false)
    try {
      const created = await simulationsApi.create({
        project_id: graph.project_id,
        organization_id: user.organization_id,
        name: simName,
        prompt: simPrompt || undefined,
      })
      setLoading(true)
      await simulationsApi.run(created.simulation_id, numSteps)
      const full = await simulationsApi.get(created.simulation_id)
      setSimulation(full)
      setCurrentStep(-1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao executar simulação.')
    } finally {
      setCreating(false)
      setLoading(false)
    }
  }

  function handlePlay() {
    if (!simulation) return
    if (currentStep >= simulation.steps.length - 1) {
      setCurrentStep(0)
    }
    setPlaying(true)
  }

  function handlePause() { setPlaying(false) }

  function handleReset() {
    setPlaying(false)
    setCurrentStep(-1)
  }

  const visibleSteps = simulation ? simulation.steps.slice(0, currentStep + 1) : []
  const activeStep = simulation?.steps[currentStep]
  const activeNodeId = activeStep?.agent_node_id ?? null
  const highlightedLabels = activeStep?.affected_nodes ?? []

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Simulação</h1>
          <p className="text-gray-500 text-sm mt-1">
            Veja os agentes do grafo interagindo em tempo real.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ScreenRecorder />
          <Link to="/graph" className="text-sm text-gray-500 hover:text-gray-700">
            ← Grafos
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-5 gap-5">
        {/* Left: config + graph */}
        <div className="col-span-3 space-y-4">
          {!graph ? (
            <div className="bg-white border border-gray-200 rounded-xl p-6 text-center text-gray-400">
              <p className="text-4xl mb-3">🕸</p>
              <p className="text-sm">Nenhum grafo selecionado.</p>
              <Link to="/graph" className="text-brand-600 text-sm hover:underline mt-2 inline-block">
                Ir para Grafos →
              </Link>
            </div>
          ) : (
            <>
              {/* Graph */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {graph.name}
                    {activeStep && (
                      <span className="ml-2 text-brand-500 font-normal">
                        — {activeStep.agent_label} está {activeStep.action === 'speak' ? 'falando' : 'agindo'}
                      </span>
                    )}
                  </span>
                  <span className="text-xs text-gray-400">
                    {graph.node_count} nós · {graph.edge_count} arestas
                  </span>
                </div>
                <GraphViewer
                  nodes={graph.nodes}
                  edges={graph.edges}
                  activeNodeId={activeNodeId}
                  highlightedNodeLabels={highlightedLabels}
                  height="380px"
                />
              </div>

              {/* Simulation form */}
              {!simulation && (
                <form onSubmit={handleCreateAndRun} className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
                  <h3 className="font-semibold text-gray-900">Configurar Simulação</h3>
                  <input
                    value={simName}
                    onChange={(e) => setSimName(e.target.value)}
                    required
                    placeholder="Nome da simulação"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
                  />
                  <textarea
                    value={simPrompt}
                    onChange={(e) => setSimPrompt(e.target.value)}
                    rows={3}
                    placeholder="Descreva o cenário ou situação que deseja simular (ex: 'candidato sofre escândalo de corrupção')"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none resize-none"
                  />
                  <div className="flex items-center gap-4">
                    <label className="text-sm text-gray-600">Passos:</label>
                    {[8, 12, 16, 20].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setNumSteps(n)}
                        className={`px-3 py-1 text-sm rounded-lg border transition-colors ${numSteps === n ? 'bg-brand-600 text-white border-brand-600' : 'border-gray-300 text-gray-600'}`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <button
                    type="submit"
                    disabled={creating || loading}
                    className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-medium py-2.5 rounded-lg text-sm"
                  >
                    {loading ? '🤖 Gerando simulação com IA…' : creating ? 'Criando…' : '▶ Gerar e Executar Simulação'}
                  </button>
                </form>
              )}
            </>
          )}
        </div>

        {/* Right: simulation log + controls */}
        <div className="col-span-2 flex flex-col gap-4">
          {simulation && (
            <>
              {/* Summary */}
              {simulation.summary && (
                <div className="bg-gray-800 rounded-xl p-4">
                  <p className="text-xs text-gray-400 uppercase mb-1 tracking-wider">Resumo</p>
                  <p className="text-sm text-gray-200">{simulation.summary}</p>
                </div>
              )}

              {/* Controls */}
              <div className="bg-white border border-gray-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <button
                    onClick={handlePlay}
                    disabled={playing}
                    className="flex-1 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg"
                  >
                    ▶ Play
                  </button>
                  <button
                    onClick={handlePause}
                    disabled={!playing}
                    className="flex-1 bg-gray-200 hover:bg-gray-300 disabled:opacity-50 text-gray-700 text-sm font-medium py-2 rounded-lg"
                  >
                    ⏸ Pausar
                  </button>
                  <button
                    onClick={handleReset}
                    className="px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-sm"
                  >
                    ↩
                  </button>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span>Velocidade:</span>
                  {[{label:'Lento', v:3000}, {label:'Normal', v:1500}, {label:'Rápido', v:700}].map(({label, v}) => (
                    <button
                      key={v}
                      onClick={() => setSpeed(v)}
                      className={`px-2 py-0.5 rounded border text-xs transition-colors ${speed === v ? 'bg-brand-600 text-white border-brand-600' : 'border-gray-300 text-gray-500'}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div className="mt-2 text-xs text-gray-400 text-center">
                  Passo {Math.max(0, currentStep + 1)} / {simulation.steps.length}
                </div>
              </div>

              {/* Log */}
              <div
                ref={logRef}
                className="bg-gray-950 rounded-xl p-3 overflow-y-auto flex-1 space-y-2"
                style={{ maxHeight: '380px', minHeight: '200px' }}
              >
                {visibleSteps.length === 0 && (
                  <p className="text-gray-600 text-sm text-center py-8">
                    Clique em ▶ Play para iniciar
                  </p>
                )}
                {visibleSteps.map((step, i) => (
                  <div
                    key={step.step_number}
                    className={`rounded-lg border-l-2 px-3 py-2 text-xs ${ACTION_COLORS[step.action] ?? 'border-gray-500 bg-gray-800'} ${i === currentStep ? 'ring-1 ring-white/20' : ''}`}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <span>{ACTION_ICONS[step.action] ?? '▸'}</span>
                      <span className="font-bold text-white">{step.agent_label}</span>
                      <span className="text-gray-500">({step.agent_type})</span>
                      <span className="ml-auto text-gray-600">#{step.step_number}</span>
                    </div>
                    <p className="text-gray-300 leading-snug">{step.content}</p>
                    {step.affected_nodes.length > 0 && (
                      <p className="text-gray-500 mt-1">
                        Afeta: {step.affected_nodes.join(', ')}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              <button
                onClick={() => { setSimulation(null); setCurrentStep(-1) }}
                className="text-xs text-gray-400 hover:text-gray-200 text-center"
              >
                Nova simulação
              </button>
            </>
          )}

          {!simulation && !graph && (
            <div className="bg-gray-100 rounded-xl p-6 text-center text-gray-400 text-sm">
              O log da simulação aparecerá aqui.
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
