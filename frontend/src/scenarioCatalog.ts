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
    type: 'education',
    label: 'Educação',
    description: 'Cenários para escolas públicas e privadas. Dados via plataforma FORGE.',
    sourceSystem: 'FORGE',
    icon: '🎓',
    factors: [
      { key: 'training', label: 'Treinamento', weight: 0.20 },
      { key: 'digital_maturity', label: 'Maturidade Digital', weight: 0.20 },
      { key: 'teacher_adoption', label: 'Adoção por Professores', weight: 0.20 },
      { key: 'infrastructure', label: 'Infraestrutura', weight: 0.15 },
      { key: 'institutional_support', label: 'Suporte Institucional', weight: 0.15 },
      { key: 'engagement', label: 'Engajamento', weight: 0.10 },
    ],
  },
  {
    type: 'political',
    label: 'Político (Eleições)',
    description: 'Chances de eleição de candidatos. Dados via plataforma CampanhaPro.',
    sourceSystem: 'CAMPANHAPRO',
    icon: '🗳️',
    factors: [
      { key: 'public_opinion', label: 'Opinião Pública', weight: 0.25 },
      { key: 'legislative_support', label: 'Apoio Legislativo', weight: 0.20 },
      { key: 'media_sentiment', label: 'Sentimento na Mídia', weight: 0.20 },
      { key: 'party_unity', label: 'Unidade Partidária', weight: 0.15 },
      { key: 'economic_perception', label: 'Percepção Econômica', weight: 0.10 },
      { key: 'voter_turnout', label: 'Comparecimento do Eleitorado', weight: 0.10 },
    ],
  },
  {
    type: 'business',
    label: 'Empresas e Produtos',
    description: 'Tendências de moda e mercado para um público-alvo. Dados via backoffice.',
    sourceSystem: 'BACKOFFICE',
    icon: '📊',
    factors: [
      { key: 'market_demand', label: 'Demanda de Mercado', weight: 0.25 },
      { key: 'target_audience_fit', label: 'Alinhamento com Público-Alvo', weight: 0.20 },
      { key: 'trend_alignment', label: 'Alinhamento com Tendências', weight: 0.20 },
      { key: 'competitive_position', label: 'Posição Competitiva', weight: 0.15 },
      { key: 'brand_sentiment', label: 'Sentimento de Marca', weight: 0.10 },
      { key: 'distribution_reach', label: 'Alcance de Distribuição', weight: 0.10 },
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
