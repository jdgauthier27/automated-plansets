import { useEffect, useRef, useState } from 'react'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'

// Disable Cesium Ion — we use Google 3D Tiles directly, no Ion account needed
Cesium.Ion.defaultAccessToken = undefined

const DEFAULT_ORBIT_HEADING_DEG = 340
const FT_PER_M = 3.28084
const FT_PER_DEG_LAT = 364000

function isFiniteNumber(value) {
  return Number.isFinite(Number(value))
}

function normalizeLatLngPoint(point) {
  if (!point) return null

  if (Array.isArray(point) && point.length >= 2 && isFiniteNumber(point[0]) && isFiniteNumber(point[1])) {
    return [Number(point[0]), Number(point[1])]
  }

  if (typeof point === 'object') {
    const lng = point.lng ?? point.lon ?? point.longitude ?? point.x
    const lat = point.lat ?? point.latitude ?? point.y
    if (isFiniteNumber(lng) && isFiniteNumber(lat)) {
      return [Number(lng), Number(lat)]
    }
  }

  return null
}

function ensureClosedRing(ring) {
  if (!ring.length) return ring
  const [firstLng, firstLat] = ring[0]
  const [lastLng, lastLat] = ring[ring.length - 1]
  if (Math.abs(firstLng - lastLng) < 1e-10 && Math.abs(firstLat - lastLat) < 1e-10) {
    return ring
  }
  return [...ring, ring[0]]
}

function extractPolygonRings(value, depth = 0) {
  if (!value || depth > 6) return []

  if (Array.isArray(value)) {
    if (value.length === 0) return []

    if (normalizeLatLngPoint(value[0])) {
      const ring = value.map(normalizeLatLngPoint).filter(Boolean)
      return ring.length >= 3 ? [ensureClosedRing(ring)] : []
    }

    const rings = []
    for (const item of value) {
      rings.push(...extractPolygonRings(item, depth + 1))
    }
    return rings
  }

  if (typeof value === 'object') {
    const keys = [
      'polygon_latlng',
      'polygon',
      'full_polygon',
      'usable_polygon',
      'usablePolygon',
      'outline',
      'boundary',
      'vertices',
      'points',
      'coordinates',
      'rings',
    ]
    for (const key of keys) {
      const rings = extractPolygonRings(value[key], depth + 1)
      if (rings.length) return rings
    }
  }

  return []
}

function convertFtRingToLatLng(ring, centerLat, centerLng) {
  const metersPerDegLng = Math.max(1, 111320 * Math.cos(centerLat * Math.PI / 180))
  return ensureClosedRing(
    ring
      .map((point) => {
        const normalized = normalizeLatLngPoint(point)
        if (!normalized) return null
        const [xFt, yFt] = normalized
        const lng = centerLng + (xFt / FT_PER_M) / metersPerDegLng
        const lat = centerLat + (yFt / FT_PER_M) / FT_PER_DEG_LAT
        return [lng, lat]
      })
      .filter(Boolean),
  )
}

