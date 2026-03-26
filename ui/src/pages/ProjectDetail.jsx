import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'

function Spinner({ className = 'w-4 h-4' }) {
  return (
    <div className={`${className} border-2 border-current border-t-transparent rounded-full animate-spin`} />
  )
}

function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div className="bg-red-600 text-white rounded-lg px-4 py-3 flex items-center justify-between mb-3">
      <span className="text-sm">{message}</span>
      {onDismiss && <button onClick={onDismiss} className="text-white/80 hover:text-white ml-4 text-lg leading-none">&times;</button>}
    </div>
  )
}

const ROOF_MATERIALS = {
  asphalt_shingle: 'Asphalt Shingle',
  composite_shingle: 'Composite Shingle',
  metal_standing_seam: 'Metal Standing Seam',
  clay_tile: 'Clay Tile',
  concrete_tile: 'Concrete Tile',
  flat_membrane: 'Flat Membrane (TPO/EPDM)',
  metal_corrugated: 'Corrugated Metal',
}

const GENERATION_STAGES = [
  { label: 'Downloading satellite imagery...', icon: '\u{1F6F0}' },
  { label: 'Extracting roof geometry...', icon: '\u{1F3E0}' },
  { label: 'Placing solar panels...', icon: '\u2600' },
  { label: 'Computing electrical design...', icon: '\u26A1' },
  { label: 'Rendering planset pages...', icon: '\u{1F4C4}' },
]

