import { useState } from 'react'
import {
  ReportFormat,
  ReportRequestBody,
  ReportType,
  reportsApi,
} from '../api/client'

interface ReportOption {
  type: ReportType
  label: string
  description: string
}

const ALL_OPTIONS: ReportOption[] = [
  {
    type: 'executive_summary',
    label: 'Resumo executivo',
    description: '1 página com score, probabilidade, forças e fraquezas',
  },
  {
    type: 'factor_deep_dive',
    label: 'Deep dive — 12 fatores',
    description: 'Detalhamento por fator com origem e avisos',
  },
  {
    type: 'candidate_comparison',
    label: 'Comparação de candidatos (Monte Carlo)',
    description: 'Resultado de uma simulação Monte Carlo',
  },
  {
    type: 'scenario_what_if',
    label: 'Cenário what-if',
    description: 'Baseline vs alternativo de um cenário',
  },
  {
    type: 'compliance_audit',
    label: 'Auditoria de compliance',
    description: 'Alertas LGPD/TSE abertos',
  },
  {
    type: 'dossier_export',
    label: 'Dossiê de candidato',
    description: 'Dossiê completo (próprio ou adversário)',
  },
]

interface Props {
  projectId: string
  /** Restringe quais tipos aparecem no dropdown. Default: todos. */
  allowedTypes?: ReportType[]
  /** Tipo pré-selecionado para abrir o dropdown. */
  defaultType?: ReportType
  /** Context extra (ex: scenario_id, dossier_id, election_result_id). */
  context?: Record<string, unknown>
  /** Label customizado do botão. */
  label?: string
  /** Variant compacto para usar em headers de páginas de detalhe. */
  compact?: boolean
}

export default function ExportReportButton({
  projectId,
  allowedTypes,
  defaultType,
  context,
  label = '📄 Exportar relatório',
  compact = false,
}: Props) {
  const options = allowedTypes
    ? ALL_OPTIONS.filter((o) => allowedTypes.includes(o.type))
    : ALL_OPTIONS
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [type, setType] = useState<ReportType>(defaultType ?? options[0]?.type ?? 'executive_summary')

  async function generate(fmt: ReportFormat) {
    setPending(fmt)
    setError(null)
    try {
      const body: ReportRequestBody = { type, format: fmt, context }
      const blob = await reportsApi.generate(projectId, body)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${type}.${fmt}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setOpen(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={
          compact
            ? 'px-2 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50'
            : 'px-3 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50'
        }
      >
        {label}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-lg p-3">
          <div className="mb-3">
            <label className="text-xs text-gray-600">Tipo de relatório</label>
            <select
              className="input mt-1 text-sm"
              value={type}
              onChange={(e) => setType(e.target.value as ReportType)}
            >
              {options.map((o) => (
                <option key={o.type} value={o.type}>
                  {o.label}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-gray-500 mt-1">
              {options.find((o) => o.type === type)?.description}
            </p>
          </div>
          {error && (
            <div className="mb-2 p-2 rounded bg-red-50 text-red-700 text-xs border border-red-200">
              {error}
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => generate('pdf')}
              disabled={pending !== null}
              className="flex-1 px-3 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
            >
              {pending === 'pdf' ? 'Gerando…' : 'Baixar PDF'}
            </button>
            <button
              onClick={() => generate('docx')}
              disabled={pending !== null}
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              {pending === 'docx' ? 'Gerando…' : 'Baixar DOCX'}
            </button>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="mt-3 w-full text-xs text-gray-500 hover:underline"
          >
            cancelar
          </button>
        </div>
      )}
    </div>
  )
}
