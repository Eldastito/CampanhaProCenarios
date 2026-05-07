import { FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { graphApi } from '../api/client'
import type { GraphProjectSummary, GraphData } from '../api/client'
import Layout from '../components/Layout'
import GraphViewer from '../components/GraphViewer'
import { useAuth } from '../contexts/AuthContext'
import { SCENARIO_CATALOG } from '../scenarioCatalog'

export default function GraphPage() {
  const { user } = useAuth()
  const [projects, setProjects] = useState<GraphProjectSummary[]>([])
  const [selectedProject, setSelectedProject] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const [building, setBuilding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // New project form
  const [showForm, setShowForm] = useState(false)
  const [formName, setFormName] = useState('')
  const [formType, setFormType] = useState('political')
  const [formText, setFormText] = useState('')

  // Edit modal
  const [editingProject, setEditingProject] = useState<GraphProjectSummary | null>(null)
  const [editName, setEditName] = useState('')
  const [saving, setSaving] = useState(false)

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    if (user) loadProjects()
  }, [user]) // eslint-disable-line react-hooks/exhaustive-deps

  async function loadProjects() {
    if (!user) return
    try {
      const data = await graphApi.list(user.organization_id)
      setProjects(data.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar projetos.')
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!user) return
    setLoading(true)
    setError(null)
    try {
      const project = await graphApi.create({
        organization_id: user.organization_id,
        name: formName,
        scenario_type: formType,
      })
      setBuilding(true)
      const built = await graphApi.build(project.project_id, formText || 'Dados de demonstração.')
      setBuilding(false)
      setShowForm(false)
      setFormName('')
      setFormText('')
      await loadProjects()
      if (built.status === 'ready') {
        const graph = await graphApi.get(project.project_id)
        setSelectedProject(graph)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao criar projeto.')
      setBuilding(false)
    } finally {
      setLoading(false)
    }
  }

  async function openProject(projectId: string) {
    try {
      const graph = await graphApi.get(projectId)
      setSelectedProject(graph)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar grafo.')
    }
  }

  async function handleSaveEdit() {
    if (!editingProject || !editName.trim()) return
    setSaving(true)
    try {
      await graphApi.patch(editingProject.project_id, { name: editName.trim() })
      setProjects((prev) =>
        prev.map((p) => p.project_id === editingProject.project_id ? { ...p, name: editName.trim() } : p)
      )
      if (selectedProject?.project_id === editingProject.project_id) {
        setSelectedProject((prev) => prev ? { ...prev, name: editName.trim() } : prev)
      }
      setEditingProject(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao renomear.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(projectId: string) {
    try {
      await graphApi.delete(projectId)
      setProjects((prev) => prev.filter((p) => p.project_id !== projectId))
      if (selectedProject?.project_id === projectId) setSelectedProject(null)
      setDeletingId(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao excluir.')
      setDeletingId(null)
    }
  }

  const scenarioLabel = (type: string) =>
    SCENARIO_CATALOG.find((s) => s.type === type)?.label ?? type

  return (
    <Layout>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Grafos de Conhecimento</h1>
          <p className="text-gray-500 mt-1">
            Construa grafos a partir de textos e visualize relações entre entidades.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadProjects}
            className="border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm px-3 py-2 rounded-lg transition-colors"
            title="Atualizar lista"
          >
            ↻
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            + Novo Grafo
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center justify-between">
          {error}
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-3">✕</button>
        </div>
      )}

      {/* New project form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-brand-200 p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Novo Grafo de Conhecimento</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nome do Projeto *</label>
                <input
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
                  placeholder="Ex: Eleição Municipal 2026"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de Cenário</label>
                <select
                  value={formType}
                  onChange={(e) => setFormType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
                >
                  {SCENARIO_CATALOG.map((s) => (
                    <option key={s.type} value={s.type}>{s.icon} {s.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Texto fonte (cole notícias, relatórios, dados)
              </label>
              <textarea
                value={formText}
                onChange={(e) => setFormText(e.target.value)}
                rows={8}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none resize-y font-mono"
                placeholder="Cole aqui o texto que será analisado para extrair entidades e relações. Quanto mais detalhado, melhor o grafo."
              />
              <p className="text-xs text-gray-400 mt-1">
                💡 Com OPENAI_API_KEY configurada, a IA extrai entidades automaticamente. Sem chave, gera grafo de demonstração.
              </p>
            </div>
            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
                Cancelar
              </button>
              <button
                type="submit"
                disabled={loading || building}
                className="bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-medium py-2 px-6 rounded-lg text-sm"
              >
                {building ? '🔄 Construindo grafo…' : loading ? 'Criando…' : 'Criar e Construir'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Project list */}
        <div className="col-span-1 space-y-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Projetos</h2>
          {projects.length === 0 && !showForm && (
            <p className="text-sm text-gray-400 py-8 text-center">Nenhum grafo criado ainda.</p>
          )}
          {projects.map((p) => (
            <div
              key={p.project_id}
              onClick={() => openProject(p.project_id)}
              className={`bg-white border rounded-xl p-4 cursor-pointer transition-all hover:border-brand-300 ${
                selectedProject?.project_id === p.project_id ? 'border-brand-500 bg-brand-50' : 'border-gray-200'
              }`}
            >
              <p className="font-medium text-gray-900 text-sm truncate">{p.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">{scenarioLabel(p.scenario_type)}</p>
              <div className="flex gap-3 mt-2 text-xs text-gray-400">
                <span>{p.node_count} nós</span>
                <span>{p.edge_count} arestas</span>
                <span className={`font-medium ${p.status === 'ready' ? 'text-green-600' : p.status === 'building' ? 'text-yellow-600' : 'text-gray-400'}`}>
                  {p.status}
                </span>
              </div>
              {/* Action buttons */}
              <div className="flex gap-2 mt-3 pt-2 border-t border-gray-100" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => { setEditingProject(p); setEditName(p.name) }}
                  className="flex-1 text-xs text-gray-500 hover:text-brand-700 hover:bg-brand-50 py-1 rounded transition-colors"
                >
                  ✏ Renomear
                </button>
                <button
                  onClick={() => setDeletingId(p.project_id)}
                  className="flex-1 text-xs text-gray-500 hover:text-red-600 hover:bg-red-50 py-1 rounded transition-colors"
                >
                  🗑 Excluir
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Graph viewer */}
        <div className="col-span-2">
          {!selectedProject ? (
            <div className="bg-gray-950 rounded-xl h-96 flex items-center justify-center">
              <p className="text-gray-600">Selecione um projeto para visualizar o grafo</p>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold text-gray-900">{selectedProject.name}</h2>
                <Link
                  to={`/workspace?project=${selectedProject.project_id}`}
                  className="text-sm bg-brand-600 hover:bg-brand-700 text-white px-3 py-1.5 rounded-lg transition-colors"
                >
                  🔬 Abrir na Bancada
                </Link>
              </div>
              <GraphViewer
                nodes={selectedProject.nodes}
                edges={selectedProject.edges}
                height="520px"
              />
              <p className="text-xs text-gray-400 mt-2 text-center">
                {selectedProject.node_count} entidades · {selectedProject.edge_count} relações · Arraste para mover, scroll para zoom
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Rename modal */}
      {editingProject && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Renomear Grafo</h3>
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSaveEdit() }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none mb-4"
              autoFocus
            />
            <div className="flex gap-3">
              <button
                onClick={() => setEditingProject(null)}
                className="flex-1 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={saving || !editName.trim()}
                className="flex-1 py-2 text-sm bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white rounded-lg font-medium"
              >
                {saving ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      {deletingId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-sm shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Excluir Grafo</h3>
            <p className="text-sm text-gray-500 mb-6">
              Isso vai excluir permanentemente o grafo e todas as simulações associadas. Não é reversível.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeletingId(null)}
                className="flex-1 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDelete(deletingId)}
                className="flex-1 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium"
              >
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
