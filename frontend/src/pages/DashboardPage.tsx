import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  scenariosApi,
  simulationsApi,
  graphApi,
  savedPredictionsApi,
  savedResearchApi,
} from '../api/client'
import type { ScenarioSummary, SimulationSummary, GraphProjectSummary } from '../api/client'
import Layout from '../components/Layout'
import { useAuth } from '../contexts/AuthContext'

// ─── helpers ────────────────────────────────────────────────────────────────

function bandColor(band: string): string {
  switch (band) {
    case 'A+': return '#10b981'
    case 'A':  return '#34d399'
    case 'B':  return '#60a5fa'
    case 'C':  return '#f59e0b'
    case 'D':  return '#ef4444'
    default:   return '#6b7280'
  }
}

function bandBg(band: string): string {
  switch (band) {
    case 'A+': return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
    case 'A':  return 'bg-emerald-400/15 text-emerald-400 border-emerald-400/30'
    case 'B':  return 'bg-blue-400/15 text-blue-300 border-blue-400/30'
    case 'C':  return 'bg-amber-400/15 text-amber-300 border-amber-400/30'
    case 'D':  return 'bg-red-400/15 text-red-300 border-red-400/30'
    default:   return 'bg-gray-600/20 text-gray-400 border-gray-600/30'
  }
}

function deltaArrow(direction: string, delta: number | null): { arrow: string; cls: string } {
  if (delta === null || delta === 0) return { arrow: '→', cls: 'text-gray-400' }
  if (direction === 'positive' || delta > 0) return { arrow: '↑', cls: 'text-emerald-400' }
  return { arrow: '↓', cls: 'text-red-400' }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 2)  return 'agora'
  if (m < 60) return `há ${m}min`
  const h = Math.floor(m / 60)
  if (h < 24) return `há ${h}h`
  const d = Math.floor(h / 24)
  return `há ${d}d`
}

function confidenceLabel(level: string): { label: string; pct: number; cls: string } {
  switch (level) {
    case 'alta':   return { label: 'Alta', pct: 88, cls: 'text-emerald-400' }
    case 'média':  return { label: 'Média', pct: 55, cls: 'text-amber-400' }
    case 'baixa':  return { label: 'Baixa', pct: 22, cls: 'text-red-400' }
    default:       return { label: level, pct: 50, cls: 'text-gray-400' }
  }
}

// ─── sub-components ─────────────────────────────────────────────────────────

function StatCard({
  icon, label, value, sub, accent = false,
}: {
  icon: string; label: string; value: string | number; sub?: string; accent?: boolean
}) {
  return (
    <div className={`rounded-xl border p-4 flex flex-col gap-1 ${
      accent
        ? 'bg-brand-600/10 border-brand-500/30'
        : 'bg-gray-800/60 border-gray-700/60'
    }`}>
      <div className="flex items-center gap-2 text-gray-400 text-xs font-medium uppercase tracking-wider">
        <span className="text-base">{icon}</span>
        {label}
      </div>
      <div className={`text-2xl font-bold ${accent ? 'text-brand-400' : 'text-white'}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500">{sub}</div>}
    </div>
  )
}

function PulsingDot({ color }: { color: string }) {
  return (
    <span className="relative inline-flex h-2 w-2 mr-1">
      <span
        className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
        style={{ backgroundColor: color }}
      />
      <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: color }} />
    </span>
  )
}

function ScoreRing({ value, size = 56 }: { value: number; size?: number }) {
  const r = (size - 8) / 2
  const circ = 2 * Math.PI * r
  const filled = ((value ?? 0) / 100) * circ
  const color = value >= 70 ? '#10b981' : value >= 40 ? '#f59e0b' : '#ef4444'
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#374151" strokeWidth={5} />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke={color} strokeWidth={5}
        strokeDasharray={`${filled} ${circ - filled}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x="50%" y="54%" textAnchor="middle" fontSize="11" fontWeight="700"
        fill={color} dominantBaseline="middle"
      >
        {value}
      </text>
    </svg>
  )
}

function BandBar({ scenarios }: { scenarios: ScenarioSummary[] }) {
  const bands = ['A+', 'A', 'B', 'C', 'D', '—']
  const counts: Record<string, number> = {}
  bands.forEach((b) => (counts[b] = 0))
  scenarios.forEach((s) => {
    const b = s.alternative_band || '—'
    counts[b in counts ? b : '—'] = (counts[b in counts ? b : '—'] ?? 0) + 1
  })
  const total = scenarios.length || 1
  return (
    <div className="flex w-full h-3 rounded-full overflow-hidden gap-px">
      {bands.map((b) =>
        counts[b] > 0 ? (
          <div
            key={b}
            title={`${b}: ${counts[b]}`}
            style={{ width: `${(counts[b] / total) * 100}%`, backgroundColor: bandColor(b) }}
          />
        ) : null,
      )}
    </div>
  )
}

function ConfidenceBar({ level }: { level: string }) {
  const { pct, cls } = confidenceLabel(level)
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: pct >= 70 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444' }}
        />
      </div>
      <span className={`text-xs font-medium shrink-0 ${cls}`}>{confidenceLabel(level).label}</span>
    </div>
  )
}

