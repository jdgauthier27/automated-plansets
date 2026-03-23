import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import AddressConfirm from '../components/AddressConfirm'
import EquipmentSelect from '../components/EquipmentSelect'
import SolarMap from '../components/SolarMap'
import SolarStep from '../components/SolarStep'

const STEPS = ['Address', 'Roof', 'Equipment', 'Solar', 'Electrical', 'Review']

const ROOF_MATERIALS = [
  { value: 'asphalt_shingle', label: 'Asphalt Shingle' },
  { value: 'composite_shingle', label: 'Composite Shingle' },
  { value: 'metal_standing_seam', label: 'Metal Standing Seam' },
  { value: 'clay_tile', label: 'Clay Tile' },
  { value: 'concrete_tile', label: 'Concrete Tile' },
  { value: 'flat_membrane', label: 'Flat Membrane (TPO/EPDM)' },
]

export default function ProjectWizard() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
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
    panel_dimensions_mm: null, // { length, width } from selected panel
    main_panel_breaker_a: 200,
    main_panel_bus_rating_a: 225,
    num_panels: 13,
    company_name: 'Quebec Solaire',
    designer_name: '',
    project_name: '',
  })

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
        navigate(`/project/${data.project_id}`)
      } else {
        alert(data.detail || 'Error creating project')
      }
    } catch (e) {
      alert('Network error: ' + e.message)
    }
    setSubmitting(false)
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Project</h1>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center">
            <button
              onClick={() => i < step && setStep(i)}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                i === step
                  ? 'bg-solar-600 text-white'
                  : i < step
                  ? 'bg-solar-100 text-solar-700 cursor-pointer'
                  : 'bg-gray-100 text-gray-400'
              }`}
            >
              {i + 1}
            </button>
            <span className={`ml-2 text-sm ${i === step ? 'text-gray-900 font-medium' : 'text-gray-400'}`}>
              {s}
            </span>
            {i < STEPS.length - 1 && <div className="w-8 h-px bg-gray-200 mx-2" />}
          </div>
        ))}
      </div>

      {/* Step content */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {step === 0 && (
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
        )}

        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Roof Configuration</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Roof Material</label>
              <select
                value={form.roof_material}
                onChange={e => update({ roof_material: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
              >
                {ROOF_MATERIALS.map(m => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Roof Pitch (degrees)</label>
              <input
                type="number" min="0" max="60"
                value={form.roof_pitch}
                onChange={e => update({ roof_pitch: parseInt(e.target.value) || 0 })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Number of Panels</label>
              <input
                type="number" min="1" max="100"
                value={form.num_panels}
                onChange={e => update({ num_panels: parseInt(e.target.value) || 1 })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
              />
            </div>
          </div>
        )}

        {step === 2 && (
          <EquipmentSelect
            panelId={form.panel_id}
            inverterId={form.inverter_id}
            rackingId={form.racking_id}
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

        {step === 4 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Electrical Configuration</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Main Breaker (A)</label>
                <select
                  value={form.main_panel_breaker_a}
                  onChange={e => update({ main_panel_breaker_a: parseInt(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2"
                >
                  {[100, 125, 150, 200].map(a => <option key={a} value={a}>{a}A</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Bus Rating (A)</label>
                <select
                  value={form.main_panel_bus_rating_a}
                  onChange={e => update({ main_panel_bus_rating_a: parseInt(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2"
                >
                  {[100, 125, 150, 200, 225].map(a => <option key={a} value={a}>{a}A</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
              <input
                type="text"
                value={form.company_name}
                onChange={e => update({ company_name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Designer Name</label>
              <input
                type="text"
                value={form.designer_name}
                onChange={e => update({ designer_name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                placeholder="AI Solar Design Engine"
              />
            </div>
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Review & Generate</h2>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
              <div><span className="font-medium text-gray-600">Address:</span> {form.address}</div>
              <div><span className="font-medium text-gray-600">Roof:</span> {ROOF_MATERIALS.find(m => m.value === form.roof_material)?.label} &middot; {form.num_panels} panels</div>
              <div><span className="font-medium text-gray-600">Panel:</span> {form.panel_id}</div>
              <div><span className="font-medium text-gray-600">Inverter:</span> {form.inverter_id}</div>
              <div><span className="font-medium text-gray-600">Racking:</span> {form.racking_id}</div>
              <div><span className="font-medium text-gray-600">Main Panel:</span> {form.main_panel_breaker_a}A breaker / {form.main_panel_bus_rating_a}A bus</div>
              <div><span className="font-medium text-gray-600">Company:</span> {form.company_name}</div>
            </div>
          </div>
        )}
      </div>

      {/* Navigation buttons */}
      <div className="flex justify-between mt-6">
        <button
          onClick={() => setStep(s => Math.max(0, s - 1))}
          disabled={step === 0}
          className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-lg disabled:opacity-50"
        >
          Back
        </button>
        {step < STEPS.length - 1 ? (
          <button
            onClick={() => setStep(s => s + 1)}
            disabled={!canNext()}
            className="px-6 py-2 text-sm font-medium text-white bg-solar-600 hover:bg-solar-700 rounded-lg disabled:opacity-50 transition-colors"
          >
            Next
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-6 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg disabled:opacity-50 transition-colors"
          >
            {submitting ? 'Creating...' : 'Create & Generate Planset'}
          </button>
        )}
      </div>
    </div>
  )
}
