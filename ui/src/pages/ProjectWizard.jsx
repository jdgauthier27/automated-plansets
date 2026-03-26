import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import AddressConfirm from '../components/AddressConfirm'
import EquipmentSelect from '../components/EquipmentSelect'
import SolarMap from '../components/SolarMap'
import SolarStep from '../components/SolarStep'

const STEPS = ['Address', 'Roof', 'Equipment', 'Solar', 'Electrical', 'Review']
const STORAGE_KEY = 'solar_wizard_state'
const STALE_MS = 7 * 24 * 60 * 60 * 1000 // 7 days

const ROOF_MATERIALS = [
  { value: 'asphalt_shingle', label: 'Asphalt Shingle', desc: 'Most common residential roofing — comp shingles', icon: '\u2302' },
  { value: 'composite_shingle', label: 'Composite Shingle', desc: 'Synthetic shingles, similar attachment to asphalt', icon: '\u2302' },
  { value: 'metal_standing_seam', label: 'Metal Standing Seam', desc: 'Raised seam metal panels — clamp-on racking', icon: '\u2588' },
  { value: 'clay_tile', label: 'Clay Tile', desc: 'Curved clay tiles — tile hooks required', icon: '\u223F' },
  { value: 'concrete_tile', label: 'Concrete Tile', desc: 'Flat or curved concrete tiles — tile hooks required', icon: '\u2395' },
  { value: 'flat_membrane', label: 'Flat / Membrane', desc: 'TPO, EPDM, or built-up — ballasted or adhered racking', icon: '\u25AD' },
]

const DEFAULT_FORM = {
  address: '',
  latitude: 0,
  longitude: 0,
  addressConfirmed: false,
  streetViewB64: null,
  satelliteB64: null,
  roof_material: 'asphalt_shingle',
  roof_pitch: 25,
  panel_id: '',
  inverter_id: '',
  racking_id: '',
  panel_wattage_w: 0,
  panel_dimensions_mm: null,
  panel_model: '',
  inverter_model: '',
  inverter_type: '',
  inverter_rated_w: 0,
  racking_model: '',
  main_panel_breaker_a: 200,
  main_panel_bus_rating_a: 225,
  num_panels: 13,
  company_name: localStorage.getItem('solar_company_name') || 'Solar Contractor',
  designer_name: localStorage.getItem('solar_designer_name') || '',
  project_name: '',
}

function loadSavedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const saved = JSON.parse(raw)
    if (!saved.savedAt || Date.now() - saved.savedAt > STALE_MS) {
      localStorage.removeItem(STORAGE_KEY)
      return null
    }
    return saved
  } catch {
    return null
  }
}

function Spinner({ className = 'w-4 h-4' }) {
  return (
    <div className={`${className} border-2 border-current border-t-transparent rounded-full animate-spin`} />
  )
}

function validationMessage(step, form) {
  if (step === 0) {
    if (form.address.length <= 5) return 'Enter an address and verify it to continue'
    if (!form.addressConfirmed && (form.latitude === 0 || form.longitude === 0)) return 'Enter an address and verify it to continue'
    return null
  }
  if (step === 1) {
    if (!form.roof_material) return 'Select a roof material and enter panel count'
    if (form.num_panels <= 0) return 'Select a roof material and enter panel count'
    return null
  }
  if (step === 2) {
    const missing = []
    if (!form.panel_id) missing.push('panel')
    if (!form.inverter_id) missing.push('inverter')
    if (!form.racking_id) missing.push('racking system')
    if (missing.length > 0) return `Select a ${missing.join(', ')}`
    return null
  }
  if (step === 3) {
    if (form.latitude === 0) return 'Load solar data to continue'
    return null
  }
  return null
}

