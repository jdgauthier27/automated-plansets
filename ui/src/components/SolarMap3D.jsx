import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * 3D Photorealistic Building Viewer with Solar Panels
 *
 * Uses Google Photorealistic 3D Tiles via deck.gl for Google Earth-quality
 * 3D visualization with solar panel polygons overlaid on the roof.
 *
 * Panel elevation comes from DSM height data so panels sit flush on the roof.
 */
export default function SolarMap3D({
  lat, lng, apiKey,
  panelCount = 13, panels = [], segments = [], panelDimensions,
  dsmHeights, onPanelCountChange, onDataLoaded,
  maxPanels = 78, totalKwh = 0, carbonOffset = 0, panelCapacityW = 400,
}) {
  const containerRef = useRef(null)
  const deckInstanceRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [loading, setLoading] = useState(true)

  // Fetch building data if not already provided
  useEffect(() => {
    if (panels.length > 0 || !lat || !lng) return
    fetch(`/api/solar/building?lat=${lat}&lng=${lng}`)
      .then(r => r.json())
      .then(data => { if (onDataLoaded) onDataLoaded(data) })
      .catch(() => {})
  }, [lat, lng])

  // Load deck.gl from CDN (avoids build issues with ES module loaders)
  useEffect(() => {
    if (window.deck) { setReady(true); return }

    const loadScript = (src) => new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = src
      s.async = true
      s.onload = resolve
      s.onerror = reject
      document.head.appendChild(s)
    })

    // deck.gl standalone bundle includes all layers
    loadScript('https://unpkg.com/deck.gl@9.1.0/dist.min.js')
      .then(() => { setReady(true); setLoading(false) })
      .catch(e => { console.error('deck.gl load failed:', e); setLoading(false) })
  }, [])

  // Build and render deck.gl instance
  useEffect(() => {
    if (!ready || !containerRef.current || !lat || !lng || !apiKey) return

    // Clean up previous instance
    if (deckInstanceRef.current) {
      deckInstanceRef.current.finalize()
      deckInstanceRef.current = null
    }

    const selectedPanels = panels.slice(0, panelCount)
    // Prefer equipment-selected dimensions (mm → m), fall back to building data defaults
    const panelW = panelDimensions?.width
      ? panelDimensions.width / 1000
      : (panelDimensions?.width_m || 1.045)
    const panelH = panelDimensions?.length
      ? panelDimensions.length / 1000
      : (panelDimensions?.height_m || 1.879)

    // Build panel polygon GeoJSON features
    const panelFeatures = selectedPanels.map((panel, i) => {
      const [w, h] = [panelW / 2, panelH / 2]
      const corners = [
        { x: +w, y: +h }, { x: +w, y: -h },
        { x: -w, y: -h }, { x: -w, y: +h },
      ]

      const orientation = panel.orientation === 'PORTRAIT' ? 90 : 0
      const segIdx = panel.segment_index || 0
      const azimuth = segments[segIdx]?.azimuth_deg || 0

      // Convert corners to lng/lat using simplified spherical offset
      const cLat = panel.lat
      const cLng = panel.lng
      const cosLat = Math.cos(cLat * Math.PI / 180)

      // Get roof elevation from DSM — this is critical for 3D placement
      // DSM gives absolute elevation (e.g., 23m above sea level for the roof)
      // We need the building height above ground for deck.gl
      const absElevation = dsmHeights?.panel_heights?.[String(i)] || 0
      const groundElevation = dsmHeights?.building?.ground_elevation_m || 0
      const roofHeight = absElevation > 0 ? absElevation - groundElevation : 0

      const coords = corners.map(({ x, y }) => {
        const dist = Math.sqrt(x * x + y * y)
        const bearingRad = (Math.atan2(y, x) * 180 / Math.PI + orientation + azimuth) * Math.PI / 180
        const dLat = dist * Math.cos(bearingRad) / 111319.5
        const dLng = dist * Math.sin(bearingRad) / (111319.5 * cosLat)
        // Third coordinate = altitude in meters above ground
        return [cLng + dLng, cLat + dLat, roofHeight]
      })
      coords.push(coords[0]) // close polygon

      const elevation = roofHeight

      return {
        type: 'Feature',
        properties: {
          id: i,
          kwh: panel.yearly_energy_kwh || 0,
          elevation,
          segment: segIdx,
        },
        geometry: { type: 'Polygon', coordinates: [coords] },
      }
    })

    // Obstruction markers from DSM
    const obstructionFeatures = (dsmHeights?.features || []).map((f, i) => ({
      position: [f.lng, f.lat],
      elevation: f.height_m || 0,
      type: f.type,
    }))

    const layers = [
      // Layer 1: Google Photorealistic 3D Tiles
      new window.deck.Tile3DLayer({
        id: 'google-3d-tiles',
        data: 'https://tile.googleapis.com/v1/3dtiles/root.json',
        loadOptions: {
          fetch: { headers: { 'X-GOOG-API-KEY': apiKey } },
        },
        onTilesetLoad: () => setLoading(false),
        operation: 'terrain+draw',
      }),

      // Layer 2: Solar panel polygons (draped on terrain)
      new window.deck.GeoJsonLayer({
        id: 'solar-panels',
        data: { type: 'FeatureCollection', features: panelFeatures },
        filled: true,
        stroked: true,
        extruded: false,
        getFillColor: [26, 35, 126, 200],  // dark navy, semi-transparent
        getLineColor: [176, 190, 197, 230],
        getLineWidth: 0.2,
        lineWidthUnits: 'meters',
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 200, 0, 180],
        onClick: (info) => {
          if (info.object) {
            const p = info.object.properties
            alert(`Panel ${p.id + 1}\n${p.kwh.toFixed(0)} kWh/year\nSegment ${p.segment}`)
          }
        },
      }),

      // Obstruction markers omitted from 3D view — shown in stats instead
    ]

    const deck = new window.deck.DeckGL({
      container: containerRef.current,
      initialViewState: {
        latitude: lat - 0.00015,  // Offset slightly south to look AT the building
        longitude: lng,
        zoom: 20,
        bearing: 0,
        pitch: 50,
        maxPitch: 75,
      },
      controller: {
        minZoom: 16,
        maxZoom: 22,
      },
      layers,
      getTooltip: ({ object }) => {
        if (!object?.properties) return null
        const p = object.properties
        return {
          html: `<b>Panel ${p.id + 1}</b><br>${p.kwh?.toFixed(0)} kWh/yr`,
          style: { fontSize: '12px', padding: '4px 8px' },
        }
      },
    })

    deckInstanceRef.current = deck

    return () => {
      if (deckInstanceRef.current) {
        deckInstanceRef.current.finalize()
        deckInstanceRef.current = null
      }
    }
  }, [ready, lat, lng, apiKey, panelCount, panels, segments, dsmHeights])

  // Totals
  const selectedPanels = panels.slice(0, panelCount)
  const calcTotalKwh = selectedPanels.reduce((s, p) => s + (p.yearly_energy_kwh || 0), 0) || totalKwh
  const totalKw = panelCount * panelCapacityW / 1000

  return (
    <div className="space-y-3">
      {/* 3D Map */}
      <div className="relative">
        <div
          ref={containerRef}
          className="w-full rounded-lg border border-gray-200 bg-gray-900"
          style={{ height: '450px' }}
        />
        {loading && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center rounded-lg">
            <div className="text-white text-sm">Loading 3D model...</div>
          </div>
        )}
        <div className="absolute bottom-2 left-2 bg-black/60 text-white text-[10px] px-2 py-1 rounded">
          Drag to rotate · Scroll to zoom · Shift+drag to pan
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        {/* Panel count slider */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="font-medium text-gray-700">Panel Count</span>
            <span className="text-solar-600 font-bold">{panelCount} panels</span>
          </div>
          <input type="range" min="1" max={maxPanels} value={panelCount}
            onChange={e => onPanelCountChange?.(parseInt(e.target.value))}
            className="w-full accent-solar-600" />
          <div className="flex justify-between text-xs text-gray-400">
            <span>1</span><span>{maxPanels} max</span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-2 text-center">
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-lg font-bold text-gray-900">{panelCount}</div>
            <div className="text-xs text-gray-500">Panels</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-lg font-bold text-gray-900">{totalKw.toFixed(1)}</div>
            <div className="text-xs text-gray-500">kW DC</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-lg font-bold text-gray-900">{calcTotalKwh.toFixed(0)}</div>
            <div className="text-xs text-gray-500">kWh/yr</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-2">
            <div className="text-lg font-bold text-gray-900">
              {carbonOffset ? (calcTotalKwh * carbonOffset / 1000000).toFixed(1) : '—'}
            </div>
            <div className="text-xs text-gray-500">t CO₂/yr</div>
          </div>
        </div>

        {/* Monthly Production */}
        <div>
          <div className="text-sm font-medium text-gray-700 mb-2">Monthly Production</div>
          <div className="flex items-end gap-1" style={{ height: '60px' }}>
            {[0.04,0.05,0.08,0.10,0.12,0.13,0.13,0.12,0.09,0.07,0.04,0.03].map((f, i) => {
              const months = 'JFMAMJJASOND'
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                  <div className="w-full rounded-t" style={{
                    height: `${(f / 0.13) * 100}%`, minHeight: '3px',
                    backgroundColor: `hsl(${40 + (f/0.13)*60}, 80%, 55%)`
                  }} title={`${months[i]}: ${Math.round(calcTotalKwh * f)} kWh`} />
                  <span className="text-[8px] text-gray-400">{months[i]}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Roof segments */}
        {segments.length > 0 && (
          <div className="text-xs text-gray-500 space-y-0.5">
            {segments.map((seg, i) => {
              const dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
              const dir = dirs[Math.round((seg.azimuth_deg || 0) / 22.5) % 16]
              return (
                <div key={i} className="flex justify-between">
                  <span>Seg {i}: {dir}-facing, {seg.pitch_deg?.toFixed(1)}° pitch</span>
                  <span>{(seg.area_m2 * 10.764).toFixed(0)} sqft</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
