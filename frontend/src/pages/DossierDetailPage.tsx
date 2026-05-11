import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import {
  CandidateDossier,
  DossierSocialSnapshot,
  SocialPlatform,
  SocialSnapshotCreatePayload,
  dossiersApi,
} from '../api/client'

type Tab =
  | 'resumo'
  | 'propostas'
  | 'historico'
  | 'midia'
  | 'redes'
  | 'juridico'
  | 'drivers'
  | 'fontes'

const TABS: { key: Tab; label: string }[] = [
  { key: 'resumo', label: 'Resumo' },
  { key: 'propostas', label: 'Propostas' },
  { key: 'historico', label: 'Histórico' },
  { key: 'midia', label: 'Mídia' },
  { key: 'redes', label: 'Redes Sociais' },
  { key: 'juridico', label: 'Jurídico' },
  { key: 'drivers', label: 'Drivers' },
  { key: 'fontes', label: 'Fontes' },
]

const TAB_KEYS = TABS.map((t) => t.key) as Tab[]

function isTab(value: string | null): value is Tab {
  return value !== null && (TAB_KEYS as string[]).includes(value)
}

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  queued: { label: 'na fila', color: 'bg-gray-100 text-gray-700 border-gray-200' },
  running: {
    label: 'gerando…',
    color: 'bg-amber-100 text-amber-700 border-amber-200',
  },
  ready: { label: 'pronto', color: 'bg-green-100 text-green-700 border-green-200' },
  failed: { label: 'falhou', color: 'bg-red-100 text-red-700 border-red-200' },
}

