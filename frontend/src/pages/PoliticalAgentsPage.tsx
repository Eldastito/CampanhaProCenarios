import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import {
  politicalAgentsApi,
  politicalProjectsApi,
  type PoliticalAgentProfile,
  type PoliticalAgentType,
  type PoliticalProject,
} from '../api/client'

const CONFIDENCE_COLOR: Record<string, string> = {
  high: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  medium: 'bg-amber-100 text-amber-800 border-amber-300',
  low: 'bg-red-100 text-red-800 border-red-300',
}

export default function PoliticalAgentsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<PoliticalProject | null>(null)
  const [agents, setAgents] = useState<PoliticalAgentProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<PoliticalAgentType>('fixed_specialist')
  const [seeding, setSeeding] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const [openAgent, setOpenAgent] = useState<PoliticalAgentProfile | null>(null)

  const load = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    setError(null)
    try {
      const [proj, list] = await Promise.all([
        politicalProjectsApi.get(projectId),
        politicalAgentsApi.list(projectId),
      ])
      setProject(proj)
      setAgents(list)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  async function seedSpecialists() {
    if (!projectId) return
    setSeeding(true)
    setError(null)
    setActionMsg(null)
    try {
      const result = await politicalAgentsApi.seedSpecialists(projectId)
      setActionMsg(result.detail)
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSeeding(false)
    }
  }

  async function generateFromGraph() {
    if (!projectId) return
    setGenerating(true)
    setError(null)
    setActionMsg(null)
    try {
      const result = await politicalAgentsApi.generateFromGraph(projectId)
      setActionMsg(result.detail)
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGenerating(false)
    }
  }

  const visibleAgents = agents.filter((a) => a.agent_type === tab)
  const fixedCount = agents.filter((a) => a.agent_type === 'fixed_specialist').length
  const generatedCount = agents.filter((a) => a.agent_type === 'generated').length

  return (
    <Layout>
      <div className="mb-6">
        <Link to="/political/projects" className="text-sm text-brand-600 hover:underline">
          ← Projetos
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Bancada de Agentes</h1>
        <p className="text-sm text-gray-600 mt-1">
          {project ? (
            <>
              {project.name} · {project.candidate_name} · {project.office} {project.election_year}
            </>
          ) : (
            'Carregando projeto…'
          )}
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}
      {actionMsg && (
        <div className="mb-4 p-3 rounded-lg bg-emerald-50 text-emerald-800 text-sm border border-emerald-200">
          {actionMsg}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 mb-5">
        <button
          onClick={seedSpecialists}
          disabled={seeding}
          className="text-sm px-3 py-1.5 rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {seeding ? 'Semeando…' : '🧑‍⚖️ Semear especialistas fixos'}
        </button>
        <button
          onClick={generateFromGraph}
          disabled={generating}
          className="text-sm px-3 py-1.5 rounded-lg border border-brand-600 text-brand-700 hover:bg-brand-50 disabled:opacity-50"
          title="Requer um grafo construído na Fase 3"
        >
          {generating ? 'Gerando…' : '🕸 Gerar agentes do grafo'}
        </button>
        <Link
          to={`/political/projects/${projectId}/evidence`}
          className="text-xs text-gray-600 hover:underline ml-auto"
        >
          📄 Voltar para Evidências
        </Link>
      </div>

      <div className="border-b border-gray-200 mb-4 flex gap-1">
        <TabButton active={tab === 'fixed_specialist'} onClick={() => setTab('fixed_specialist')}>
          Especialistas fixos · {fixedCount}
        </TabButton>
        <TabButton active={tab === 'generated'} onClick={() => setTab('generated')}>
          Gerados do grafo · {generatedCount}
        </TabButton>
      </div>

      {loading ? (
        <p className="text-gray-500">Carregando…</p>
      ) : visibleAgents.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center">
          {tab === 'fixed_specialist' ? (
            <>
              <p className="text-gray-600">Bancada de especialistas vazia.</p>
              <p className="text-sm text-gray-500 mt-1">
                Clique em <strong>Semear especialistas fixos</strong> para criar os 17 papéis padrão.
              </p>
            </>
          ) : (
            <>
              <p className="text-gray-600">Nenhum agente gerado a partir do grafo ainda.</p>
              <p className="text-sm text-gray-500 mt-1">
                Construa o grafo na tela de Evidências e depois clique em{' '}
                <strong>Gerar agentes do grafo</strong>.
              </p>
            </>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {visibleAgents.map((a) => (
            <AgentCard key={a.id} agent={a} onOpen={() => setOpenAgent(a)} />
          ))}
        </div>
      )}

      {openAgent && <AgentDetailModal agent={openAgent} onClose={() => setOpenAgent(null)} />}
    </Layout>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
        active
          ? 'border-brand-600 text-brand-700'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      {children}
    </button>
  )
}

function AgentCard({
  agent,
  onOpen,
}: {
  agent: PoliticalAgentProfile
  onOpen: () => void
}) {
  return (
    <button
      onClick={onOpen}
      className="text-left rounded-lg border border-gray-200 bg-white p-4 hover:shadow-sm hover:border-brand-300 transition"
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3 className="font-semibold text-gray-900 text-sm leading-snug">
          {agent.synthetic_name}
        </h3>
        <span
          className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border whitespace-nowrap ${
            CONFIDENCE_COLOR[agent.confidence_level] ?? 'bg-gray-100 text-gray-600 border-gray-300'
          }`}
        >
          {agent.confidence_level}
        </span>
      </div>
      <p className="text-xs text-gray-600 font-medium">{agent.role}</p>
      <p className="text-xs text-gray-500 mt-2 line-clamp-3">{agent.biography}</p>
      <div className="flex items-center gap-2 mt-3 text-[11px] text-gray-400">
        <span>{agent.biases_declared.length} viés(es) declarado(s)</span>
        {agent.source_node_ids.length > 0 && (
          <span>· {agent.source_node_ids.length} fonte(s) do grafo</span>
        )}
      </div>
    </button>
  )
}

function AgentDetailModal({
  agent,
  onClose,
}: {
  agent: PoliticalAgentProfile
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-white rounded-xl w-full max-w-2xl p-6 shadow-xl max-h-[90vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{agent.synthetic_name}</h2>
            <p className="text-sm text-gray-600">{agent.role}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            aria-label="Fechar"
          >
            ×
          </button>
        </div>

        <Section title="Biografia">
          <p className="text-sm text-gray-700">{agent.biography}</p>
        </Section>

        <Section title="Vieses declarados">
          <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
            {agent.biases_declared.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </Section>

        <Section title="Limitações">
          <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
            {agent.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </Section>

        <Section title="Confiança declarada">
          <span
            className={`inline-block text-xs uppercase tracking-wide px-2 py-1 rounded border ${
              CONFIDENCE_COLOR[agent.confidence_level] ?? 'bg-gray-100 text-gray-600 border-gray-300'
            }`}
          >
            {agent.confidence_level}
          </span>
        </Section>

        {agent.source_node_ids.length > 0 && (
          <Section title="Origem (nós do grafo)">
            <p className="text-xs text-gray-500">{agent.source_node_ids.join(', ')}</p>
          </Section>
        )}

        <Section title="Persona Prompt (visível para auditoria)">
          <pre className="text-xs bg-gray-50 border border-gray-200 rounded p-3 whitespace-pre-wrap text-gray-700 max-h-64 overflow-auto">
            {agent.persona_prompt}
          </pre>
        </Section>

        <p className="text-[11px] text-gray-400 mt-4">
          Criado em {new Date(agent.created_at).toLocaleString('pt-BR')} ·
          Tipo: {agent.agent_type === 'fixed_specialist' ? 'Especialista fixo' : 'Gerado do grafo'}
        </p>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{title}</h3>
      {children}
    </div>
  )
}
