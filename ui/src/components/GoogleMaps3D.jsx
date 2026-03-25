import { useEffect, useRef, useState, useCallback } from 'react'
import {
  PlaneGeometry, MeshStandardMaterial, Mesh,
  Raycaster, Vector2, CanvasTexture, DoubleSide,
} from 'three'
import { ThreeJSOverlayView } from '@googlemaps/three'

/**
 * 3D Solar Panel Viewer — Google Maps WebGL Overlay + THREE.js
 *
 * Uses Google Maps' own WebGL rendering context so THREE.js objects share
 * the exact same coordinate system as the 3D map. No ECEF math, no geoid
 * offsets — latLngAltitudeToVector3() handles everything.
 *
 * Requirements:
 * - Google Maps JS API with a Map ID that has vector rendering enabled
 * - @googlemaps/three package
 */

// Build a dark solar panel texture with cell grid lines (like OpenSolar)
function createPanelTexture() {
  const c = document.createElement('canvas')
  c.width = 120
  c.height = 200
  const ctx = c.getContext('2d')

  // Dark panel fill
  ctx.fillStyle = '#1a2a3a'
  ctx.fillRect(0, 0, 120, 200)

  // Cell grid lines (6 columns × 10 rows)
  ctx.strokeStyle = 'rgba(84, 110, 122, 0.45)'
  ctx.lineWidth = 0.5
  for (let i = 1; i < 6; i++) {
    ctx.beginPath(); ctx.moveTo(i * 20, 0); ctx.lineTo(i * 20, 200); ctx.stroke()
  }
  for (let i = 1; i < 10; i++) {
    ctx.beginPath(); ctx.moveTo(0, i * 20); ctx.lineTo(120, i * 20); ctx.stroke()
  }

  // Panel frame border
  ctx.strokeStyle = 'rgba(200, 210, 220, 0.6)'
  ctx.lineWidth = 2
  ctx.strokeRect(1, 1, 118, 198)

  const tex = new CanvasTexture(c)
  tex.needsUpdate = true
  return tex
}

