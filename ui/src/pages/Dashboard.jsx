import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

function Spinner({ className = 'w-4 h-4' }) {
  return (
    <div className={`${className} border-2 border-current border-t-transparent rounded-full animate-spin`} />
  )
}

export default function Dashboard() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchProjects = () => {
    setLoading(true)
    setError(null)
    fetch('/api/projects')
      .then(r => {
        if (!r.ok) throw new Error('Failed to load projects')
        return r.json()
      })
      .then(data => { setProjects(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  useEffect(() => { fetchProjects() }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <Link
          to="/new"
          className="bg-solar-600 hover:bg-solar-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-sm hover:shadow-md transition-all"
        >
          + New Project
        </Link>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 text-gray-500">
          <Spinner className="w-8 h-8 text-solar-600" />
          <span className="mt-3 text-sm">Loading projects...</span>
        </div>
      ) : error ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <div className="bg-red-600 text-white rounded-lg px-4 py-3 inline-block mb-4 text-sm">{error}</div>
          <div>
            <button
              onClick={fetchProjects}
              className="bg-solar-600 hover:bg-solar-700 text-white px-6 py-2 rounded-lg font-medium text-sm"
            >
              Retry
            </button>
          </div>
        </div>
      ) : projects.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <div className="w-16 h-16 bg-solar-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-solar-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 3v2m0 14v2m9-9h-2M5 12H3m15.364-6.364l-1.414 1.414M7.05 16.95l-1.414 1.414m12.728 0l-1.414-1.414M7.05 7.05L5.636 5.636M12 8a4 4 0 100 8 4 4 0 000-8z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-gray-700 mb-2">No projects yet</h2>
          <p className="text-gray-500 mb-4">Create your first solar planset project to get started.</p>
          <Link
            to="/new"
            className="inline-block bg-solar-600 hover:bg-solar-700 text-white px-6 py-2 rounded-lg font-medium"
          >
            Create Project
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {[...projects].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).map(p => (
            <Link
              key={p.project_id}
              to={`/project/${p.project_id}`}
              className="bg-white rounded-xl border border-gray-200 p-5 hover:border-solar-500 hover:shadow-lg transition-all duration-200 group"
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-gray-900 group-hover:text-solar-700 transition-colors truncate">{p.address}</h3>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500 mt-1.5">
                    <span className="inline-flex items-center gap-1">
                      <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" strokeWidth="1.5"/><line x1="3" y1="9" x2="21" y2="9" strokeWidth="1.5"/><line x1="9" y1="3" x2="9" y2="21" strokeWidth="1.5"/></svg>
                      {p.num_panels} panels
                    </span>
                    <span className="text-gray-300">&middot;</span>
                    <span>{p.panel_id}</span>
                    <span className="text-gray-300">&middot;</span>
                    <span>{p.inverter_id}</span>
                  </div>
                </div>
                <div className="text-right ml-4 flex-shrink-0">
                  <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full ${
                    p.planset_ready
                      ? 'bg-green-50 text-green-700'
                      : 'bg-yellow-50 text-yellow-700'
                  }`}>
                    {p.planset_ready ? (
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7"/></svg>
                    ) : null}
                    {p.planset_ready ? 'Ready' : 'Draft'}
                  </span>
                  <div className="text-xs text-gray-400 mt-1.5">
                    {new Date(p.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
