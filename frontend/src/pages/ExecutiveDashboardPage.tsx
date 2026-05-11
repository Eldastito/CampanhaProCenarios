import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import ExportReportButton from '../components/ExportReportButton'
import {
  CandidateDossierSummary,
  ElectionProbabilityResult,
  ElectionProbabilitySummary,
  LatestFactorsResponse,
  PoliticalProject,
  dossiersApi,
  electionProbabilityApi,
  politicalProjectsApi,
} from '../api/client'

const FACTOR_LABELS: Record<string, string> = {
  vote_intention: 'Intenção de voto',
  rejection: 'Rejeição',
  awareness: 'Conhecimento',
  territorial_strength: 'Força territorial',
  alliances: 'Alianças',
  mobilization: 'Mobilização',
  digital_sentiment: 'Sentimento digital',
  local_agenda_fit: 'Aderência à pauta',
  reputation_risk: 'Risco reputacional',
  operational_efficiency: 'Eficiência operacional',
  media_coverage: 'Cobertura de mídia',
  declared_funding: 'Captação',
}

export default function ExecutiveDashboardPage() {
  const { projectId = '' } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<PoliticalProject | null>(null)
  const [factors, setFactors] = useState<LatestFactorsResponse | null>(null)
  const [dossiers, setDossiers] = useState<CandidateDossierSummary[]>([])
  const [electionHistory, setElectionHistory] = useState<ElectionProbabilitySummary[]>([])
  const [latestElection, setLatestElection] = useState<ElectionProbabilityResult | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!projectId) return
    let alive = true
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const proj = await politicalProjectsApi.get(projectId)
        if (!alive) return
        setProject(proj)
        const tasks = await Promise.all([
          politicalProjectsApi.getLatestFactors(projectId).catch(() => null),
          dossiersApi.list(projectId).catch(() => []),
          electionProbabilityApi.list(projectId).catch(() => []),
        ])
        if (!alive) return
        setFactors(tasks[0])
        setDossiers(tasks[1])
        setElectionHistory(tasks[2])
        // Detalhe da última simulação completed
        const lastCompleted = tasks[2].find((r) => r.status === 'completed')
        if (lastCompleted) {
          const detail = await electionProbabilityApi
            .get(projectId, lastCompleted.id)
            .catch(() => null)
          if (alive) setLatestElection(detail)
        }
      } catch (e) {
        if (alive) setError((e as Error).message)
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => {
      alive = false
    }
  }, [projectId])

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

  const sortedFactors = factors
    ? Object.entries(factors.factors)
        .map(([k, v]) => ({ key: k, value: v as number, label: FACTOR_LABELS[k] ?? k }))
        .sort((a, b) => b.value - a.value)
    : []
  const forces = sortedFactors.slice(0, 3)
  const weaknesses = sortedFactors.slice(-3).reverse()

  const topElectionItem = latestElection?.output_results
    ? [...latestElection.output_results].sort(
        (a, b) => b.win_probability - a.win_probability,
      )[0]
    : null

  const winLabel = (() => {
    if (!topElectionItem) return '—'
    const wp = topElectionItem.win_probability
    if (wp >= 0.95) return `≥95% · ${topElectionItem.candidate_name}`
    if (wp <= 0.05) return `≤5% · ${topElectionItem.candidate_name}`
    return `${(wp * 100).toFixed(1)}% · ${topElectionItem.candidate_name}`
  })()

  const opponentDossiers = dossiers.filter((d) => d.candidate_type === 'opponent')

  return (
    <Layout>
      <div className="mb-2">
        <Link to={`/political/projects`} className="text-xs text-gray-500 hover:underline">
          ← voltar para projetos
        </Link>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard Executivo</h1>
          <p className="text-sm text-gray-600 mt-1">
            {project.name} · {project.candidate_name} · {project.office} ·{' '}
            {project.election_year}
          </p>
        </div>
        <ExportReportButton
          projectId={projectId}
          defaultType="executive_summary"
          label="📄 Exportar relatório executivo"
        />
      </div>

      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}

      {/* Cards superiores */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          title="Score (média fatores reais)"
          value={
            sortedFactors.length
              ? (
                  sortedFactors.reduce((s, f) => s + f.value, 0) / sortedFactors.length
                ).toFixed(1)
              : '—'
          }
          hint="Maior é melhor"
        />
        <StatCard title="Probabilidade vitória" value={winLabel} hint="último Monte Carlo" />
        <StatCard
          title="Cobertura dados reais"
          value={factors ? `${factors.coverage_percent.toFixed(1)}%` : '—'}
          hint="snapshot CampanhaPro"
        />
        <StatCard
          title="Dossiês monitorados"
          value={dossiers.length.toString()}
          hint={`${opponentDossiers.length} adversário(s)`}
        />
      </div>

      {/* Forças / Fraquezas / Adversários */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card title="Top 3 forças">
          {forces.length === 0 ? (
            <EmptyHint>Sem fatores reais ainda — envie um snapshot v1.</EmptyHint>
          ) : (
            <ul className="text-sm space-y-1">
              {forces.map((f) => (
                <li key={f.key} className="flex justify-between">
                  <span>{f.label}</span>
                  <span className="font-mono text-green-700">{f.value.toFixed(0)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Top 3 fraquezas">
          {weaknesses.length === 0 ? (
            <EmptyHint>—</EmptyHint>
          ) : (
            <ul className="text-sm space-y-1">
              {weaknesses.map((f) => (
                <li key={f.key} className="flex justify-between">
                  <span>{f.label}</span>
                  <span className="font-mono text-red-700">{f.value.toFixed(0)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Adversários monitorados">
          {opponentDossiers.length === 0 ? (
            <EmptyHint>
              Nenhum dossiê de adversário ainda.{' '}
              <Link
                to={`/political/projects/${projectId}/dossiers`}
                className="text-brand-700 hover:underline"
              >
                criar agora
              </Link>
            </EmptyHint>
          ) : (
            <ul className="text-sm space-y-1">
              {opponentDossiers.slice(0, 5).map((d) => (
                <li key={d.id} className="flex justify-between">
                  <Link
                    to={`/political/projects/${projectId}/dossiers/${d.id}`}
                    className="hover:underline truncate"
                  >
                    {d.candidate_name}
                  </Link>
                  <span className="text-[11px] text-gray-500">{d.status}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Histórico Monte Carlo */}
      <Card title="Histórico de simulações Monte Carlo">
        {electionHistory.length === 0 ? (
          <EmptyHint>
            Nenhuma simulação ainda.{' '}
            <Link
              to={`/political/projects/${projectId}/election-probability`}
              className="text-brand-700 hover:underline"
            >
              calcular probabilidade
            </Link>
          </EmptyHint>
        ) : (
          <ul className="divide-y divide-gray-100 text-sm">
            {electionHistory.slice(0, 5).map((h) => (
              <li key={h.id} className="py-2 flex items-center justify-between">
                <span>
                  {h.office} · {h.iterations.toLocaleString('pt-BR')} iter ·{' '}
                  <span className="text-xs text-gray-500">
                    {new Date(h.created_at).toLocaleString('pt-BR')}
                  </span>
                </span>
                <span className="text-[11px] uppercase bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                  {h.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Avisos do mapper */}
      {factors && factors.warnings.length > 0 && (
        <div className="mt-4 p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 text-xs">
          <strong>Avisos do mapeamento:</strong>
          <ul className="list-disc list-inside mt-1">
            {factors.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </Layout>
  )
}

function StatCard({ title, value, hint }: { title: string; value: string; hint?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <p className="text-[11px] uppercase text-gray-500">{title}</p>
      <p className="text-xl font-bold text-gray-900 mt-1">{value}</p>
      {hint && <p className="text-[11px] text-gray-500 mt-1">{hint}</p>}
    </div>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-4">
      <h2 className="text-xs uppercase tracking-wide text-gray-500 mb-3">{title}</h2>
      {children}
    </section>
  )
}

function EmptyHint({ children }: { children?: React.ReactNode }) {
  return (
    <p className="text-xs text-gray-500 italic">{children ?? 'Sem dados.'}</p>
  )
}
