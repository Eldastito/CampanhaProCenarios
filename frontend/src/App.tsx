import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import CreateScenarioPage from './pages/CreateScenarioPage'
import ScenarioDetailPage from './pages/ScenarioDetailPage'
import ComparePage from './pages/ComparePage'
import PredictionsPage from './pages/PredictionsPage'
import SavedPredictionsPage from './pages/SavedPredictionsPage'
import GraphPage from './pages/GraphPage'
import SimulationPage from './pages/SimulationPage'
import WorkspacePage from './pages/WorkspacePage'
import ResearchPage from './pages/ResearchPage'
import ChatPage from './pages/ChatPage'
import PoliticalProjectsPage from './pages/PoliticalProjectsPage'
import EvidencePage from './pages/EvidencePage'
import PoliticalAgentsPage from './pages/PoliticalAgentsPage'
import PoliticalGraphPage from './pages/PoliticalGraphPage'
import DossiersPage from './pages/DossiersPage'
import DossierDetailPage from './pages/DossierDetailPage'
import ElectionProbabilityPage from './pages/ElectionProbabilityPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/political/projects" element={<PoliticalProjectsPage />} />
            <Route path="/political/projects/:projectId/evidence" element={<EvidencePage />} />
            <Route path="/political/projects/:projectId/agents" element={<PoliticalAgentsPage />} />
            <Route path="/political/projects/:projectId/graph" element={<PoliticalGraphPage />} />
            <Route path="/political/projects/:projectId/dossiers" element={<DossiersPage />} />
            <Route
              path="/political/projects/:projectId/dossiers/:dossierId"
              element={<DossierDetailPage />}
            />
            <Route
              path="/political/projects/:projectId/election-probability"
              element={<ElectionProbabilityPage />}
            />
            <Route path="/scenarios/new" element={<CreateScenarioPage />} />
            <Route path="/scenarios/:id" element={<ScenarioDetailPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/predictions" element={<PredictionsPage />} />
            <Route path="/saved-predictions" element={<SavedPredictionsPage />} />
            <Route path="/graph" element={<GraphPage />} />
            <Route path="/simulations/new" element={<SimulationPage />} />
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/research" element={<ResearchPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