export default function DossierDetailPage() {
  const { projectId = '', dossierId = '' } = useParams<{
    projectId: string
    dossierId: string
  }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [dossier, setDossier] = useState<CandidateDossier | null>(null)
  const [snapshots, setSnapshots] = useState<DossierSocialSnapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Aba ativa vem de ?tab=… para sobreviver a navegação back/forward.
  const tabParam = searchParams.get('tab')
  const tab: Tab = isTab(tabParam) ? tabParam : 'resumo'
  function setTab(next: Tab) {
    const params = new URLSearchParams(searchParams)
    if (next === 'resumo') {
      params.delete('tab')
    } else {
      params.set('tab', next)
    }
    setSearchParams(params, { replace: true })
  }
  const [refreshing, setRefreshing] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [d, snaps] = await Promise.all([
        dossiersApi.get(projectId, dossierId),
        dossiersApi.listSocialSnapshots(projectId, dossierId),
      ])
      setDossier(d)
      setSnapshots(snaps)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (projectId && dossierId) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, dossierId])

  // Polling enquanto status estiver pendente.
  useEffect(() => {
    if (!dossier) return
    if (dossier.status !== 'queued' && dossier.status !== 'running') return
    const t = setInterval(() => {
      dossiersApi
        .get(projectId, dossierId)
        .then(setDossier)
        .catch(() => undefined)
    }, 3000)
    return () => clearInterval(t)
  }, [dossier, projectId, dossierId])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await dossiersApi.refresh(projectId, dossierId)
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRefreshing(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Apagar este dossiê?')) return
    await dossiersApi.remove(projectId, dossierId)
    navigate(`/political/projects/${projectId}/dossiers`)
  }

  if (loading) {
    return (
      <Layout>
        <p className="text-gray-500">Carregando…</p>
      </Layout>
    )
  }

  if (error || !dossier) {
    return (
      <Layout>
        <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error ?? 'Dossiê não encontrado.'}
        </div>
        <Link
          to={`/political/projects/${projectId}/dossiers`}
          className="text-xs text-gray-500 hover:underline mt-3 inline-block"
        >
          ← voltar para lista
        </Link>
      </Layout>
    )
  }

  const tag = STATUS_BADGE[dossier.status] ?? STATUS_BADGE.queued

  return (
    <Layout>
      <div className="mb-2">
        <Link
          to={`/political/projects/${projectId}/dossiers`}
          className="text-xs text-gray-500 hover:underline"
        >
          ← voltar para lista
        </Link>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-gray-900">
              {dossier.candidate_name}
            </h1>
            <span className={`text-[11px] px-2 py-0.5 rounded border ${tag.color}`}>
              {tag.label}
            </span>
            <span className="text-[10px] uppercase tracking-wide bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">
              {dossier.candidate_type === 'own' ? 'próprio' : 'adversário'}
            </span>
          </div>
          <p className="text-sm text-gray-600 mt-1">
            {dossier.party ?? 's/ partido'} · {dossier.office} · confiança:{' '}
            {dossier.confidence_level}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {dossier.last_refreshed_at
              ? `Atualizado em ${new Date(dossier.last_refreshed_at).toLocaleString('pt-BR')}`
              : 'Ainda não processado'}
            {dossier.llm_models_used.length > 0 && (
              <> · modelo: {dossier.llm_models_used.join(', ')}</>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="px-3 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {refreshing ? 'Atualizando…' : '↻ Atualizar dossiê'}
          </button>
          <button
            onClick={handleDelete}
            className="px-3 py-2 text-sm rounded-lg border border-red-200 text-red-700 hover:bg-red-50"
          >
            Apagar
          </button>
        </div>
      </div>

      <div className="my-3 p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 text-xs">
        ⚠ Conteúdo gerado por IA com base em fontes públicas. Sempre verifique
        informações sensíveis antes de uso operacional. FATO / INFERÊNCIA /
        HIPÓTESE estão marcados quando aplicável.
      </div>

      {dossier.status === 'failed' && dossier.error_message && (
        <div className="my-3 p-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-xs">
          Falha na geração: {dossier.error_message}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mt-6 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-sm border-b-2 -mb-px ${
              tab === t.key
                ? 'border-brand-600 text-brand-700 font-medium'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {tab === 'resumo' && <ResumoTab dossier={dossier} />}
        {tab === 'propostas' && <PropostasTab dossier={dossier} />}
        {tab === 'historico' && <HistoricoTab dossier={dossier} />}
        {tab === 'midia' && <MidiaTab dossier={dossier} />}
        {tab === 'redes' && (
          <RedesTab
            dossier={dossier}
            snapshots={snapshots}
            projectId={projectId}
            dossierId={dossierId}
            onAdded={load}
          />
        )}
        {tab === 'juridico' && <JuridicoTab dossier={dossier} />}
        {tab === 'drivers' && <DriversTab dossier={dossier} />}
        {tab === 'fontes' && <FontesTab dossier={dossier} />}
      </div>
    </Layout>
  )
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
      <h2 className="text-sm font-semibold text-gray-900 mb-3">{title}</h2>
      {children}
    </section>
  )
}

function EmptyHint({ children }: { children?: React.ReactNode }) {
  return (
    <p className="text-xs text-gray-500 italic">
      {children ?? 'Sem dado coletado nesta seção.'}
    </p>
  )
}

function ResumoTab({ dossier }: { dossier: CandidateDossier }) {
  const swot = (dossier.swot ?? {}) as Record<string, unknown>
  const hasSwot = Object.values(swot).some(
    (v) => Array.isArray(v) && (v as unknown[]).length > 0,
  )

  return (
    <>
      <Card title="Biografia">
        {dossier.biography ? (
          <p className="text-sm text-gray-700 whitespace-pre-wrap">
            {dossier.biography}
          </p>
        ) : (
          <EmptyHint>Biografia ainda não consolidada.</EmptyHint>
        )}
      </Card>

      <Card title="Mandatos atuais">
        {dossier.current_mandates && dossier.current_mandates.length > 0 ? (
          <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
            {dossier.current_mandates.map((m, i) => (
              <li key={i}>{String(m)}</li>
            ))}
          </ul>
        ) : (
          <EmptyHint />
        )}
      </Card>

      <Card title="Ficha Limpa">
        {dossier.ficha_limpa_status ? (
          <span className="inline-block text-sm bg-green-100 text-green-800 px-2 py-1 rounded">
            {dossier.ficha_limpa_status}
          </span>
        ) : (
          <EmptyHint>Status não verificado.</EmptyHint>
        )}
      </Card>

      <Card title="SWOT">
        {hasSwot ? (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <SwotBlock label="Forças" items={swot.strengths as unknown[]} color="green" />
            <SwotBlock label="Fraquezas" items={swot.weaknesses as unknown[]} color="amber" />
            <SwotBlock label="Oportunidades" items={swot.opportunities as unknown[]} color="indigo" />
            <SwotBlock label="Ameaças" items={swot.threats as unknown[]} color="red" />
          </div>
        ) : (
          <EmptyHint>SWOT ainda não consolidado pela IA.</EmptyHint>
        )}
      </Card>
    </>
  )
}

function SwotBlock({
  label,
  items,
  color,
}: {
  label: string
  items: unknown[] | undefined
  color: 'green' | 'amber' | 'indigo' | 'red'
}) {
  const cls: Record<typeof color, string> = {
    green: 'bg-green-50 text-green-800 border-green-200',
    amber: 'bg-amber-50 text-amber-800 border-amber-200',
    indigo: 'bg-indigo-50 text-indigo-800 border-indigo-200',
    red: 'bg-red-50 text-red-800 border-red-200',
  }
  return (
    <div className={`rounded border p-3 ${cls[color]}`}>
      <p className="font-semibold text-xs mb-2 uppercase">{label}</p>
      {items && items.length > 0 ? (
        <ul className="list-disc list-inside text-xs space-y-1">
          {items.map((it, i) => (
            <li key={i}>{String(it)}</li>
          ))}
        </ul>
      ) : (
        <p className="text-xs italic opacity-70">—</p>
      )}
    </div>
  )
}

function PropostasTab({ dossier }: { dossier: CandidateDossier }) {
  const p = (dossier.platform_and_proposals ?? {}) as Record<string, unknown>
  const principais = (p.principais as unknown[]) ?? []
  const tom = p.tom as string | undefined
  return (
    <Card title="Plataforma e propostas">
      {principais.length === 0 && !tom ? (
        <EmptyHint />
      ) : (
        <>
          {tom && (
            <p className="text-sm text-gray-600 mb-3">
              <span className="font-medium">Tom:</span> {tom}
            </p>
          )}
          {principais.length > 0 && (
            <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
              {principais.map((it, i) => (
                <li key={i}>{String(it)}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  )
}

function HistoricoTab({ dossier }: { dossier: CandidateDossier }) {
  const h = (dossier.political_history ?? {}) as Record<string, unknown>
  const trajectory = h.trajectory as string | undefined
  const positions = (h.key_positions as unknown[]) ?? []
  if (!trajectory && positions.length === 0) {
    return (
      <Card title="Trajetória política">
        <EmptyHint />
      </Card>
    )
  }
  return (
    <Card title="Trajetória política">
      {trajectory && (
        <p className="text-sm text-gray-700 whitespace-pre-wrap mb-3">
          {trajectory}
        </p>
      )}
      {positions.length > 0 && (
        <>
          <p className="text-xs text-gray-500 uppercase mb-1">Posições-chave</p>
          <ul className="list-disc list-inside text-sm text-gray-700">
            {positions.map((it, i) => (
              <li key={i}>{String(it)}</li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}

function MidiaTab({ dossier }: { dossier: CandidateDossier }) {
  const news = (dossier.recent_news ?? []) as Array<Record<string, unknown>>
  return (
    <Card title="Notícias recentes (últimos 30 dias)">
      {news.length === 0 ? (
        <EmptyHint />
      ) : (
        <ul className="space-y-3">
          {news.map((n, i) => (
            <li key={i} className="border-b border-gray-100 pb-2 last:border-0">
              <a
                href={String(n.url ?? '#')}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-brand-700 hover:underline"
              >
                {String(n.title ?? n.url ?? 'sem título')}
              </a>
              <p className="text-xs text-gray-500 mt-1">
                {String(n.source ?? '')} ·{' '}
                {n.published_at ? new Date(String(n.published_at)).toLocaleDateString('pt-BR') : ''}
              </p>
              {Boolean(n.snippet) && (
                <p className="text-xs text-gray-600 mt-1">{String(n.snippet)}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function RedesTab({
  dossier,
  snapshots,
  projectId,
  dossierId,
  onAdded,
}: {
  dossier: CandidateDossier
  snapshots: DossierSocialSnapshot[]
  projectId: string
  dossierId: string
  onAdded: () => void
}) {
  const [form, setForm] = useState<SocialSnapshotCreatePayload>({
    platform: 'twitter',
    handle: '',
    followers: null,
    posts_last_30d: null,
    engagement_rate: null,
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr(null)
    try {
      await dossiersApi.addSocialSnapshot(projectId, dossierId, form)
      setForm({
        platform: form.platform,
        handle: '',
        followers: null,
        posts_last_30d: null,
        engagement_rate: null,
      })
      onAdded()
    } catch (e2) {
      setErr((e2 as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Card title="Snapshots coletados">
        {snapshots.length === 0 ? (
          <EmptyHint>
            Nenhum snapshot ainda. Use o formulário abaixo para registrar manualmente
            (ou habilite a integração Meta para o candidato próprio).
          </EmptyHint>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-gray-500 uppercase">
              <tr>
                <th className="py-1">Plataforma</th>
                <th>Handle</th>
                <th>Seguidores</th>
                <th>Posts 30d</th>
                <th>Eng. (%)</th>
                <th>Origem</th>
                <th>Coletado</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((s) => (
                <tr key={s.id} className="border-t border-gray-100">
                  <td className="py-1">{s.platform}</td>
                  <td>{s.handle}</td>
                  <td>{s.followers ?? '—'}</td>
                  <td>{s.posts_last_30d ?? '—'}</td>
                  <td>{s.engagement_rate ?? '—'}</td>
                  <td>
                    <span className="text-[10px] uppercase bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                      {s.source}
                    </span>
                  </td>
                  <td className="text-xs text-gray-500">
                    {new Date(s.collected_at).toLocaleDateString('pt-BR')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card
        title={
          dossier.candidate_type === 'opponent'
            ? 'Adicionar snapshot manual (adversário)'
            : 'Adicionar snapshot manual'
        }
      >
        <p className="text-xs text-gray-500 mb-3">
          Sem APIs pagas no MVP. Cole aqui handle e métricas observadas; o snapshot
          fica registrado como <code>source=manual</code>.
        </p>
        {err && (
          <div className="mb-2 p-2 rounded bg-red-50 text-red-700 text-xs border border-red-200">
            {err}
          </div>
        )}
        <form onSubmit={submit} className="grid grid-cols-3 gap-3 text-sm">
          <label className="block">
            <span className="text-xs text-gray-600">Plataforma</span>
            <select
              className="input mt-1"
              value={form.platform}
              onChange={(e) =>
                setForm({ ...form, platform: e.target.value as SocialPlatform })
              }
            >
              <option value="twitter">Twitter / X</option>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="tiktok">TikTok</option>
            </select>
          </label>
          <label className="block col-span-2">
            <span className="text-xs text-gray-600">Handle</span>
            <input
              required
              className="input mt-1"
              value={form.handle}
              onChange={(e) => setForm({ ...form, handle: e.target.value })}
              placeholder="@adversariox"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-600">Seguidores</span>
            <input
              type="number"
              className="input mt-1"
              value={form.followers ?? ''}
              onChange={(e) =>
                setForm({
                  ...form,
                  followers: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-600">Posts (30d)</span>
            <input
              type="number"
              className="input mt-1"
              value={form.posts_last_30d ?? ''}
              onChange={(e) =>
                setForm({
                  ...form,
                  posts_last_30d: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-600">Engajamento (%)</span>
            <input
              type="number"
              step="0.01"
              className="input mt-1"
              value={form.engagement_rate ?? ''}
              onChange={(e) =>
                setForm({
                  ...form,
                  engagement_rate: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
          </label>
          <div className="col-span-3 flex justify-end">
            <button
              type="submit"
              disabled={saving || !form.handle}
              className="px-3 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? 'Salvando…' : 'Adicionar snapshot'}
            </button>
          </div>
        </form>
      </Card>
    </>
  )
}

function JuridicoTab({ dossier }: { dossier: CandidateDossier }) {
  const items = (dossier.legal_issues ?? []) as Array<Record<string, unknown>>
  return (
    <Card title="Questões jurídicas conhecidas">
      {items.length === 0 ? (
        <EmptyHint />
      ) : (
        <ul className="space-y-2 text-sm">
          {items.map((it, i) => (
            <li key={i} className="border-b border-gray-100 pb-2 last:border-0">
              <p className="font-medium text-gray-800">
                {String(it.tipo ?? 'questão')} — {String(it.status ?? '?')}
              </p>
              {Boolean(it.descricao) && (
                <p className="text-xs text-gray-600">{String(it.descricao)}</p>
              )}
              {Boolean(it.fonte_url) && (
                <a
                  href={String(it.fonte_url)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-brand-700 hover:underline"
                >
                  fonte
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function DriversTab({ dossier }: { dossier: CandidateDossier }) {
  return (
    <>
      <Card title="O que sustenta apoio (strength drivers)">
        {dossier.strength_drivers.length === 0 ? (
          <EmptyHint />
        ) : (
          <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
            {dossier.strength_drivers.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="O que sustenta rejeição (rejection drivers)">
        {dossier.rejection_drivers.length === 0 ? (
          <EmptyHint />
        ) : (
          <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
            {dossier.rejection_drivers.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}

function FontesTab({ dossier }: { dossier: CandidateDossier }) {
  const sources = useMemo(
    () => (dossier.sources ?? []).filter(Boolean),
    [dossier.sources],
  )
  return (
    <Card title="Fontes consultadas">
      {sources.length === 0 ? (
        <EmptyHint>
          Sem URLs preservadas — pipeline rodou em modo gracioso (sem APIs externas
          configuradas) ou o consolidador não associou URLs aos dados.
        </EmptyHint>
      ) : (
        <ul className="text-sm space-y-1">
          {sources.map((s, i) => (
            <li key={i}>
              <a
                href={s}
                target="_blank"
                rel="noreferrer"
                className="text-brand-700 hover:underline break-all"
              >
                {s}
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
