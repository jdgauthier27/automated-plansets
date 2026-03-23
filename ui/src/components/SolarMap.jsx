import { useState, useEffect, useRef } from 'react'

/**
 * Interactive solar potential map using Google Maps JavaScript API.
 *
 * Renders:
 * - Satellite imagery (Google Maps)
 * - Solar flux overlay (annual irradiance heatmap from Data Layers API)
 * - Panel polygons rotated to match roof azimuth (from Building Insights API)
 * - Monthly production chart
 *
 * Panel polygon algorithm (from Google's reference implementation):
 *   corners = [{x:+w,y:+h}, {x:+w,y:-h}, {x:-w,y:-h}, {x:-w,y:+h}]
 *   for each corner: computeOffset(center, sqrt(x²+y²), atan2(y,x) + orientation + azimuth)
 */
export default function SolarMap({ lat, lng, apiKey, panelCount = 13, panelDimensions, panelWattage, onPanelCountChange, onDataLoaded }) {
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [buildingData, setBuildingData] = useState(null)
  const [showPanels, setShowPanels] = useState(true)
  const [showFlux, setShowFlux] = useState(true)
  const [groupedData, setGroupedData] = useState(null)
  const panelPolygonsRef = useRef([])
  const fluxOverlayRef = useRef(null)
  const geometryLibRef = useRef(null)

  // Fetch building insights data
  useEffect(() => {
    if (!lat || !lng) return
    setLoading(true)
    setError(null)

    fetch(`/api/solar/building?lat=${lat}&lng=${lng}`)
      .then(r => {
        if (!r.ok) throw new Error('Failed to fetch solar data')
        return r.json()
      })
      .then(data => {
        setBuildingData(data)
        if (onDataLoaded) onDataLoaded(data)
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })
  }, [lat, lng])

  // Initialize Google Map
  useEffect(() => {
    if (!mapRef.current || !lat || !lng || !apiKey) return

    const initMap = async () => {
      if (!window.google?.maps) {
        await new Promise((resolve) => {
          const script = document.createElement('script')
          script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=geometry`
          script.async = true
          script.onload = resolve
          document.head.appendChild(script)
        })
      }

      const map = new window.google.maps.Map(mapRef.current, {
        center: { lat, lng },
        zoom: 20,
        mapTypeId: 'satellite',
        tilt: 0,
        disableDefaultUI: true,
        zoomControl: true,
      })
      mapInstanceRef.current = map
      geometryLibRef.current = window.google.maps.geometry

      // Fetch and render the solar flux overlay
      fetchFluxOverlay(map)
    }

    initMap()
  }, [lat, lng, apiKey])

  // Fetch annual flux data layer and render as ground overlay
  const fetchFluxOverlay = async (map) => {
    try {
      const res = await fetch(`/api/solar/datalayers?lat=${lat}&lng=${lng}&radius_m=50`)
      if (!res.ok) return
      const layers = await res.json()

      if (layers.annual_flux_url) {
        // Fetch the flux GeoTIFF through our proxy
        const proxyUrl = `/api/solar/proxy-geotiff?url=${encodeURIComponent(layers.annual_flux_url)}`
        const tiffRes = await fetch(proxyUrl)
        if (!tiffRes.ok) return
        const arrayBuf = await tiffRes.arrayBuffer()

        // Parse GeoTIFF using the geotiff.js library (loaded from CDN)
        if (!window.GeoTIFF) {
          await new Promise((resolve) => {
            const script = document.createElement('script')
            script.src = 'https://cdn.jsdelivr.net/npm/geotiff@2.1.3/dist-browser/geotiff.js'
            script.onload = resolve
            document.head.appendChild(script)
          })
        }

        const tiff = await window.GeoTIFF.fromArrayBuffer(arrayBuf)
        const image = await tiff.getImage()
        const data = await image.readRasters()
        const width = image.getWidth()
        const height = image.getHeight()
        const bbox = image.getBoundingBox() // [minX, minY, maxX, maxY]

        // Render flux data to canvas with iron palette
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        const imageData = ctx.createImageData(width, height)
        const band = data[0] // annual flux values

        // Find min/max for normalization
        let min = Infinity, max = -Infinity
        for (let i = 0; i < band.length; i++) {
          if (band[i] > 0) { // ignore zero (non-roof)
            if (band[i] < min) min = band[i]
            if (band[i] > max) max = band[i]
          }
        }

        // Iron palette: dark → purple → orange → yellow → white
        const ironColors = [
          [0, 0, 10], [50, 0, 80], [120, 0, 120],
          [180, 30, 30], [220, 80, 0], [240, 150, 0],
          [250, 200, 50], [255, 240, 200], [255, 255, 246]
        ]

        for (let i = 0; i < band.length; i++) {
          const idx = i * 4
          if (band[i] <= 0) {
            // Non-roof: transparent
            imageData.data[idx] = 0
            imageData.data[idx + 1] = 0
            imageData.data[idx + 2] = 0
            imageData.data[idx + 3] = 0
          } else {
            // Map value to iron palette
            const t = Math.min(1, Math.max(0, (band[i] - min) / (max - min)))
            const ci = t * (ironColors.length - 1)
            const lo = Math.floor(ci)
            const hi = Math.min(lo + 1, ironColors.length - 1)
            const f = ci - lo
            imageData.data[idx] = ironColors[lo][0] + (ironColors[hi][0] - ironColors[lo][0]) * f
            imageData.data[idx + 1] = ironColors[lo][1] + (ironColors[hi][1] - ironColors[lo][1]) * f
            imageData.data[idx + 2] = ironColors[lo][2] + (ironColors[hi][2] - ironColors[lo][2]) * f
            imageData.data[idx + 3] = 180 // semi-transparent
          }
        }

        ctx.putImageData(imageData, 0, 0)

        // Create ground overlay with GeoTIFF bounds
        // bbox is in EPSG:4326 (lat/lng)
        const bounds = {
          south: bbox[1], west: bbox[0],
          north: bbox[3], east: bbox[2],
        }

        if (fluxOverlayRef.current) {
          fluxOverlayRef.current.setMap(null)
        }

        const overlay = new window.google.maps.GroundOverlay(
          canvas.toDataURL(),
          bounds,
          { opacity: 0.7 }
        )
        overlay.setMap(showFlux ? map : null)
        fluxOverlayRef.current = overlay
      }
    } catch (e) {
      console.warn('Flux overlay failed:', e)
    }
  }

  // Fetch grouped panels whenever count changes
  useEffect(() => {
    if (!lat || !lng || !buildingData) return
    fetch(`/api/solar/panels-grouped?lat=${lat}&lng=${lng}&count=${panelCount}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setGroupedData(data) })
      .catch(() => {})
  }, [lat, lng, panelCount, buildingData])

  // Toggle flux overlay
  useEffect(() => {
    if (fluxOverlayRef.current && mapInstanceRef.current) {
      fluxOverlayRef.current.setMap(showFlux ? mapInstanceRef.current : null)
    }
  }, [showFlux])

  // Render panels when data or count changes
  useEffect(() => {
    const map = mapInstanceRef.current
    const geometry = geometryLibRef.current
    if (!map || !geometry || !buildingData) return

    // Clear existing panels
    panelPolygonsRef.current.forEach(p => p.setMap(null))
    panelPolygonsRef.current = []

    if (!showPanels || !groupedData) return

    const segments = buildingData.roof_segments || []
    // Prefer equipment-selected panel dimensions (mm → m), fall back to building data defaults
    const panelW = panelDimensions?.width
      ? panelDimensions.width / 1000
      : (buildingData.panel_dimensions?.width_m || 1.045)
    const panelH = panelDimensions?.length
      ? panelDimensions.length / 1000
      : (buildingData.panel_dimensions?.height_m || 1.879)

    // Flatten all panels from grouped arrays
    const allPanels = []
    for (const arr of (groupedData.arrays || [])) {
      for (const p of arr.panels) {
        allPanels.push({ ...p, azimuth_deg: arr.azimuth_deg })
      }
    }

    allPanels.forEach((panel, i) => {
      const [w, h] = [panelW / 2, panelH / 2]
      const corners = [
        { x: +w, y: +h },
        { x: +w, y: -h },
        { x: -w, y: -h },
        { x: -w, y: +h },
        { x: +w, y: +h },
      ]

      const orientation = panel.orientation === 'PORTRAIT' ? 90 : 0
      const azimuth = panel.azimuth_deg || 0
      const center = { lat: panel.lat, lng: panel.lng }

      const paths = corners.map(({ x, y }) => {
        const distance = Math.sqrt(x * x + y * y)
        const bearing = Math.atan2(y, x) * (180 / Math.PI) + orientation + azimuth
        return geometry.spherical.computeOffset(center, distance, bearing)
      })

      // Color by status: green = valid, yellow = flagged, default = navy
      const hasViolations = panel.violations?.length > 0
      const fillColor = hasViolations ? '#FFA000' : '#1A237E'
      const strokeColor = hasViolations ? '#E65100' : '#B0BEC5'

      const poly = new window.google.maps.Polygon({
        paths,
        strokeColor,
        strokeOpacity: 0.9,
        strokeWeight: 1,
        fillColor,
        fillOpacity: 0.85,
        map,
        clickable: true,
      })

      poly.addListener('click', () => {
        const flags = panel.violations?.length ? `<br><span style="color:#E65100">⚠ ${panel.violations.join(', ')}</span>` : ''
        new window.google.maps.InfoWindow({
          content: `<div style="font-size:12px;font-family:Arial;line-height:1.5">
            <b>Panel ${panel.index + 1}</b> (Array ${panel.array_id})<br>
            ${panel.yearly_energy_kwh?.toFixed(0)} kWh/year<br>
            Segment ${panel.segment_index} · Row ${panel.row}, Col ${panel.col}<br>
            ${panel.orientation}${flags}
          </div>`,
          position: center,
        }).open(map)
      })

      panelPolygonsRef.current.push(poly)
    })
  }, [buildingData, panelCount, showPanels, groupedData])

  // Totals from grouped data
  const totalKwh = groupedData?.total_kwh || 0
  const totalPanelsPlaced = groupedData?.total_panels || panelCount
  const totalKw = (totalPanelsPlaced * (buildingData?.panel_capacity_w || 400) / 1000)
  const maxPanels = buildingData?.max_panels || 78

  if (error) {
    return <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">Solar data unavailable: {error}</div>
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <div ref={mapRef} className="w-full rounded-lg border border-gray-200" style={{ height: '450px' }} />
        {loading && (
          <div className="absolute inset-0 bg-white/70 flex items-center justify-center rounded-lg">
            <div className="text-gray-600">Loading solar data...</div>
          </div>
        )}
      </div>

      {buildingData && (
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
              <div className="text-lg font-bold text-gray-900">{totalKwh.toFixed(0)}</div>
              <div className="text-xs text-gray-500">kWh/yr</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <div className="text-lg font-bold text-gray-900">
                {buildingData.carbon_offset ? (totalKwh * buildingData.carbon_offset / 1000000).toFixed(1) : '—'}
              </div>
              <div className="text-xs text-gray-500">t CO₂/yr</div>
            </div>
          </div>

          {/* Toggles */}
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={showFlux} onChange={e => setShowFlux(e.target.checked)} className="accent-orange-500" />
              <span className="text-gray-600">Solar irradiance</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={showPanels} onChange={e => setShowPanels(e.target.checked)} className="accent-solar-600" />
              <span className="text-gray-600">Panels</span>
            </label>
          </div>

          {/* Monthly Production */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">Monthly Production Estimate</div>
            <div className="flex items-end gap-1" style={{ height: '80px' }}>
              {(() => {
                const factors = [0.04, 0.05, 0.08, 0.10, 0.12, 0.13, 0.13, 0.12, 0.09, 0.07, 0.04, 0.03]
                const months = ['J','F','M','A','M','J','J','A','S','O','N','D']
                const maxF = Math.max(...factors)
                return months.map((m, i) => {
                  const kwh = Math.round(totalKwh * factors[i])
                  const pct = (factors[i] / maxF) * 100
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                      <div className="w-full rounded-t" style={{
                        height: `${pct}%`, minHeight: '4px',
                        backgroundColor: `hsl(${40 + pct * 0.6}, 80%, 55%)`
                      }} title={`${months[i]}: ${kwh} kWh`} />
                      <span className="text-[9px] text-gray-400">{m}</span>
                    </div>
                  )
                })
              })()}
            </div>
            <div className="flex justify-between text-[10px] text-gray-400 mt-1">
              <span>Low: {Math.round(totalKwh * 0.03)} kWh (Dec)</span>
              <span>Peak: {Math.round(totalKwh * 0.13)} kWh (Jun/Jul)</span>
            </div>
          </div>

          {/* Roof segments */}
          {buildingData.roof_segments?.length > 0 && (
            <div className="text-xs text-gray-500 space-y-0.5">
              {buildingData.roof_segments.map((seg, i) => {
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
      )}
    </div>
  )
}
