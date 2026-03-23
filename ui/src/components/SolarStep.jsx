import { useState, useEffect } from 'react'
import SolarMap from './SolarMap'
import CesiumMap3D from './CesiumMap3D'

/**
 * Solar Potential Step — Orchestrator
 * Checks if Photorealistic 3D Tiles are available for the location.
 * Shows 3D view (primary) or 2D satellite (fallback) with shared controls.
 */
export default function SolarStep({ lat, lng, apiKey, panelCount, panelDimensions, panelWattage, onPanelCountChange, onDataLoaded }) {
  const [viewMode, setViewMode] = useState('2d') // '3d' or '2d' — default 2D until 3D coverage verified
  const [buildingData, setBuildingData] = useState(null)
  const [dsmHeights, setDsmHeights] = useState(null)

  // Default to 2D — 3D tiles don't have coverage everywhere.
  // User can manually switch to 3D to try it.
  useEffect(() => {
    setViewMode('2d')
  }, [apiKey])

  // Fetch DSM heights for panel positions
  useEffect(() => {
    if (!buildingData?.panels?.length || !lat || !lng) return

    const selected = buildingData.panels.slice(0, panelCount)
    const lats = selected.map(p => p.lat).join(',')
    const lngs = selected.map(p => p.lng).join(',')

    fetch(`/api/solar/dsm-heights?lat=${lat}&lng=${lng}&panel_lats=${lats}&panel_lngs=${lngs}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setDsmHeights(data) })
      .catch(() => {})
  }, [buildingData, panelCount, lat, lng])

  const handleDataLoaded = (data) => {
    setBuildingData(data)
    if (onDataLoaded) onDataLoaded(data)
  }

  if (viewMode === null) {
    return <div className="text-center py-8 text-gray-500">Checking 3D availability...</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Solar Potential</h2>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
          <button
            onClick={() => setViewMode('2d')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              viewMode === '2d' ? 'bg-white text-solar-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            2D Satellite
          </button>
          <button
            onClick={() => setViewMode('3d')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              viewMode === '3d' ? 'bg-white text-solar-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
            title="3D view — works best in major cities with Google 3D coverage"
          >
            3D View
          </button>
        </div>
      </div>

      <p className="text-sm text-gray-500">
        Review panel placement on the satellite view. Panels are placed by Google's algorithm accounting for roof pitch, shading, and obstructions. Adjust the panel count with the slider.
      </p>

      {/* DSM building info */}
      {dsmHeights?.building && (
        <div className="flex gap-3 text-xs text-gray-500">
          <span>Building height: {dsmHeights.building.building_height_m}m</span>
          <span>Eave: {dsmHeights.building.eave_height_m}m</span>
          <span>Ridge: {dsmHeights.building.ridge_height_m}m</span>
          {dsmHeights.features?.length > 0 && (
            <span className="text-amber-600">
              {dsmHeights.features.length} obstruction{dsmHeights.features.length > 1 ? 's' : ''} detected
            </span>
          )}
        </div>
      )}

      {/* 3D View */}
      {viewMode === '3d' && (
        <CesiumMap3D
          lat={lat} lng={lng} apiKey={apiKey}
          panelCount={panelCount}
          panels={buildingData?.panels || []}
          segments={buildingData?.roof_segments || []}
          panelDimensions={panelDimensions || buildingData?.panel_dimensions}
          dsmHeights={dsmHeights}
          onPanelCountChange={onPanelCountChange}
          onDataLoaded={handleDataLoaded}
          maxPanels={buildingData?.max_panels || 78}
          totalKwh={buildingData?.panels?.slice(0, panelCount).reduce((s, p) => s + (p.yearly_energy_kwh || 0), 0) || 0}
          carbonOffset={buildingData?.carbon_offset || 0}
          panelCapacityW={panelWattage || buildingData?.panel_capacity_w || 400}
        />
      )}

      {/* 2D Satellite View — default visualization */}
      {viewMode === '2d' && (
        <SolarMap
          lat={lat} lng={lng} apiKey={apiKey}
          panelCount={panelCount}
          panelDimensions={panelDimensions}
          panelWattage={panelWattage}
          onPanelCountChange={onPanelCountChange}
          onDataLoaded={handleDataLoaded}
        />
      )}
    </div>
  )
}
