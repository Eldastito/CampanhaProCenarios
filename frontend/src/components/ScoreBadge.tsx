const BAND_STYLES: Record<string, string> = {
  advanced: 'bg-emerald-100 text-emerald-800',
  strong: 'bg-green-100 text-green-800',
  progressing: 'bg-yellow-100 text-yellow-800',
  attention: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
  unknown: 'bg-gray-100 text-gray-600',
}

const BAND_LABELS: Record<string, string> = {
  advanced: 'Avançado',
  strong: 'Forte',
  progressing: 'Progredindo',
  attention: 'Atenção',
  critical: 'Crítico',
  unknown: '—',
}

export function ScoreBadge({ band }: { band: string }) {
  const style = BAND_STYLES[band] ?? BAND_STYLES.unknown
  const label = BAND_LABELS[band] ?? band
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {label}
    </span>
  )
}

export function ScoreBar({ value, max = 100 }: { value: number | null; max?: number }) {
  if (value === null) return <span className="text-gray-400 text-sm">—</span>
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  const color =
    pct >= 90 ? 'bg-emerald-500' : pct >= 75 ? 'bg-green-500' : pct >= 60 ? 'bg-yellow-500' : pct >= 40 ? 'bg-orange-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-medium text-gray-700 w-12 text-right">{value.toFixed(1)}</span>
    </div>
  )
}

export function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) return <span className="text-gray-400">—</span>
  const color = delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-gray-500'
  const prefix = delta > 0 ? '+' : ''
  return <span className={`font-semibold ${color}`}>{prefix}{delta.toFixed(1)}</span>
}
