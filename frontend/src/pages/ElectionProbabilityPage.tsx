import { FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import {
  ElectionCandidateInput,
  ElectionProbabilityResult,
  ElectionProbabilitySummary,
  ElectionResultItem,
  electionProbabilityApi,
  PoliticalProject,
  politicalProjectsApi,
} from '../api/client'

const FACTOR_KEYS = [
  'vote_intention',
  'rejection',
  'awareness',
  'territorial_strength',
  'alliances',
  'mobilization',
  'digital_sentiment',
  'local_agenda_fit',
  'reputation_risk',
  'operational_efficiency',
  'media_coverage',
  'declared_funding',
] as const

const FACTOR_LABELS: Record<(typeof FACTOR_KEYS)[number], string> = {
  vote_intention: 'Intenção de voto',
  rejection: 'Rejeição',
  awareness: 'Conhecimento',
  territorial_strength: 'Força territorial',
  alliances: 'Alianças',
  mobilization: 'Mobilização',
  digital_sentiment: 'Sentimento digital',
  local_agenda_fit: 'Aderência à pauta local',
  reputation_risk: 'Risco reputacional',
  operational_efficiency: 'Eficiência operacional',
  media_coverage: 'Cobertura de mídia',
  declared_funding: 'Captação declarada',
}

const OFFICES = [
  'Presidente',
  'Governador',
  'Senador',
  'Deputado Federal',
  'Deputado Estadual',
  'Prefeito',
  'Vereador',
]

interface DraftCandidate {
  name: string
  confidence: number
  factors: Record<string, string> // string para input controlado
}

function emptyCandidate(name = ''): DraftCandidate {
  return {
    name,
    confidence: 0.5,
    factors: Object.fromEntries(FACTOR_KEYS.map((k) => [k, ''])),
  }
}

function toApiCandidate(c: DraftCandidate): ElectionCandidateInput {
  const factors: Record<string, number> = {}
  for (const k of FACTOR_KEYS) {
    const raw = c.factors[k]
    if (raw !== '' && raw !== undefined && !Number.isNaN(Number(raw))) {
      factors[k] = Math.max(0, Math.min(100, Number(raw)))
    }
  }
  return { name: c.name, confidence: c.confidence, factors }
}

export default function ElectionProbabilityPage() {
  const { projectId = '' } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<PoliticalProject | null>(null)
  const [history, setHistory] = useState<ElectionProbabilitySummary[]>([])
  const [office, setOffice] = useState('Prefeito')
  const [iterations, setIterations] = useState<number>(10000)
  const [seed, setSeed] = useState<string>('')
  const [candidates, setCandidates] = useState<DraftCandidate[]>([
    emptyCandidate('Maria 13'),
    emptyCandidate('João 22'),
  ])
  const [submitting, setSubmitting] = useState(false)
  const [activeResultId, setActiveResultId] = useState<string | null>(null)
  const [activeResult, setActiveResult] = useState<ElectionProbabilityResult | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    Promise.all([
      politicalProjectsApi.get(projectId).then(setProject),
      electionProbabilityApi.list(projectId).then(setHistory),
    ]).catch((e) => setError((e as Error).message))
  }, [projectId])

  // Polling 3s enquanto active result estiver pendente.
  useEffect(() => {
    if (!activeResultId) return
    let alive = true
    async function tick() {
      try {
        const r = await electionProbabilityApi.get(projectId, activeResultId!)
        if (!alive) return
        setActiveResult(r)
        return r.status
      } catch (e) {
        return undefined
      }
    }
    tick().then((status) => {
      if (status === 'completed' || status === 'failed') return
      const t = setInterval(async () => {
        const status = await tick()
        if (status === 'completed' || status === 'failed') clearInterval(t)
      }, 3000)
      return () => clearInterval(t)
    })
    return () => {
      alive = false
    }
  }, [activeResultId, projectId])

  function addCandidate() {
    if (candidates.length >= 10) return
    setCandidates((prev) => [...prev, emptyCandidate('')])
  }

  function removeCandidate(idx: number) {
    if (candidates.length <= 2) return
    setCandidates((prev) => prev.filter((_, i) => i !== idx))
  }

  function setName(idx: number, name: string) {
    setCandidates((prev) => prev.map((c, i) => (i === idx ? { ...c, name } : c)))
  }

  function setConfidence(idx: number, value: number) {
    setCandidates((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, confidence: value } : c)),
    )
  }

  function setFactor(idx: number, key: string, raw: string) {
    setCandidates((prev) =>
      prev.map((c, i) =>
        i === idx ? { ...c, factors: { ...c.factors, [key]: raw } } : c,
      ),
    )
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const apiCandidates = candidates.map(toApiCandidate)
      if (apiCandidates.some((c) => !c.name)) {
        throw new Error('Todos os candidatos precisam de nome.')
      }
      const resp = await electionProbabilityApi.create(projectId, {
        office,
        candidates: apiCandidates,
        iterations,
        seed: seed.trim() === '' ? null : Number(seed),
      })
      setActiveResultId(resp.result_id)
      setActiveResult(null)
      // refresh histórico
      electionProbabilityApi.list(projectId).then(setHistory).catch(() => undefined)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Layout>
      <div className="mb-2">
        <Link to={`/political/projects`} className="text-xs text-gray-500 hover:underline">
          ← voltar para projetos
        </Link>
      </div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Probabilidade de Eleição (Monte Carlo)
        </h1>
        <p className="text-sm text-gray-600 mt-1">
          {project ? (
            <>
              Projeto: <span className="font-medium">{project.name}</span> ·{' '}
              {project.election_year}
            </>
          ) : (
            'Carregando…'
          )}
        </p>
      </div>

      <div className="my-3 p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 text-xs">
        ⚠ Probabilidade é estimativa estatística baseada nos fatores informados.
        <strong> Não é predição de resultado eleitoral.</strong> Mesmo seed +
        mesmos fatores = mesmo resultado.
      </div>

      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}

      <form onSubmit={submit} className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="grid grid-cols-3 gap-4 mb-4">
          <label>
            <span className="text-xs text-gray-600">Cargo</span>
            <select
              className="input mt-1"
              value={office}
              onChange={(e) => setOffice(e.target.value)}
            >
              {OFFICES.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="text-xs text-gray-600">Iterações</span>
            <input
              type="number"
              min={100}
              max={50000}
              step={100}
              className="input mt-1"
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value) || 10000)}
            />
          </label>
          <label>
            <span className="text-xs text-gray-600">Seed (opcional)</span>
            <input
              className="input mt-1"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              placeholder="vazio = aleatório"
            />
          </label>
        </div>

        {candidates.map((c, idx) => (
          <CandidateBlock
            key={idx}
            index={idx}
            candidate={c}
            canRemove={candidates.length > 2}
            onName={(v) => setName(idx, v)}
            onConfidence={(v) => setConfidence(idx, v)}
            onFactor={(k, v) => setFactor(idx, k, v)}
            onRemove={() => removeCandidate(idx)}
          />
        ))}

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={addCandidate}
            disabled={candidates.length >= 10}
            className="text-sm text-brand-700 hover:underline disabled:opacity-40"
          >
            + adicionar candidato (max 10)
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? 'Disparando…' : 'Calcular probabilidade'}
          </button>
        </div>
      </form>

      {activeResultId && (
        <ResultBlock
          result={activeResult}
          resultId={activeResultId}
          onReload={() =>
            electionProbabilityApi
              .get(projectId, activeResultId)
              .then(setActiveResult)
              .catch(() => undefined)
          }
        />
      )}

      <HistoryBlock
        history={history}
        onSelect={(id) => {
          setActiveResultId(id)
          setActiveResult(null)
        }}
      />
    </Layout>
  )
}