export default function ProjectDetail() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [downloadingProposal, setDownloadingProposal] = useState(false)
  const [error, setError] = useState(null)
  const [generationSuccess, setGenerationSuccess] = useState(false)

  // Equipment resolution
  const [panelInfo, setPanelInfo] = useState(null)
  const [inverterInfo, setInverterInfo] = useState(null)
  const [rackingInfo, setRackingInfo] = useState(null)

  // Generation progress
  const [generationStage, setGenerationStage] = useState(0)
  const stageTimerRef = useRef(null)

  // Fetch equipment details by ID
  const fetchEquipment = useCallback((proj) => {
    if (proj.panel_id) {
      fetch(`/api/catalog/panels/${proj.panel_id}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data) setPanelInfo(data) })
        .catch(() => {})
    }
    if (proj.inverter_id) {
      fetch(`/api/catalog/inverters/${proj.inverter_id}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data) setInverterInfo(data) })
        .catch(() => {})
    }
    if (proj.racking_id) {
      fetch('/api/catalog/racking')
        .then(r => r.ok ? r.json() : [])
        .then(list => {
          const match = list.find(r => r.id === proj.racking_id)
          if (match) setRackingInfo(match)
        })
        .catch(() => {})
    }
  }, [])

  useEffect(() => {
    fetch(`/api/projects/${id}`)
      .then(r => {
        if (!r.ok) throw new Error('Failed to load project')
        return r.json()
      })
      .then(data => {
        setProject(data)
        fetchEquipment(data)
        fetch(`/api/projects/${id}/planset`)
          .then(r => {
            if (r.ok) {
              setGenerated(true)
              setShowPreview(true)
            }
          })
          .catch(() => {})
      })
      .catch(e => setLoadError(e.message))
  }, [id, fetchEquipment])

  // Cleanup stage timer on unmount
  useEffect(() => {
    return () => {
      if (stageTimerRef.current) clearInterval(stageTimerRef.current)
    }
  }, [])

  const startProgressSimulation = () => {
    setGenerationStage(0)
    let stage = 0
    stageTimerRef.current = setInterval(() => {
      stage += 1
      if (stage < GENERATION_STAGES.length) {
        setGenerationStage(stage)
      } else {
        clearInterval(stageTimerRef.current)
        stageTimerRef.current = null
      }
    }, 6000)
  }

  const stopProgressSimulation = () => {
    if (stageTimerRef.current) {
      clearInterval(stageTimerRef.current)
      stageTimerRef.current = null
    }
  }

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true)
    setError(null)
    try {
      const res = await fetch(`/api/projects/${id}/planset?format=pdf`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'PDF generation failed')
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
      setError('PDF download error: ' + e.message)
    } finally {
      setDownloadingPdf(false)
    }
  }

  const handleDownloadProposal = async () => {
    setDownloadingProposal(true)
    setError(null)
    try {
      const res = await fetch(`/api/proposal-pdf/${id}`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Proposal generation failed')
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
      setError('Proposal download error: ' + e.message)
    } finally {
      setDownloadingProposal(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    setGenerationSuccess(false)
    startProgressSimulation()
    try {
      const res = await fetch(`/api/projects/${id}/generate`, { method: 'POST' })
      const data = await res.json()
      stopProgressSimulation()
      if (res.ok) {
        setGenerationStage(GENERATION_STAGES.length - 1)
        setGenerationSuccess(true)
        setTimeout(() => {
          setGenerated(true)
          setShowPreview(true)
          setGenerationSuccess(false)
        }, 2000)
      } else {
        setError(data.detail || 'Generation failed')
      }
    } catch (e) {
      stopProgressSimulation()
      setError('Generation error: ' + e.message)
    }
    setGenerating(false)
  }

  // Derived values
  const systemDcKw = panelInfo && project
    ? (project.num_panels * panelInfo.wattage_w / 1000).toFixed(2)
    : null
  const inverterTypeLabel = inverterInfo
    ? inverterInfo.type === 'microinverter' ? 'Microinverter' : 'String Inverter'
    : null

  if (loadError) return (
    <div className="text-center py-12">
      <div className="bg-red-600 text-white rounded-lg px-4 py-3 inline-block mb-4 text-sm">{loadError}</div>
      <div>
        <Link to="/" className="text-solar-600 hover:text-solar-700 text-sm">&larr; Back to projects</Link>
      </div>
    </div>
  )

  if (!project) return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-500">
      <Spinner className="w-8 h-8 text-solar-600" />
      <span className="mt-3 text-sm">Loading project...</span>
    </div>
  )

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <Link to="/" className="text-solar-600 hover:text-solar-700">&larr; Back</Link>
        <h1 className="text-2xl font-bold text-gray-900">{project.project_name || project.address}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Project Details — left column */}
        <div className="space-y-6">
          {/* System Summary Card */}
          <div className="bg-gradient-to-br from-solar-600 to-solar-700 rounded-xl p-5 text-white">
            <h2 className="text-sm font-medium text-white/80 uppercase tracking-wide mb-3">System Summary</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-2xl font-bold">{systemDcKw || '—'}</div>
                <div className="text-xs text-white/70">kW DC</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{project.num_panels}</div>
                <div className="text-xs text-white/70">Panels</div>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-white/20 space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-white/70">Panel</span>
                <span className="font-medium text-right ml-2">
                  {panelInfo ? `${panelInfo.model_short} — ${panelInfo.wattage_w}W` : project.panel_id}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/70">Inverter</span>
                <span className="font-medium text-right ml-2">
                  {inverterInfo ? `${inverterInfo.model_short} — ${inverterTypeLabel}` : project.inverter_id}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/70">Racking</span>
                <span className="font-medium text-right ml-2">
                  {rackingInfo ? rackingInfo.model : project.racking_id}
                </span>
              </div>
            </div>
          </div>

          {/* Project Details Card */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold mb-4">Project Details</h2>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Address</dt>
                <dd className="font-medium text-gray-900 text-right ml-4">{project.address}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Panel</dt>
                <dd className="font-medium text-right ml-4">
                  {panelInfo
                    ? <>{panelInfo.manufacturer} {panelInfo.model_short} <span className="text-gray-500">— {panelInfo.wattage_w}W</span></>
                    : project.panel_id}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Inverter</dt>
                <dd className="font-medium text-right ml-4">
                  {inverterInfo
                    ? <>{inverterInfo.manufacturer} {inverterInfo.model_short} <span className="text-gray-500">— {inverterTypeLabel}</span></>
                    : project.inverter_id}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Racking</dt>
                <dd className="font-medium text-right ml-4">
                  {rackingInfo
                    ? <>{rackingInfo.manufacturer} {rackingInfo.model}</>
                    : project.racking_id}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Roof</dt>
                <dd className="font-medium">{ROOF_MATERIALS[project.roof_material] || project.roof_material}</dd>
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
            <ErrorBanner message={error} onDismiss={() => setError(null)} />

            {/* Generation Progress */}
            {generating && (
              <div className="mb-4">
                <div className="space-y-2">
                  {GENERATION_STAGES.map((stage, i) => (
                    <div
                      key={i}
                      className={`flex items-center gap-2 text-sm transition-all duration-300 ${
                        i < generationStage ? 'text-green-600' :
                        i === generationStage ? 'text-solar-600 font-medium' :
                        'text-gray-300'
                      }`}
                    >
                      <span className="w-5 text-center flex-shrink-0">
                        {i < generationStage ? (
                          <svg className="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : i === generationStage ? (
                          <Spinner className="w-4 h-4" />
                        ) : (
                          <span className="text-gray-300">&bull;</span>
                        )}
                      </span>
                      <span>{stage.label}</span>
                    </div>
                  ))}
                </div>
                {/* Animated progress bar */}
                <div className="mt-3 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-solar-600 rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${Math.min(((generationStage + 1) / GENERATION_STAGES.length) * 100, 100)}%` }}
                  />
                </div>
              </div>
            )}

            {/* Generation Success Flash */}
            {generationSuccess && !generating && (
              <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm font-medium">Planset generated successfully!</span>
              </div>
            )}

            {generated && !generating && !generationSuccess ? (
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
                  className="w-full bg-green-600 hover:bg-green-700 text-white px-4 py-2.5 rounded-lg font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {downloadingPdf && <Spinner />}
                  {downloadingPdf ? 'Generating PDF...' : 'Download PDF'}
                </button>
                <button
                  onClick={handleDownloadProposal}
                  disabled={downloadingProposal}
                  className="w-full bg-amber-500 hover:bg-amber-600 text-white px-4 py-2.5 rounded-lg font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {downloadingProposal && <Spinner />}
                  {downloadingProposal ? 'Generating...' : 'Download Proposal'}
                </button>
              </div>
            ) : !generating && !generationSuccess ? (
              <div className="space-y-3">
                <p className="text-sm text-gray-600">
                  Generate a 13-page engineering planset with equipment specs, electrical calculations, and code compliance.
                </p>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="w-full bg-solar-600 hover:bg-solar-700 text-white px-4 py-2.5 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  Generate Planset
                </button>
              </div>
            ) : null}
          </div>
        </div>

        {/* Planset Preview — right 2 columns */}
        <div className="lg:col-span-2">
          {showPreview && generated ? (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {/* Post-generation summary bar */}
              <div className="px-4 py-2.5 bg-gray-900 text-white flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1.5">
                  <span className="text-solar-400 font-semibold">{project.num_panels}</span> Panels
                </span>
                <span className="text-gray-600">|</span>
                <span className="flex items-center gap-1.5">
                  <span className="text-solar-400 font-semibold">{systemDcKw || '—'}</span> kW DC
                </span>
                <span className="text-gray-600">|</span>
                <span className="flex items-center gap-1.5">
                  {inverterInfo
                    ? <><span className="text-solar-400 font-semibold">{inverterInfo.model_short}</span> <span className="text-gray-400">({inverterTypeLabel})</span></>
                    : <span className="text-gray-400">{project.inverter_id}</span>}
                </span>
                <span className="text-gray-600">|</span>
                <span className="flex items-center gap-1.5">
                  <span className="text-solar-400 font-semibold">13</span> Pages
                </span>
              </div>

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
                    className="text-xs bg-solar-600 hover:bg-solar-700 text-white px-3 py-1.5 rounded-md disabled:opacity-50 flex items-center gap-1"
                  >
                    {downloadingPdf && <Spinner className="w-3 h-3" />}
                    {downloadingPdf ? 'Generating...' : 'Download PDF'}
                  </button>
                  <button
                    onClick={handleDownloadProposal}
                    disabled={downloadingProposal}
                    className="text-xs bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded-md disabled:opacity-50 flex items-center gap-1"
                  >
                    {downloadingProposal && <Spinner className="w-3 h-3" />}
                    {downloadingProposal ? 'Generating...' : 'Download Proposal'}
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
