import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { useAuth } from '../contexts/AuthContext'
import {
  politicalProjectsApi,
  type PoliticalProject,
  type PoliticalProjectCreatePayload,
} from '../api/client'

const STATES = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
  'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
  'SP', 'SE', 'TO',
]

const OFFICES = [
  'Presidente',
  'Governador',
  'Senador',
  'Deputado Federal',
  'Deputado Estadual',
  'Prefeito',
  'Vereador',
]

export default function PoliticalProjectsPage() {
  const { user } = useAuth()
  const [projects, setProjects] = useState<PoliticalProject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const list = await politicalProjectsApi.list()
      setProjects(list)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projetos Eleitorais</h1>
          <p className="text-sm text-gray-600 mt-1">
            Cada projeto agrupa cenários, evidências, agentes e simulações de uma campanha.
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
        >
          + Novo projeto
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Carregando…</p>
      ) : projects.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center">
          <p className="text-gray-600">Nenhum projeto eleitoral ainda.</p>
          <p className="text-sm text-gray-500 mt-1">
            Crie um projeto para começar a anexar evidências e configurar cenários.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}

      {showForm && user && (
        <CreateProjectModal
          orgId={user.organization_id}
          onClose={() => setShowForm(false)}
          onCreated={() => {
            setShowForm(false)
            load()
          }}
        />
      )}
    </Layout>
  )
}

