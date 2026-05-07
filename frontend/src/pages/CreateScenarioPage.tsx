import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { scenariosApi } from '../api/client'
import Layout from '../components/Layout'
import { FactorGroup } from '../components/FactorInput'
import { useAuth } from '../contexts/AuthContext'
import { SCENARIO_CATALOG, defaultFactors, getScenarioTypeDef } from '../scenarioCatalog'

export default function CreateScenarioPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [scenarioType, setScenarioType] = useState('education')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [baseline, setBaseline] = useState<Record<string, number>>(defaultFactors('education'))
  const [alternative, setAlternative] = useState<Record<string, number>>(defaultFactors('education'))
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function handleTypeChange(type: string) {
    setScenarioType(type)
    setBaseline(defaultFactors(type))
    setAlternative(defaultFactors(type))
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
