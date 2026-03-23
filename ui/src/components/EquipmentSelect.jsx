import { useState, useEffect } from 'react'

export default function EquipmentSelect({ panelId, inverterId, rackingId, onUpdate }) {
  const [panels, setPanels] = useState([])
  const [inverters, setInverters] = useState([])
  const [racking, setRacking] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/catalog/panels').then(r => r.json()),
      fetch('/api/catalog/inverters').then(r => r.json()),
      fetch('/api/catalog/racking').then(r => r.json()),
    ]).then(([p, i, r]) => {
      setPanels(p)
      setInverters(i)
      setRacking(r)
      setLoading(false)
      // Auto-select first option if none selected
      if (!panelId && p.length) onUpdate({
        panel_id: p[0].id,
        panel_wattage_w: p[0].wattage_w,
        panel_dimensions_mm: p[0].dimensions_mm,
      })
      if (!inverterId && i.length) onUpdate({ inverter_id: i[0].id })
      if (!rackingId && r.length) onUpdate({ racking_id: r[0].id })
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-8 text-gray-500">Loading equipment catalog...</div>

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Equipment Selection</h2>

      {/* Panels */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Solar Panel</label>
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
                })}
                className="sr-only"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">{p.manufacturer} {p.model_short}</div>
                <div className="text-sm text-gray-500 mt-0.5">
                  {p.wattage_w}W &middot; Voc={p.voc_v}V &middot; {p.efficiency_pct}% eff &middot;
                  {p.dimensions_mm.length}x{p.dimensions_mm.width}mm &middot; {p.weight_kg}kg
                  {p.bifacial && ' \u00b7 Bifacial'}
                </div>
              </div>
              <div className="text-lg font-bold text-solar-600">{p.wattage_w}W</div>
            </label>
          ))}
        </div>
      </div>

      {/* Inverters */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Inverter</label>
        <div className="grid gap-3">
          {inverters.map(inv => (
            <label
              key={inv.id}
              className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                inverterId === inv.id
                  ? 'border-solar-500 bg-solar-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <input
                type="radio" name="inverter" value={inv.id}
                checked={inverterId === inv.id}
                onChange={() => onUpdate({ inverter_id: inv.id })}
                className="sr-only"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">{inv.manufacturer} {inv.model_short}</div>
                <div className="text-sm text-gray-500 mt-0.5">
                  {inv.type === 'micro' ? 'Microinverter' : 'String Inverter'} &middot;
                  {inv.rated_ac_output_w}W AC &middot; {inv.mppt_count} MPPT &middot;
                  {inv.cec_efficiency_pct}% CEC eff
                  {inv.rapid_shutdown_builtin && ' \u00b7 RSD Built-in'}
                </div>
              </div>
              <div className="text-sm font-medium text-gray-600 uppercase">{inv.type}</div>
            </label>
          ))}
        </div>
      </div>

      {/* Racking */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Racking System</label>
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
                onChange={() => onUpdate({ racking_id: r.id })}
                className="sr-only"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">{r.manufacturer} {r.model}</div>
                <div className="text-sm text-gray-500 mt-0.5">
                  {r.material} &middot; Wind: {r.wind_load_psf} psf &middot; Snow: {r.snow_load_psf} psf
                </div>
              </div>
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}
