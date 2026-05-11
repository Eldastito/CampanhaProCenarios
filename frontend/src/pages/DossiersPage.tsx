import { FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import {
  CandidateDossierCreatePayload,
  CandidateDossierSummary,
  DossierStatus,
  dossiersApi,
  PoliticalProject,
  politicalProjectsApi,
} from '../api/client'

const STATUS_LABEL: Record<DossierStatus, { label: string; color: string }> = {
  queued: { label: 'na fila', color: 'bg-gray-100 text-gray-700 border-gray-200' },
  running: {
    label: 'gerando…',
    color: 'bg-amber-100 text-amber-700 border-amber-200',
  },
  ready: {
    label: 'pronto',
    color: 'bg-green-100 text-green-700 border-green-200',
  },
  failed: {
    label: 'falhou',
    color: 'bg-red-100 text-red-700 border-red-200',
  },
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

export default function DossiersPage() {
  const { projectId = '' } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<PoliticalProject | null>(null)
  const [dossiers, setDossiers] = useState<CandidateDossierSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [proj, list] = await Promise.all([
        politicalProjectsApi.get(projectId),
        dossiersApi.list(projectId),
      ])
      setProject(proj)
      setDossiers(list)
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

  // Polling leve enquanto há dossiês com status queued/running.
  useEffect(() => {
    const pending = dossiers.some((d) => d.status === 'queued' || d.status === 'running')
    if (!pending) return
    const t = setInterval(() => {
      dossiersApi
        .list(projectId)
        .then(setDossiers)
        .catch(() => undefined)
    }, 4000)
    return () => clearInterval(t)
  }, [dossiers, projectId])

  return (
    <Layout>
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dossiês de Candidato</h1>
          <p className="text-sm text-gray-600 mt-1">
            {project ? (
              <>
                Projeto: <span className="font-medium">{project.name}</span> · {project.office} ·{' '}
                {project.election_year}
              </>
            ) : (
              'Carregando…'
            )}
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
        >
          + Novo dossiê
        </button>
      </div>

      <div className="my-4 p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 text-xs">
        ⚠ Os dossiês são gerados por IA com base em fontes públicas (TSE, mídia,
        redes). Sempre verifique informações sensíveis antes de uso operacional.
        Cada item traz a fonte na aba “Fontes”.
      </div>

      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}

      <div className="mb-4">
        <Link
          to={`/political/projects`}
          className="text-xs text-gray-500 hover:underline"
        >
          ← voltar para projetos
        </Link>
      </div>

      {loading ? (
        <p className="text-gray-500">Carregando…</p>
      ) : dossiers.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center">
          <p className="text-gray-600">Nenhum dossiê ainda.</p>
          <p className="text-sm text-gray-500 mt-1">
            Crie o dossiê do seu candidato (próprio) e dos 3-5 adversários diretos
            para alimentar a análise estratégica.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {dossiers.map((d) => (
            <DossierCard key={d.id} dossier={d} projectId={projectId} />
          ))}
        </div>
      )}

      {showForm && (
        <CreateDossierModal
          projectId={projectId}
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

function DossierCard({
  dossier,
  projectId,
}: {
  dossier: CandidateDossierSummary
  projectId: string
}) {
  const tag = STATUS_LABEL[dossier.status]
  return (
    <Link
      to={`/political/projects/${projectId}/dossiers/${dossier.id}`}
      className="block rounded-lg border border-gray-200 bg-white p-4 hover:shadow-sm transition"
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-gray-900">{dossier.candidate_name}</h3>
        <span
          className={`text-[11px] px-2 py-0.5 rounded border ${tag.color}`}
        >
          {tag.label}
        </span>
      </div>
      <p className="text-sm text-gray-600">
        {dossier.candidate_type === 'own' ? 'Candidato próprio' : 'Adversário'} ·{' '}
        {dossier.party ?? 's/ partido'} · {dossier.office}
      </p>
      <p className="text-xs text-gray-500 mt-2">
        Confiança: {dossier.confidence_level} ·{' '}
        {dossier.last_refreshed_at
          ? `atualizado em ${new Date(dossier.last_refreshed_at).toLocaleString('pt-BR')}`
          : 'ainda não processado'}
      </p>
    </Link>
  )
}

function CreateDossierModal({
  projectId,
  onClose,
  onCreated,
}: {
  projectId: string
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState<CandidateDossierCreatePayload>({
    candidate_name: '',
    candidate_type: 'opponent',
    office: 'Prefeito',
    party: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setErr(null)
    try {
      await dossiersApi.create(projectId, {
        ...form,
        party: form.party || undefined,
      })
      onCreated()
    } catch (e2) {
      setErr((e2 as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <form
        onSubmit={submit}
        className="bg-white rounded-xl w-full max-w-lg p-6 shadow-xl max-h-[90vh] overflow-auto"
      >
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Novo dossiê</h2>
        {err && (
          <div className="mb-3 p-2 rounded bg-red-50 text-red-700 text-xs border border-red-200">
            {err}
          </div>
        )}
        <div className="space-y-3">
          <Field label="Nome do candidato">
            <input
              required
              className="input"
              value={form.candidate_name}
              onChange={(e) => setForm({ ...form, candidate_name: e.target.value })}
              placeholder="ex: João Adversário"
            />
          </Field>
          <Field label="Tipo">
            <select
              className="input"
              value={form.candidate_type}
              onChange={(e) =>
                setForm({
                  ...form,
                  candidate_type: e.target.value as 'own' | 'opponent',
                })
              }
            >
              <option value="own">Candidato próprio</option>
              <option value="opponent">Adversário</option>
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Cargo">
              <select
                className="input"
                value={form.office}
                onChange={(e) => setForm({ ...form, office: e.target.value })}
              >
                {OFFICES.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Partido (opcional)">
              <input
                className="input"
                value={form.party ?? ''}
                onChange={(e) => setForm({ ...form, party: e.target.value })}
                placeholder="ex: PT, PL, PSDB"
              />
            </Field>
          </div>
          <Field label="ID TSE (opcional)">
            <input
              className="input"
              value={form.tse_candidate_id ?? ''}
              onChange={(e) =>
                setForm({ ...form, tse_candidate_id: e.target.value || null })
              }
              placeholder="número do registro no TSE"
            />
          </Field>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={submitting || !form.candidate_name}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? 'Criando…' : 'Criar dossiê'}
          </button>
        </div>
      </form>
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
