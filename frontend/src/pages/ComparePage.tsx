import { useEffect, useState } from 'react'
import { scenariosApi } from '../api/client'
import type { ScenarioSummary, CompareResponse } from '../api/client'
import Layout from '../components/Layout'
import { ScoreBadge, ScoreBar, DeltaBadge } from '../components/ScoreBadge'
import { useAuth } from '../contexts/AuthContext'

export default function ComparePage() {
  const { user } = useAuth()
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [idA, setIdA] = useState('')
  const [idB, setIdB] = useState('')
  const [result, setResult] = useState<CompareResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function loadScenarios() {
    if (!user?.organization_id) return
    setRefreshing(true)
    scenariosApi.list(user.organization_id)
      .then((d) => setScenarios(d.items))
      .catch(() => {})
      .finally(() => setRefreshing(false))
  }

  useEffect(() => {
    loadScenarios()
  }, [user?.organization_id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCompare() {
    if (!idA || !idB) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await scenariosApi.compare(idA, idB))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao comparar cenários.')
    } finally {
      setLoading(false)
    }
  }

  const cc = result?.cross_comparison

  return (
    <Layout>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Comparar Cenários</h1>
          <p className="text-gray-500 mt-1">Analise dois cenários lado a lado.</p>
        </div>
        <button
          onClick={loadScenarios}
          disabled={refreshing}
          className="border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-60 text-sm px-3 py-2 rounded-lg transition-colors"
          title="Atualizar lista de cenários"
        >
          {refreshing ? '⏳ Atualizando…' : '↻ Atualizar lista'}
        </button>
      </div>

      {/* Selector */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cenário A</label>
            <select
              value={idA}
              onChange={(e) => setIdA(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Selecionar…</option>
              {scenarios.map((s) => (
                <option key={s.scenario_id} value={s.scenario_id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cenário B</label>
            <select
              value={idB}
              onChange={(e) => setIdB(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Selecionar…</option>
              {scenarios.map((s) => (
                <option key={s.scenario_id} value={s.scenario_id}>{s.name}</option>
              ))}
            </select>
          </div>
        </div>
        <button
          onClick={handleCompare}
          disabled={!idA || !idB || idA === idB || loading}
          className="bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-medium py-2 px-6 rounded-lg text-sm transition-colors"
        >
          {loading ? 'Comparando…' : 'Comparar'}
        </button>
        {idA === idB && idA && (
          <p className="text-xs text-amber-600 mt-2">Selecione dois cenários diferentes.</p>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm mb-6">{error}</div>
      )}

      {result && cc && (
        <div className="space-y-6">
          {/* Cross-comparison summary */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Baseline A', value: cc.baseline_score_a },
              { label: 'Baseline B', value: cc.baseline_score_b },
              { label: 'Delta (B−A)', delta: cc.baseline_delta_b_minus_a },
              { label: 'Melhor baseline', winner: cc.baseline_winner },
            ].map((card) => (
              <div key={card.label} className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-400 mb-2">{card.label}</p>
                {card.winner !== undefined ? (
                  <p className="text-xl font-bold text-gray-900">
                    {card.winner === 'tie' ? 'Empate' : `Cenário ${card.winner.toUpperCase()}`}
                  </p>
                ) : card.delta !== undefined ? (
                  <p className="text-xl font-bold"><DeltaBadge delta={card.delta} /></p>
                ) : (
                  <p className="text-2xl font-bold text-gray-900">{(card.value ?? 0).toFixed(1)}</p>
                )}
              </div>
            ))}
          </div>

          {/* Side-by-side */}
          <div className="grid grid-cols-2 gap-6">
            {([
              { label: 'Cenário A', data: result.scenario_a },
              { label: 'Cenário B', data: result.scenario_b },
            ] as const).map(({ label, data }) => (
              <div key={label} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="text-xs text-gray-400">{label}</p>
                    <h3 className="font-semibold text-gray-900">{data.name}</h3>
                    {data.description && (
                      <p className="text-xs text-gray-500 mt-0.5 truncate">{data.description}</p>
                    )}
                  </div>
                  <ScoreBadge band={data.baseline_band} />
                </div>
                <div className="space-y-3">
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Baseline</p>
                    <ScoreBar value={data.baseline_normalized_score} />
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Alternativa</p>
                    <ScoreBar value={data.alternative_normalized_score} />
                  </div>
                  <div className="flex gap-4 text-xs text-gray-500 mt-2">
                    <span>Delta: <DeltaBadge delta={data.normalized_delta} /></span>
                    <span>Confiança: {data.confidence_level}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Layout>
  )
}
