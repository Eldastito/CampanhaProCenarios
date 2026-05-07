const BASE = '/api/v1'

function getToken(): string | null {
  return localStorage.getItem('fsl_token')
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...init.headers,
    },
  })

  if (res.status === 401) {
    // Token expired or invalid — clear and reload
    localStorage.removeItem('fsl_token')
    localStorage.removeItem('fsl_user')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = (body as { detail?: unknown }).detail
    let message: string
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail)) {
      message = detail
        .map((d) => {
          if (d && typeof d === 'object' && 'msg' in d) {
            const loc = Array.isArray((d as { loc?: unknown }).loc)
              ? ((d as { loc: unknown[] }).loc).join('.')
              : ''
            return loc ? `${loc}: ${(d as { msg: string }).msg}` : (d as { msg: string }).msg
          }
          return JSON.stringify(d)
        })
        .join('; ')
    } else if (detail && typeof detail === 'object') {
      message = JSON.stringify(detail)
    } else {
      message = `HTTP ${res.status}`
    }
    throw new Error(message)
  }

  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: string
  email: string
  organization_id: string
  role: string
}

export const authApi = {
  register: (body: { email: string; password: string; organization_id: string; role?: string }) =>
    request<TokenResponse>('/auth/register', { method: 'POST', body: JSON.stringify(body) }),

  login: (body: { email: string; password: string }) =>
    request<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
}

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------

export interface ScenarioSummary {
  scenario_id: string
  organization_id: string
  name: string
  description: string | null
  scenario_type: string
  status: string
  result_status: string
  baseline_score: number | null
  alternative_score: number | null
  delta: number | null
  baseline_normalized_score: number | null
  alternative_normalized_score: number | null
  normalized_delta: number | null
  baseline_band: string
  alternative_band: string
  delta_direction: string
  confidence_level: string
  baseline_coverage_percent: number
  alternative_coverage_percent: number
  created_at: string
  updated_at: string
}

export interface ScenarioListResponse {
  count: number
  items: ScenarioSummary[]
}

export interface ScenarioResults {
  contract_version: string
  scenario_id: string
  scenario_status: string
  run_status: string | null
  result_status: string
  result_meta: {
    is_stale: boolean
    last_refreshed_at: string | null
    result_source_run_id: string | null
    latest_run_id: string | null
    latest_run_label: string | null
  }
  result: {
    baseline_score: number | null
    alternative_score: number | null
    delta: number | null
  }
  normalized_result: {
    baseline_score: number | null
    alternative_score: number | null
    delta: number | null
  }
  input_quality: {
    baseline_coverage_percent: number
    alternative_coverage_percent: number
    baseline_missing_factors: string[]
    alternative_missing_factors: string[]
  }
  interpretation: {
    baseline_band: string
    alternative_band: string
    delta_direction: string
    confidence_level: string
    warnings: string[]
  }
  factor_breakdown: Array<{
    factor: string
    label: string
    weight: number
    baseline_value: number | null
    alternative_value: number | null
    baseline_contribution: number | null
    alternative_contribution: number | null
    delta: number | null
    direction: string
  }>
  recommendations: Array<{ priority: string; type: string; title: string; detail: string }>
}

export interface CompareResponse {
  contract_version: string
  scenario_a: ScenarioSummary
  scenario_b: ScenarioSummary
  cross_comparison: {
    baseline_score_a: number | null
    baseline_score_b: number | null
    baseline_delta_b_minus_a: number | null
    baseline_winner: string
    alternative_score_a: number | null
    alternative_score_b: number | null
    alternative_delta_b_minus_a: number | null
    alternative_winner: string
  }
}

export const scenariosApi = {
  list: (organization_id?: string) =>
    request<ScenarioListResponse>(
      `/scenarios${organization_id ? `?organization_id=${organization_id}` : ''}`,
    ),

  get: (id: string) => request<ScenarioSummary>(`/scenarios/${id}`),

  getResults: (id: string) => request<ScenarioResults>(`/scenarios/${id}/results`),

  create: (body: {
    organization_id: string
    name: string
    description?: string
    scenario_type?: string
    baseline_inputs: Record<string, number>
    alternative_inputs: Record<string, number>
  }) => request<ScenarioSummary>('/scenarios', { method: 'POST', body: JSON.stringify(body) }),

  run: (id: string, force_recalculate = false, run_label?: string) =>
    request<{ run_id: string; run_status: string; results: ScenarioResults }>(
      `/scenarios/${id}/run`,
      { method: 'POST', body: JSON.stringify({ force_recalculate, run_label }) },
    ),

  compare: (a: string, b: string) =>
    request<CompareResponse>(`/scenarios/compare?a=${a}&b=${b}`),
}

