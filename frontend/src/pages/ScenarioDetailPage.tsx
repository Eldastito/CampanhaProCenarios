import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { scenariosApi } from '../api/client'
import type { ScenarioResults } from '../api/client'
import Layout from '../components/Layout'
import { ScoreBadge, ScoreBar, DeltaBadge } from '../components/ScoreBadge'

const DIRECTION_LABELS: Record<string, string> = {
  strong_gain: '⬆ Ganho forte',
  moderate_gain: '↑ Ganho moderado',
  slight_gain: '↗ Ganho leve',
  neutral: '→ Neutro',
  negative: '↓ Negativo',
}

export default function ScenarioDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [results, setResults] = useState<ScenarioResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    if (!id) return
    setLoading(true)
    try {
      const data = await scenariosApi.getResults(id)
      setResults(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar cenário.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRun() {
    if (!id) return
    setRunning(true)
    try {
      const data = await scenariosApi.run(id, true)
      setResults(data.results)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao executar cenário.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <Layout>
      <div className="flex items-center justify-between mb-8">
        <div>
          <Link to="/" className="text-sm text-gray-400 hover:text-gray-600">← Dashboard</Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">Detalhes do Cenário</h1>
          {results && (
            <p className="text-gray-500 text-sm mt-1">ID: {results.scenario_id}</p>
          )}
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {running ? 'Executando…' : '▶ Re-executar'}
        </button>
      </div>

      {loading && (
        <div className="flex justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      {results && (
        <div className="space-y-6">
          {/* Score summary */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Baseline', score: results.normalized_result.baseline_score, band: results.interpretation.baseline_band },
              { label: 'Alternativa', score: results.normalized_result.alternative_score, band: results.interpretation.alternative_band },
              { label: 'Delta', score: null, delta: results.normalized_result.delta, direction: results.interpretation.delta_direction },
            ].map((card) => (
              <div key={card.label} className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">{card.label}</p>
                {card.score !== undefined && card.band ? (
                  <>
                    <p className="text-3xl font-bold text-gray-900">{card.score?.toFixed(1) ?? '—'}</p>
                    <div className="mt-2"><ScoreBadge band={card.band} /></div>
                  </>
                ) : (
                  <>
                    <p className="text-3xl font-bold">
                      <DeltaBadge delta={card.delta ?? null} />
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      {DIRECTION_LABELS[card.direction ?? ''] ?? card.direction}
                    </p>
                  </>
                )}
              </div>
            ))}
          </div>

          {/* Interpretation */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-900 mb-3">Interpretação</h2>
            <div className="flex gap-6 text-sm text-gray-600">
              <span>Confiança: <strong>{results.interpretation.confidence_level}</strong></span>
              <span>Cobertura baseline: <strong>{results.input_quality.baseline_coverage_percent.toFixed(0)}%</strong></span>
              <span>Cobertura alternativa: <strong>{results.input_quality.alternative_coverage_percent.toFixed(0)}%</strong></span>
            </div>
            {results.interpretation.warnings.length > 0 && (
              <ul className="mt-3 space-y-1">
                {results.interpretation.warnings.map((w, i) => (
                  <li key={i} className="text-sm text-amber-700 bg-amber-50 rounded px-3 py-1">⚠ {w}</li>
                ))}
              </ul>
            )}
          </div>

          {/* Factor breakdown */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Breakdown por Fator</h2>
            <div className="space-y-4">
              {results.factor_breakdown.map((f) => (
                <div key={f.factor} className="grid grid-cols-4 gap-4 items-center text-sm">
                  <span className="text-gray-700 font-medium">{f.label ?? f.factor}</span>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Baseline</p>
                    <ScoreBar value={f.baseline_value} />
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Alternativa</p>
                    <ScoreBar value={f.alternative_value} />
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-400 mb-1">Delta</p>
                    <DeltaBadge delta={f.delta} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recommendations */}
          {results.recommendations.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-gray-900 mb-3">Recomendações</h2>
              <ul className="space-y-3">
                {results.recommendations.map((r, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className={`shrink-0 font-semibold ${r.priority === 'high' ? 'text-red-500' : 'text-brand-500'}`}>
                      {r.priority === 'high' ? '!' : '•'}
                    </span>
                    <div>
                      <p className="font-medium text-gray-800">{r.title}</p>
                      <p className="text-gray-500 mt-0.5">{r.detail}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Layout>
  )
}