// Load Google Maps JS API (avoids double-loading with SolarMap)
function loadGoogleMapsApi(apiKey) {
  return new Promise((resolve, reject) => {
    if (window.google?.maps?.Map) {
      resolve(window.google.maps)
      return
    }
    // Check if script is already loading
    if (document.querySelector('script[src*="maps.googleapis.com"]')) {
      const check = setInterval(() => {
        if (window.google?.maps?.Map) { clearInterval(check); resolve(window.google.maps) }
      }, 100)
      setTimeout(() => { clearInterval(check); reject(new Error('Maps API load timeout')) }, 15000)
      return
    }
    const script = document.createElement('script')
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&v=weekly&libraries=geometry`
    script.async = true
    script.defer = true
    script.onload = () => {
      if (window.google?.maps) resolve(window.google.maps)
      else reject(new Error('Google Maps failed to initialize'))
    }
    script.onerror = () => reject(new Error('Failed to load Google Maps API'))
    document.head.appendChild(script)
  })
}

export default function GoogleMaps3D({
  lat, lng, apiKey,
  panelCount = 13, panels = [], segments = [], panelDimensions,
  dsmHeights, onPanelCountChange, onDataLoaded,
  maxPanels = 78, totalKwh = 0, carbonOffset = 0, panelCapacityW = 400,
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const overlayRef = useRef(null)
  const panelMeshesRef = useRef([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [clickTooltip, setClickTooltip] = useState(null)

  // Fetch building data if not provided
  useEffect(() => {
    if (panels.length > 0 || !lat || !lng) return
    fetch(`/api/solar/building?lat=${lat}&lng=${lng}`)
      .then(r => r.json())
      .then(data => { if (onDataLoaded) onDataLoaded(data) })
      .catch(() => {})
  }, [lat, lng])

  // Initialize Google Map + ThreeJSOverlayView
  useEffect(() => {
    if (!containerRef.current || !lat || !lng || !apiKey) return

    let cancelled = false

    loadGoogleMapsApi(apiKey).then((maps) => {
      if (cancelled) return

      // Create the Google Map with 3D tilt enabled
      // mapId enables vector rendering (required for WebGLOverlayView)
      const map = new maps.Map(containerRef.current, {
        center: { lat, lng },
        zoom: 20,
        tilt: 45,
        heading: 0,
        // Note: mapTypeId 'satellite' may not support WebGL overlay
        // Vector map rendering requires a real Map ID from Google Cloud Console
        mapId: 'DEMO_MAP_ID',
        disableDefaultUI: true,
        gestureHandling: 'greedy',
        zoomControl: true,
        rotateControl: true,
      })

      mapRef.current = map

      // Create ThreeJSOverlayView anchored at building
      const overlay = new ThreeJSOverlayView({
        anchor: { lat, lng, altitude: 0 },
        map,
        upAxis: 'Y', // THREE.js convention
        animationMode: 'always',
        addDefaultLighting: true,
      })

      overlayRef.current = overlay

      // Fly to optimal viewing angle once map loads
      map.addListener('tilesloaded', () => {
        if (!cancelled) {
          setLoading(false)
          // Tilt for 3D effect
          map.moveCamera({
            center: { lat, lng },
            zoom: 20,
            tilt: 55,
            heading: getPrimaryAzimuth() + 135,
          })
        }
      })

      function getPrimaryAzimuth() {
        if (segments.length > 0) return segments[0].azimuth_deg || 180
        return 180
      }

    }).catch(err => {
      if (!cancelled) setError('Failed to load Google Maps: ' + err.message)
      setLoading(false)
    })

    return () => {
      cancelled = true
      // Cleanup overlay
      if (overlayRef.current) {
        overlayRef.current.setMap(null)
        overlayRef.current = null
      }
      mapRef.current = null
    }
  }, [lat, lng, apiKey])

  // Place panel meshes
  useEffect(() => {
    const overlay = overlayRef.current
    if (!overlay || !panels.length || loading) return

    // Remove previous panels
    panelMeshesRef.current.forEach(m => {
      overlay.scene.remove(m)
      m.geometry.dispose()
    })
    panelMeshesRef.current = []

    const selectedPanels = panels.slice(0, panelCount)

    // Panel dimensions (mm → m)
    const panelW = panelDimensions?.width ? panelDimensions.width / 1000 : 1.045
    const panelH = panelDimensions?.length ? panelDimensions.length / 1000 : 1.879

    const texture = createPanelTexture()
    const material = new MeshStandardMaterial({
      map: texture,
      metalness: 0.3,
      roughness: 0.6,
      side: DoubleSide,
    })

    const groundElev = dsmHeights?.building?.ground_elevation_m || 0

    selectedPanels.forEach((panel, i) => {
      if (!panel.lat || !panel.lng) return

      // Altitude: height above ground from DSM
      const panelDsmH = dsmHeights?.panel_heights?.[String(i)]
      const altAboveGround = panelDsmH > 0
        ? (panelDsmH - groundElev) + 0.3  // DSM roof height + 30cm
        : 7  // fallback: ~7m for typical 2-story house

      // Convert to local THREE.js coordinates relative to anchor
      const pos = overlay.latLngAltitudeToVector3({
        lat: panel.lat,
        lng: panel.lng,
        altitude: altAboveGround,
      })

      const geom = new PlaneGeometry(panelW, panelH)
      const mesh = new Mesh(geom, material)
      mesh.position.copy(pos)

      // Rotate to match roof segment
      const segIdx = panel.segment_index || 0
      const azimuthDeg = segments[segIdx]?.azimuth_deg || 180
      const pitchDeg = segments[segIdx]?.pitch_deg || 15

      // Panel faces up by default (PlaneGeometry normal = +Z in local)
      // With upAxis='Y': Y is up, so rotate panel to lay flat first
      mesh.rotation.x = -Math.PI / 2 // lay flat (face up)
      mesh.rotation.x += (pitchDeg * Math.PI / 180) // tilt to roof pitch
      mesh.rotation.z = -((azimuthDeg - 180) * Math.PI / 180) // rotate to azimuth

      // Store panel data for click tooltips
      mesh.userData.panelData = {
        panelNum: i + 1,
        wattage: panelCapacityW || 400,
        faceName: panel.face_name || `Roof Face ${segIdx + 1}`,
        kwhPerYear: (panel.yearly_energy_kwh || 0).toFixed(0),
      }

      overlay.scene.add(mesh)
      panelMeshesRef.current.push(mesh)
    })

    // Request redraw
    overlay.requestRedraw()

    console.log(`[GoogleMaps3D] Placed ${panelMeshesRef.current.length}/${selectedPanels.length} panels`)
  }, [panels, panelCount, segments, panelDimensions, dsmHeights, loading])

  // Click handler for panel tooltips
  const handleClick = useCallback((e) => {
    const overlay = overlayRef.current
    if (!overlay || panelMeshesRef.current.length === 0) return

    const rect = containerRef.current.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1

    const hits = overlay.raycast({ x, y }, panelMeshesRef.current, { recursive: false })
    if (hits.length > 0 && hits[0].object.userData.panelData) {
      const d = hits[0].object.userData.panelData
      setClickTooltip({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        ...d,
      })
      setTimeout(() => setClickTooltip(null), 5000)
    } else {
      setClickTooltip(null)
    }
  }, [])

  // Stats
  const selectedPanels = panels.slice(0, panelCount)
  const calcTotalKwh = selectedPanels.reduce((s, p) => s + (p.yearly_energy_kwh || 0), 0) || totalKwh
  const totalKw = (panelCount * panelCapacityW) / 1000

  return (
    <div className="space-y-3">
      {/* 3D Map */}
      <div className="relative">
        <div
          ref={containerRef}
          className="w-full rounded-lg border border-gray-200 bg-gray-900"
          style={{ height: '450px' }}
          onClick={handleClick}
        />

        {/* Panel count overlay */}
        {!loading && !error && (
          <div className="absolute top-2 left-2 bg-black/65 text-white rounded-lg px-3 py-2 space-y-0.5 pointer-events-none">
            <div className="text-sm font-bold text-solar-400">{panelCount} panels · {totalKw.toFixed(1)} kW</div>
            <div className="text-xs text-gray-300">{calcTotalKwh.toFixed(0)} kWh/yr estimated</div>
          </div>
        )}

        {/* Compass rose */}
        {!loading && !error && (
          <div className="absolute bottom-16 right-3 w-12 h-12 pointer-events-none">
            <svg viewBox="0 0 48 48" className="w-full h-full drop-shadow-lg">
              <circle cx="24" cy="24" r="22" fill="rgba(0,0,0,0.5)" stroke="rgba(255,255,255,0.3)" strokeWidth="1"/>
              <polygon points="24,4 20,22 24,19 28,22" fill="#e53935"/>
              <polygon points="24,44 20,26 24,29 28,26" fill="rgba(255,255,255,0.6)"/>
              <text x="24" y="11" textAnchor="middle" fill="white" fontSize="7" fontWeight="bold">N</text>
              <text x="24" y="42" textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="6">S</text>
              <text x="40" y="26" textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="6">E</text>
              <text x="8" y="26" textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="6">W</text>
            </svg>
          </div>
        )}

        {loading && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center rounded-lg">
            <div className="text-white text-sm">Loading 3D model...</div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 bg-black/80 flex items-center justify-center rounded-lg p-6">
            <div className="text-center">
              <div className="text-amber-400 text-sm font-medium mb-2">3D View Unavailable</div>
              <div className="text-gray-300 text-xs max-w-xs">{error}</div>
            </div>
          </div>
        )}

        {!loading && !error && (
          <div className="absolute bottom-2 left-2 bg-black/60 text-white text-[10px] px-2 py-1 rounded">
            Drag to rotate · Scroll to zoom · Right-drag to pan
          </div>
        )}

        {!loading && !error && (
          <div className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-2 py-1 rounded">
            © Google, Imagery © 2024
          </div>
        )}

        {/* Click tooltip */}
        {clickTooltip && (
          <div
            className="absolute bg-gray-900/95 text-white text-xs rounded-lg shadow-xl border border-gray-500 p-3 min-w-[190px]"
            style={{ left: clickTooltip.x + 15, top: Math.max(8, clickTooltip.y - 10), zIndex: 50 }}
          >
            <button
              onClick={(e) => { e.stopPropagation(); setClickTooltip(null) }}
              className="absolute top-1.5 right-2 text-gray-400 hover:text-white text-base leading-none"
            >×</button>
            <div className="font-semibold text-solar-400 mb-1.5">Panel #{clickTooltip.panelNum}</div>
            <div className="text-gray-300 space-y-0.5">
              <div>{clickTooltip.wattage} W</div>
              <div>{clickTooltip.faceName}</div>
              <div>{clickTooltip.kwhPerYear} kWh/yr</div>
            </div>
          </div>
        )}
      </div>

      {/* Controls panel */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="font-medium text-gray-700">Panel Count</span>
            <span className="text-solar-600 font-bold">{panelCount} panels</span>
          </div>
          <input
            type="range" min="1" max={maxPanels} value={panelCount}
            onChange={e => onPanelCountChange?.(parseInt(e.target.value))}
            className="w-full accent-solar-600"
          />
          <div className="flex justify-between text-xs text-gray-400">
            <span>1</span><span>{maxPanels} max</span>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2 text-center">
          {[
            { val: panelCount, label: 'Panels' },
            { val: totalKw.toFixed(1), label: 'kW DC' },
            { val: calcTotalKwh.toFixed(0), label: 'kWh/yr' },
            { val: carbonOffset ? (calcTotalKwh * carbonOffset / 1e6).toFixed(1) : '—', label: 't CO₂/yr' },
          ].map(({ val, label }) => (
            <div key={label} className="bg-gray-50 rounded-lg p-2">
              <div className="text-lg font-bold text-gray-900">{val}</div>
              <div className="text-xs text-gray-500">{label}</div>
            </div>
          ))}
        </div>

        {segments.length > 0 && (
          <div className="text-xs text-gray-500 space-y-0.5">
            {segments.map((seg, i) => {
              const dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW']
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
