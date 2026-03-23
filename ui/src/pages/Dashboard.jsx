import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function Dashboard() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/projects')
      .then(r => r.json())
      .then(data => { setProjects(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <Link
          to="/new"
          className="bg-solar-600 hover:bg-solar-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          + New Project
        </Link>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : projects.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <div className="text-4xl mb-4">&#9728;</div>
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
          {projects.map(p => (
            <Link
              key={p.project_id}
              to={`/project/${p.project_id}`}
              className="bg-white rounded-xl border border-gray-200 p-5 hover:border-solar-500 hover:shadow-md transition-all"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{p.address}</h3>
                  <div className="text-sm text-gray-500 mt-1">
                    {p.panel_id} &middot; {p.inverter_id} &middot; {p.num_panels} panels
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-medium ${p.planset_ready ? 'text-green-600' : 'text-yellow-600'}`}>
                    {p.planset_ready ? 'Planset Ready' : 'Draft'}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
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
