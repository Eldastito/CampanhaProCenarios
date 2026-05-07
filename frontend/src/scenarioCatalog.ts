export interface ScenarioFactorDef {
  key: string
  label: string
  weight: number
}

export interface ScenarioTypeDef {
  type: string
  label: string
  description: string
  sourceSystem: string
  icon: string
  factors: ScenarioFactorDef[]
}

export const SCENARIO_CATALOG: ScenarioTypeDef[] = [
  {
    type: 'electoral',
    label: 'Eleitoral',
    description: 'Cenários de campanha e eleição. Dados via plataforma CampanhaPro.',
    sourceSystem: 'CAMPANHAPRO',
    icon: '🗳️',
    factors: [
      { key: 'rejection', label: 'Rejeição', weight: 0.15 },
      { key: 'vote_intention', label: 'Intenção de Voto / Apoio Inicial', weight: 0.14 },
      { key: 'awareness', label: 'Conhecimento do Candidato', weight: 0.10 },
      { key: 'territorial_strength', label: 'Força Territorial', weight: 0.10 },
      { key: 'alliances', label: 'Força de Alianças', weight: 0.08 },
      { key: 'mobilization', label: 'Mobilização de Base', weight: 0.08 },
      { key: 'digital_sentiment', label: 'Sentimento Digital', weight: 0.08 },
      { key: 'local_agenda_fit', label: 'Aderência a Pautas Locais', weight: 0.07 },
      { key: 'reputation_risk', label: 'Risco Reputacional', weight: 0.07 },
      { key: 'operational_efficiency', label: 'Eficiência Operacional', weight: 0.06 },
      { key: 'media_coverage', label: 'Cobertura de Mídia', weight: 0.04 },
      { key: 'declared_funding', label: 'Capacidade Financeira Declarada', weight: 0.03 },
    ],
  },
]

export function getScenarioTypeDef(type: string): ScenarioTypeDef {
  return SCENARIO_CATALOG.find((s) => s.type === type) ?? SCENARIO_CATALOG[0]
}

export function getFactorKeys(type: string): string[] {
  return getScenarioTypeDef(type).factors.map((f) => f.key)
}

export function getFactorLabel(type: string, key: string): string {
  return getScenarioTypeDef(type).factors.find((f) => f.key === key)?.label ?? key
}

export function defaultFactors(type: string): Record<string, number> {
  return Object.fromEntries(getFactorKeys(type).map((k) => [k, 50]))
}
