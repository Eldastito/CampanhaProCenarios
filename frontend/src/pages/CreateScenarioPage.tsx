import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  PoliticalProject,
  politicalProjectsApi,
  scenariosApi,
} from '../api/client'
import Layout from '../components/Layout'
import { FactorGroup } from '../components/FactorInput'
import { useAuth } from '../contexts/AuthContext'
import { SCENARIO_CATALOG, defaultFactors, getScenarioTypeDef } from '../scenarioCatalog'

export default function CreateScenarioPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  function patchParams(updates: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(updates)) {
      if (v === null || v === '') {
        params.delete(k)
      } else {
        params.set(k, v)
      }
    }
    setSearchParams(params, { replace: true })
  }

  // type e project persistem via URL para sobreviver back/forward.
  const scenarioType = searchParams.get('type') || 'education'
  const selectedProjectId = searchParams.get('project') || ''

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [baseline, setBaseline] = useState<Record<string, number>>(defaultFactors(scenarioType))
  const [alternative, setAlternative] = useState<Record<string, number>>(defaultFactors(scenarioType))
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Fase 2 PRD v2 — import de fatores reais a partir do CampanhaPro.
  const [politicalProjects, setPoliticalProjects] = useState<PoliticalProject[]>([])
  const [importedFactorKeys, setImportedFactorKeys] = useState<Set<string>>(new Set())
  const [importMeta, setImportMeta] = useState<{
    coverage_percent: number
    warnings: string[]
    reference_date: string
    sources_used: Record<string, string[]>
  } | null>(null)
  const [importing, setImporting] = useState(false)
  const [importMessage, setImportMessage] = useState<string | null>(null)

  useEffect(() => {
    if (scenarioType !== 'electoral') return
    politicalProjectsApi
      .list()
      .then(setPoliticalProjects)
      .catch(() => setPoliticalProjects([]))
  }, [scenarioType])

  function handleTypeChange(type: string) {
    patchParams({ type: type === 'education' ? null : type })
    setBaseline(defaultFactors(type))
    setAlternative(defaultFactors(type))
    setImportedFactorKeys(new Set())
    setImportMeta(null)
    setImportMessage(null)
  }

  function handleProjectChange(id: string) {
    patchParams({ project: id || null })
  }

  async function handleImportFromCampanhaPro() {
    if (!selectedProjectId) return
    setImporting(true)
    setImportMessage(null)
    try {
      const data = await politicalProjectsApi.getLatestFactors(selectedProjectId)
      // Pré-preenche tanto baseline quanto alternativo com fatores reais.
      // O usuário ajusta o alternativo manualmente para projetar mudanças.
      setBaseline((prev) => ({ ...prev, ...data.factors }))
      setAlternative((prev) => ({ ...prev, ...data.factors }))
      setImportedFactorKeys(new Set(Object.keys(data.factors)))
      setImportMeta({
        coverage_percent: data.coverage_percent,
        warnings: data.warnings,
        reference_date: data.reference_date,
        sources_used: data.sources_used,
      })
      setImportMessage(
        `${Object.keys(data.factors).length} fatores importados. Cobertura ${data.coverage_percent.toFixed(1)}%.`,
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Falha ao importar.'
      // 404 = sem snapshot ainda → mensagem amigável
      if (msg.includes('Nenhum snapshot') || msg.includes('404')) {
        setImportMessage(
          'Nenhum snapshot CampanhaPro processado para esta campanha ainda. Envie um snapshot v1 antes.',
        )
      } else {
        setImportMessage(msg)
      }
    } finally {
      setImporting(false)
    }
  }

  function setBaselineFactor(factor: string, value: number) {
    setBaseline((prev) => ({ ...prev, [factor]: value }))
  }

  function setAlternativeFactor(factor: string, value: number) {
    setAlternative((prev) => ({ ...prev, [factor]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!user) return
    setError(null)
    setLoading(true)
    try {
      const scenario = await scenariosApi.create({
        organization_id: user.organization_id,
        name,
        description: description || undefined,
        scenario_type: scenarioType,
        baseline_inputs: baseline,
        alternative_inputs: alternative,
      })
      await scenariosApi.run(scenario.scenario_id, false, 'initial_run')
      navigate(`/scenarios/${scenario.scenario_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar cenário.')
    } finally {
      setLoading(false)
    }
  }

  const typeDef = getScenarioTypeDef(scenarioType)

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Novo Cenário</h1>
        <p className="text-gray-500 mt-1">
          Selecione o tipo de cenário e defina os fatores baseline e alternativo.
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Scenario type selector */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Tipo de Cenário</h2>
          <div className="grid grid-cols-3 gap-3">
            {SCENARIO_CATALOG.map((t) => (
              <button
                key={t.type}
                type="button"
                onClick={() => handleTypeChange(t.type)}
                className={`flex flex-col items-start p-4 rounded-lg border-2 text-left transition-all ${
                  scenarioType === t.type
                    ? 'border-brand-500 bg-brand-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <span className="text-2xl mb-2">{t.icon}</span>
                <span className={`text-sm font-semibold ${scenarioType === t.type ? 'text-brand-700' : 'text-gray-800'}`}>
                  {t.label}
                </span>
                <span className="text-xs text-gray-500 mt-1 leading-snug">{t.description}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Import from CampanhaPro — visível apenas para cenários eleitorais */}
        {scenarioType === 'electoral' && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
            <div className="flex items-start justify-between gap-4 mb-3">
              <div>
                <h2 className="text-base font-semibold text-gray-900">
                  Importar do CampanhaPro
                </h2>
                <p className="text-xs text-gray-500 mt-1">
                  Pré-preenche os fatores com base no último snapshot v1 enviado pela campanha.
                </p>
              </div>
              <span className="text-[10px] uppercase tracking-wide bg-indigo-100 text-indigo-700 px-2 py-1 rounded">
                Fase 2
              </span>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-[260px]">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Projeto eleitoral
                </label>
                <select
                  value={selectedProjectId}
                  onChange={(e) => handleProjectChange(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="">— selecione —</option>
                  {politicalProjects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.candidate_name} · {p.office} · {p.election_year}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={handleImportFromCampanhaPro}
                disabled={!selectedProjectId || importing}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-medium py-2 px-4 rounded-lg text-sm transition-colors"
              >
                {importing ? 'Importando…' : '📥 Importar dados do CampanhaPro'}
              </button>
            </div>
            {importMessage && (
              <p className="mt-3 text-sm text-gray-600">{importMessage}</p>
            )}
            {importMeta && (
              <div className="mt-4 p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-xs text-indigo-900">
                <div className="font-semibold mb-1">
                  Cobertura: {importMeta.coverage_percent.toFixed(1)}% · referência:{' '}
                  {new Date(importMeta.reference_date).toLocaleString('pt-BR')}
                </div>
                {importMeta.warnings.length > 0 && (
                  <ul className="list-disc list-inside text-indigo-800">
                    {importMeta.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                )}
                {importedFactorKeys.size > 0 && (
                  <div className="mt-2">
                    Fatores marcados como{' '}
                    <span className="bg-indigo-200 text-indigo-900 px-1.5 py-0.5 rounded">
                      real
                    </span>
                    : {Array.from(importedFactorKeys).join(', ')}.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Basic info */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Informações Gerais</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Nome do Cenário <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder={`Ex: ${typeDef.label} — Cenário Q3 2026`}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                placeholder="Contexto e objetivo do cenário"
              />
            </div>
          </div>
        </div>

        {/* Factors — two columns */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <FactorGroup
              title="Cenário Atual (Baseline)"
              factors={typeDef.factors}
              values={baseline}
              onChange={setBaselineFactor}
            />
          </div>
          <div className="bg-white rounded-xl border border-brand-200 p-6">
            <FactorGroup
              title="Cenário Alternativo (Desejado)"
              factors={typeDef.factors}
              values={alternative}
              onChange={setAlternativeFactor}
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-4">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={loading}
            className="bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-medium py-2.5 px-6 rounded-lg text-sm transition-colors"
          >
            {loading ? 'Criando e executando…' : 'Criar e Executar Cenário'}
          </button>
        </div>
      </form>
    </Layout>
  )
}
