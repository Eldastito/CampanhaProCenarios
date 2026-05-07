import { useEffect, useRef, useState } from 'react'
import Layout from '../components/Layout'
import { chatApi, graphApi } from '../api/client'
import type {
  AgentPersona,
  ChatMessage,
  ChatThreadSummary,
  ChatTool,
  GraphProjectSummary,
} from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const TOOLS: { id: ChatTool; icon: string; label: string; desc: string }[] = [
  { id: 'conversation', icon: '💬', label: 'Conversa', desc: 'Diálogo com a persona' },
  { id: 'insight_forge', icon: '🔥', label: 'InsightForge', desc: 'Atribuição profunda — alinha simulação com grafo' },
  { id: 'panorama_search', icon: '🌐', label: 'PanoramaSearch', desc: 'BFS — propagação de eventos' },
  { id: 'quick_search', icon: '⚡', label: 'Recuperação Rápida', desc: 'GraphRAG — busca instantânea' },
  { id: 'virtual_interview', icon: '🎤', label: 'Entrevista Virtual', desc: 'Entrevista em múltiplos turnos' },
]

const CATEGORY_COLORS: Record<string, string> = {
  'Plataforma digital': 'bg-blue-100 text-blue-700',
  'Mídia': 'bg-purple-100 text-purple-700',
  'Eleitor': 'bg-green-100 text-green-700',
  'Educação': 'bg-yellow-100 text-yellow-700',
  'Profissional': 'bg-indigo-100 text-indigo-700',
  'Instituição': 'bg-red-100 text-red-700',
  'Político': 'bg-pink-100 text-pink-700',
  'Sociedade civil': 'bg-orange-100 text-orange-700',
  'Análise': 'bg-cyan-100 text-cyan-700',
  'Outros': 'bg-gray-100 text-gray-700',
}

