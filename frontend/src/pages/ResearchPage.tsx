import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import {
  researchApi,
  savedResearchApi,
  type CandidateResearch,
  type CompareRejectionResponse,
  type SavedResearchSummary,
} from '../api/client'
import { useAuth } from '../contexts/AuthContext'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CandidateForm {
  name: string
  party: string
  party_abbreviation: string
  office: string
}

const EMPTY_FORM: CandidateForm = { name: '', party: '', party_abbreviation: '', office: '' }

const OFFICES = [
  'Deputado Estadual',
  'Deputado Federal',
  'Senador',
  'Governador',
  'Prefeito',
  'Vereador',
  'Presidente',
]

// ---------------------------------------------------------------------------
// Segment colors for rejection bars
// ---------------------------------------------------------------------------

function rejectionColor(pct: number): string {
  if (pct >= 60) return 'bg-red-500'
  if (pct >= 40) return 'bg-orange-400'
  if (pct >= 25) return 'bg-yellow-400'
  return 'bg-green-400'
}

// ---------------------------------------------------------------------------
// Component: rejection bar chart for one segment group
// ---------------------------------------------------------------------------

function SegmentGroup({
  title,
  data,
}: {
  title: string
  data: Record<string, number>
}) {
  return (
    <div className="mb-4">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">{title}</p>
      <div className="space-y-1">
        {Object.entries(data).map(([label, pct]) => (
          <div key={label} className="flex items-center gap-2">
            <span className="text-xs text-gray-600 w-40 shrink-0 truncate">{label}</span>
            <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden">
              <div
                className={`h-full ${rejectionColor(pct)} rounded transition-all`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs font-mono text-gray-700 w-8 text-right">{pct}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component: full research result card
// ---------------------------------------------------------------------------

function ResearchCard({
  data,
  onUseInGraph,
  onSave,
  saved,
}: {
  data: CandidateResearch
  onUseInGraph: (text: string) => void
  onSave: () => void
  saved: boolean
}) {
  const [section, setSection] = useState<'overview' | 'rejection' | 'sources'>('overview')
  const bySegment = data.rejection_profile?.by_segment ?? {}
  const overallRejection = data.rejection_profile?.overall_rejection

  const sections = [
    { id: 'overview' as const, label: 'Perfil completo' },
    { id: 'rejection' as const, label: 'Rejeição por segmento' },
    { id: 'sources' as const, label: `Fontes (${data.sources?.length ?? 0})` },
  ]

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-800 text-white px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold">{data.name}</h2>
            <p className="text-gray-300 text-sm mt-0.5">
              {data.party_abbreviation} · {data.party} · {data.office}
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {overallRejection !== null && overallRejection !== undefined && (
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-400">{overallRejection}%</div>
                <div className="text-xs text-gray-400">rejeição geral</div>
              </div>
            )}
            <div className="flex flex-col gap-2">
              <button
                onClick={() => onUseInGraph(data.graph_context_text)}
                className="bg-brand-600 hover:bg-brand-700 text-white text-sm px-4 py-2 rounded-lg font-medium transition-colors"
              >
                Usar no Grafo
              </button>
              <button
                onClick={onSave}
                disabled={saved}
                className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:opacity-70 text-white text-sm px-4 py-2 rounded-lg font-medium transition-colors"
              >
                {saved ? '✓ Salvo' : '💾 Salvar'}
              </button>
            </div>
          </div>
        </div>
        {!data.search_performed && (
          <p className="text-xs text-yellow-300 mt-2">
            ⚠ Pesquisa baseada no conhecimento do modelo — sem busca em tempo real
          </p>
        )}
        {data.search_performed && (
          <p className="text-xs text-green-300 mt-2">
            ✓ Pesquisado na internet em tempo real
          </p>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200">
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            className={`px-5 py-2.5 text-sm font-medium transition-colors ${
              section === s.id
                ? 'border-b-2 border-brand-600 text-brand-700'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-6">
        {section === 'overview' && (
          <div className="space-y-5">
            {[
              { key: 'background', title: 'Origem e Formação' },
              { key: 'political_history', title: 'Histórico Político' },
              { key: 'current_mandates', title: 'Mandatos' },
              { key: 'platform_and_goals', title: 'Plataforma e Propostas' },
              { key: 'recent_news', title: 'Notícias Recentes' },
              { key: 'legal_issues', title: 'Questões Legais e Judiciais' },
              { key: 'ficha_limpa_status', title: 'Ficha Limpa' },
            ].map(({ key, title }) => {
              const value = (data as unknown as Record<string, unknown>)[key] as string
              if (!value) return null
              return (
                <div key={key}>
                  <h3 className="text-sm font-semibold text-gray-800 mb-1">{title}</h3>
                  <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">{value}</p>
                </div>
              )
            })}
          </div>
        )}

        {section === 'rejection' && (
          <div>
            {data.rejection_profile?.key_weaknesses?.length > 0 && (
              <div className="mb-5 p-3 bg-red-50 rounded-lg border border-red-100">
                <p className="text-xs font-semibold text-red-700 mb-1">Principais vulnerabilidades</p>
                <ul className="text-sm text-red-600 space-y-0.5">
                  {data.rejection_profile.key_weaknesses.map((w: string, i: number) => (
                    <li key={i}>• {w}</li>
                  ))}
                </ul>
              </div>
            )}
            {data.rejection_profile?.key_strengths?.length > 0 && (
              <div className="mb-5 p-3 bg-green-50 rounded-lg border border-green-100">
                <p className="text-xs font-semibold text-green-700 mb-1">Grupos mais favoráveis</p>
                <ul className="text-sm text-green-600 space-y-0.5">
                  {data.rejection_profile.key_strengths.map((s: string, i: number) => (
                    <li key={i}>• {s}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {Object.entries(bySegment).map(([segKey, segData]) => {
                const titles: Record<string, string> = {
                  region: 'Região',
                  sex: 'Sexo',
                  income: 'Renda familiar',
                  age: 'Faixa etária',
                  education: 'Escolaridade',
                  religion: 'Religião',
                  employment: 'Situação trabalhista',
                  aid: 'Beneficiário de auxílio',
                }
                return (
                  <SegmentGroup
                    key={segKey}
                    title={titles[segKey] || segKey}
                    data={segData as Record<string, number>}
                  />
                )
              })}
            </div>
          </div>
        )}

        {section === 'sources' && (
          <div className="space-y-3">
            {(!data.sources || data.sources.length === 0) && (
              <p className="text-sm text-gray-500 italic">
                Nenhuma fonte verificável encontrada. Informações baseadas no conhecimento do modelo.
              </p>
            )}
            {data.sources?.map((src, i) => (
              <div key={i} className="p-3 border border-gray-200 rounded-lg">
                <a
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-brand-700 hover:underline"
                >
                  {src.title}
                </a>
                {src.url && (
                  <p className="text-xs text-gray-400 mt-0.5 truncate">{src.url}</p>
                )}
                {src.snippet && (
                  <p className="text-xs text-gray-600 mt-1 leading-relaxed">{src.snippet}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component: comparative rejection chart
// ---------------------------------------------------------------------------

function CompareRejectionView({ data }: { data: CompareRejectionResponse }) {
  const [activeSegment, setActiveSegment] = useState<string>('region')

  const segmentTitles: Record<string, string> = {
    region: 'Região',
    sex: 'Sexo',
    income: 'Renda familiar',
    age: 'Faixa etária',
    education: 'Escolaridade',
    religion: 'Religião',
    employment: 'Situação trabalhista',
    aid: 'Beneficiário de auxílio',
  }

  const CANDIDATE_COLORS = ['bg-blue-500', 'bg-purple-500', 'bg-pink-500', 'bg-orange-500', 'bg-teal-500']
  const CANDIDATE_TEXT = ['text-blue-700', 'text-purple-700', 'text-pink-700', 'text-orange-700', 'text-teal-700']

  if (!data.candidates || data.candidates.length === 0) {
    return <p className="text-sm text-gray-500">Nenhum dado de comparação disponível.</p>
  }

  // Gather all subcategories for the active segment
  const firstCandidateSegment = data.candidates[0]?.rejection_by_segment?.[activeSegment] ?? {}
  const subcategories = Object.keys(firstCandidateSegment)

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 mb-4">Comparação de Rejeição</h2>

      {data.analysis && (
        <div className="mb-5 p-3 bg-gray-50 rounded-lg text-sm text-gray-600 leading-relaxed">
          {data.analysis}
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mb-5">
        {data.candidates.map((c, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className={`inline-block w-3 h-3 rounded-full ${CANDIDATE_COLORS[i % CANDIDATE_COLORS.length]}`} />
            <span className={`text-sm font-medium ${CANDIDATE_TEXT[i % CANDIDATE_TEXT.length]}`}>
              {c.name}
            </span>
            {c.overall_rejection != null && (
              <span className="text-xs text-gray-400">({c.overall_rejection}% geral)</span>
            )}
          </div>
        ))}
      </div>

      {/* Segment tabs */}
      <div className="flex flex-wrap gap-2 mb-5">
        {Object.entries(segmentTitles).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveSegment(key)}
            className={`text-xs px-3 py-1 rounded-full font-medium transition-colors ${
              activeSegment === key
                ? 'bg-brand-700 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Bars */}
      <div className="space-y-3">
        {subcategories.map((subcat) => (
          <div key={subcat}>
            <p className="text-xs font-medium text-gray-500 mb-1">{subcat}</p>
            <div className="space-y-1">
              {data.candidates.map((c, i) => {
                const pct = c.rejection_by_segment?.[activeSegment]?.[subcat] ?? 0
                return (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 w-28 shrink-0 truncate">{c.name}</span>
                    <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden">
                      <div
                        className={`h-full ${CANDIDATE_COLORS[i % CANDIDATE_COLORS.length]} rounded transition-all opacity-80`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-gray-700 w-8 text-right">{pct}%</span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ResearchPage() {
  const { user } = useAuth()
  const [forms, setForms] = useState<CandidateForm[]>([{ ...EMPTY_FORM }])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<CandidateResearch[]>([])
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set())
  const [compareData, setCompareData] = useState<CompareRejectionResponse | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [savedList, setSavedList] = useState<SavedResearchSummary[]>([])
  const [showSaved, setShowSaved] = useState(false)

  useEffect(() => {
    if (user) loadSavedList()
  }, [user]) // eslint-disable-line react-hooks/exhaustive-deps

  async function loadSavedList() {
    if (!user) return
    try {
      const data = await savedResearchApi.list(user.organization_id)
      setSavedList(data.items)
    } catch { /* silent */ }
  }

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  function updateForm(idx: number, field: keyof CandidateForm, value: string) {
    setForms((prev) => prev.map((f, i) => (i === idx ? { ...f, [field]: value } : f)))
  }

  function addCandidate() {
    if (forms.length < 5) setForms((prev) => [...prev, { ...EMPTY_FORM }])
  }

  function removeCandidate(idx: number) {
    setForms((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleResearch() {
    const valid = forms.filter((f) => f.name.trim() && f.party.trim() && f.office.trim())
    if (valid.length === 0) {
      setError('Preencha pelo menos o nome, partido e cargo pretendido.')
      return
    }
    setError(null)
    setLoading(true)
    setResults([])
    setSavedIds(new Set())
    setCompareData(null)

    try {
      const researched = await Promise.all(
        valid.map((f) =>
          researchApi.candidate({
            name: f.name.trim(),
            party: f.party.trim(),
            party_abbreviation: f.party_abbreviation.trim() || f.party.trim(),
            office: f.office.trim(),
          })
        )
      )
      setResults(researched)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao pesquisar candidatos.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveResult(idx: number) {
    if (!user) return
    const r = results[idx]
    try {
      await savedResearchApi.save({
        organization_id: user.organization_id,
        name: `${r.name} — ${r.office}`,
        candidate_name: r.name,
        party: r.party,
        party_abbreviation: r.party_abbreviation,
        office: r.office,
        search_performed: r.search_performed,
        political_history: r.political_history,
        current_mandates: r.current_mandates,
        platform_and_goals: r.platform_and_goals,
        recent_news: r.recent_news,
        legal_issues: r.legal_issues,
        ficha_limpa_status: r.ficha_limpa_status,
        background: r.background,
        rejection_profile: r.rejection_profile,
        graph_context_text: r.graph_context_text,
        sources: r.sources,
      })
      setSavedIds((prev) => new Set([...prev, idx]))
      showToast(`✓ Pesquisa de ${r.name} salva!`)
      loadSavedList()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar pesquisa.')
    }
  }

  async function handleDeleteSaved(id: string) {
    try {
      await savedResearchApi.delete(id)
      setSavedList((prev) => prev.filter((r) => r.id !== id))
    } catch { /* silent */ }
  }

  async function handleCompare() {
    if (results.length < 2) return
    setCompareLoading(true)
    try {
      const resp = await researchApi.compare(
        results.map((r) => ({
          name: r.name,
          party: r.party,
          party_abbreviation: r.party_abbreviation,
          office: r.office,
        }))
      )
      setCompareData(resp)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao comparar candidatos.')
    } finally {
      setCompareLoading(false)
    }
  }

  function handleUseInGraph(text: string) {
    navigator.clipboard.writeText(text).catch(() => {})
    showToast('✓ Texto copiado — cole na janela de contexto do Grafo')
  }

  return (
    <Layout>
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Agente de Pesquisa Política</h1>
            <p className="text-gray-500 text-sm mt-1">
              Pesquise candidatos com IA — histórico, propostas, ficha limpa, processos e perfil de rejeição
            </p>
          </div>
          <button
            onClick={() => setShowSaved((v) => !v)}
            className="border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm px-4 py-2 rounded-lg transition-colors"
          >
            📂 Pesquisas salvas ({savedList.length})
          </button>
        </div>

        {/* Saved list panel */}
        {showSaved && (
          <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-3">Pesquisas Salvas</h2>
            {savedList.length === 0 && (
              <p className="text-sm text-gray-400">Nenhuma pesquisa salva ainda.</p>
            )}
            <div className="space-y-2">
              {savedList.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{r.candidate_name}</p>
                    <p className="text-xs text-gray-500">{r.party_abbreviation} · {r.office} · {new Date(r.created_at).toLocaleDateString('pt-BR')}</p>
                  </div>
                  <button
                    onClick={() => handleDeleteSaved(r.id)}
                    className="text-xs text-gray-400 hover:text-red-500 px-2 py-1 rounded transition-colors"
                  >
                    🗑
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Candidate forms */}
        <div className="space-y-4 mb-6">
          {forms.map((form, idx) => (
            <div key={idx} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-800 text-sm">Candidato {idx + 1}</h3>
                {forms.length > 1 && (
                  <button onClick={() => removeCandidate(idx)} className="text-xs text-gray-400 hover:text-red-500 transition-colors">
                    Remover
                  </button>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Nome completo *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => updateForm(idx, 'name', e.target.value)}
                    placeholder="Ex: Maria Silva"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Partido *</label>
                  <input
                    type="text"
                    value={form.party}
                    onChange={(e) => updateForm(idx, 'party', e.target.value)}
                    placeholder="Ex: Partido dos Trabalhadores"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Sigla do partido</label>
                  <input
                    type="text"
                    value={form.party_abbreviation}
                    onChange={(e) => updateForm(idx, 'party_abbreviation', e.target.value)}
                    placeholder="Ex: PT"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Cargo pretendido *</label>
                  <select
                    value={form.office}
                    onChange={(e) => updateForm(idx, 'office', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                  >
                    <option value="">Selecione o cargo</option>
                    {OFFICES.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-3 mb-8">
          {forms.length < 5 && (
            <button
              onClick={addCandidate}
              className="text-sm text-brand-700 border border-brand-300 hover:bg-brand-50 rounded-lg px-4 py-2 transition-colors"
            >
              + Adicionar candidato
            </button>
          )}
          <button
            onClick={handleResearch}
            disabled={loading}
            className="bg-brand-700 hover:bg-brand-800 disabled:opacity-50 text-white font-medium text-sm px-6 py-2 rounded-lg transition-colors"
          >
            {loading ? '🔍 Pesquisando...' : '🔍 Pesquisar candidatos'}
          </button>
          {loading && <p className="text-xs text-gray-500">Aguarde — consultando IA e fontes externas...</p>}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-center justify-between">
            {error}
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-3">✕</button>
          </div>
        )}

        {toast && (
          <div className="fixed bottom-6 right-6 bg-gray-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg z-50">
            {toast}
          </div>
        )}

        {results.length > 0 && (
          <div className="space-y-6">
            {results.map((r, i) => (
              <ResearchCard
                key={i}
                data={r}
                onUseInGraph={handleUseInGraph}
                onSave={() => handleSaveResult(i)}
                saved={savedIds.has(i)}
              />
            ))}

            {results.length >= 2 && (
              <div className="flex justify-center">
                <button
                  onClick={handleCompare}
                  disabled={compareLoading}
                  className="bg-purple-700 hover:bg-purple-800 disabled:opacity-50 text-white font-medium text-sm px-6 py-2 rounded-lg transition-colors"
                >
                  {compareLoading ? '📊 Gerando comparação...' : '📊 Comparar rejeição entre candidatos'}
                </button>
              </div>
            )}

            {compareData && <CompareRejectionView data={compareData} />}
          </div>
        )}
      </div>
    </Layout>
  )
}
