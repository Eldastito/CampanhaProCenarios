import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import PoliticalGraphPanel from '../components/PoliticalGraphPanel'
import {
  politicalGraphApi,
  politicalProjectsApi,
  type PoliticalGraphData,
  type PoliticalProject,
} from '../api/client'

export default function PoliticalGraphPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<PoliticalProject | null>(null)
  const [graph, setGraph] = useState<PoliticalGraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [building, setBuilding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(
    async (mode: 'initial' | 'refresh' = 'initial') => {
      if (!projectId) return
      if (mode === 'initial') setLoading(true)
      else setRefreshing(true)
      setError(null)
      try {
        const proj = await politicalProjectsApi.get(projectId)
        setProject(proj)
        try {
          const g = await politicalGraphApi.get(projectId)
          setGraph(g)
        } catch (e) {
          // 404 esperado quando o grafo ainda não foi construído
          if ((e as Error).message?.toLowerCase().includes('nenhum grafo')) {
            setGraph(null)
          } else {
            throw e
          }
        }
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [projectId],
  )

  useEffect(() => {
    load('initial')
  }, [load])

  async function buildGraph() {
    if (!projectId) return
    setBuilding(true)
    setError(null)
    try {
      await politicalGraphApi.build(projectId)
      await load('refresh')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBuilding(false)
    }
  }

  return (
    <Layout wide>
      <div className="mb-4">
        <Link to="/political/projects" className="text-sm text-brand-600 hover:underline">
          ← Projetos
        </Link>
        <div className="flex items-start justify-between mt-2">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Grafo Político</h1>
            <p className="text-sm text-gray-600 mt-1">
              {project ? (
                <>
                  {project.name} · {project.candidate_name} · {project.office} {project.election_year}
                </>
              ) : (
                'Carregando projeto…'
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to={`/political/projects/${projectId}/evidence`}
              className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              📄 Evidências
            </Link>
            <Link
              to={`/political/projects/${projectId}/agents`}
              className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              🧑‍⚖️ Bancada
            </Link>
            <button
              onClick={buildGraph}
              disabled={building}
              className="text-xs px-3 py-1.5 rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {building ? '🕸 Reconstruindo…' : '🕸 Reconstruir grafo'}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}

      {loading ? (
        <LoadingState />
      ) : graph === null ? (
        <EmptyState onBuild={buildGraph} building={building} projectId={projectId} />
      ) : (
        <>
          <PoliticalGraphPanel
            nodes={graph.nodes}
            edges={graph.edges}
            height={680}
            isLive={building}
            onRefresh={() => load('refresh')}
            refreshing={refreshing}
          />
          <p className="mt-3 text-xs text-gray-500">
            Status: <code className="text-gray-700">{graph.status}</code> · clique num nó para
            inspecionar a entidade · clique numa aresta para ver a relação · use a roda do mouse
            para zoom · arraste nós para reorganizar.
          </p>
        </>
      )}
    </Layout>
  )
}

function LoadingState() {
  return (
    <div className="rounded-xl border border-slate-700 pg-canvas h-[680px] flex flex-col items-center justify-center gap-4">
      <span className="ring-loader">
        <span />
        <span />
        <span />
      </span>
      <p className="text-sm text-slate-300">Carregando grafo…</p>
    </div>
  )
}

function EmptyState({
  onBuild,
  building,
  projectId,
}: {
  onBuild: () => void
  building: boolean
  projectId: string | undefined
}) {
  return (
    <div className="rounded-xl border-2 border-dashed border-gray-300 p-12 text-center">
      <p className="text-gray-700 font-medium">Nenhum grafo construído para este projeto.</p>
      <p className="text-sm text-gray-500 mt-2 max-w-md mx-auto">
        Suba evidências (notícias, manifestos, atas, pesquisas) e clique em{' '}
        <strong>Construir grafo</strong> para extrair entidades e relações políticas com IA.
      </p>
      <div className="mt-5 flex items-center justify-center gap-2">
        {projectId && (
          <Link
            to={`/political/projects/${projectId}/evidence`}
            className="text-xs px-3 py-1.5 rounded-lg border border-brand-600 text-brand-700 hover:bg-brand-50"
          >
            📄 Subir evidências
          </Link>
        )}
        <button
          onClick={onBuild}
          disabled={building}
          className="text-xs px-3 py-1.5 rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {building ? '🕸 Construindo…' : '🕸 Construir grafo'}
        </button>
      </div>
    </div>
  )
}