// ---------------------------------------------------------------------------
// Predictions
// ---------------------------------------------------------------------------

export interface PredictionResponse {
  prediction_type: string
  organization_id: string
  scope_type: string
  scope_id: string
  value: number
  confidence: number
  explanation: string[]
}

export const predictionsApi = {
  acceptance: (body: {
    organization_id: string
    scope_type: string
    scope_id: string
    factors?: Record<string, number>
  }) => request<PredictionResponse>('/predictions/acceptance', { method: 'POST', body: JSON.stringify(body) }),

  evasionRisk: (body: {
    organization_id: string
    scope_type: string
    scope_id: string
    factors?: Record<string, number>
  }) => request<PredictionResponse>('/predictions/evasion-risk', { method: 'POST', body: JSON.stringify(body) }),
}

// ---------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------

export interface GraphProjectSummary {
  project_id: string
  organization_id: string
  name: string
  scenario_type: string
  status: string
  node_count: number
  edge_count: number
  created_at: string
}

export interface GraphProjectListResponse {
  items: GraphProjectSummary[]
}

export interface GraphNode {
  id: string
  entity_type: string
  label: string
  properties: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  relationship_type: string
  properties: Record<string, unknown>
}

export interface GraphData {
  project_id: string
  organization_id: string
  name: string
  scenario_type: string
  status: string
  description?: string | null
  node_count: number
  edge_count: number
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphBuildResponse {
  project_id: string
  status: string
  node_count: number
  edge_count: number
}

export const graphApi = {
  list: (organization_id: string) =>
    request<GraphProjectListResponse>(`/graph?organization_id=${organization_id}`),

  get: (project_id: string) =>
    request<GraphData>(`/graph/${project_id}`),

  create: (body: { organization_id: string; name: string; scenario_type: string }) =>
    request<GraphProjectSummary>('/graph', { method: 'POST', body: JSON.stringify(body) }),

  build: (project_id: string, source_text: string) =>
    request<GraphBuildResponse>(`/graph/${project_id}/build`, {
      method: 'POST',
      body: JSON.stringify({ source_text }),
    }),

  patch: (project_id: string, body: { name?: string; description?: string }) =>
    request<{ project_id: string; name: string; description: string | null }>(
      `/graph/${project_id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    ),

  delete: (project_id: string) =>
    request<{ deleted: string }>(`/graph/${project_id}`, { method: 'DELETE' }),

  populateOpinions: (project_id: string, prompt_hint = '') =>
    request<{ added_nodes: number; added_edges: number; total_nodes: number; total_edges: number }>(
      `/graph/${project_id}/populate-opinions`,
      { method: 'POST', body: JSON.stringify({ prompt_hint }) },
    ),
}

// ---------------------------------------------------------------------------
// Simulations
// ---------------------------------------------------------------------------

export interface SimulationSummary {
  simulation_id: string
  project_id: string
  organization_id: string
  name: string
  status: string
  step_count: number
  created_at: string
}

export interface SimulationStep {
  step_number: number
  agent_label: string
  agent_type: string
  agent_node_id: string | null
  action: string
  content: string
  affected_nodes: string[]
}

export interface SimulationView {
  simulation_id: string
  project_id: string
  name: string
  status: string
  summary: string | null
  steps: SimulationStep[]
}

export type SimulationStreamEvent =
  | ({ type: 'step' } & SimulationStep)
  | { type: 'done'; summary: string; step_count: number }
  | { type: 'error'; message: string }

export const simulationsApi = {
  create: (body: {
    project_id: string
    organization_id: string
    name: string
    prompt?: string
  }) => request<SimulationSummary>('/simulations', { method: 'POST', body: JSON.stringify(body) }),

  run: (simulation_id: string, num_steps = 12) =>
    request<{ simulation_id: string; status: string; step_count: number }>(
      `/simulations/${simulation_id}/run`,
      { method: 'POST', body: JSON.stringify({ num_steps }) },
    ),

  async *streamRun(simulation_id: string, num_steps = 12): AsyncGenerator<SimulationStreamEvent> {
    const token = localStorage.getItem('fsl_token')
    const res = await fetch(`${BASE}/simulations/${simulation_id}/stream-run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ num_steps }),
    })

    if (res.status === 401) {
      localStorage.removeItem('fsl_token')
      localStorage.removeItem('fsl_user')
      window.location.href = '/login'
      throw new Error('Unauthorized')
    }
    if (!res.ok || !res.body) throw new Error(`Stream failed: HTTP ${res.status}`)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() ?? ''
      for (const chunk of chunks) {
        const dataLine = chunk.split('\n').find((l) => l.startsWith('data: '))
        if (!dataLine) continue
        try {
          yield JSON.parse(dataLine.slice(6)) as SimulationStreamEvent
        } catch {
          // malformed SSE line — skip
        }
      }
    }
  },

  get: (simulation_id: string) =>
    request<SimulationView>(`/simulations/${simulation_id}`),

  list: (organization_id: string) =>
    request<{ items: SimulationSummary[] }>(`/simulations?organization_id=${organization_id}`),
}

