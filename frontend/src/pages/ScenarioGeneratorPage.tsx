import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import {
  AvailableAgent,
  PoliticalProject,
  RateLimitInfo,
  ScenarioOrchestratorCall,
  politicalProjectsApi,
  scenarioOrchestratorApi,
} from '../api/client'

const PROMPT_EXAMPLES = [
  'Simule o impacto de dobrar nossa presença no bairro Boa Vista durante 3 semanas com endosso do líder Y.',
  'O que acontece com o score se a rejeição cair 10 pontos depois de uma resposta rápida a uma crise reputacional?',
  'Cenário em que conseguimos uma coligação com o partido X e aumentamos sentimento digital em 15%.',
]

// Categorias relevantes para Claude Managed (mídia, crise, adversários, estratégia).
const DEFAULT_AGENT_CATEGORIES = new Set(['midia', 'crise', 'adversarios', 'estrategia'])

export default function ScenarioGeneratorPage() {
  const { projectId = '' } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<PoliticalProject | null>(null)
  const [agents, setAgents] = useState<AvailableAgent[]>([])
  const [rateLimit, setRateLimit] = useState<RateLimitInfo | null>(null)
  const [history, setHistory] = useState<ScenarioOrchestratorCall[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const [prompt, setPrompt] = useState('')
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set())
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ScenarioOrchestratorCall | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [proj, ag, rl, hist] = await Promise.all([
        politicalProjectsApi.get(projectId),
        scenarioOrchestratorApi.listAgents(projectId),
        scenarioOrchestratorApi.getRateLimit(projectId),
        scenarioOrchestratorApi.list(projectId),
      ])
      setProject(proj)
      setAgents(ag)
      setRateLimit(rl)
      setHistory(hist)
      // pré-seleciona os 4 default
      const defaults = new Set(
        ag.filter((a) => DEFAULT_AGENT_CATEGORIES.has(a.category)).map((a) => a.role),
      )
      setSelectedAgents(defaults)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (projectId) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  function toggleAgent(role: string) {
    setSelectedAgents((prev) => {
      const next = new Set(prev)
      if (next.has(role)) next.delete(role)
      else next.add(role)
      return next
    })
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (prompt.trim().length < 10) {
      setError('Prompt precisa ter ao menos 10 caracteres.')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const call = await scenarioOrchestratorApi.generate(projectId, {
        prompt: prompt.trim(),
        agents_to_consult: Array.from(selectedAgents),
      })
      setResult(call)
      scenarioOrchestratorApi.getRateLimit(projectId).then(setRateLimit).catch(() => undefined)
      scenarioOrchestratorApi.list(projectId).then(setHistory).catch(() => undefined)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <Layout>
        <p className="text-gray-500">Carregando…</p>
      </Layout>
    )
  }

  if (!project) {
    return (
      <Layout>
        <p className="text-gray-500">Projeto não encontrado.</p>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="mb-2">
        <Link to="/scenarios/new" className="text-xs text-gray-500 hover:underline">
          ← voltar para criar cenário manual
        </Link>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Gerar cenário com IA
            <span className="ml-2 text-[10px] uppercase tracking-wide bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">
              Claude Managed
            </span>
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Projeto: <span className="font-medium">{project.name}</span> · {project.office} ·{' '}
            {project.election_year}
          </p>
        </div>
        {rateLimit && (
          <div className="text-right">
            <p className="text-xs text-gray-500">
              {rateLimit.used_last_hour}/{rateLimit.limit_per_hour} no último hora
            </p>
            <p className="text-[11px] text-gray-400">
              {rateLimit.remaining} restantes
            </p>
          </div>
        )}
      </div>

      <div className="my-3 p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 text-xs">
        ⚠ O modelo lê o contexto do projeto (12 fatores cacheados, dossiês, identidade),
        gera um cenário válido e (opcional) consulta agentes especialistas. Toda saída
        separa <strong>FATO / INFERÊNCIA / HIPÓTESE</strong>. Conteúdo gerado por IA —
        verifique antes de uso operacional.
      </div>

      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}

      <form onSubmit={submit} className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <label className="block">
          <span className="text-xs text-gray-600">Prompt</span>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={5}
            placeholder={PROMPT_EXAMPLES[0]}
            className="input mt-1 text-sm font-mono"
          />
        </label>
        <div className="flex flex-wrap gap-1 mt-2">
          {PROMPT_EXAMPLES.map((ex, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setPrompt(ex)}
              className="text-[11px] text-gray-500 hover:text-brand-700 hover:underline truncate max-w-[280px]"
              title={ex}
            >
              exemplo {i + 1}
            </button>
          ))}
        </div>

        <div className="mt-5">
          <p className="text-xs text-gray-600 mb-2">
            Especialistas a consultar ({selectedAgents.size} selecionados)
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-64 overflow-auto pr-1">
            {agents.map((a) => {
              const selected = selectedAgents.has(a.role)
              return (
                <button
                  key={a.role}
                  type="button"
                  onClick={() => toggleAgent(a.role)}
                  className={`text-left p-2 rounded border text-xs transition ${
                    selected
                      ? 'border-brand-600 bg-brand-50 text-brand-900'
                      : 'border-gray-200 bg-white hover:bg-gray-50 text-gray-700'
                  }`}
                >
                  <div className="font-medium">{a.role}</div>
                  <div className="text-[10px] opacity-70 mt-0.5">{a.synthetic_name}</div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex items-center justify-end mt-5">
          <button
            type="submit"
            disabled={submitting || prompt.trim().length < 10}
            className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? 'Gerando…' : '🪄 Gerar cenário'}
          </button>
        </div>
      </form>

      {result && <ResultBlock call={result} navigate={navigate} />}

      <HistoryBlock history={history} />
    </Layout>
  )
}

function ResultBlock({
  call,
  navigate,
}: {
  call: ScenarioOrchestratorCall
  navigate: (path: string) => void
}) {
  const payload = call.scenario_payload || {}
  const inputs = payload.alternative_inputs ?? {}
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-base font-semibold text-gray-900">
          {payload.name || 'Cenário gerado'}
        </h2>
        {call.scenario_id && (
          <button
            onClick={() => navigate(`/scenarios/${call.scenario_id}`)}
            className="text-xs text-brand-700 hover:underline"
          >
            ver cenário completo →
          </button>
        )}
      </div>
      {payload.description && (
        <p className="text-sm text-gray-700 mb-3">{payload.description}</p>
      )}

      {call.rationale && (
        <div className="mb-4 p-3 rounded bg-gray-50 border border-gray-200 text-xs whitespace-pre-wrap">
          {call.rationale}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-[11px] uppercase text-gray-500 mb-1">Baseline</p>
          <FactorTable factors={payload.baseline_inputs ?? {}} />
        </div>
        <div>
          <p className="text-[11px] uppercase text-gray-500 mb-1">Alternativo</p>
          <FactorTable factors={inputs} />
        </div>
      </div>

      {call.agents_analyses.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-2">
            Análises de especialistas ({call.agents_analyses.length})
          </h3>
          <div className="space-y-3">
            {call.agents_analyses.map((a, i) => (
              <div key={i} className="border border-gray-200 rounded p-3">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-medium text-gray-900">
                    {a.agent_role}
                    {a.agent_synthetic_name && (
                      <span className="text-xs text-gray-500 ml-2">
                        — {a.agent_synthetic_name}
                      </span>
                    )}
                  </p>
                  <span className="text-[10px] uppercase bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                    {a.status}
                  </span>
                </div>
                <p className="text-xs text-gray-700 whitespace-pre-wrap">
                  {a.analysis || <em className="opacity-60">sem retorno</em>}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {call.llm_model_used && (
        <p className="mt-3 text-[11px] text-gray-400">
          Modelo: {call.llm_model_used} · audit log #{call.id.slice(0, 8)}
        </p>
      )}
    </section>
  )
}

function FactorTable({ factors }: { factors: Record<string, number> }) {
  const entries = Object.entries(factors)
  if (entries.length === 0) {
    return <p className="text-xs text-gray-500 italic">—</p>
  }
  return (
    <table className="w-full text-xs">
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k} className="border-b border-gray-100">
            <td className="py-1 text-gray-600">{k}</td>
            <td className="py-1 text-right font-mono">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function HistoryBlock({ history }: { history: ScenarioOrchestratorCall[] }) {
  if (history.length === 0) return null
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Histórico</h3>
      <ul className="text-sm divide-y divide-gray-100">
        {history.slice(0, 10).map((h) => (
          <li key={h.id} className="py-2">
            <p className="text-sm text-gray-800 truncate" title={h.prompt}>
              {h.prompt.slice(0, 110)}
              {h.prompt.length > 110 ? '…' : ''}
            </p>
            <p className="text-[11px] text-gray-500 mt-1">
              {new Date(h.created_at).toLocaleString('pt-BR')} ·{' '}
              {h.agents_consulted.length} agente(s) ·{' '}
              <span className="uppercase">{h.status}</span>
              {h.scenario_id && (
                <>
                  {' · '}
                  <Link
                    to={`/scenarios/${h.scenario_id}`}
                    className="text-brand-700 hover:underline"
                  >
                    cenário
                  </Link>
                </>
              )}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}