function ProjectCard({ project }: { project: PoliticalProject }) {
  const region = [project.municipality, project.state].filter(Boolean).join(' / ')
  const [sync, setSync] = useState<{
    label: string
    color: string
    coverage: number | null
  } | null>(null)

  // Fase 2 PRD v2 — semáforo de última sincronização CampanhaPro.
  useEffect(() => {
    let alive = true
    politicalProjectsApi
      .getLatestFactors(project.id)
      .then((data) => {
        if (!alive) return
        const ageDays =
          (Date.now() - new Date(data.reference_date).getTime()) / 86_400_000
        let color = 'bg-green-100 text-green-700 border-green-200'
        if (ageDays > 30) color = 'bg-red-100 text-red-700 border-red-200'
        else if (ageDays > 7) color = 'bg-amber-100 text-amber-700 border-amber-200'
        const formatter = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' })
        const days = Math.round(ageDays)
        const label = days <= 0 ? 'agora' : formatter.format(-days, 'day')
        setSync({ label, color, coverage: data.coverage_percent })
      })
      .catch(() => {
        if (!alive) return
        setSync({
          label: 'sem snapshot',
          color: 'bg-gray-100 text-gray-500 border-gray-200',
          coverage: null,
        })
      })
    return () => {
      alive = false
    }
  }, [project.id])

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 hover:shadow-sm transition">
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-gray-900">{project.name}</h3>
        <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
          {project.status}
        </span>
      </div>
      <p className="text-sm text-gray-600">
        {project.candidate_name} · {project.office} · {project.election_year}
      </p>
      {region && <p className="text-xs text-gray-500 mt-1">{region}</p>}
      {project.parties.length > 0 && (
        <p className="text-xs text-gray-500 mt-1">Partidos: {project.parties.join(', ')}</p>
      )}
      {project.known_opponents.length > 0 && (
        <p className="text-xs text-gray-500 mt-1">
          Adversários: {project.known_opponents.slice(0, 3).join(', ')}
          {project.known_opponents.length > 3 ? '…' : ''}
        </p>
      )}
      {sync && (
        <div className="mt-2">
          <span
            className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border ${sync.color}`}
            title={
              sync.coverage !== null
                ? `Cobertura: ${sync.coverage.toFixed(1)}%`
                : 'Envie um snapshot v1 do CampanhaPro para esta campanha'
            }
          >
            sync CampanhaPro: {sync.label}
            {sync.coverage !== null && (
              <span className="opacity-70">· {sync.coverage.toFixed(0)}%</span>
            )}
          </span>
        </div>
      )}
      <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-3">
        <Link
          to={`/political/projects/${project.id}/evidence`}
          className="text-xs text-brand-700 hover:underline"
        >
          📄 Evidências
        </Link>
        <Link
          to={`/political/projects/${project.id}/graph`}
          className="text-xs text-brand-700 hover:underline"
        >
          🕸 Grafo Político
        </Link>
        <Link
          to={`/political/projects/${project.id}/agents`}
          className="text-xs text-brand-700 hover:underline"
        >
          🧑‍⚖️ Bancada de Agentes
        </Link>
        <Link
          to={`/political/projects/${project.id}/dossiers`}
          className="text-xs text-brand-700 hover:underline"
        >
          🗂 Dossiês
        </Link>
        <Link
          to={`/political/projects/${project.id}/election-probability`}
          className="text-xs text-brand-700 hover:underline"
        >
          🎲 Probabilidade
        </Link>
      </div>
    </div>
  )
}

function CreateProjectModal({
  orgId,
  onClose,
  onCreated,
}: {
  orgId: string
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState<PoliticalProjectCreatePayload>({
    organization_id: orgId,
    name: '',
    election_year: new Date().getFullYear(),
    office: 'Prefeito',
    candidate_name: '',
    parties: [],
    known_opponents: [],
  })
  const [partiesText, setPartiesText] = useState('')
  const [opponentsText, setOpponentsText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function submit() {
    setSubmitting(true)
    setErr(null)
    try {
      await politicalProjectsApi.create({
        ...form,
        parties: partiesText.split(',').map((s) => s.trim()).filter(Boolean),
        known_opponents: opponentsText.split(',').map((s) => s.trim()).filter(Boolean),
      })
      onCreated()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl w-full max-w-lg p-6 shadow-xl max-h-[90vh] overflow-auto">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Novo projeto eleitoral</h2>
        {err && (
          <div className="mb-3 p-2 rounded bg-red-50 text-red-700 text-xs border border-red-200">{err}</div>
        )}
        <div className="space-y-3">
          <Field label="Nome do projeto">
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="ex: Campanha Prefeitura X 2026"
            />
          </Field>
          <Field label="Candidato principal">
            <input
              className="input"
              value={form.candidate_name}
              onChange={(e) => setForm({ ...form, candidate_name: e.target.value })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Cargo">
              <select
                className="input"
                value={form.office}
                onChange={(e) => setForm({ ...form, office: e.target.value })}
              >
                {OFFICES.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </Field>
            <Field label="Ano eleitoral">
              <input
                type="number"
                className="input"
                value={form.election_year}
                onChange={(e) => setForm({ ...form, election_year: Number(e.target.value) || 0 })}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Estado (UF)">
              <select
                className="input"
                value={form.state ?? ''}
                onChange={(e) => setForm({ ...form, state: e.target.value || null })}
              >
                <option value="">—</option>
                {STATES.map((uf) => (
                  <option key={uf} value={uf}>{uf}</option>
                ))}
              </select>
            </Field>
            <Field label="Município">
              <input
                className="input"
                value={form.municipality ?? ''}
                onChange={(e) => setForm({ ...form, municipality: e.target.value || null })}
              />
            </Field>
          </div>
          <Field label="Partidos / Coligação (separar por vírgula)">
            <input
              className="input"
              value={partiesText}
              onChange={(e) => setPartiesText(e.target.value)}
              placeholder="ex: Partido A, Partido B"
            />
          </Field>
          <Field label="Adversários conhecidos (separar por vírgula)">
            <input
              className="input"
              value={opponentsText}
              onChange={(e) => setOpponentsText(e.target.value)}
            />
          </Field>
          <Field label="Objetivo do cenário">
            <textarea
              className="input min-h-[70px]"
              value={form.objective ?? ''}
              onChange={(e) => setForm({ ...form, objective: e.target.value })}
              placeholder="ex: avaliar impacto de pauta econômica em municípios do interior"
            />
          </Field>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            onClick={submit}
            disabled={submitting || !form.name || !form.candidate_name}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? 'Criando…' : 'Criar projeto'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-gray-700">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  )
}
