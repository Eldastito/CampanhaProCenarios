import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import {
  evidenceApi,
  politicalProjectsApi,
  type PoliticalEvidenceSource,
  type PoliticalProject,
  type ReliabilityLevel,
  type ManualEvidencePayload,
} from '../api/client'

const RELIABILITY_LABEL: Record<ReliabilityLevel, string> = {
  official: 'Oficial',
  press: 'Imprensa',
  registered_poll: 'Pesquisa registrada',
  public_base: 'Base pública',
  internal: 'Interno',
  social: 'Mídia social',
  unverified: 'Não verificada',
}

const RELIABILITY_COLOR: Record<ReliabilityLevel, string> = {
  official: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  press: 'bg-blue-100 text-blue-800 border-blue-300',
  registered_poll: 'bg-indigo-100 text-indigo-800 border-indigo-300',
  public_base: 'bg-cyan-100 text-cyan-800 border-cyan-300',
  internal: 'bg-gray-100 text-gray-800 border-gray-300',
  social: 'bg-amber-100 text-amber-800 border-amber-300',
  unverified: 'bg-red-100 text-red-800 border-red-300',
}

const ACCEPTED_FILES = '.pdf,.txt,.md,.markdown,.csv'

export default function EvidencePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<PoliticalProject | null>(null)
  const [items, setItems] = useState<PoliticalEvidenceSource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [showManualModal, setShowManualModal] = useState(false)

  const load = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    setError(null)
    try {
      const [proj, list] = await Promise.all([
        politicalProjectsApi.get(projectId),
        evidenceApi.list(projectId),
      ])
      setProject(proj)
      setItems(list)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  async function uploadFiles(files: FileList | File[]) {
    if (!projectId) return
    setUploading(true)
    setError(null)
    const list = Array.from(files)
    try {
      for (const f of list) {
        await evidenceApi.upload(projectId, f, { title: f.name })
      }
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <Layout>
      <div className="mb-6">
        <Link to="/political/projects" className="text-sm text-brand-600 hover:underline">
          ← Projetos
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Evidências</h1>
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

      <DropZone disabled={uploading} onFiles={uploadFiles} />

      <div className="flex justify-end mb-3 mt-4">
        <button
          onClick={() => setShowManualModal(true)}
          className="text-sm text-brand-700 hover:underline"
        >
          + Cadastrar manualmente (texto colado ou link)
        </button>
      </div>

      {loading ? (
        <p className="text-gray-500">Carregando…</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center mt-2">
          <p className="text-gray-600">Nenhuma evidência ainda neste projeto.</p>
          <p className="text-sm text-gray-500 mt-1">
            Solte arquivos na área acima ou cadastre uma fonte manualmente.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
          {items.map((e) => (
            <EvidenceCard key={e.id} evidence={e} />
          ))}
        </div>
      )}

      {showManualModal && projectId && (
        <ManualEvidenceModal
          projectId={projectId}
          onClose={() => setShowManualModal(false)}
          onCreated={() => {
            setShowManualModal(false)
            load()
          }}
        />
      )}
    </Layout>
  )
}

function DropZone({ onFiles, disabled }: { onFiles: (f: FileList | File[]) => void; disabled: boolean }) {
  const [over, setOver] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files)
      }}
      className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
        disabled
          ? 'border-gray-200 bg-gray-50 text-gray-400'
          : over
          ? 'border-brand-500 bg-brand-50 text-brand-700'
          : 'border-gray-300 bg-white text-gray-600'
      }`}
    >
      <p className="text-sm">
        {disabled ? (
          'Enviando…'
        ) : (
          <>
            Arraste arquivos PDF, TXT, MD ou CSV aqui — ou{' '}
            <button
              onClick={() => inputRef.current?.click()}
              className="text-brand-700 underline hover:text-brand-800"
              type="button"
            >
              selecione do computador
            </button>
          </>
        )}
      </p>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_FILES}
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.length) onFiles(e.target.files)
          e.target.value = ''
        }}
      />
    </div>
  )
}

function EvidenceCard({ evidence }: { evidence: PoliticalEvidenceSource }) {
  const meta = evidence.metadata_json as { extraction?: { method?: string; page_count?: number } }
  const ext = meta?.extraction
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-gray-900 text-sm leading-snug">{evidence.title}</h3>
        <span
          className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border whitespace-nowrap ${
            RELIABILITY_COLOR[evidence.reliability_level]
          }`}
        >
          {RELIABILITY_LABEL[evidence.reliability_level]}
        </span>
      </div>
      <p className="text-xs text-gray-500">
        {evidence.source_type.toUpperCase()}
        {evidence.source_name ? ` · ${evidence.source_name}` : ''}
        {evidence.author ? ` · ${evidence.author}` : ''}
      </p>
      {evidence.source_url && (
        <a
          href={evidence.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-brand-600 hover:underline break-all"
        >
          {evidence.source_url}
        </a>
      )}
      <p className="text-[11px] text-gray-400 mt-2">
        {ext?.method && <>Extração: {ext.method}</>}
        {ext?.page_count ? ` · ${ext.page_count} páginas` : ''}
        {evidence.processing_status === 'failed' && (
          <span className="text-red-600 ml-1">· falhou: {evidence.processing_error}</span>
        )}
      </p>
    </div>
  )
}