export default function ChatPage() {
  const { user } = useAuth()
  const [agents, setAgents] = useState<AgentPersona[]>([])
  const [selectedAgent, setSelectedAgent] = useState<AgentPersona | null>(null)
  const [tool, setTool] = useState<ChatTool>('conversation')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [projects, setProjects] = useState<GraphProjectSummary[]>([])
  const [graphProjectId, setGraphProjectId] = useState<string>('')
  const [threads, setThreads] = useState<ChatThreadSummary[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatApi.listAgents().then((d) => setAgents(d.items)).catch((e) => setError(e.message))
    if (user) {
      graphApi.list(user.organization_id).then((d) => setProjects(d.items)).catch(() => {})
      refreshThreads()
    }
  }, [user]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [messages])

  async function refreshThreads() {
    if (!user) return
    try {
      const d = await chatApi.listThreads(user.organization_id)
      setThreads(d.items)
    } catch {
      // soft-fail; thread list is optional
    }
  }

  const categories = ['all', ...Array.from(new Set(agents.map((a) => a.category)))]
  const filtered = agents.filter((a) => {
    if (categoryFilter !== 'all' && a.category !== categoryFilter) return false
    if (search && !a.name.toLowerCase().includes(search.toLowerCase()) &&
        !a.role.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const agentThreads = selectedAgent
    ? threads.filter((t) => t.agent_id === selectedAgent.id)
    : []

  async function handleSend() {
    if (!input.trim() || !selectedAgent || !user || loading) return
    const userMsg: ChatMessage = { role: 'user', content: input.trim() }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setLoading(true)
    setError(null)

    try {
      let threadId = activeThreadId
      if (!threadId) {
        const created = await chatApi.createThread({
          organization_id: user.organization_id,
          agent_id: selectedAgent.id,
          title: userMsg.content.slice(0, 60),
          graph_project_id: graphProjectId || undefined,
        })
        threadId = created.thread_id
        setActiveThreadId(threadId)
      }

      const resp = await chatApi.send({
        agent_id: selectedAgent.id,
        tool_type: tool,
        messages: newMessages,
        graph_project_id: graphProjectId || undefined,
        thread_id: threadId,
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: resp.reply }])
      refreshThreads()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao enviar mensagem.')
    } finally {
      setLoading(false)
    }
  }

  function selectAgent(a: AgentPersona) {
    setSelectedAgent(a)
    setMessages([])
    setActiveThreadId(null)
    setError(null)
  }

  async function loadThread(threadId: string) {
    setLoading(true)
    setError(null)
    try {
      const t = await chatApi.getThread(threadId)
      setMessages(t.messages.map((m) => ({ role: m.role, content: m.content })))
      setActiveThreadId(t.thread_id)
      if (t.graph_project_id) setGraphProjectId(t.graph_project_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar conversa.')
    } finally {
      setLoading(false)
    }
  }

  function startNewConversation() {
    setMessages([])
    setActiveThreadId(null)
  }

  async function handleRenameThread(threadId: string, currentTitle: string) {
    const title = window.prompt('Novo título:', currentTitle)
    if (!title || title === currentTitle) return
    try {
      await chatApi.renameThread(threadId, title.trim())
      refreshThreads()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao renomear.')
    }
  }

  async function handleDeleteThread(threadId: string) {
    if (!window.confirm('Excluir esta conversa? Esta ação é permanente.')) return
    try {
      await chatApi.deleteThread(threadId)
      if (activeThreadId === threadId) {
        setActiveThreadId(null)
        setMessages([])
      }
      refreshThreads()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao excluir.')
    }
  }

  const activeThread = threads.find((t) => t.thread_id === activeThreadId)

  return (
    <Layout>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Chat com Agentes</h1>
          <p className="text-gray-500 text-sm mt-1">
            55 personas simuladas · 5 ferramentas profissionais · conversas salvas
          </p>
        </div>
        <select
          value={graphProjectId}
          onChange={(e) => setGraphProjectId(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
          title="Grafo para uso das ferramentas"
        >
          <option value="">Sem grafo (apenas conversa)</option>
          {projects.map((p) => (
            <option key={p.project_id} value={p.project_id}>{p.name}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-12 gap-4" style={{ height: 'calc(100vh - 200px)', minHeight: '500px' }}>
        {/* Left: Agent list */}
        <div className="col-span-3 bg-white border border-gray-200 rounded-xl p-3 flex flex-col min-h-0">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="🔍 Buscar agente…"
            className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm mb-2 shrink-0"
          />
          <div className="flex flex-wrap gap-1 mb-2 shrink-0">
            {categories.slice(0, 7).map((c) => (
              <button
                key={c}
                onClick={() => setCategoryFilter(c)}
                className={`text-xs px-2 py-0.5 rounded-full transition-colors ${
                  categoryFilter === c ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {c === 'all' ? 'Todos' : c}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-400 mb-1 shrink-0">
            {filtered.length} de {agents.length} agentes
          </p>
          <div className="flex-1 overflow-y-auto space-y-1 -mx-1 px-1 min-h-0">
            {filtered.map((a) => {
              const agentThreadCount = threads.filter((t) => t.agent_id === a.id).length
              return (
                <button
                  key={a.id}
                  onClick={() => selectAgent(a)}
                  className={`w-full text-left flex items-start gap-2 p-2 rounded-lg transition-colors ${
                    selectedAgent?.id === a.id ? 'bg-brand-50 border border-brand-300' : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <span className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-xs font-bold flex items-center justify-center shrink-0 uppercase">
                    {a.avatar_letter}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1">
                      <p className="text-sm font-medium text-gray-900 truncate flex-1">{a.name}</p>
                      {agentThreadCount > 0 && (
                        <span className="text-[10px] bg-brand-100 text-brand-700 px-1.5 py-0.5 rounded-full font-semibold">
                          {agentThreadCount}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 truncate">{a.role}</p>
                    <span className={`inline-block mt-0.5 text-[10px] px-1.5 py-0.5 rounded ${CATEGORY_COLORS[a.category] || 'bg-gray-100 text-gray-700'}`}>
                      {a.category}
                    </span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Right: Chat area */}
        <div className="col-span-9 flex flex-col gap-3 min-h-0 overflow-hidden">
          {!selectedAgent ? (
            <div className="flex-1 min-h-0 bg-white border border-dashed border-gray-300 rounded-xl flex items-center justify-center">
              <div className="text-center">
                <p className="text-5xl mb-3">🤖</p>
                <p className="text-gray-500">Selecione um agente para começar</p>
                <p className="text-xs text-gray-400 mt-1">{agents.length} personas · {threads.length} conversas salvas</p>
              </div>
            </div>
          ) : (
            <>
              {/* Thread bar */}
              {agentThreads.length > 0 && (
                <div className="bg-white border border-gray-200 rounded-xl p-2 flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-gray-500 font-medium px-1">Conversas:</span>
                  <button
                    onClick={startNewConversation}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      !activeThreadId
                        ? 'bg-brand-600 text-white border-brand-600'
                        : 'bg-white border-gray-300 text-gray-600 hover:border-brand-400'
                    }`}
                  >
                    ＋ Nova
                  </button>
                  {agentThreads.slice(0, 8).map((t) => (
                    <div
                      key={t.thread_id}
                      className={`group flex items-center gap-1 text-xs rounded-full border transition-colors ${
                        activeThreadId === t.thread_id
                          ? 'bg-brand-600 text-white border-brand-600'
                          : 'bg-white border-gray-300 text-gray-600 hover:border-brand-400'
                      }`}
                    >
                      <button
                        onClick={() => loadThread(t.thread_id)}
                        className="px-2.5 py-1 max-w-[180px] truncate"
                        title={`${t.title} — ${new Date(t.updated_at).toLocaleString('pt-BR')}`}
                      >
                        {t.title}
                      </button>
                      <button
                        onClick={() => handleRenameThread(t.thread_id, t.title)}
                        className={`opacity-0 group-hover:opacity-100 px-1 transition-opacity ${
                          activeThreadId === t.thread_id ? 'text-white/80' : 'text-gray-400 hover:text-brand-600'
                        }`}
                        title="Renomear"
                      >
                        ✎
                      </button>
                      <button
                        onClick={() => handleDeleteThread(t.thread_id)}
                        className={`opacity-0 group-hover:opacity-100 px-1 pr-2 transition-opacity ${
                          activeThreadId === t.thread_id ? 'text-white/80' : 'text-gray-400 hover:text-red-600'
                        }`}
                        title="Excluir"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  {agentThreads.length > 8 && (
                    <span className="text-xs text-gray-400">+{agentThreads.length - 8} mais</span>
                  )}
                </div>
              )}

              {/* Tool selector */}
              <div className="bg-white border border-gray-200 rounded-xl p-3">
                <div className="flex items-center gap-3 mb-3">
                  <span className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-bold flex items-center justify-center uppercase">
                    {selectedAgent.avatar_letter}
                  </span>
                  <div className="flex-1">
                    <p className="font-bold text-gray-900">{selectedAgent.name}</p>
                    <p className="text-xs text-gray-500">{selectedAgent.role} · {selectedAgent.category}</p>
                  </div>
                  {activeThread && (
                    <span className="text-xs text-brand-600 font-medium">
                      📌 {activeThread.title.slice(0, 40)}{activeThread.title.length > 40 ? '…' : ''}
                    </span>
                  )}
                  <button
                    onClick={startNewConversation}
                    className="text-xs text-gray-500 hover:text-brand-600"
                    title="Iniciar nova conversa (sem apagar a atual)"
                  >
                    ＋ Nova conversa
                  </button>
                </div>
                <p className="text-xs text-gray-600 mb-2">{selectedAgent.description}</p>
                <div className="grid grid-cols-5 gap-2">
                  {TOOLS.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setTool(t.id)}
                      title={t.desc}
                      className={`p-2 rounded-lg text-xs transition-all border ${
                        tool === t.id
                          ? 'border-brand-500 bg-brand-50 shadow-sm'
                          : 'border-gray-200 bg-white hover:border-brand-300'
                      }`}
                    >
                      <div className="text-lg">{t.icon}</div>
                      <p className={`font-semibold mt-0.5 ${tool === t.id ? 'text-brand-700' : 'text-gray-800'}`}>
                        {t.label}
                      </p>
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-gray-400 mt-2">
                  {TOOLS.find((t) => t.id === tool)?.desc}
                  {(tool === 'quick_search' || tool === 'panorama_search' || tool === 'insight_forge') && !graphProjectId && (
                    <span className="text-amber-600"> · ⚠ requer um grafo selecionado acima</span>
                  )}
                </p>
              </div>

              {/* Messages */}
              <div ref={logRef} className="flex-1 min-h-0 bg-gray-50 border border-gray-200 rounded-xl p-4 overflow-y-auto space-y-3">
                {messages.length === 0 && (
                  <div className="text-center text-gray-400 py-12">
                    <p className="text-3xl mb-2">{TOOLS.find((t) => t.id === tool)?.icon}</p>
                    <p className="text-sm">Inicie a conversa com {selectedAgent.name}</p>
                    <p className="text-xs mt-1">Modo: {TOOLS.find((t) => t.id === tool)?.label}</p>
                    {agentThreads.length > 0 && (
                      <p className="text-xs mt-2 text-gray-500">
                        ou continue uma conversa anterior acima ↑
                      </p>
                    )}
                  </div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {m.role === 'assistant' && (
                      <span className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-xs font-bold flex items-center justify-center shrink-0 uppercase">
                        {selectedAgent.avatar_letter}
                      </span>
                    )}
                    <div className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap leading-relaxed ${
                      m.role === 'user'
                        ? 'bg-brand-600 text-white rounded-tr-sm'
                        : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm'
                    }`}>
                      {m.content}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex gap-3 justify-start">
                    <span className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-xs font-bold flex items-center justify-center shrink-0 uppercase">
                      {selectedAgent.avatar_letter}
                    </span>
                    <div className="bg-white border border-gray-200 rounded-2xl px-4 py-2 text-sm text-gray-400">
                      <span className="inline-block animate-pulse">Pensando…</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Input */}
              <div className="bg-white border border-gray-200 rounded-xl p-3 flex gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                  placeholder={`Mensagem para ${selectedAgent.name}…`}
                  disabled={loading}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
                />
                <button
                  onClick={handleSend}
                  disabled={loading || !input.trim()}
                  className="bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-medium px-4 py-2 rounded-lg text-sm"
                >
                  {loading ? '…' : 'Enviar'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </Layout>
  )
}