// ---------------------------------------------------------------------------
// Candidato (form)
// ---------------------------------------------------------------------------

function CandidateBlock({
  index,
  candidate,
  canRemove,
  onName,
  onConfidence,
  onFactor,
  onRemove,
}: {
  index: number
  candidate: DraftCandidate
  canRemove: boolean
  onName: (v: string) => void
  onConfidence: (v: number) => void
  onFactor: (k: string, v: string) => void
  onRemove: () => void
}) {
  return (
    <div className="border border-gray-200 rounded-lg p-3 mb-3 bg-gray-50">
      <div className="flex items-center justify-between mb-2">
        <div className="flex-1 grid grid-cols-2 gap-3">
          <label>
            <span className="text-xs text-gray-600">Candidato {index + 1}</span>
            <input
              required
              className="input mt-1"
              value={candidate.name}
              onChange={(e) => onName(e.target.value)}
              placeholder="Nome de urna"
            />
          </label>
          <label>
            <span className="text-xs text-gray-600">
              Confiança nos dados ({(candidate.confidence * 100).toFixed(0)}%)
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={candidate.confidence}
              onChange={(e) => onConfidence(Number(e.target.value))}
              className="w-full mt-2"
            />
          </label>
        </div>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="ml-2 text-xs text-red-600 hover:underline"
          >
            remover
          </button>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {FACTOR_KEYS.map((k) => (
          <label key={k} className="block">
            <span className="text-[11px] text-gray-600">{FACTOR_LABELS[k]}</span>
            <input
              type="number"
              min={0}
              max={100}
              className="input mt-0.5 text-sm"
              value={candidate.factors[k] ?? ''}
              onChange={(e) => onFactor(k, e.target.value)}
              placeholder="0-100"
            />
          </label>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Resultado
// ---------------------------------------------------------------------------

function ResultBlock({
  result,
  resultId,
  onReload,
}: {
  result: ElectionProbabilityResult | null
  resultId: string
  onReload: () => void
}) {
  if (!result) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <p className="text-sm text-gray-500">
          Aguardando worker… (id: <code>{resultId.slice(0, 8)}</code>)
        </p>
      </div>
    )
  }
  if (result.status === 'queued' || result.status === 'running') {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <p className="text-sm text-gray-500">
          Status: <strong>{result.status}</strong> — atualizando…
        </p>
      </div>
    )
  }
  if (result.status === 'failed') {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-5 mb-6">
        <p className="text-sm text-red-700">
          Falhou: {result.error_message ?? 'erro desconhecido'}
        </p>
        <button
          onClick={onReload}
          className="text-xs text-red-700 hover:underline mt-2"
        >
          recarregar
        </button>
      </div>
    )
  }

  const sorted = [...result.output_results].sort(
    (a, b) => b.win_probability - a.win_probability,
  )
  const max = Math.max(...sorted.map((s) => s.win_probability), 0.01)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-gray-900">
          Resultado · {result.iterations.toLocaleString('pt-BR')} iterações
        </h2>
        <span className="text-[11px] uppercase tracking-wide bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
          confiança {result.confidence_level}
        </span>
      </div>
      <div className="space-y-3">
        {sorted.map((r) => (
          <ResultBar key={r.candidate_name} item={r} max={max} />
        ))}
      </div>
      {result.seed !== null && (
        <p className="mt-3 text-xs text-gray-500">
          Seed usado: <code>{result.seed}</code> · reproduzível.
        </p>
      )}
    </div>
  )
}