export default function ProjectWizard() {
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)

  const [step, setStep] = useState(() => {
    const saved = loadSavedState()
    return saved?.step ?? 0
  })

  const [form, setForm] = useState(() => {
    const saved = loadSavedState()
    if (saved?.form) return { ...DEFAULT_FORM, ...saved.form }
    return DEFAULT_FORM
  })

  // Persist state to localStorage on every change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ step, form, savedAt: Date.now() }))
    } catch {}
  }, [step, form])

  const clearState = () => {
    localStorage.removeItem(STORAGE_KEY)
    setStep(0)
    setForm(DEFAULT_FORM)
  }

  const update = (fields) => setForm(prev => ({ ...prev, ...fields }))
  const canNext = () => {
    if (step === 0) {
      return form.address.length > 5 && (form.addressConfirmed || (form.latitude !== 0 && form.longitude !== 0))
    }
    if (step === 1) return form.roof_material && form.num_panels > 0  // Roof step
    if (step === 2) return form.panel_id && form.inverter_id && form.racking_id  // Equipment step
    if (step === 3) return form.latitude !== 0  // Solar step — just need valid coords
    return true
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          address: form.address,
          latitude: form.latitude,
          longitude: form.longitude,
          panel_id: form.panel_id,
          inverter_id: form.inverter_id,
          racking_id: form.racking_id,
          roof_material: form.roof_material,
          main_panel_breaker_a: form.main_panel_breaker_a,
          main_panel_bus_rating_a: form.main_panel_bus_rating_a,
          num_panels: form.num_panels,
          company_name: form.company_name,
          designer_name: form.designer_name,
          project_name: form.project_name || undefined,
        }),
      })
      const data = await res.json()
      if (res.ok) {
        localStorage.removeItem(STORAGE_KEY)
        navigate(`/project/${data.project_id}`)
      } else {
        setSubmitError(data.detail || 'Error creating project')
      }
    } catch (e) {
      setSubmitError('Network error: ' + e.message)
    }
    setSubmitting(false)
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Project</h1>

      {/* Step indicator */}
      <div className="flex items-start mb-8">
        {STEPS.map((s, i) => (
          <div key={s} className={`flex items-center ${i < STEPS.length - 1 ? 'flex-1' : ''}`}>
            <div className="flex flex-col items-center">
              <button
                onClick={() => i < step && setStep(i)}
                className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                  i < step
                    ? 'bg-solar-600 text-white cursor-pointer hover:bg-solar-700'
                    : i === step
                    ? 'bg-solar-600 text-white ring-4 ring-solar-500/20'
                    : 'bg-gray-100 text-gray-400'
                }`}
              >
                {i < step ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  i + 1
                )}
              </button>
              <span className={`mt-1.5 text-xs hidden md:block whitespace-nowrap ${
                i === step ? 'text-solar-600 font-semibold' : i < step ? 'text-gray-600' : 'text-gray-400'
              }`}>
                {s}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-0.5 mx-2 mt-[18px] ${i < step ? 'bg-solar-600' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {step === 0 && (
          <>
            <AddressConfirm
              address={form.address}
              streetViewB64={form.streetViewB64}
              satelliteB64={form.satelliteB64}
              confirmed={form.addressConfirmed}
              latitude={form.latitude}
              longitude={form.longitude}
              apiKey={window.__GOOGLE_API_KEY || ''}
              onUpdate={update}
            />
            {(form.address || form.addressConfirmed) && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={clearState}
                  className="text-sm text-red-500 hover:text-red-700 underline"
                >
                  Start Over
                </button>
              </div>
            )}
          </>
        )}

        {step === 1 && (
          <div className="space-y-5">
            <h2 className="text-lg font-semibold text-gray-900">Roof Configuration</h2>

            {/* Roof material selector — visual cards */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Roof Material</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {ROOF_MATERIALS.map(m => (
                  <button
                    key={m.value}
                    type="button"
                    onClick={() => update({ roof_material: m.value })}
                    className={`text-left p-3 rounded-lg border-2 transition-colors ${
                      form.roof_material === m.value
                        ? 'border-solar-600 bg-solar-50 ring-1 ring-solar-600'
                        : 'border-gray-200 hover:border-gray-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg leading-none">{m.icon}</span>
                      <span className="text-sm font-medium text-gray-900">{m.label}</span>
                    </div>
                    <p className="text-xs text-gray-500 leading-snug">{m.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Roof pitch */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Roof Pitch (degrees)</label>
              <input
                type="number" min="0" max="60"
                value={form.roof_pitch}
                onChange={e => update({ roof_pitch: parseInt(e.target.value) || 0 })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-solar-500 focus:border-solar-500 focus:outline-none"
              />
            </div>

            {/* Panel count */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Number of Panels</label>
              <input
                type="number"
                min="1"
                max="200"
                value={form.num_panels}
                onChange={e => {
                  const v = parseInt(e.target.value)
                  if (isNaN(v) || v < 1) update({ num_panels: 1 })
                  else if (v > 200) update({ num_panels: 200 })
                  else update({ num_panels: v })
                }}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-solar-500 focus:border-solar-500 focus:outline-none"
              />
              <p className="text-xs text-gray-500 mt-1">
                Panel count determines system size. You can adjust this in the Solar step based on roof area and production targets.
              </p>
              {form.solarData?.max_panels && form.num_panels > form.solarData.max_panels && (
                <p className="text-xs text-amber-600 mt-1">
                  Solar API estimates a maximum of {form.solarData.max_panels} panels for this roof. Consider reducing the count.
                </p>
              )}
            </div>
          </div>
        )}

        {step === 2 && (
          <EquipmentSelect
            panelId={form.panel_id}
            inverterId={form.inverter_id}
            rackingId={form.racking_id}
            numPanels={form.num_panels}
            onUpdate={update}
          />
        )}

        {step === 3 && (
          <SolarStep
            lat={form.latitude}
            lng={form.longitude}
            apiKey={window.__GOOGLE_API_KEY || ''}
            panelCount={form.num_panels}
            panelDimensions={form.panel_dimensions_mm}
            panelWattage={form.panel_wattage_w}
            onPanelCountChange={(count) => update({ num_panels: count })}
            targetProductionKwh={form.target_production_kwh || 0}
            onTargetProductionChange={(kwh) => update({ target_production_kwh: kwh })}
            onDataLoaded={(data) => {
              if (data.roof_segments?.length > 0) {
                const mainSeg = data.roof_segments[0]
                update({
                  roof_pitch: Math.round(mainSeg.pitch_deg || 25),
                  solarData: data,
                })
              }
            }}
          />
        )}

        {step === 4 && (() => {
          const maxBackfeed = Math.floor(form.main_panel_bus_rating_a * 1.2) - form.main_panel_breaker_a
          const busWarning = form.main_panel_bus_rating_a < form.main_panel_breaker_a
          return (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold text-gray-900">Electrical Configuration</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Main Breaker (A)</label>
                  <select
                    value={form.main_panel_breaker_a}
                    onChange={e => update({ main_panel_breaker_a: parseInt(e.target.value) })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-solar-500 focus:border-solar-500 focus:outline-none"
                  >
                    {[100, 125, 150, 200, 225, 400].map(a => <option key={a} value={a}>{a}A</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Bus Rating (A)</label>
                  <select
                    value={form.main_panel_bus_rating_a}
                    onChange={e => update({ main_panel_bus_rating_a: parseInt(e.target.value) })}
                    className={`w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-solar-500 focus:outline-none ${busWarning ? 'border-red-400 bg-red-50 focus:border-red-400' : 'border-gray-300 focus:border-solar-500'}`}
                  >
                    {[125, 150, 200, 225, 400].map(a => <option key={a} value={a}>{a}A</option>)}
                  </select>
                  {busWarning && (
                    <p className="text-xs text-red-600 mt-1">Bus rating must be &ge; main breaker amperage</p>
                  )}
                </div>
              </div>

              {/* 120% Rule */}
              <div className={`rounded-lg p-4 border text-sm ${maxBackfeed > 0 ? 'bg-green-50 border-green-200' : 'bg-amber-50 border-amber-200'}`}>
                <p className="font-medium text-gray-700 mb-1">NEC 705.12 &mdash; 120% Rule</p>
                <p className="text-gray-600">
                  Max backfeed breaker = ({form.main_panel_bus_rating_a}A &times; 1.2) &minus; {form.main_panel_breaker_a}A = <span className="font-bold">{maxBackfeed}A</span>
                </p>
                {maxBackfeed > 0 ? (
                  <p className="text-green-700 mt-1">The system backfeed breaker must be &le; {maxBackfeed}A to comply.</p>
                ) : (
                  <p className="text-amber-700 mt-1">No room for a backfeed breaker with this configuration. Consider a larger bus rating or supply-side connection.</p>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
                  <input
                    type="text"
                    value={form.company_name}
                    onChange={e => {
                      update({ company_name: e.target.value })
                      localStorage.setItem('solar_company_name', e.target.value)
                    }}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-solar-500 focus:border-solar-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Designer Name</label>
                  <input
                    type="text"
                    value={form.designer_name}
                    onChange={e => {
                      update({ designer_name: e.target.value })
                      localStorage.setItem('solar_designer_name', e.target.value)
                    }}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-solar-500 focus:border-solar-500 focus:outline-none"
                    placeholder="AI Solar Design Engine"
                  />
                </div>
              </div>
            </div>
          )
        })()}

        {step === 5 && (() => {
          const dcKw = (form.panel_wattage_w * form.num_panels / 1000).toFixed(2)
          const acKw = form.inverter_rated_w
            ? form.inverter_type === 'micro'
              ? (form.inverter_rated_w * form.num_panels / 1000).toFixed(2)
              : (form.inverter_rated_w / 1000).toFixed(2)
            : '—'
          return (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900">Review &amp; Generate</h2>

              {/* Address */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">Address</h3>
                  <button onClick={() => setStep(0)} className="text-xs text-solar-600 hover:text-solar-700 underline">Edit</button>
                </div>
                <div className="text-sm text-gray-800">{form.address}</div>
                <div className="text-xs text-gray-500 mt-0.5">{form.latitude.toFixed(6)}, {form.longitude.toFixed(6)}</div>
              </div>

              {/* Roof */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">Roof</h3>
                  <button onClick={() => setStep(1)} className="text-xs text-solar-600 hover:text-solar-700 underline">Edit</button>
                </div>
                <div className="text-sm text-gray-800">
                  {ROOF_MATERIALS.find(m => m.value === form.roof_material)?.label || form.roof_material}
                  {form.roof_pitch > 0 && <span> &middot; {form.roof_pitch}&deg; pitch</span>}
                </div>
              </div>

              {/* Equipment */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">Equipment</h3>
                  <button onClick={() => setStep(2)} className="text-xs text-solar-600 hover:text-solar-700 underline">Edit</button>
                </div>
                <div className="space-y-1 text-sm text-gray-800">
                  <div><span className="text-gray-500">Panel:</span> {form.panel_model || form.panel_id} &middot; {form.panel_wattage_w}W</div>
                  <div><span className="text-gray-500">Inverter:</span> {form.inverter_model || form.inverter_id} &middot; {form.inverter_type === 'micro' ? 'Micro' : 'String'}</div>
                  <div><span className="text-gray-500">Racking:</span> {form.racking_model || form.racking_id}</div>
                </div>
              </div>

              {/* System */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">System</h3>
                  <button onClick={() => setStep(1)} className="text-xs text-solar-600 hover:text-solar-700 underline">Edit</button>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center sm:grid-cols-3">
                  <div>
                    <div className="text-xl font-bold text-solar-600">{form.num_panels}</div>
                    <div className="text-xs text-gray-500">Panels</div>
                  </div>
                  <div>
                    <div className="text-xl font-bold text-solar-600">{dcKw}</div>
                    <div className="text-xs text-gray-500">DC kW</div>
                  </div>
                  <div>
                    <div className="text-xl font-bold text-solar-600">{acKw}</div>
                    <div className="text-xs text-gray-500">AC kW</div>
                  </div>
                </div>
              </div>

              {/* Electrical */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">Electrical</h3>
                  <button onClick={() => setStep(4)} className="text-xs text-solar-600 hover:text-solar-700 underline">Edit</button>
                </div>
                <div className="space-y-1 text-sm text-gray-800">
                  <div><span className="text-gray-500">Main Breaker:</span> {form.main_panel_breaker_a}A</div>
                  <div><span className="text-gray-500">Bus Rating:</span> {form.main_panel_bus_rating_a}A</div>
                  <div><span className="text-gray-500">Company:</span> {form.company_name}</div>
                  {form.designer_name && <div><span className="text-gray-500">Designer:</span> {form.designer_name}</div>}
                </div>
              </div>
            </div>
          )
        })()}
      </div>

      {/* Submit error banner */}
      {submitError && (
        <div className="mt-4 bg-red-600 text-white rounded-lg px-4 py-3 flex items-center justify-between">
          <span className="text-sm">{submitError}</span>
          <button onClick={() => setSubmitError(null)} className="text-white/80 hover:text-white ml-4 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Navigation buttons */}
      <div className="flex justify-between items-end mt-6">
        <button
          onClick={() => setStep(s => Math.max(0, s - 1))}
          disabled={step === 0}
          className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-lg disabled:opacity-50"
        >
          Back
        </button>
        <div className="flex flex-col items-end gap-1">
          {step < STEPS.length - 1 && !canNext() && (
            <p className="text-xs text-amber-600">{validationMessage(step, form)}</p>
          )}
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep(s => s + 1)}
              disabled={!canNext()}
              data-testid="next-btn"
              className={`px-6 py-2 text-sm font-medium text-white bg-solar-600 rounded-lg transition-colors ${
                canNext() ? 'hover:bg-solar-700' : 'opacity-50 cursor-not-allowed'
              }`}
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-6 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {submitting && <Spinner />}
              {submitting ? 'Creating...' : 'Create & Generate Planset'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
