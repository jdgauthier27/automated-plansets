import { useEffect, useRef, useState } from 'react'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'

// Disable Cesium Ion — we use Google 3D Tiles directly, no Ion account needed
Cesium.Ion.defaultAccessToken = undefined

/**
 * 3D Photorealistic Building Viewer with Solar Panels
 *
 * Uses Google Photorealistic 3D Tiles via CesiumJS — the only officially
 * supported renderer for Google's 3D tile format.
 *
 * Panels are clamped to ground so they sit on the actual roof surface,
 * not floating in the air like the old deck.gl implementation.
 */
export default function CesiumMap3D({
  lat, lng, apiKey,
  panelCount = 13, panels = [], segments = [], panelDimensions,
  dsmHeights, onPanelCountChange, onDataLoaded,
  maxPanels = 78, totalKwh = 0, carbonOffset = 0, panelCapacityW = 400,
}) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const panelEntitiesRef = useRef([])
  const outlineEntitiesRef = useRef([])
  const handlerRef = useRef(null)
  const orbitListenerRef = useRef(null)
  const orbitHeadingRef = useRef(0)
  const isOrbitingRef = useRef(false)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isOrbiting, setIsOrbiting] = useState(false)
  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, text: '' })

  // Fetch building data if not already provided
  useEffect(() => {
    if (panels.length > 0 || !lat || !lng) return
    fetch(`/api/solar/building?lat=${lat}&lng=${lng}`)
      .then(r => r.json())
      .then(data => { if (onDataLoaded) onDataLoaded(data) })
      .catch(() => {})
  }, [lat, lng])

  // Initialize Cesium viewer and load Google 3D Tiles
  useEffect(() => {
    if (!containerRef.current || !lat || !lng || !apiKey) return

    // Cleanup previous instance
    if (viewerRef.current && !viewerRef.current.isDestroyed()) {
      viewerRef.current.destroy()
      viewerRef.current = null
    }

    setLoading(true)
    setError(null)
    setIsOrbiting(false)
    isOrbitingRef.current = false

    const creditDiv = document.createElement('div')

    let viewer
    try {
      viewer = new Cesium.Viewer(containerRef.current, {
        // Disable default Bing imagery — Google 3D Tiles provide their own
        imageryProvider: false,
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        vrButton: false,
        creditContainer: creditDiv, // hide credit display (we show Google attribution separately)
        depthPlaneEllipsoidOffset: 0.1,
      })

      // Show globe as fallback while 3D tiles load
      viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0a0a1a')
      viewer.scene.globe.show = true // show globe until 3D tiles cover it

      // Immediately set camera to building location (don't wait for tiles)
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(lng, lat, 200),
        orientation: {
          heading: Cesium.Math.toRadians(0),
          pitch: Cesium.Math.toRadians(-45),
          roll: 0,
        },
      })

      viewerRef.current = viewer
    } catch (err) {
      setError('Failed to initialize 3D viewer: ' + err.message)
      setLoading(false)
      return
    }

    // Set up hover tooltip handler
    handlerRef.current = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    handlerRef.current.setInputAction((movement) => {
      const picked = viewer.scene.pick(movement.endPosition)
      if (Cesium.defined(picked) && picked.id?.description) {
        const desc = picked.id.description.getValue(Cesium.JulianDate.now())
        const rect = containerRef.current?.getBoundingClientRect()
        if (rect) {
          setTooltip({
            visible: true,
            x: movement.endPosition.x,
            y: movement.endPosition.y,
            text: desc,
          })
        }
      } else {
        setTooltip({ visible: false, x: 0, y: 0, text: '' })
      }
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE)

    // Stop orbit on user interaction
    handlerRef.current.setInputAction(() => {
      if (isOrbitingRef.current) {
        stopOrbit(viewer)
        setIsOrbiting(false)
      }
    }, Cesium.ScreenSpaceEventType.LEFT_DOWN)
    handlerRef.current.setInputAction(() => {
      if (isOrbitingRef.current) {
        stopOrbit(viewer)
        setIsOrbiting(false)
      }
    }, Cesium.ScreenSpaceEventType.RIGHT_DOWN)
    handlerRef.current.setInputAction(() => {
      if (isOrbitingRef.current) {
        stopOrbit(viewer)
        setIsOrbiting(false)
      }
    }, Cesium.ScreenSpaceEventType.MIDDLE_DOWN)

    // Load Google Photorealistic 3D Tiles
    ;(async () => {
      try {
        const tileset = await Cesium.Cesium3DTileset.fromUrl(
          `https://tile.googleapis.com/v1/3dtiles/root.json?key=${apiKey}`
        )

        if (viewerRef.current && !viewerRef.current.isDestroyed()) {
          viewerRef.current.scene.primitives.add(tileset)

          // Once tiles are loaded, hide globe and fly to building
          viewerRef.current.scene.globe.show = false
          orbitHeadingRef.current = 0
          viewerRef.current.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(lng - 0.0002, lat - 0.0003, 80),
            orientation: {
              heading: Cesium.Math.toRadians(30),
              pitch: Cesium.Math.toRadians(-40),
              roll: 0,
            },
            duration: 2.0,
          })

          setLoading(false)
        }
      } catch (err) {
        if (err.message?.includes('403') || err.message?.includes('401')) {
          setError('Google 3D Tiles: API key not authorized. Enable "Map Tiles API" in Google Cloud Console.')
        } else if (err.message?.includes('404')) {
          setError('No 3D tile coverage for this location. Use the 2D Satellite view instead.')
        } else {
          setError('3D tiles failed to load: ' + err.message)
        }
        setLoading(false)
      }
    })()

    return () => {
      if (handlerRef.current && !handlerRef.current.isDestroyed()) {
        handlerRef.current.destroy()
        handlerRef.current = null
      }
      if (orbitListenerRef.current) {
        orbitListenerRef.current()
        orbitListenerRef.current = null
      }
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy()
        viewerRef.current = null
      }
    }
  }, [lat, lng, apiKey])

  // Add/update panel entities whenever panel data or count changes
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !panels.length) return

    // Remove previous panel and outline entities
    panelEntitiesRef.current.forEach(e => viewer.entities.remove(e))
    panelEntitiesRef.current = []
    outlineEntitiesRef.current.forEach(e => viewer.entities.remove(e))
    outlineEntitiesRef.current = []

    const selectedPanels = panels.slice(0, panelCount)

    // Panel dimensions: prefer equipment-selected (mm → m), fall back to API defaults
    const panelW = panelDimensions?.width
      ? panelDimensions.width / 1000
      : (panelDimensions?.width_m || 1.045)
    const panelH = panelDimensions?.length
      ? panelDimensions.length / 1000
      : (panelDimensions?.height_m || 1.879)

    // Collect panel centers for building outline
    const allLats = []
    const allLngs = []

    selectedPanels.forEach((panel, i) => {
      const cLat = panel.lat
      const cLng = panel.lng
      if (!cLat || !cLng) return

      allLats.push(cLat)
      allLngs.push(cLng)

      const segIdx = panel.segment_index || 0
      const azimuth = segments[segIdx]?.azimuth_deg || 180 // default south-facing
      const orientation = panel.orientation === 'PORTRAIT' ? 90 : 0
      const totalAngle = azimuth + orientation

      // Half-dimensions in degrees (approximate)
      const cosLat = Math.cos(cLat * Math.PI / 180)
      const halfW = (panelW / 2) / (111319.5 * cosLat) // half-width in degrees lng
      const halfH = (panelH / 2) / 111319.5             // half-height in degrees lat

      // Rotate corners by roof azimuth
      const corners = [
        { dx: +halfW, dy: +halfH },
        { dx: +halfW, dy: -halfH },
        { dx: -halfW, dy: -halfH },
        { dx: -halfW, dy: +halfH },
      ].map(({ dx, dy }) => {
        const angleRad = totalAngle * Math.PI / 180
        const rotX = dx * Math.cos(angleRad) - dy * Math.sin(angleRad)
        const rotY = dx * Math.sin(angleRad) + dy * Math.cos(angleRad)
        return [cLng + rotX, cLat + rotY]
      })

      // Use DSM height if available, otherwise clamp to terrain
      const absElevation = dsmHeights?.panel_heights?.[String(i)]
      const groundElevation = dsmHeights?.building?.ground_elevation_m || 0
      const roofHeight = absElevation > 0 ? absElevation - groundElevation : null

      const coordsFlat = corners.flatMap(([lng, lat]) => [lng, lat])

      // Tooltip text for this panel
      const kwhPerYear = (panel.yearly_energy_kwh || 0).toFixed(0)
      const wattage = panelCapacityW || 400
      const tooltipText = `Panel ${i + 1} · ${wattage}W · ${kwhPerYear} kWh/yr`

      const entity = viewer.entities.add({
        polygon: {
          hierarchy: {
            positions: Cesium.Cartesian3.fromDegreesArray(coordsFlat),
          },
          material: Cesium.Color.fromCssColorString('#1a3a5c').withAlpha(0.88),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString('#b0bec5').withAlpha(0.9),
          outlineWidth: 1,
          // Clamp to ground surface so panels sit on roof, not floating
          heightReference: roofHeight !== null
            ? Cesium.HeightReference.RELATIVE_TO_GROUND
            : Cesium.HeightReference.CLAMP_TO_GROUND,
          height: roofHeight !== null ? roofHeight : undefined,
          perPositionHeight: false,
          classificationType: Cesium.ClassificationType.CESIUM_3D_TILE,
        },
        description: tooltipText,
      })

      panelEntitiesRef.current.push(entity)
    })

    // Draw building footprint outline from panel bounding box (convex hull approximation)
    if (allLats.length >= 3) {
      const minLat = Math.min(...allLats)
      const maxLat = Math.max(...allLats)
      const minLng = Math.min(...allLngs)
      const maxLng = Math.max(...allLngs)
      // Expand bounding box by ~1m around panels
      const padLat = 0.00001
      const padLng = 0.00001

      const bboxCoords = [
        minLng - padLng, minLat - padLat,
        maxLng + padLng, minLat - padLat,
        maxLng + padLng, maxLat + padLat,
        minLng - padLng, maxLat + padLat,
        minLng - padLng, minLat - padLat, // close
      ]

      const outlineEntity = viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(bboxCoords),
          width: 2,
          material: new Cesium.PolylineGlowMaterialProperty({
            glowPower: 0.2,
            color: Cesium.Color.fromCssColorString('#f59e0b').withAlpha(0.7),
          }),
          clampToGround: true,
          classificationType: Cesium.ClassificationType.CESIUM_3D_TILE,
        },
      })
      outlineEntitiesRef.current.push(outlineEntity)
    }
  }, [panels, panelCount, segments, panelDimensions, dsmHeights])

  // Orbit controls
  function startOrbit() {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return

    isOrbitingRef.current = true
    setIsOrbiting(true)

    // Record current heading as orbit start
    orbitHeadingRef.current = viewer.camera.heading

    // Remove any existing listener
    if (orbitListenerRef.current) {
      orbitListenerRef.current()
      orbitListenerRef.current = null
    }

    const targetPos = Cesium.Cartesian3.fromDegrees(lng, lat, 0)

    orbitListenerRef.current = viewer.scene.postRender.addEventListener(() => {
      if (!isOrbitingRef.current) return
      orbitHeadingRef.current += 0.003 // radians per frame (~10°/sec at 60fps)
      viewer.camera.lookAt(
        targetPos,
        new Cesium.HeadingPitchRange(
          orbitHeadingRef.current,
          Cesium.Math.toRadians(-35),
          150 // distance in meters
        )
      )
    })
  }

  function stopOrbit(viewer) {
    isOrbitingRef.current = false
    if (orbitListenerRef.current) {
      orbitListenerRef.current()
      orbitListenerRef.current = null
    }
    // Unlock camera so user can interact freely
    if (viewer && !viewer.isDestroyed()) {
      viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY)
    }
  }

  function toggleOrbit() {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return
    if (isOrbitingRef.current) {
      stopOrbit(viewer)
      setIsOrbiting(false)
    } else {
      startOrbit()
    }
  }

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
        />

        {/* Panel count overlay — top left */}
        {!loading && !error && (
          <div className="absolute top-2 left-2 bg-black/65 text-white rounded-lg px-3 py-2 space-y-0.5 pointer-events-none">
            <div className="text-sm font-bold text-solar-400">{panelCount} panels · {totalKw.toFixed(1)} kW</div>
            <div className="text-xs text-gray-300">{calcTotalKwh.toFixed(0)} kWh/yr estimated</div>
          </div>
        )}

        {/* Orbit button — top right */}
        {!loading && !error && (
          <button
            onClick={toggleOrbit}
            className={`absolute top-2 right-2 px-2 py-1 text-xs font-medium rounded transition-colors ${
              isOrbiting
                ? 'bg-solar-600 text-white'
                : 'bg-black/65 text-white hover:bg-black/80'
            }`}
            title={isOrbiting ? 'Stop orbit (or click/drag map)' : 'Auto-orbit around building'}
          >
            {isOrbiting ? '⏸ Stop' : '⟳ Orbit'}
          </button>
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
              <div className="text-gray-500 text-xs mt-2">Use 2D Satellite view for panel editing.</div>
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

        {/* Hover tooltip */}
        {tooltip.visible && (
          <div
            className="absolute pointer-events-none bg-gray-900/90 text-white text-xs px-2 py-1 rounded shadow-lg border border-gray-600"
            style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
          >
            {tooltip.text}
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        {/* Panel count slider */}
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
              {carbonOffset ? (calcTotalKwh * carbonOffset / 1_000_000).toFixed(1) : '—'}
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
                  <div
                    className="w-full rounded-t"
                    style={{
                      height: `${(f / 0.13) * 100}%`,
                      minHeight: '3px',
                      backgroundColor: `hsl(${40 + (f / 0.13) * 60}, 80%, 55%)`,
                    }}
                    title={`${months[i]}: ${Math.round(calcTotalKwh * f)} kWh`}
                  />
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