function summarizeRoofGeometry(roofGeometry, fallbackLat, fallbackLng) {
  const centerLat = Number(
    roofGeometry?.center?.latitude ??
    roofGeometry?.center?.lat ??
    roofGeometry?.center_lat ??
    roofGeometry?.lat ??
    fallbackLat
  )
  const centerLng = Number(
    roofGeometry?.center?.longitude ??
    roofGeometry?.center?.lng ??
    roofGeometry?.center_lng ??
    roofGeometry?.lng ??
    fallbackLng
  )

  const faces = (roofGeometry?.roof_faces || []).map((face, index) => {
    const fullRings = extractPolygonRings(
      face?.full_polygon ??
      face?.polygon_latlng ??
      face?.polygon ??
      face?.outline ??
      face?.boundary ??
      face?.vertices ??
      face?.points ??
      face?.coordinates ??
      face?.rings,
    )

    const usableRings = extractPolygonRings(
      face?.usable_polygon_latlng ??
      face?.usable_polygon ??
      face?.usablePolygon ??
      face?.usable ??
      face?.usable_outline ??
      face?.usableOutline,
    )

    const fallbackRings = fullRings.length ? fullRings : usableRings
    return {
      key: face?.id ?? face?.label ?? index,
      label: face?.label ?? `Roof Face ${index + 1}`,
      azimuthDeg: isFiniteNumber(face?.azimuth_deg) ? Number(face.azimuth_deg) : null,
      pitchDeg: isFiniteNumber(face?.pitch_deg) ? Number(face.pitch_deg) : null,
      areaSqft: isFiniteNumber(face?.area_sqft) ? Number(face.area_sqft) : null,
      heightM: isFiniteNumber(face?.height_m) ? Number(face.height_m) : null,
      fullRings: fallbackRings,
      usableRings,
    }
  })

  let outlineRings = extractPolygonRings(
    roofGeometry?.building_outline_latlng ??
    roofGeometry?.building_outline ??
    roofGeometry?.building_outline_polygon ??
    roofGeometry?.outline ??
    roofGeometry?.footprint,
  )

  if (!outlineRings.length && Array.isArray(roofGeometry?.building_outline_ft)) {
    outlineRings = [convertFtRingToLatLng(roofGeometry.building_outline_ft, centerLat, centerLng)]
  }

  const cameraHint = roofGeometry?.camera_hint ?? roofGeometry?.geometry?.camera_hint ?? null

  return { centerLat, centerLng, faces, outlineRings, cameraHint }
}

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
  dsmHeights, roofGeometry, onPanelCountChange, onDataLoaded,
  maxPanels = 78, totalKwh = 0, carbonOffset = 0, panelCapacityW = 400,
}) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const panelEntitiesRef = useRef([])
  const outlineEntitiesRef = useRef([])
  const roofSurfaceEntitiesRef = useRef([])
  const roofOutlineEntitiesRef = useRef([])
  const handlerRef = useRef(null)
  const clickTimerRef = useRef(null)
  const orbitListenerRef = useRef(null)
  const orbitHeadingRef = useRef(0)
  const isOrbitingRef = useRef(false)
  const dsmHeightsRef = useRef(dsmHeights)
  const roofGeometryRef = useRef(roofGeometry)
  const roofRenderSeqRef = useRef(0)

  // Keep ref in sync with latest prop so async blocks always see current value
  useEffect(() => { dsmHeightsRef.current = dsmHeights }, [dsmHeights])
  useEffect(() => { roofGeometryRef.current = roofGeometry }, [roofGeometry])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isOrbiting, setIsOrbiting] = useState(false)
  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, text: '' })
  const [clickTooltip, setClickTooltip] = useState(null)

  function clearEntityCollection(collectionRef) {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return
    collectionRef.current.forEach(entity => viewer.entities.remove(entity))
    collectionRef.current = []
  }

  function getRoofViewState() {
    const summary = summarizeRoofGeometry(roofGeometryRef.current, lat, lng)
    const cameraHint = summary.cameraHint
    const faceCandidates = summary.faces
      .filter(face => isFiniteNumber(face.areaSqft))
      .sort((a, b) => (b.areaSqft || 0) - (a.areaSqft || 0))

    const primaryFace = faceCandidates[0]
    const targetCenterLat = summary.centerLat
    const targetCenterLng = summary.centerLng

    const points = [
      ...summary.outlineRings.flat(),
      ...summary.faces.flatMap(face => face.usableRings.flat()),
      ...summary.faces.flatMap(face => face.fullRings.flat()),
    ]

    let minLat = targetCenterLat
    let maxLat = targetCenterLat
    let minLng = targetCenterLng
    let maxLng = targetCenterLng

    for (const [pointLng, pointLat] of points) {
      if (pointLat < minLat) minLat = pointLat
      if (pointLat > maxLat) maxLat = pointLat
      if (pointLng < minLng) minLng = pointLng
      if (pointLng > maxLng) maxLng = pointLng
    }

    const latMeters = Math.max((maxLat - minLat) * FT_PER_DEG_LAT / FT_PER_M, 20)
    const lngMeters = Math.max((maxLng - minLng) * 111320 * Math.cos(targetCenterLat * Math.PI / 180), 20)
    const hintedSpan = Math.max(
      Number(cameraHint?.radius_m || 0) * 2,
      Number(cameraHint?.width_m || 0),
      Number(cameraHint?.height_m || 0),
    )
    const spanMeters = Math.max(latMeters, lngMeters, hintedSpan || 0)
    const groundH = dsmHeightsRef.current?.building?.ground_elevation_m ?? 0
    // Altitude: close enough to see a residential roof clearly
    // ~50m for a small house, ~80m for a large commercial building
    const altitudeM = groundH + Math.min(120, Math.max(45, spanMeters * 1.8))

    return {
      centerLat: targetCenterLat,
      centerLng: targetCenterLng,
      spanMeters,
      altitudeM,
      headingDeg: primaryFace?.azimuthDeg != null
        ? (primaryFace.azimuthDeg + 135) % 360
        : DEFAULT_ORBIT_HEADING_DEG,
      pitchDeg: -50,
    }
  }

  function focusRoof({ immediate = false } = {}) {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) return

    stopOrbit(viewer)
    setIsOrbiting(false)

    // Use the actual panel positions to find the true building center
    // (the geocode lat/lng is often at the street curb, not the roof)
    let targetLat = lat
    let targetLng = lng
    if (panels.length > 0) {
      const selected = panels.slice(0, Math.min(panelCount, panels.length))
      const validPanels = selected.filter(p => p.lat && p.lng)
      if (validPanels.length > 0) {
        targetLat = validPanels.reduce((s, p) => s + p.lat, 0) / validPanels.length
        targetLng = validPanels.reduce((s, p) => s + p.lng, 0) / validPanels.length
      }
    }

    // Sample the actual tile mesh height at building center for accurate target
    ;(async () => {
      let rooftopH = 280 // fallback: high enough to be safe
      try {
        const cart = Cesium.Cartographic.fromDegrees(targetLng, targetLat)
        const results = await viewer.scene.sampleHeightMostDetailed([cart])
        if (results[0]?.height > 0) {
          rooftopH = results[0].height + 2 // just above roof surface
        }
      } catch (_) {
        // Fallback: use DSM + geoid estimate
        const groundH = dsmHeightsRef.current?.building?.ground_elevation_m ?? 0
        const buildingH = dsmHeightsRef.current?.building?.building_height_m ?? 6
        if (groundH > 0) {
          // Rough geoid offset for this area
          rooftopH = groundH + buildingH - 29
        }
      }

      if (viewer.isDestroyed()) return

      const target = Cesium.Cartesian3.fromDegrees(targetLng, targetLat, rooftopH)
      const primaryAzimuth = segments.length > 0 ? (segments[0].azimuth_deg || 180) : 180
      const headingDeg = (primaryAzimuth + 135) % 360
      const range = 55

      console.log(`[focusRoof] lookAt center=(${targetLat.toFixed(5)}, ${targetLng.toFixed(5)}), rooftopH=${rooftopH.toFixed(1)}m, range=${range}m`)

      viewer.camera.lookAt(
        target,
        new Cesium.HeadingPitchRange(
          Cesium.Math.toRadians(headingDeg),
          Cesium.Math.toRadians(-40),
          range,
        )
      )
      viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY)
    })()
  }

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
        // Disable default Ion imagery — Google 3D Tiles provide their own texture
        // NOTE: imageryProvider:false was removed in CesiumJS 1.118; baseLayer:false is correct API
        baseLayer: false,
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
      })

      // Show globe as fallback while 3D tiles load
      viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0a0a1a')
      viewer.scene.globe.show = true // show globe until 3D tiles cover it

      // Position camera near building while tiles load
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(lng, lat, 280),
        orientation: {
          heading: Cesium.Math.toRadians(DEFAULT_ORBIT_HEADING_DEG),
          pitch: Cesium.Math.toRadians(-52),
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

    // Panel click — show floating tooltip with panel metadata
    handlerRef.current.setInputAction((event) => {
      const picked = viewer.scene.pick(event.position)
      if (Cesium.defined(picked) && picked.id?.properties) {
        const props = picked.id.properties
        if (Cesium.defined(props.panelNum)) {
          const panelNum = props.panelNum.getValue(Cesium.JulianDate.now())
          const wattage = props.wattage.getValue(Cesium.JulianDate.now())
          const faceName = props.faceName.getValue(Cesium.JulianDate.now())
          const row = props.row.getValue(Cesium.JulianDate.now())
          const col = props.col.getValue(Cesium.JulianDate.now())
          if (clickTimerRef.current) clearTimeout(clickTimerRef.current)
          setClickTooltip({ x: event.position.x, y: event.position.y, panelNum, wattage, faceName, row, col })
          clickTimerRef.current = setTimeout(() => setClickTooltip(null), 5000)
          return
        }
      }
      setClickTooltip(null)
      if (clickTimerRef.current) clearTimeout(clickTimerRef.current)
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

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
          focusRoof({ immediate: true })

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
      if (clickTimerRef.current) clearTimeout(clickTimerRef.current)
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

  // When DSM heights arrive after tile-load fly, re-fly to correct building altitude
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || loading || !dsmHeights?.building?.ground_elevation_m) return
    focusRoof({ immediate: true })
  }, [dsmHeights, loading])

  // Render GeoTIFF-derived roof geometry when available so the 3D view reads like a design scene.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || loading) return

    clearEntityCollection(roofSurfaceEntitiesRef)
    clearEntityCollection(roofOutlineEntitiesRef)

    const summary = summarizeRoofGeometry(roofGeometry, lat, lng)
    const descriptors = []
    const accentColors = ['#38bdf8', '#22d3ee', '#60a5fa', '#06b6d4', '#0ea5e9']

    summary.faces.forEach((face, index) => {
      const accent = Cesium.Color.fromCssColorString(accentColors[index % accentColors.length])
      const faceRings = face.fullRings.length ? face.fullRings : face.usableRings

      faceRings.forEach((ring) => {
        descriptors.push({
          kind: 'roof-fill',
          label: face.label,
          ring,
          offsetM: 0.2,
          fillColor: Cesium.Color.fromCssColorString('#0f172a').withAlpha(0.2),
          outlineColor: Cesium.Color.fromCssColorString('#cbd5e1').withAlpha(0.6),
          outlineWidth: 2.0,
        })
      })

      face.usableRings.forEach((ring) => {
        descriptors.push({
          kind: 'usable-fill',
          label: `${face.label} usable area`,
          ring,
          offsetM: 0.55,
          fillColor: accent.withAlpha(0.2),
          outlineColor: accent.withAlpha(0.95),
          outlineWidth: 2.8,
        })
      })
    })

    summary.outlineRings.forEach((ring) => {
      descriptors.push({
        kind: 'building-outline',
        label: 'Building outline',
        ring,
        offsetM: 1.0,
        outlineColor: Cesium.Color.WHITE.withAlpha(0.85),
        outlineWidth: 3.2,
      })
    })

    if (!descriptors.length) return

    const renderSeq = ++roofRenderSeqRef.current

    ;(async () => {
      const cartographics = descriptors.flatMap((descriptor) =>
        descriptor.ring.map(([pointLng, pointLat]) => Cesium.Cartographic.fromDegrees(pointLng, pointLat))
      )

      let sampledHeights = []
      if (cartographics.length) {
        try {
          sampledHeights = await viewer.scene.sampleHeightMostDetailed(cartographics)
        } catch (_) {
          sampledHeights = []
        }
      }

      if (renderSeq !== roofRenderSeqRef.current || viewer.isDestroyed()) return

      const fallbackGroundH = dsmHeightsRef.current?.building?.ground_elevation_m ?? 0
      let cursor = 0

      descriptors.forEach((descriptor) => {
        const coordsWithHeights = []

        descriptor.ring.forEach(([pointLng, pointLat]) => {
          const sampledHeight = sampledHeights[cursor]?.height
          cursor += 1
          const absoluteHeight = Number.isFinite(sampledHeight)
            ? sampledHeight + descriptor.offsetM
            : fallbackGroundH + descriptor.offsetM
          coordsWithHeights.push(pointLng, pointLat, absoluteHeight)
        })

        const positions = Cesium.Cartesian3.fromDegreesArrayHeights(coordsWithHeights)

        if (descriptor.kind !== 'building-outline') {
          const polygonEntity = viewer.entities.add({
            polygon: {
              hierarchy: { positions },
              material: descriptor.fillColor,
              outline: true,
              outlineColor: descriptor.outlineColor,
              outlineWidth: 1,
              perPositionHeight: true,
            },
            description: descriptor.label,
          })
          roofSurfaceEntitiesRef.current.push(polygonEntity)
        }

        const outlineEntity = viewer.entities.add({
          polyline: {
            positions,
            width: descriptor.outlineWidth,
            material: descriptor.outlineColor,
          },
          description: descriptor.label,
        })
        roofOutlineEntitiesRef.current.push(outlineEntity)
      })
    })()

    return () => {
      roofRenderSeqRef.current += 1
      clearEntityCollection(roofSurfaceEntitiesRef)
      clearEntityCollection(roofOutlineEntitiesRef)
    }
  }, [roofGeometry, lat, lng, dsmHeights, loading])

  // Add/update panel entities whenever panel data or count changes
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !panels.length) return
    const roofSummary = summarizeRoofGeometry(roofGeometry, lat, lng)
    const hasRoofGeometry = roofSummary.faces.some((face) => face.fullRings.length || face.usableRings.length)

    // Remove previous panel and outline entities
    panelEntitiesRef.current.forEach(e => viewer.entities.remove(e))
    panelEntitiesRef.current = []
    outlineEntitiesRef.current.forEach(e => viewer.entities.remove(e))
    outlineEntitiesRef.current = []

    const selectedPanels = panels.slice(0, panelCount)

    // Pre-compute row/col within each face group for click tooltip
    const faceIndices = new Map()
    const faceGroups = {}
    selectedPanels.forEach((panel, i) => {
      const key = panel.face_name || `Face${panel.segment_index || 0}`
      if (!faceGroups[key]) faceGroups[key] = []
      faceGroups[key].push(i)
    })
    Object.values(faceGroups).forEach(indices => {
      const sorted = [...indices].sort((a, b) => {
        const latDiff = (selectedPanels[b].lat || 0) - (selectedPanels[a].lat || 0)
        if (Math.abs(latDiff) > 1e-6) return latDiff
        return (selectedPanels[a].lng || 0) - (selectedPanels[b].lng || 0)
      })
      const cols = Math.max(1, Math.ceil(Math.sqrt(sorted.length)))
      sorted.forEach((origIdx, fi) => {
        faceIndices.set(origIdx, { row: Math.floor(fi / cols) + 1, col: (fi % cols) + 1 })
      })
    })

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

    // Pre-compute corner geometry for all panels (sync)
    const panelGeometries = []
    selectedPanels.forEach((panel, i) => {
      const cLat = panel.lat
      const cLng = panel.lng
      if (!cLat || !cLng) return

      allLats.push(cLat)
      allLngs.push(cLng)

      const segIdx = panel.segment_index || 0
      const azimuth = segments[segIdx]?.azimuth_deg || 180
      const orientation = panel.orientation === 'PORTRAIT' ? 90 : 0
      const totalAngle = azimuth + orientation

      const cosLat = Math.cos(cLat * Math.PI / 180)
      const halfW = (panelW / 2) / (111319.5 * cosLat)
      const halfH = (panelH / 2) / 111319.5

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

      const kwhPerYear = (panel.yearly_energy_kwh || 0).toFixed(0)
      const wattage = panelCapacityW || 400
      const tooltipText = `Panel ${i + 1} · ${wattage}W · ${kwhPerYear} kWh/yr`
      const faceName = panel.face_name || `Roof Face ${segIdx + 1}`
      const { row, col } = faceIndices.get(i) || { row: 1, col: 1 }

      panelGeometries.push({ i, cLat, cLng, corners, tooltipText, wattage, faceName, row, col })
    })

    // Place panels by sampling center height from 3D tile mesh, then
    // computing corner heights using roof pitch + azimuth from Solar API.
    // This is more reliable than sampling 4 independent corners which gives
    // noisy results from the tile mesh resolution.
    ;(async () => {
      const OFFSET = 0.4 // 40cm above tile mesh

      // Sample each panel CENTER + building center for geoid reference
      const centerCarts = panelGeometries.map((pg) =>
        Cesium.Cartographic.fromDegrees(pg.cLng, pg.cLat)
      )
      centerCarts.push(Cesium.Cartographic.fromDegrees(lng, lat))

      let sampledHeights = []
      if (!loading && centerCarts.length > 0) {
        try {
          sampledHeights = await viewer.scene.sampleHeightMostDetailed(centerCarts)
        } catch (_) { /* tiles not ready */ }
      }

      if (viewer.isDestroyed()) return

      // Compute geoid undulation from building center sample vs DSM
      const buildingSample = sampledHeights[sampledHeights.length - 1]
      let geoidUndulation = -33.5 // Default Southern California
      const dsmGround = dsmHeights?.building?.ground_elevation_m || 0
      if (buildingSample?.height > 0 && dsmGround > 0) {
        geoidUndulation = buildingSample.height - dsmGround
      }

      console.log(`[CesiumMap3D] Geoid undulation: ${geoidUndulation.toFixed(2)}m, DSM ground: ${dsmGround.toFixed(1)}m`)
      console.log(`[CesiumMap3D] Sampled ${sampledHeights.length - 1} panel centers for ${panelGeometries.length} panels`)

      panelGeometries.forEach((pg, idx) => {
        // Panel center height from 3D tile mesh
        const sampled = sampledHeights[idx]
        let centerH
        if (Number.isFinite(sampled?.height) && sampled.height > 0) {
          centerH = sampled.height + OFFSET
        } else {
          // Fallback: DSM height + geoid
          const dsmPanelH = dsmHeights?.panel_heights?.[String(pg.i)]
          const roofH = dsmPanelH > 0 ? dsmPanelH : (dsmGround + 6)
          centerH = roofH + geoidUndulation + OFFSET
        }

        // Compute corner heights using roof pitch + azimuth
        // Each corner's height offset from center depends on its position
        // relative to the roof slope direction
        const segIdx = selectedPanels[pg.i]?.segment_index || 0
        const pitchDeg = segments[segIdx]?.pitch_deg || 0
        const azimuthDeg = segments[segIdx]?.azimuth_deg || 180
        const pitchRad = pitchDeg * Math.PI / 180
        const azimuthRad = azimuthDeg * Math.PI / 180

        // Slope direction vector (downhill) in local ENU coords
        const slopeEast = Math.sin(azimuthRad)
        const slopeNorth = Math.cos(azimuthRad)

        const cornerHeights = pg.corners.map(([cornerLng, cornerLat]) => {
          // Distance from panel center in meters
          const dLng = (cornerLng - pg.cLng) * 111320 * Math.cos(pg.cLat * Math.PI / 180)
          const dLat = (cornerLat - pg.cLat) * 111320
          // Project onto slope direction
          const distAlongSlope = dLng * slopeEast + dLat * slopeNorth
          // Height offset = distance along slope × tan(pitch)
          const heightOffset = -distAlongSlope * Math.tan(pitchRad)
          return centerH + heightOffset
        })

        // Build positions with per-corner heights
        const coordsWithH = []
        pg.corners.forEach(([cornerLng, cornerLat], c) => {
          coordsWithH.push(cornerLng, cornerLat, cornerHeights[c])
        })
        const positions = Cesium.Cartesian3.fromDegreesArrayHeights(coordsWithH)

        // --- Panel fill: dark blue-black like real solar panels ---
        const entity = viewer.entities.add({
          polygon: {
            hierarchy: { positions },
            material: Cesium.Color.fromCssColorString('#0d1b2a').withAlpha(0.92),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString('#90caf9').withAlpha(0.95),
            outlineWidth: 2,
            perPositionHeight: true,
          },
          description: pg.tooltipText,
          properties: {
            panelNum: pg.i + 1,
            wattage: pg.wattage,
            faceName: pg.faceName,
            row: pg.row,
            col: pg.col,
          },
        })
        panelEntitiesRef.current.push(entity)

        // --- Cell grid lines (like OpenSolar) ---
        // Draw internal grid: ~6 columns × ~10 rows on portrait panel
        const CELL_COLS = 6
        const CELL_ROWS = 10
        const c0 = pg.corners[0] // TL
        const c1 = pg.corners[1] // TR
        const c2 = pg.corners[2] // BR
        const c3 = pg.corners[3] // BL
        const h0 = cornerHeights[0], h1 = cornerHeights[1], h2 = cornerHeights[2], h3 = cornerHeights[3]

        // Helper: interpolate between two [lng,lat,h] points
        const lerp3 = (aLng, aLat, aH, bLng, bLat, bH, t) => [
          aLng + (bLng - aLng) * t,
          aLat + (bLat - aLat) * t,
          aH + (bH - aH) * t,
        ]

        // Vertical cell lines (columns)
        for (let col = 1; col < CELL_COLS; col++) {
          const t = col / CELL_COLS
          const [topLng, topLat, topH] = lerp3(c0[0], c0[1], h0, c1[0], c1[1], h1, t)
          const [botLng, botLat, botH] = lerp3(c3[0], c3[1], h3, c2[0], c2[1], h2, t)
          const gridLine = viewer.entities.add({
            polyline: {
              positions: Cesium.Cartesian3.fromDegreesArrayHeights([
                topLng, topLat, topH, botLng, botLat, botH,
              ]),
              width: 1,
              material: Cesium.Color.fromCssColorString('#546e7a').withAlpha(0.5),
            },
          })
          panelEntitiesRef.current.push(gridLine)
        }

        // Horizontal cell lines (rows)
        for (let row = 1; row < CELL_ROWS; row++) {
          const t = row / CELL_ROWS
          const [leftLng, leftLat, leftH] = lerp3(c0[0], c0[1], h0, c3[0], c3[1], h3, t)
          const [rightLng, rightLat, rightH] = lerp3(c1[0], c1[1], h1, c2[0], c2[1], h2, t)
          const gridLine = viewer.entities.add({
            polyline: {
              positions: Cesium.Cartesian3.fromDegreesArrayHeights([
                leftLng, leftLat, leftH, rightLng, rightLat, rightH,
              ]),
              width: 1,
              material: Cesium.Color.fromCssColorString('#546e7a').withAlpha(0.5),
            },
          })
          panelEntitiesRef.current.push(gridLine)
        }
      })
    })()

    // Billboard label near roof center showing panel count and system size
    if (allLats.length > 0) {
      const centerLat = allLats.reduce((a, b) => a + b, 0) / allLats.length
      const centerLng = allLngs.reduce((a, b) => a + b, 0) / allLngs.length
      const totalKwLabel = ((selectedPanels.length * (panelCapacityW || 400)) / 1000).toFixed(2)
      const labelEntity = viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(centerLng, centerLat),
        label: {
          text: `${selectedPanels.length} panels | ${totalKwLabel} kW`,
          font: '14px sans-serif',
          fillColor: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(0, -10),
          heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      })
      panelEntitiesRef.current.push(labelEntity)
    }

    // Fallback outline only when GeoTIFF roof geometry is unavailable.
    if (!hasRoofGeometry && segments.length === 0 && allLats.length >= 3) {
      const pad = 0.000015
      const bboxCoords = [
        Math.min(...allLngs) - pad, Math.min(...allLats) - pad,
        Math.max(...allLngs) + pad, Math.min(...allLats) - pad,
        Math.max(...allLngs) + pad, Math.max(...allLats) + pad,
        Math.min(...allLngs) - pad, Math.max(...allLats) + pad,
        Math.min(...allLngs) - pad, Math.min(...allLats) - pad,
      ]
      const outlineEntity = viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(bboxCoords),
          width: 3,
          material: Cesium.Color.fromCssColorString('#00bcd4').withAlpha(0.85),
          clampToGround: true,
        },
      })
      outlineEntitiesRef.current.push(outlineEntity)
    }
  }, [panels, panelCount, segments, panelDimensions, dsmHeights, roofGeometry, lat, lng, loading])

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

    // Orbit around building center
    const orbitGroundH = dsmHeights?.building?.ground_elevation_m || 300
    const targetPos = Cesium.Cartesian3.fromDegrees(lng, lat, orbitGroundH)

    orbitListenerRef.current = viewer.scene.postRender.addEventListener(() => {
      if (!isOrbitingRef.current) return
      orbitHeadingRef.current += 0.003 // radians per frame (~10°/sec at 60fps)
      viewer.camera.lookAt(
        targetPos,
        new Cesium.HeadingPitchRange(
          orbitHeadingRef.current,
          Cesium.Math.toRadians(-35),
          40 // distance in meters — matches OpenSolar close-up
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

        {/* Roof controls — top right */}
        {!loading && !error && (
          <div className="absolute top-2 right-2 flex items-center gap-2">
            <button
              onClick={() => focusRoof()}
              className="bg-black/65 text-white hover:bg-black/80 px-2 py-1 text-xs font-medium rounded transition-colors"
              title="Reset the camera to the roof-focused design view"
            >
              ⌖ Focus
            </button>
            <button
              onClick={toggleOrbit}
              className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                isOrbiting
                  ? 'bg-solar-600 text-white'
                  : 'bg-black/65 text-white hover:bg-black/80'
              }`}
              title={isOrbiting ? 'Stop orbit (or click/drag map)' : 'Auto-orbit around building'}
            >
              {isOrbiting ? '⏸ Stop' : '⟳ Orbit'}
            </button>
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
              <div className="text-gray-500 text-xs mt-2">Use 2D Satellite view for panel editing.</div>
            </div>
          </div>
        )}

        {!loading && !error && (
          <div className="absolute bottom-2 left-2 bg-black/60 text-white text-[10px] px-2 py-1 rounded">
            Drag to rotate · Scroll to zoom · Right-drag to pan
          </div>
        )}

        {/* Compass rose — like OpenSolar */}
        {!loading && !error && (
          <div className="absolute bottom-16 right-3 w-12 h-12 pointer-events-none">
            <svg viewBox="0 0 48 48" className="w-full h-full drop-shadow-lg">
              <circle cx="24" cy="24" r="22" fill="rgba(0,0,0,0.5)" stroke="rgba(255,255,255,0.3)" strokeWidth="1" />
              {/* N arrow (red) */}
              <polygon points="24,4 20,22 24,19 28,22" fill="#e53935" />
              {/* S arrow (white) */}
              <polygon points="24,44 20,26 24,29 28,26" fill="rgba(255,255,255,0.6)" />
              {/* E/W ticks */}
              <line x1="42" y1="24" x2="36" y2="24" stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" />
              <line x1="6" y1="24" x2="12" y2="24" stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" />
              {/* Labels */}
              <text x="24" y="11" textAnchor="middle" fill="white" fontSize="7" fontWeight="bold">N</text>
              <text x="24" y="42" textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="6">S</text>
              <text x="40" y="26" textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="6">E</text>
              <text x="8" y="26" textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="6">W</text>
            </svg>
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

        {/* Click tooltip — panel details */}
        {clickTooltip && (
          <div
            className="absolute bg-gray-900/95 text-white text-xs rounded-lg shadow-xl border border-gray-500 p-3 min-w-[190px]"
            style={{ left: clickTooltip.x + 15, top: Math.max(8, clickTooltip.y - 10), zIndex: 50 }}
          >
            <button
              onClick={() => { setClickTooltip(null); if (clickTimerRef.current) clearTimeout(clickTimerRef.current) }}
              className="absolute top-1.5 right-2 text-gray-400 hover:text-white text-base leading-none"
              title="Close"
            >×</button>
            <div className="font-semibold text-solar-400 mb-1.5">Panel #{clickTooltip.panelNum}</div>
            <div className="text-gray-300 space-y-0.5">
              <div>{clickTooltip.wattage} W</div>
              <div>{clickTooltip.faceName}</div>
              <div>Row {clickTooltip.row}, Col {clickTooltip.col}</div>
            </div>
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
