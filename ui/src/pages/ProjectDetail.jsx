import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'

export default function ProjectDetail() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [currentPage, setCurrentPage] = useState(0)
  const [totalPages, setTotalPages] = useState(13)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [downloadingProposal, setDownloadingProposal] = useState(false)

  useEffect(() => {
    fetch(`/api/projects/${id}`)
      .then(r => r.json())
      .then(data => {
        setProject(data)
        // Check if planset already exists by trying to fetch it
        fetch(`/api/projects/${id}/planset`)
          .then(r => {
            if (r.ok) {
              setGenerated(true)
              setShowPreview(true)
            }
          })
          .catch(() => {})
      })
      .catch(console.error)
  }, [id])

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true)
    try {
      const res = await fetch(`/api/projects/${id}/planset?format=pdf`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        alert(data.detail || 'PDF generation failed')
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `planset_${id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('Error: ' + e.message)
    } finally {
      setDownloadingPdf(false)
    }
  }

  const handleDownloadProposal = async () => {
    setDownloadingProposal(true)
    try {
      const res = await fetch(`/api/proposal-pdf/${id}`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        alert(data.detail || 'Proposal generation failed')
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `proposal_${id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('Error: ' + e.message)
    } finally {
      setDownloadingProposal(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await fetch(`/api/projects/${id}/generate`, { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        setGenerated(true)
        setShowPreview(true)
      } else {
        alert(data.detail || 'Generation failed')
      }
    } catch (e) {
      alert('Error: ' + e.message)
    }
    setGenerating(false)
  }

  if (!project) return <div className="text-center py-12 text-gray-500">Loading...</div>

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <Link to="/" className="text-solar-600 hover:text-solar-700">&larr; Back</Link>
        <h1 className="text-2xl font-bold text-gray-900">{project.project_name || project.address}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Project Details — left column */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">Project Details</h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Address</dt>
              <dd className="font-medium text-gray-900 text-right ml-4">{project.address}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Panel</dt>
              <dd className="font-medium">{project.panel_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Inverter</dt>
              <dd className="font-medium">{project.inverter_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Racking</dt>
              <dd className="font-medium">{project.racking_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Roof</dt>
              <dd className="font-medium">{project.roof_material}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Panels</dt>
              <dd className="font-medium">{project.num_panels}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Main Breaker</dt>
              <dd className="font-medium">{project.main_panel_breaker_a}A</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Bus Rating</dt>
              <dd className="font-medium">{project.main_panel_bus_rating_a}A</dd>
            </div>
          </dl>

          <hr className="my-4" />

          {/* Actions */}
          {generated ? (
            <div className="space-y-3">
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-green-800 text-sm">
                Planset ready
              </div>
              <button
                onClick={() => setShowPreview(true)}
                className="w-full bg-solar-600 hover:bg-solar-700 text-white px-4 py-2.5 rounded-lg font-medium text-sm"
              >
                Review Planset
              </button>
              <button
                onClick={handleDownloadPdf}
                disabled={downloadingPdf}
                className="w-full bg-green-600 hover:bg-green-700 text-white px-4 py-2.5 rounded-lg font-medium text-sm disabled:opacity-50"
              >
                {downloadingPdf ? 'Generating PDF…' : 'Download PDF'}
              </button>
              <button
                onClick={handleDownloadProposal}
                disabled={downloadingProposal}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white px-4 py-2.5 rounded-lg font-medium text-sm disabled:opacity-50"
              >
                {downloadingProposal ? 'Generating…' : 'Download Proposal'}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-600">
                Generate a 13-page engineering planset with equipment specs, electrical calculations, and code compliance.
              </p>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="w-full bg-solar-600 hover:bg-solar-700 text-white px-4 py-2.5 rounded-lg font-medium disabled:opacity-50"
              >
                {generating ? 'Generating...' : 'Generate Planset'}
              </button>
            </div>
          )}
        </div>

        {/* Planset Preview — right 2 columns */}
        <div className="lg:col-span-2">
          {showPreview && generated ? (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {/* Preview toolbar */}
              <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-700">Planset Preview</span>
                  <span className="text-xs text-gray-400">Scroll to review all pages</span>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={`/api/projects/${id}/planset`}
                    target="_blank"
                    className="text-xs bg-white border border-gray-300 hover:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-md"
                  >
                    Open in New Tab
                  </a>
                  <button
                    onClick={handleDownloadPdf}
                    disabled={downloadingPdf}
                    className="text-xs bg-solar-600 hover:bg-solar-700 text-white px-3 py-1.5 rounded-md disabled:opacity-50"
                  >
                    {downloadingPdf ? 'Generating…' : 'Download PDF'}
                  </button>
                  <button
                    onClick={handleDownloadProposal}
                    disabled={downloadingProposal}
                    className="text-xs bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded-md disabled:opacity-50"
                  >
                    {downloadingProposal ? 'Generating…' : 'Download Proposal'}
                  </button>
                </div>
              </div>

              {/* Planset iframe */}
              <iframe
                src={`/api/projects/${id}/planset?t=${Date.now()}`}
                title="Planset Preview"
                className="w-full border-0"
                style={{ height: '75vh', minHeight: '600px' }}
                sandbox="allow-same-origin allow-scripts"
              />
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center" style={{ minHeight: '400px' }}>
              <div className="flex flex-col items-center justify-center h-full">
                <div className="text-5xl mb-4 opacity-30">&#128196;</div>
                <h3 className="text-lg font-medium text-gray-400 mb-2">Planset Preview</h3>
                <p className="text-sm text-gray-400">
                  {generated
                    ? 'Click "Review Planset" to preview the generated planset here.'
                    : 'Generate a planset to preview it here.'}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
