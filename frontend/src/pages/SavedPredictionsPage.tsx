import { useEffect, useState } from 'react'
import { savedPredictionsApi } from '../api/client'
import type { SavedPrediction } from '../api/client'
import Layout from '../components/Layout'
import { useAuth } from '../contexts/AuthContext'

function ValueBadge({ type, value }: { type: string; value: number }) {
  const pct = Math.round(value * 100)
  const isRisk = type === 'evasion_risk'
  const color = isRisk
    ? pct >= 60 ? 'text-red-600' : pct >= 40 ? 'text-yellow-600' : 'text-green-600'
    : pct >= 60 ? 'text-green-600' : pct >= 40 ? 'text-yellow-600' : 'text-red-600'
  return <span className={`text-2xl font-bold ${color}`}>{pct}%</span>
}

export default function SavedPredictionsPage() {
  const { user } = useAuth()
  const [items, setItems] = useState<SavedPrediction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<SavedPrediction | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  useEffect(() => {
    if (user) loadSaved()
  }, [user]) // eslint-disable-line react-hooks/exhaustive-deps

  async function loadSaved() {
    if (!user) return
    setLoading(true)
    try {
      const data = await savedPredictionsApi.list(user.organization_id)
      setItems(data.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar predições.')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id: string) {
    setDeleting(id)
    try {
      await savedPredictionsApi.delete(id)
      setItems((prev) => prev.filter((i) => i.id !== id))
      if (selected?.id === id) setSelected(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao deletar.')
    } finally {
      setDeleting(null)
    }
  }

  const typeLabel = (t: string) =>
    t === 'acceptance' ? 'Aceitação' : t === 'evasion_risk' ? 'Risco de Evasão' : t

  const scenarioTypeLabel = (t: string) =>
    t === 'education' ? '🎓 Educação' : t === 'political' ? '🗳 Político' : t === 'business' ? '📦 Empresa' : t

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Predições Salvas</h1>
        <p className="text-gray-500 mt-1">Histórico de predições calculadas e salvas.</p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      {loading && (
        <div className="text-center py-16 text-gray-400">Carregando…</div>
      )}

      {!loading && items.length === 0 && (
        <div className="bg-white border border-dashed border-gray-300 rounded-xl p-16 text-center text-gray-400">
          <p className="text-4xl mb-3">◎</p>
          <p>Nenhuma predição salva ainda.</p>
          <p className="text-sm mt-1">Vá até Predições, calcule e clique em "Salvar".</p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="grid grid-cols-3 gap-6">
          {/* List */}
          <div className="col-span-1 space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelected(item)}
                className={`bg-white border rounded-xl p-4 cursor-pointer transition-all hover:border-brand-300 ${
                  selected?.id === item.id ? 'border-brand-500 bg-brand-50' : 'border-gray-200'
                }`}
              >
                <p className="font-medium text-gray-900 text-sm truncate">{item.name}</p>
                <p className="text-xs text-gray-400 mt-0.5">{scenarioTypeLabel(item.scenario_type)}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-gray-500">{typeLabel(item.prediction_type)}</span>
                  <ValueBadge type={item.prediction_type} value={item.result_value} />
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  {new Date(item.created_at).toLocaleDateString('pt-BR')}
                </p>
              </div>
            ))}
          </div>

          {/* Detail */}
          <div className="col-span-2">
            {!selected ? (
              <div className="bg-gray-50 border border-dashed border-gray-300 rounded-xl h-64 flex items-center justify-center text-gray-400">
                Selecione uma predição para ver os detalhes
              </div>
            ) : (
              <div className="space-y-4">
                <div className="bg-white border border-gray-200 rounded-xl p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900">{selected.name}</h2>
                      <p className="text-sm text-gray-500 mt-0.5">
                        {scenarioTypeLabel(selected.scenario_type)} · {typeLabel(selected.prediction_type)}
                      </p>
                    </div>
                    <div className="text-right">
                      <ValueBadge type={selected.prediction_type} value={selected.result_value} />
                      <p className="text-xs text-gray-400 mt-1">
                        Confiança: {Math.round(selected.confidence * 100)}%
                      </p>
                    </div>
                  </div>

                  {selected.notes && (
                    <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
                      {selected.notes}
                    </div>
                  )}
                </div>

                {/* Explanation */}
                <div className="bg-white border border-gray-200 rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">Explicação</h3>
                  <ul className="space-y-2">
                    {selected.explanation.map((line, i) => (
                      <li key={i} className="flex gap-2 text-sm text-gray-600">
                        <span className="text-brand-500 mt-0.5 shrink-0">•</span>
                        <span>{line}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Factors */}
                <div className="bg-white border border-gray-200 rounded-xl p-5">
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">Fatores Utilizados</h3>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(selected.factors).map(([key, val]) => (
                      <div key={key} className="flex items-center justify-between text-sm">
                        <span className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className="font-medium text-gray-900">{val}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(selected.id)}
                  disabled={deleting === selected.id}
                  className="text-xs text-red-400 hover:text-red-600 disabled:opacity-50"
                >
                  {deleting === selected.id ? 'Deletando…' : 'Deletar esta predição'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </Layout>
  )
}
