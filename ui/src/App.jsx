import { useState, useEffect } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import ProjectWizard from './pages/ProjectWizard'
import ProjectDetail from './pages/ProjectDetail'

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')

  useEffect(() => {
    document.body.classList.remove('light', 'dark')
    document.body.classList.add(theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light')

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--bg)', color: 'var(--text)' }}>
      {/* Navigation */}
      <nav style={{ backgroundColor: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }} className="px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-solar-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">QS</span>
            </div>
            <span className="text-lg font-semibold" style={{ color: 'var(--text)' }}>Quebec Solaire</span>
            <span className="text-sm ml-1" style={{ color: 'var(--text-muted)' }}>Planset Generator</span>
          </Link>
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
              style={{ backgroundColor: 'var(--border)', color: 'var(--text)' }}
              aria-label="Toggle dark mode"
            >
              {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
            </button>
            <Link
              to="/new"
              className="bg-solar-600 hover:bg-solar-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              + New Project
            </Link>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 w-full">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<ProjectWizard />} />
          <Route path="/project/:id" element={<ProjectDetail />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="text-xs text-gray-400 py-4 text-center" style={{ borderTop: '1px solid var(--border)' }}>
        Solar Planset Tool &middot; v2.0
      </footer>
    </div>
  )
}
