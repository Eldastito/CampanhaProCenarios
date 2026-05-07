import { useState } from 'react'
import { predictionsApi, savedPredictionsApi } from '../api/client'
import type { PredictionResponse } from '../api/client'
import Layout from '../components/Layout'
import { FactorGroup } from '../components/FactorInput'
import { useAuth } from '../contexts/AuthContext'
import { getScenarioTypeDef } from '../scenarioCatalog'

const ELECTORAL_FACTORS = getScenarioTypeDef('electoral').factors
const DEFAULT_FACTORS = Object.fromEntries(ELECTORAL_FACTORS.map((f) => [f.key, 60]))

type PredictionType = 'acceptance' | 'evasion-risk'

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-medium text-gray-700 w-12 text-right">{pct}%</span>
    </div>
  )
}

export default function PredictionsPage() {
  const { user } = useAuth()
  const [factors, setFactors] = useState<Record<string, number>>({ ...DEFAULT_FACTORS })
  const [type, setType] = useState<PredictionType>('acceptance')
  const [scope, setScope] = useState({ scope_type: 'network', scope_id: '' })
  const [result, setResult] = useState<PredictionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [saveName, setSaveName] = useState('')

  function setFactor(factor: string, value: number) {
    setFactors((prev) => ({ ...prev, [factor]: value }))
  }

  async function handlePredict() {
    if (!user) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const body = {
        organization_id: user.organization_id,
        scope_type: scope.scope_type,
        scope_id: scope.scope_id || user.organization_id,
        factors,
      }
      const data =
        type === 'acceptance'
          ? await predictionsApi.acceptance(body)
          : await predictionsApi.evasionRisk(body)
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao calcular predição.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!user || !result) return
    setSaving(true)
    setSaveSuccess(false)
    try {
      await savedPredictionsApi.save({
        organization_id: user.organization_id,
        name: saveName || `Predição ${new Date().toLocaleDateString('pt-BR')}`,
        prediction_type: result.prediction_type,
        scenario_type: 'education',
        factors,
        result_value: result.value,
        confidence: result.confidence,
        explanation: result.explanation,
      })
      setSaveSuccess(true)
      setShowSaveModal(false)
      setSaveName('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar.')
    } finally {
      setSaving(false)
    }
  }

  const valuePct = result ? Math.round(result.value * 100) : null

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Predições</h1>
        <p className="text-gray-500 mt-1">
          Calcule a probabilidade de aceitação e o risco de evasão com base nos fatores organizacionais.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Controls */}
        <div className="space-y-6">
          {/* Type selector */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Tipo de Predição</h2>
            <div className="flex gap-3">
              {(['acceptance', 'evasion-risk'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => { setType(t); setResult(null) }}
                  className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${
                    type === t
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'border-gray-300 text-gray-600 hover:border-brand-300'
                  }`}
                >
                  {t === 'acceptance' ? 'Aceitação' : 'Risco de Evasão'}
                </button>
              ))}
            </div>
          </div>

          {/* Scope */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Escopo</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Tipo</label>
                <select
                  value={scope.scope_type}
                  onChange={(e) => setScope((s) => ({ ...s, scope_type: e.target.value }))}
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                >
                  <option value="network">Rede</option>
                  <option value="school">Escola</option>
                  <option value="region">Região</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">ID do Escopo</label>
                <input
                  type="text"
                  value={scope.scope_id}
                  onChange={(e) => setScope((s) => ({ ...s, scope_id: e.target.value }))}
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                  placeholder="escola_01"
                />
              </div>
            </div>
          </div>

          {/* Factors */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <FactorGroup title="Fatores" factors={ELECTORAL_FACTORS} values={factors} onChange={setFactor} />
          </div>

          <button
            onClick={handlePredict}
            disabled={loading}
            className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
          >
            {loading ? 'Calculando…' : 'Calcular Predição'}
          </button>
        </div>

        {/* Result */}
        <div>
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm mb-4">{error}</div>
          )}

          {!result && !loading && !error && (
            <div className="bg-white rounded-xl border border-dashed border-gray-300 p-10 text-center text-gray-400">
              <p className="text-4xl mb-3">◎</p>
              <p>Configure os fatores e clique em Calcular</p>
            </div>
          )}

          {result && valuePct !== null && (
            <div className="space-y-4">
              {/* Main result */}
              <div className="bg-white rounded-xl border border-gray-200 p-6 text-center">
                <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">
                  {result.prediction_type === 'acceptance' ? 'Probabilidade de Aceitação' : 'Risco de Evasão'}
                </p>
                <p
                  className={`text-6xl font-bold ${
                    result.prediction_type === 'acceptance'
                      ? valuePct >= 60 ? 'text-green-600' : valuePct >= 40 ? 'text-yellow-600' : 'text-red-600'
                      : valuePct >= 60 ? 'text-red-600' : valuePct >= 40 ? 'text-yellow-600' : 'text-green-600'
                  }`}
                >
                  {valuePct}%
                </p>
                <button
                  onClick={() => setShowSaveModal(true)}
                  className="mt-4 text-sm text-brand-600 hover:text-brand-800 font-medium"
                >
                  💾 Salvar Predição
                </button>
                {saveSuccess && (
                  <p className="text-xs text-green-600 mt-1">Salvo com sucesso!</p>
                )}
              </div>

              {/* Confidence */}
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-700">Confiança</p>
                </div>
                <ConfidenceBar value={result.confidence} />
              </div>

              {/* Explanation */}
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Explicação</h3>
                <ul className="space-y-2">
                  {result.explanation.map((line, i) => (
                    <li key={i} className="flex gap-2 text-sm text-gray-600">
                      <span className="text-brand-500 mt-0.5 shrink-0">•</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
      {/* Save modal */}
      {showSaveModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Salvar Predição</h3>
            <input
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder={`Predição ${new Date().toLocaleDateString('pt-BR')}`}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none mb-4"
              autoFocus
            />
            <div className="flex gap-3">
              <button
                onClick={() => setShowSaveModal(false)}
                className="flex-1 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 py-2 text-sm bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white rounded-lg font-medium"
              >
                {saving ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
