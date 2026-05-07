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

export type ChatTool = 'conversation' | 'quick_search' | 'panorama_search' | 'insight_forge' | 'virtual_interview'

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