// ─── clock ──────────────────────────────────────────────────────────────────

function LiveClock() {
  const [time, setTime] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="font-mono text-xs text-gray-500 tabular-nums">
      {time.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
    </span>
  )
}

// ─── main page ───────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth()
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [simulations, setSimulations] = useState<SimulationSummary[]>([])
  const [graphs, setGraphs] = useState<GraphProjectSummary[]>([])
  const [savedCount, setSavedCount] = useState(0)
  const [researchCount, setResearchCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    if (!user?.organization_id) return

    const org = user.organization_id
    Promise.allSettled([
      scenariosApi.list(org),
      simulationsApi.list(org),
      graphApi.list(org),
      savedPredictionsApi.list(org),
      savedResearchApi.list(org),
    ]).then((results) => {
      if (!mountedRef.current) return
      if (results[0].status === 'fulfilled') setScenarios(results[0].value.items)
      if (results[1].status === 'fulfilled') setSimulations(results[1].value.items)
      if (results[2].status === 'fulfilled') setGraphs(results[2].value.items)
      if (results[3].status === 'fulfilled') setSavedCount(results[3].value.items.length)
      if (results[4].status === 'fulfilled') setResearchCount(results[4].value.items.length)
      setLoading(false)
    })

    return () => { mountedRef.current = false }
  }, [user?.organization_id])

  // ── computed ─────────────────────────────────────────────────────────────
  const ranked = [...scenarios]
    .filter((s) => s.normalized_delta !== null)
    .sort((a, b) => Math.abs(b.normalized_delta ?? 0) - Math.abs(a.normalized_delta ?? 0))
    .slice(0, 7)

  const bestConf = scenarios
    .filter((s) => s.confidence_level === 'alta').length

  const highRisk = scenarios
    .filter((s) => (s.normalized_delta ?? 0) < -10).length

  const avgBaseline = scenarios.length
    ? Math.round(scenarios.reduce((acc, s) => acc + (s.baseline_normalized_score ?? 0), 0) / scenarios.length)
    : 0

  const completedSims = simulations.filter((s) => s.status === 'completed').length
  const runningSims   = simulations.filter((s) => s.status === 'running').length

  const recentSims = [...simulations]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 6)

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <Layout>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="mb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <PulsingDot color="#6366f1" />
              <span className="text-xs font-medium text-brand-400 uppercase tracking-widest">
                Central de Previsão
              </span>
              <LiveClock />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">
              Inteligência Preditiva
            </h1>
            <p className="text-gray-500 text-sm mt-0.5">
              {user?.organization_id} · monitorando {scenarios.length} cenário{scenarios.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Link
              to="/workspace"
              className="px-3 py-2 text-xs font-medium rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
            >
              🔬 Bancada
            </Link>
            <Link
              to="/scenarios/new"
              className="px-3 py-2 text-xs font-medium rounded-lg bg-brand-600 hover:bg-brand-700 text-white transition-colors"
            >
              + Novo Cenário
            </Link>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-24">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
        </div>
      ) : (
        <div className="space-y-6">

          {/* ── KPI Row ──────────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <StatCard icon="📊" label="Cenários" value={scenarios.length} sub={`${bestConf} com alta confiança`} accent />
            <StatCard icon="⚡" label="Simulações" value={simulations.length} sub={`${completedSims} concluídas · ${runningSims} em andamento`} />
            <StatCard icon="🕸" label="Grafos" value={graphs.length} sub={graphs.length > 0 ? `${graphs.reduce((a, g) => a + g.node_count, 0)} nós · ${graphs.reduce((a, g) => a + g.edge_count, 0)} conexões` : 'nenhum ainda'} />
            <StatCard icon="🔴" label="Alto Risco" value={highRisk} sub="cenários com queda &gt;10pts" />
            <StatCard icon="💾" label="Pesquisas" value={researchCount} sub={`${savedCount} predições salvas`} />
          </div>

          {/* ── Main Grid ────────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* ─ Scenario Forecast Table (2/3 wide) ───────────────────── */}
            <div className="lg:col-span-2 bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
              <div className="px-5 py-3.5 border-b border-gray-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">Previsão de Cenários</span>
                  <span className="text-xs text-gray-500">· ordenado por impacto</span>
                </div>
                {scenarios.length > 0 && <BandBar scenarios={scenarios} />}
              </div>

              {ranked.length === 0 ? (
                <div className="py-16 text-center text-gray-600 text-sm">
                  Nenhum cenário calculado ainda.{' '}
                  <Link to="/scenarios/new" className="text-brand-500 hover:text-brand-400">Criar →</Link>
                </div>
              ) : (
                <div className="divide-y divide-gray-800/60">
                  {ranked.map((s) => {
                    const { arrow, cls } = deltaArrow(s.delta_direction, s.normalized_delta)
                    const absDelta = Math.abs(s.normalized_delta ?? 0)
                    const deltaColor = (s.normalized_delta ?? 0) > 0 ? 'text-emerald-400' : 'text-red-400'
                    return (
                      <Link
                        key={s.scenario_id}
                        to={`/scenarios/${s.scenario_id}`}
                        className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-800/40 transition-colors group"
                      >
                        {/* Band migration */}
                        <div className="flex items-center gap-1 shrink-0 w-24">
                          <span className={`text-xs font-bold px-1.5 py-0.5 rounded border ${bandBg(s.baseline_band)}`}>
                            {s.baseline_band || '—'}
                          </span>
                          <span className="text-gray-600 text-xs">→</span>
                          <span className={`text-xs font-bold px-1.5 py-0.5 rounded border ${bandBg(s.alternative_band)}`}>
                            {s.alternative_band || '—'}
                          </span>
                        </div>

                        {/* Name */}
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-100 truncate group-hover:text-white">
                            {s.name}
                          </div>
                          <ConfidenceBar level={s.confidence_level} />
                        </div>

                        {/* Score ring + delta */}
                        <div className="flex items-center gap-3 shrink-0">
                          <ScoreRing value={s.alternative_normalized_score ?? 0} />
                          <div className="text-right w-12">
                            <div className={`text-sm font-bold ${cls}`}>{arrow}</div>
                            <div className={`text-xs font-semibold ${deltaColor}`}>
                              {absDelta.toFixed(1)}
                            </div>
                          </div>
                        </div>
                      </Link>
                    )
                  })}
                </div>
              )}

              {scenarios.length > 7 && (
                <div className="px-5 py-3 border-t border-gray-800 text-center">
                  <Link to="/compare" className="text-xs text-brand-400 hover:text-brand-300">
                    Ver todos os {scenarios.length} cenários →
                  </Link>
                </div>
              )}
            </div>

            {/* ─ Right column ─────────────────────────────────────────── */}
            <div className="flex flex-col gap-5">

              {/* Network Health */}
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                <div className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <span>🌐</span> Saúde da Rede
                </div>
                {graphs.length === 0 ? (
                  <div className="text-xs text-gray-600 py-4 text-center">
                    Nenhum grafo criado.{' '}
                    <Link to="/graph" className="text-brand-500 hover:text-brand-400">Criar →</Link>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {graphs.slice(0, 4).map((g) => {
                      const density = g.edge_count > 0 && g.node_count > 1
                        ? Math.min(100, Math.round((g.edge_count / (g.node_count * (g.node_count - 1))) * 100 * 4))
                        : 0
                      return (
                        <div key={g.project_id}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-gray-300 truncate max-w-[140px]">{g.name}</span>
                            <span className="text-gray-500">{g.node_count}n · {g.edge_count}e</span>
                          </div>
                          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-brand-600 to-brand-400"
                              style={{ width: `${Math.max(4, density)}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                    {graphs.length > 4 && (
                      <Link to="/graph" className="block text-xs text-center text-gray-600 hover:text-gray-400">
                        +{graphs.length - 4} mais
                      </Link>
                    )}
                  </div>
                )}
              </div>

              {/* Prediction Score Gauge */}
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                <div className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <span>🎯</span> Pontuação Média
                </div>
                <div className="flex items-center gap-4">
                  <ScoreRing value={avgBaseline} size={72} />
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Score baseline médio</div>
                    <div className="text-lg font-bold text-white">{avgBaseline}<span className="text-xs text-gray-500">/100</span></div>
                    <div className="text-xs text-gray-500 mt-1">
                      {avgBaseline >= 70 ? '✅ Positivo' : avgBaseline >= 40 ? '⚠️ Moderado' : '🔴 Crítico'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                <div className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <span>⚡</span> Ações Rápidas
                </div>
                <div className="space-y-1.5">
                  {[
                    { to: '/political/projects', icon: '🗳', label: 'Projetos Eleitorais' },
                    { to: '/scenarios/new', icon: '＋', label: 'Novo Cenário' },
                    { to: '/workspace',     icon: '🧑‍⚖️', label: 'Bancada de Agentes' },
                    { to: '/research',      icon: '🔍', label: 'Pesquisar Candidato' },
                    { to: '/chat',          icon: '🤖', label: 'Consultar Agente IA' },
                    { to: '/predictions',   icon: '◎',  label: 'Nova Predição' },
                  ].map((a) => (
                    <Link
                      key={a.to}
                      to={a.to}
                      className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
                    >
                      <span className="text-base w-5 text-center">{a.icon}</span>
                      {a.label}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ── Simulation Feed + Band Legend ───────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Simulation Feed */}
            <div className="lg:col-span-2 bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
              <div className="px-5 py-3.5 border-b border-gray-800 flex items-center justify-between">
                <span className="text-sm font-semibold text-white">Simulações Recentes</span>
                <Link to="/simulations/new" className="text-xs text-brand-400 hover:text-brand-300">
                  + Nova →
                </Link>
              </div>
              {recentSims.length === 0 ? (
                <div className="py-12 text-center text-gray-600 text-sm">
                  Nenhuma simulação rodada ainda.{' '}
                  <Link to="/simulations/new" className="text-brand-500 hover:text-brand-400">Iniciar →</Link>
                </div>
              ) : (
                <div className="divide-y divide-gray-800/60">
                  {recentSims.map((sim) => {
                    const statusColor =
                      sim.status === 'completed' ? 'text-emerald-400' :
                      sim.status === 'running'   ? 'text-amber-400 animate-pulse' :
                      'text-gray-500'
                    const statusIcon =
                      sim.status === 'completed' ? '✓' :
                      sim.status === 'running'   ? '▶' : '○'
                    return (
                      <div key={sim.simulation_id} className="flex items-center gap-4 px-5 py-3">
                        <span className={`text-base ${statusColor}`}>{statusIcon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-gray-200 truncate">{sim.name}</div>
                          <div className="text-xs text-gray-500">
                            {sim.step_count} etapas · {relativeTime(sim.created_at)}
                          </div>
                        </div>
                        <span className={`text-xs font-medium ${statusColor}`}>
                          {sim.status}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Band legend + summary */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <div className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <span>📈</span> Distribuição de Bandas
              </div>
              {scenarios.length === 0 ? (
                <div className="text-xs text-gray-600 py-4 text-center">Sem dados</div>
              ) : (
                <>
                  <div className="space-y-3 mb-5">
                    {['A+', 'A', 'B', 'C', 'D'].map((band) => {
                      const count = scenarios.filter((s) => s.alternative_band === band).length
                      const pct = Math.round((count / scenarios.length) * 100)
                      return (
                        <div key={band} className="flex items-center gap-3">
                          <span
                            className={`w-8 text-xs font-bold text-center py-0.5 rounded border ${bandBg(band)}`}
                          >
                            {band}
                          </span>
                          <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{ width: `${pct}%`, backgroundColor: bandColor(band) }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 w-6 text-right">{count}</span>
                        </div>
                      )
                    })}
                  </div>

                  <div className="border-t border-gray-800 pt-4 space-y-2.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-400">Alta confiança</span>
                      <span className="text-emerald-400 font-medium">{bestConf}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-400">Alto risco</span>
                      <span className="text-red-400 font-medium">{highRisk}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-400">Grafos ativos</span>
                      <span className="text-blue-400 font-medium">{graphs.length}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-400">Pesquisas salvas</span>
                      <span className="text-purple-400 font-medium">{researchCount}</span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* ── Empty state CTA ──────────────────────────────────────────── */}
          {scenarios.length === 0 && simulations.length === 0 && (
            <div className="bg-gradient-to-br from-brand-900/30 to-gray-900 border border-brand-800/40 rounded-xl p-8 text-center">
              <div className="text-4xl mb-3">🔮</div>
              <h2 className="text-lg font-bold text-white mb-2">Comece a prever o futuro</h2>
              <p className="text-gray-400 text-sm max-w-md mx-auto mb-5">
                Crie seu primeiro cenário político, construa grafos de influência e rode simulações
                com agentes de IA para antecipar resultados eleitorais.
              </p>
              <div className="flex justify-center gap-3">
                <Link
                  to="/scenarios/new"
                  className="px-4 py-2 text-sm font-medium rounded-lg bg-brand-600 hover:bg-brand-700 text-white transition-colors"
                >
                  + Criar Cenário
                </Link>
                <Link
                  to="/workspace"
                  className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 transition-colors"
                >
                  Abrir Bancada →
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </Layout>
  )
}