function ResultBar({ item, max }: { item: ElectionResultItem; max: number }) {
  const pct = item.win_probability * 100
  const widthPct = (item.win_probability / max) * 100
  const ciLo = item.share_ci_95_first_round[0] * 100
  const ciHi = item.share_ci_95_first_round[1] * 100
  const meanPct = item.mean_share_first_round * 100
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-sm font-medium text-gray-800">{item.candidate_name}</span>
        <span className="text-sm text-gray-700">
          {pct >= 95 ? '≥95%' : pct <= 5 ? '≤5%' : `${pct.toFixed(1)}%`} de vitória
        </span>
      </div>
      <div className="h-3 rounded bg-gray-100 overflow-hidden">
        <div
          className="h-full bg-brand-600"
          style={{ width: `${widthPct.toFixed(1)}%` }}
        />
      </div>
      <p className="text-[11px] text-gray-500 mt-1">
        Share 1º turno: média {meanPct.toFixed(1)}% · IC 95% [{ciLo.toFixed(1)}% –{' '}
        {ciHi.toFixed(1)}%]
        {item.second_round_qualification_probability !== null && (
          <>
            {' · '}qualificação 2º turno:{' '}
            {(item.second_round_qualification_probability * 100).toFixed(0)}%
          </>
        )}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Histórico
// ---------------------------------------------------------------------------

function HistoryBlock({
  history,
  onSelect,
}: {
  history: ElectionProbabilitySummary[]
  onSelect: (id: string) => void
}) {
  if (history.length === 0) {
    return null
  }
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Histórico</h3>
      <ul className="text-sm divide-y divide-gray-100">
        {history.slice(0, 20).map((h) => (
          <li key={h.id} className="py-2 flex items-center justify-between">
            <div>
              <span className="font-medium">{h.office}</span> ·{' '}
              {h.iterations.toLocaleString('pt-BR')} iter ·{' '}
              <span className="text-xs text-gray-500">
                {new Date(h.created_at).toLocaleString('pt-BR')}
              </span>
              <span className="ml-2 text-[10px] uppercase bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                {h.status}
              </span>
            </div>
            <button
              onClick={() => onSelect(h.id)}
              className="text-xs text-brand-700 hover:underline"
            >
              ver
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