// ---------------------------------------------------------------------------
// Saved Predictions
// ---------------------------------------------------------------------------

export interface SavedPrediction {
  id: string
  organization_id: string
  name: string
  prediction_type: string
  scenario_type: string
  factors: Record<string, number>
  result_value: number
  confidence: number
  explanation: string[]
  notes: string | null
  created_at: string
}

export const savedPredictionsApi = {
  list: (organization_id: string) =>
    request<{ items: SavedPrediction[] }>(`/saved-predictions?organization_id=${organization_id}`),

  save: (body: {
    organization_id: string
    name: string
    prediction_type: string
    scenario_type: string
    factors: Record<string, number>
    result_value: number
    confidence: number
    explanation: string[]
    notes?: string
  }) => request<SavedPrediction>('/saved-predictions', { method: 'POST', body: JSON.stringify(body) }),

  delete: (id: string) =>
    request<void>(`/saved-predictions/${id}`, { method: 'DELETE' }),
}

// ---------------------------------------------------------------------------
// Research Agent
// ---------------------------------------------------------------------------

export interface ResearchSource {
  title: string
  url: string
  snippet: string
}

export interface RejectionProfile {
  overall_rejection: number | null
  by_segment: Record<string, Record<string, number>>
  key_weaknesses: string[]
  key_strengths: string[]
}

export interface CandidateResearch {
  name: string
  party: string
  party_abbreviation: string
  office: string
  search_performed: boolean
  political_history: string
  current_mandates: string
  platform_and_goals: string
  recent_news: string
  legal_issues: string
  ficha_limpa_status: string
  background: string
  rejection_profile: RejectionProfile
  graph_context_text: string
  sources: ResearchSource[]
}

export interface CompareRejectionCandidate {
  name: string
  overall_rejection: number | null
  rejection_by_segment: Record<string, Record<string, number>>
  key_weaknesses: string[]
  key_strengths: string[]
}

export interface CompareRejectionResponse {
  candidates: CompareRejectionCandidate[]
  analysis: string
}

export const researchApi = {
  candidate: (body: {
    name: string
    party: string
    party_abbreviation: string
    office: string
  }) => request<CandidateResearch>('/research/candidate', { method: 'POST', body: JSON.stringify(body) }),

  compare: (candidates: Array<{ name: string; party: string; party_abbreviation: string; office: string }>) =>
    request<CompareRejectionResponse>('/research/compare', {
      method: 'POST',
      body: JSON.stringify({ candidates }),
    }),
}

// ---------------------------------------------------------------------------
// Saved Research
// ---------------------------------------------------------------------------

export interface SavedResearchSummary {
  id: string
  name: string
  candidate_name: string
  party: string
  party_abbreviation: string
  office: string
  search_performed: boolean
  created_at: string
}

export interface SavedResearchDetail extends SavedResearchSummary {
  organization_id: string
  political_history: string | null
  current_mandates: string | null
  platform_and_goals: string | null
  recent_news: string | null
  legal_issues: string | null
  ficha_limpa_status: string | null
  background: string | null
  rejection_profile: RejectionProfile | null
  graph_context_text: string | null
  sources: ResearchSource[] | null
  notes: string | null
}

export const savedResearchApi = {
  list: (organization_id: string) =>
    request<{ items: SavedResearchSummary[] }>(`/saved-research?organization_id=${organization_id}`),

  get: (id: string) => request<SavedResearchDetail>(`/saved-research/${id}`),

  save: (body: {
    organization_id: string
    name: string
    candidate_name: string
    party: string
    party_abbreviation: string
    office: string
    search_performed: boolean
    political_history?: string
    current_mandates?: string
    platform_and_goals?: string
    recent_news?: string
    legal_issues?: string
    ficha_limpa_status?: string
    background?: string
    rejection_profile?: RejectionProfile
    graph_context_text?: string
    sources?: ResearchSource[]
    notes?: string
  }) => request<SavedResearchDetail>('/saved-research', { method: 'POST', body: JSON.stringify(body) }),

  delete: (id: string) => request<{ deleted: string }>(`/saved-research/${id}`, { method: 'DELETE' }),
}

