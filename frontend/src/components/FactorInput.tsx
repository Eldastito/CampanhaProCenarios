import type { ScenarioFactorDef } from '../scenarioCatalog'

interface FactorInputProps {
  factor: string
  label: string
  value: number | undefined
  onChange: (factor: string, value: number) => void
}

export function FactorInput({ factor, label, value, onChange }: FactorInputProps) {
  const displayValue = value ?? 0

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        <span className="text-sm font-bold text-brand-600 w-10 text-right">{displayValue}</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={displayValue}
        onChange={(e) => onChange(factor, Number(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
      />
      <div className="flex justify-between text-xs text-gray-400">
        <span>0</span>
        <span>50</span>
        <span>100</span>
      </div>
    </div>
  )
}

export function FactorGroup({
  title,
  factors,
  values,
  onChange,
}: {
  title: string
  factors: ScenarioFactorDef[]
  values: Record<string, number>
  onChange: (factor: string, value: number) => void
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">{title}</h3>
      <div className="space-y-5">
        {factors.map((f) => (
          <FactorInput key={f.key} factor={f.key} label={f.label} value={values[f.key]} onChange={onChange} />
        ))}
      </div>
    </div>
  )
}