function ManualEvidenceModal({
  projectId,
  onClose,
  onCreated,
}: {
  projectId: string
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState<ManualEvidencePayload>({
    title: '',
    source_type: 'link',
  })
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function submit() {
    setSubmitting(true)
    setErr(null)
    try {
      await evidenceApi.createManual(projectId, form)
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
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Cadastrar evidência manual</h2>
        {err && (
          <div className="mb-3 p-2 rounded bg-red-50 text-red-700 text-xs border border-red-200">{err}</div>
        )}
        <div className="space-y-3">
          <label className="block">
            <span className="text-xs font-medium text-gray-700">Título</span>
            <input
              className="input mt-1"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-gray-700">Tipo</span>
            <select
              className="input mt-1"
              value={form.source_type}
              onChange={(e) =>
                setForm({ ...form, source_type: e.target.value as ManualEvidencePayload['source_type'] })
              }
            >
              <option value="link">Link (URL)</option>
              <option value="manual">Texto colado</option>
              <option value="txt">Texto bruto</option>
              <option value="md">Markdown</option>
            </select>
          </label>
          {form.source_type === 'link' ? (
            <>
              <label className="block">
                <span className="text-xs font-medium text-gray-700">URL</span>
                <input
                  className="input mt-1"
                  value={form.source_url ?? ''}
                  onChange={(e) => setForm({ ...form, source_url: e.target.value })}
                  placeholder="https://..."
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-gray-700">Veículo / instituição</span>
                <input
                  className="input mt-1"
                  value={form.source_name ?? ''}
                  onChange={(e) => setForm({ ...form, source_name: e.target.value })}
                />
              </label>
            </>
          ) : (
            <label className="block">
              <span className="text-xs font-medium text-gray-700">Texto</span>
              <textarea
                className="input mt-1 min-h-[160px]"
                value={form.raw_text ?? ''}
                onChange={(e) => setForm({ ...form, raw_text: e.target.value })}
              />
            </label>
          )}
          <label className="block">
            <span className="text-xs font-medium text-gray-700">Autor (opcional)</span>
            <input
              className="input mt-1"
              value={form.author ?? ''}
              onChange={(e) => setForm({ ...form, author: e.target.value })}
            />
          </label>
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
            disabled={submitting || !form.title || (form.source_type === 'link' ? !form.source_url : !form.raw_text)}
            className="px-4 py-2 text-sm rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
      </div>
    </div>
  )
}