// ---------------------------------------------------------------------------
// Chat (55 agents + 4 tools)
// ---------------------------------------------------------------------------

export interface AgentPersona {
  id: string
  name: string
  category: string
  role: string
  description: string
  persona_prompt: string
  avatar_letter: string
}

export type ChatTool = 'conversation' | 'quick_search' | 'panorama_search' | 'insight_campanha' | 'virtual_interview'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  reply: string
  agent_name: string
  tool_used: string
  tool_metadata: Record<string, unknown>
  thread_id?: string | null
}

export interface ChatThreadSummary {
  thread_id: string
  organization_id: string
  user_id: string
  agent_id: string
  agent_name: string
  title: string
  graph_project_id: string | null
  created_at: string
  updated_at: string
}

export interface ChatThreadMessage {
  id: string
  position: number
  role: 'user' | 'assistant'
  content: string
  tool_type: string | null
  created_at: string
}

export interface ChatThreadDetail extends ChatThreadSummary {
  messages: ChatThreadMessage[]
}

export const chatApi = {
  listAgents: () => request<{ count: number; items: AgentPersona[] }>('/chat/agents'),

  send: (body: {
    agent_id: string
    tool_type: ChatTool
    messages: ChatMessage[]
    graph_project_id?: string
    thread_id?: string
  }) => request<ChatResponse>('/chat/messages', { method: 'POST', body: JSON.stringify(body) }),

  listThreads: (organization_id: string) =>
    request<{ count: number; items: ChatThreadSummary[] }>(
      `/chat/threads?organization_id=${encodeURIComponent(organization_id)}`,
    ),

  createThread: (body: {
    organization_id: string
    agent_id: string
    title?: string
    graph_project_id?: string
  }) => request<ChatThreadDetail>('/chat/threads', { method: 'POST', body: JSON.stringify(body) }),

  getThread: (thread_id: string) => request<ChatThreadDetail>(`/chat/threads/${thread_id}`),

  renameThread: (thread_id: string, title: string) =>
    request<ChatThreadSummary>(`/chat/threads/${thread_id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  deleteThread: (thread_id: string) =>
    request<{ deleted: string }>(`/chat/threads/${thread_id}`, { method: 'DELETE' }),
}

// ---------------------------------------------------------------------------
// Political Projects (Fase 1 — projetos eleitorais)
// ---------------------------------------------------------------------------

export interface PoliticalProject {
  id: string
  organization_id: string
  name: string
  description: string | null
  election_year: number
  office: string
  state: string | null
  municipality: string | null
  candidate_name: string
  parties: string[]
  known_opponents: string[]
  objective: string | null
  horizon_start: string | null
  horizon_end: string | null
  status: string
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface PoliticalProjectCreatePayload {
  organization_id: string
  name: string
  description?: string | null
  election_year: number
  office: string
  state?: string | null
  municipality?: string | null
  candidate_name: string
  parties?: string[]
  known_opponents?: string[]
  objective?: string | null
  horizon_start?: string | null
  horizon_end?: string | null
}

export interface PoliticalProjectUpdatePayload {
  name?: string | null
  description?: string | null
  state?: string | null
  municipality?: string | null
  parties?: string[] | null
  known_opponents?: string[] | null
  objective?: string | null
  horizon_start?: string | null
  horizon_end?: string | null
  status?: string | null
}

export const politicalProjectsApi = {
  list: () => request<PoliticalProject[]>('/political/projects'),

  get: (id: string) => request<PoliticalProject>(`/political/projects/${id}`),

  create: (body: PoliticalProjectCreatePayload) =>
    request<PoliticalProject>('/political/projects', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  update: (id: string, body: PoliticalProjectUpdatePayload) =>
    request<PoliticalProject>(`/political/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  remove: (id: string) =>
    fetch(`${BASE}/political/projects/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    }).then((res) => {
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`)
    }),
}

// ---------------------------------------------------------------------------
// Political Evidence (Fase 2 — ingestão de evidências)
// ---------------------------------------------------------------------------

export type ReliabilityLevel =
  | 'official'
  | 'press'
  | 'registered_poll'
  | 'public_base'
  | 'internal'
  | 'social'
  | 'unverified'

export interface PoliticalEvidenceSource {
  id: string
  organization_id: string
  project_id: string
  title: string
  source_type: string
  source_name: string | null
  source_url: string | null
  author: string | null
  published_at: string | null
  collected_at: string
  reliability_level: ReliabilityLevel
  content_hash: string | null
  storage_uri: string | null
  metadata_json: Record<string, unknown>
  processing_status: string
  processing_error: string | null
  created_by: string | null
  created_at: string
}

