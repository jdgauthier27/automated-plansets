import { Routes, Route, Link } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import ProjectWizard from './pages/ProjectWizard'
import ProjectDetail from './pages/ProjectDetail'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-solar-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">QS</span>
            </div>
            <span className="text-lg font-semibold text-gray-900">Quebec Solaire</span>
            <span className="text-sm text-gray-400 ml-1">Planset Generator</span>
          </Link>
          <Link
            to="/new"
            className="bg-solar-600 hover:bg-solar-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            + New Project
          </Link>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<ProjectWizard />} />
          <Route path="/project/:id" element={<ProjectDetail />} />
        </Routes>
      </main>
    </div>
  )
}
