import { useState, useEffect } from 'react'

function Spinner({ className = 'w-5 h-5' }) {
  return (
    <div className={`${className} border-2 border-current border-t-transparent rounded-full animate-spin`} />
  )
}

export default function EquipmentSelect({ panelId, inverterId, rackingId, numPanels = 0, onUpdate }) {
  const [panels, setPanels] = useState([])
  const [inverters, setInverters] = useState([])
  const [racking, setRacking] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAllInverters, setShowAllInverters] = useState(false)

  useEffect(() => {
    setError(null)
    Promise.all([
      fetch('/api/catalog/panels').then(r => { if (!r.ok) throw new Error('Failed to load panels'); return r.json() }),
      fetch('/api/catalog/inverters').then(r => { if (!r.ok) throw new Error('Failed to load inverters'); return r.json() }),
      fetch('/api/catalog/racking').then(r => { if (!r.ok) throw new Error('Failed to load racking'); return r.json() }),
    ]).then(([p, i, r]) => {
      // Sort panels by wattage descending
      p.sort((a, b) => b.wattage_w - a.wattage_w)
      setPanels(p)
      setInverters(i)
      setRacking(r)
      setLoading(false)
      // Auto-select first option if none selected
      if (!panelId && p.length) onUpdate({
        panel_id: p[0].id,
        panel_wattage_w: p[0].wattage_w,
        panel_dimensions_mm: p[0].dimensions_mm,
        panel_model: `${p[0].manufacturer} ${p[0].model_short}`,
      })
      if (!inverterId && i.length) onUpdate({
        inverter_id: i[0].id,
        inverter_model: `${i[0].manufacturer} ${i[0].model_short}`,
        inverter_type: i[0].type,
        inverter_rated_w: i[0].rated_ac_output_w,
      })
      if (!rackingId && r.length) onUpdate({
        racking_id: r[0].id,
        racking_model: `${r[0].manufacturer} ${r[0].model}`,
      })
    }).catch(e => {
      setError(e.message || 'Failed to load equipment catalog')
      setLoading(false)
    })
  }, [])

  const selectedPanel = panels.find(p => p.id === panelId)

  // Filter inverters by compatibility with selected panel
  const compatibleInverters = selectedPanel
    ? inverters.filter(inv => {
        // For microinverters: max DC voltage must >= panel Voc
        // For string inverters: max DC voltage must accommodate panel Voc
        return inv.max_dc_voltage_v >= selectedPanel.voc_v
      })
    : inverters

  const displayedInverters = showAllInverters ? inverters : compatibleInverters

  // Reset showAllInverters when panel selection changes
  useEffect(() => {
    setShowAllInverters(false)
  }, [panelId])

  // System summary calculations
  const selectedInverter = inverters.find(i => i.id === inverterId)
  const totalDcKw = selectedPanel ? (selectedPanel.wattage_w * numPanels / 1000) : 0
  const totalAcKw = selectedInverter
    ? selectedInverter.type === 'micro'
      ? (selectedInverter.rated_ac_output_w * numPanels / 1000)
      : (selectedInverter.rated_ac_output_w / 1000)
    : 0

  if (loading) return (
    <div className="flex items-center justify-center py-12 gap-3 text-gray-500">
      <Spinner />
      <span>Loading equipment catalog...</span>
    </div>
  )

  if (error) return (
    <div className="text-center py-8">
      <div className="bg-red-50 text-red-700 rounded-lg px-4 py-3 inline-block">
        <p className="font-medium">Failed to load equipment catalog</p>
        <p className="text-sm mt-1">{error}</p>
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Equipment Selection</h2>

      {/* Panels */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Solar Panel</label>
        {panels.length === 0 ? (
          <p className="text-sm text-gray-500 py-4 text-center">No panels available</p>
        ) : (
          <div className="grid gap-3">
            {panels.map(p => (
              <label
                key={p.id}
                className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                  panelId === p.id
                    ? 'border-solar-500 bg-solar-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <input
                  type="radio" name="panel" value={p.id}
                  checked={panelId === p.id}
                  onChange={() => onUpdate({
                    panel_id: p.id,
                    panel_wattage_w: p.wattage_w,
                    panel_dimensions_mm: p.dimensions_mm,
                    panel_model: `${p.manufacturer} ${p.model_short}`,
                  })}
                  className="sr-only"
                />
                <div className="flex-1">
                  <div className="font-medium text-gray-900">{p.manufacturer} {p.model_short}</div>
                  <div className="text-sm text-gray-500 mt-0.5">
                    {p.technology} &middot; {p.efficiency_pct}% eff &middot;
                    {' '}{p.dimensions_mm.length}&times;{p.dimensions_mm.width}mm &middot; {p.weight_kg}kg
                    {p.bifacial && ' \u00b7 Bifacial'}
                  </div>
                </div>
                <div className="text-lg font-bold text-solar-600">{p.wattage_w}W</div>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Inverters */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Inverter</label>
        {compatibleInverters.length === 0 && !showAllInverters ? (
          <div className="text-center py-4">
            <p className="text-sm text-gray-500">No compatible inverters for the selected panel</p>
            <button
              type="button"
              onClick={() => setShowAllInverters(true)}
              className="text-sm text-solar-600 hover:text-solar-700 underline mt-1"
            >
              Show all inverters
            </button>
          </div>
        ) : (
          <div className="grid gap-3">
            {!showAllInverters && compatibleInverters.length < inverters.length && (
              <p className="text-xs text-gray-400">
                Showing {compatibleInverters.length} of {inverters.length} inverters compatible with selected panel &middot;{' '}
                <button type="button" onClick={() => setShowAllInverters(true)} className="text-solar-600 underline">Show all</button>
              </p>
            )}
            {showAllInverters && compatibleInverters.length < inverters.length && (
              <p className="text-xs text-gray-400">
                Showing all inverters &middot;{' '}
                <button type="button" onClick={() => setShowAllInverters(false)} className="text-solar-600 underline">Show compatible only</button>
              </p>
            )}
            {displayedInverters.map(inv => {
              const isCompatible = compatibleInverters.some(c => c.id === inv.id)
              return (
                <label
                  key={inv.id}
                  className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                    inverterId === inv.id
                      ? 'border-solar-500 bg-solar-50'
                      : !isCompatible && showAllInverters
                      ? 'border-amber-200 bg-amber-50 hover:border-amber-300'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="radio" name="inverter" value={inv.id}
                    checked={inverterId === inv.id}
                    onChange={() => onUpdate({
                      inverter_id: inv.id,
                      inverter_model: `${inv.manufacturer} ${inv.model_short}`,
                      inverter_type: inv.type,
                      inverter_rated_w: inv.rated_ac_output_w,
                    })}
                    className="sr-only"
                  />
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">
                      {inv.manufacturer} {inv.model_short}
                      {!isCompatible && showAllInverters && (
                        <span className="ml-2 text-xs text-amber-600 font-normal">(incompatible)</span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500 mt-0.5">
                      {inv.type === 'micro' ? 'Microinverter' : 'String Inverter'} &middot;{' '}
                      {inv.rated_ac_output_w}W AC &middot; {inv.mppt_count} MPPT &middot;{' '}
                      {inv.cec_efficiency_pct}% CEC eff &middot; Max {inv.max_dc_voltage_v}V DC
                      {inv.rapid_shutdown_builtin && ' \u00b7 RSD Built-in'}
                    </div>
                  </div>
                  <div className="text-sm font-medium text-gray-600 uppercase">{inv.type}</div>
                </label>
              )
            })}
          </div>
        )}
      </div>

      {/* Racking */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Racking System</label>
        {racking.length === 0 ? (
          <p className="text-sm text-gray-500 py-4 text-center">No racking available</p>
        ) : (
          <div className="grid gap-3">
            {racking.map(r => (
              <label
                key={r.id}
                className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                  rackingId === r.id
                    ? 'border-solar-500 bg-solar-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <input
                  type="radio" name="racking" value={r.id}
                  checked={rackingId === r.id}
                  onChange={() => onUpdate({
                    racking_id: r.id,
                    racking_model: `${r.manufacturer} ${r.model}`,
                  })}
                  className="sr-only"
                />
                <div className="flex-1">
                  <div className="font-medium text-gray-900">{r.manufacturer} {r.model}</div>
                  <div className="text-sm text-gray-500 mt-0.5">
                    {r.type.replace(/_/g, ' ')} &middot; {r.material} &middot;
                    {' '}Wind: {r.wind_load_psf} psf &middot; Snow: {r.snow_load_psf} psf
                  </div>
                </div>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* System Summary */}
      {selectedPanel && numPanels > 0 && (
        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">System Summary</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
            <div>
              <div className="text-2xl font-bold text-solar-600">{numPanels}</div>
              <div className="text-xs text-gray-500">Panels</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-solar-600">{totalDcKw.toFixed(2)}</div>
              <div className="text-xs text-gray-500">DC kW</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-solar-600">{totalAcKw.toFixed(2)}</div>
              <div className="text-xs text-gray-500">AC kW</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-solar-600">{(totalDcKw * 1400).toFixed(0)}</div>
              <div className="text-xs text-gray-500">Est. kWh/yr</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