export interface ManualEvidencePayload {
  title: string
  source_type: 'manual' | 'link' | 'txt' | 'md'
  raw_text?: string | null
  source_name?: string | null
  source_url?: string | null
  author?: string | null
  published_at?: string | null
  reliability_override?: ReliabilityLevel | null
  metadata?: Record<string, unknown>
}

export const evidenceApi = {
  list: (projectId: string) =>
    request<PoliticalEvidenceSource[]>(`/political/projects/${projectId}/evidence`),

  get: (evidenceId: string) =>
    request<PoliticalEvidenceSource>(`/political/evidence/${evidenceId}`),

  createManual: (projectId: string, body: ManualEvidencePayload) =>
    request<PoliticalEvidenceSource>(
      `/political/projects/${projectId}/evidence/manual`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  upload: async (
    projectId: string,
    file: File,
    fields: { title: string; source_url?: string; author?: string; reliability_override?: ReliabilityLevel },
  ): Promise<PoliticalEvidenceSource> => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('title', fields.title)
    if (fields.source_url) fd.append('source_url', fields.source_url)
    if (fields.author) fd.append('author', fields.author)
    if (fields.reliability_override) fd.append('reliability_override', fields.reliability_override)

    const res = await fetch(`${BASE}/political/projects/${projectId}/evidence`, {
      method: 'POST',
      headers: authHeaders(),
      body: fd,
    })
    if (res.status === 401) {
      localStorage.removeItem('fsl_token')
      localStorage.removeItem('fsl_user')
      window.location.href = '/login'
      throw new Error('Unauthorized')
    }
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { detail?: string }
      throw new Error(body.detail || `HTTP ${res.status}`)
    }
    return (await res.json()) as PoliticalEvidenceSource
  },
}

// ---------------------------------------------------------------------------
// Political Graph (Fase 3 — extração de entidades/relações das evidências)
// ---------------------------------------------------------------------------

export interface PoliticalGraphBuildResult {
  graph_project_id: string
  name: string
  status: string
  node_count: number
  edge_count: number
  political_project_id: string | null
}

export interface PoliticalGraphData {
  project_id: string
  political_project_id: string
  name: string
  scenario_type: string
  status: string
  description: string | null
  ontology: { entity_types?: string[]; relationship_types?: string[] }
  node_count: number
  edge_count: number
  nodes: { id: string; entity_type: string; label: string; properties: Record<string, unknown> }[]
  edges: {
    id: string
    source: string
    target: string
    relationship_type: string
    properties: Record<string, unknown>
  }[]
}

export const politicalGraphApi = {
  build: (projectId: string) =>
    request<PoliticalGraphBuildResult>(`/political/projects/${projectId}/graph/build`, {
      method: 'POST',
    }),

  get: (projectId: string) =>
    request<PoliticalGraphData>(`/political/projects/${projectId}/graph`),
}

// ---------------------------------------------------------------------------
// Political Agents (Fase 4 — bancada de especialistas + personas geradas)
// ---------------------------------------------------------------------------

export type PoliticalAgentType = 'fixed_specialist' | 'generated'

export interface PoliticalAgentProfile {
  id: string
  organization_id: string
  project_id: string
  agent_type: PoliticalAgentType
  role: string
  category: string
  synthetic_name: string
  biography: string
  persona_prompt: string
  biases_declared: string[]
  limitations: string[]
  confidence_level: string
  source_node_ids: string[]
  source_evidence_ids: string[]
  created_at: string
}

export interface PoliticalAgentSeedResult {
  project_id: string
  created_count: number
  skipped_count: number
  detail: string
}

export const politicalAgentsApi = {
  list: (projectId: string, agentType?: PoliticalAgentType) => {
    const q = agentType ? `?agent_type=${agentType}` : ''
    return request<PoliticalAgentProfile[]>(`/political/projects/${projectId}/agents${q}`)
  },

  get: (agentId: string) =>
    request<PoliticalAgentProfile>(`/political/agents/${agentId}`),

  seedSpecialists: (projectId: string) =>
    request<PoliticalAgentSeedResult>(
      `/political/projects/${projectId}/agents/seed-specialists`,
      { method: 'POST' },
    ),

  generateFromGraph: (projectId: string) =>
    request<PoliticalAgentSeedResult>(
      `/political/projects/${projectId}/agents/generate-from-graph`,
      { method: 'POST' },
    ),
}


