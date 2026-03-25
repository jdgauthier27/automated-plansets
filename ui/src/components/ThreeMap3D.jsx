// ThreeMap3D — forwards to CesiumMap3D (working photorealistic 3D viewer)
// THREE.js + 3d-tiles-renderer approach needs ECEF camera engineering — future sprint
export { default } from './CesiumMap3D'

/* FUTURE: full THREE.js implementation below (disabled)
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TilesRenderer } from '3d-tiles-renderer'
import { GoogleCloudAuthPlugin } from '3d-tiles-renderer/plugins'

const DEG2RAD = Math.PI / 180
const WGS84_A = 6378137.0
const WGS84_E2 = 0.00669437999014132

function latLngToECEF(lat, lng, alt = 0) {
  const lr = lat * DEG2RAD, Lr = lng * DEG2RAD
  const sLat = Math.sin(lr), cLat = Math.cos(lr)
  const N = WGS84_A / Math.sqrt(1 - WGS84_E2 * sLat * sLat)
  return new THREE.Vector3(
    (N + alt) * cLat * Math.cos(Lr),
    (N + alt) * cLat * Math.sin(Lr),
    (N * (1 - WGS84_E2) + alt) * sLat,
  )
}

function createPanelTexture() {
  const c = document.createElement('canvas')
  c.width = 120; c.height = 200
  const ctx = c.getContext('2d')
  ctx.fillStyle = '#1e3a5f'; ctx.fillRect(0, 0, 120, 200)
  ctx.strokeStyle = 'rgba(84,110,122,0.5)'; ctx.lineWidth = 0.5
  for (let i = 1; i < 6; i++) { ctx.beginPath(); ctx.moveTo(i*20,0); ctx.lineTo(i*20,200); ctx.stroke() }
  for (let i = 1; i < 10; i++) { ctx.beginPath(); ctx.moveTo(0,i*20); ctx.lineTo(120,i*20); ctx.stroke() }
  ctx.strokeStyle = 'rgba(200,210,220,0.7)'; ctx.lineWidth = 2; ctx.strokeRect(1,1,118,198)
  const t = new THREE.CanvasTexture(c); t.needsUpdate = true; return t
}

export default function ThreeMap3D({
  lat, lng, apiKey,
  panelCount = 13, panels = [], segments = [], panelDimensions,
  dsmHeights, onPanelCountChange, onDataLoaded,
  maxPanels = 78, totalKwh = 0, carbonOffset = 0, panelCapacityW = 400,
}) {
  const containerRef = useRef(null)
  const stateRef = useRef({})
  const panelMeshesRef = useRef([])
  const animFrameRef = useRef(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isOrbiting, setIsOrbiting] = useState(false)
  const [tilesReady, setTilesReady] = useState(false)
  const [clickTooltip, setClickTooltip] = useState(null)

  useEffect(() => {
    if (panels.length > 0 || !lat || !lng) return
    fetch(`/api/solar/building?lat=${lat}&lng=${lng}`)
      .then(r => r.json())
      .then(data => { if (onDataLoaded) onDataLoaded(data) })
      .catch(() => {})
  }, [lat, lng])

  useEffect(() => {
    if (!containerRef.current || !lat || !lng || !apiKey) return

    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    const prev = stateRef.current
    if (prev.tiles) prev.tiles.dispose()
    if (prev.controls) prev.controls?.dispose()
    if (prev.renderer) { prev.renderer.dispose(); prev.renderer.domElement.remove() }

    setLoading(true); setError(null); setTilesReady(false)

    const container = containerRef.current
    const W = container.clientWidth, H = 450

    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#87CEEB')
    const camera = new THREE.PerspectiveCamera(60, W / H, 1, 1e10)
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(W, H)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    container.appendChild(renderer.domElement)

    scene.add(new THREE.AmbientLight(0xffffff, 0.7))
    const sun = new THREE.DirectionalLight(0xffffff, 0.8)
    sun.position.set(50, 80, 30)
    scene.add(sun)

    // Load tiles — keep everything in ECEF (no transform hacks)
    const tiles = new TilesRenderer('https://tile.googleapis.com/v1/3dtiles/root.json')
    tiles.registerPlugin(new GoogleCloudAuthPlugin({ apiToken: apiKey, autoRefreshToken: true }))
    tiles.errorTarget = 12
    tiles.maxDepth = 20
    scene.add(tiles.group)

    // Camera in ECEF: position 40m south + 25m up from building, looking at building
    const buildingECEF = latLngToECEF(lat, lng, 0)
    const upDir = buildingECEF.clone().normalize() // "up" at this lat/lng
    const eastDir = new THREE.Vector3(-Math.sin(lng * DEG2RAD), Math.cos(lng * DEG2RAD), 0).normalize()
    const northDir = new THREE.Vector3().crossVectors(upDir, eastDir).normalize()

    // Camera: 25m south, 10m east, 20m up from building
    const camECEF = buildingECEF.clone()
      .addScaledVector(northDir, -25)
      .addScaledVector(eastDir, 10)
      .addScaledVector(upDir, 20)

    camera.position.copy(camECEF)
    camera.up.copy(upDir)
    camera.lookAt(buildingECEF)
    camera.updateMatrixWorld(true)

    // OrbitControls with target at building center in ECEF
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.copy(buildingECEF)
    controls.enableDamping = true
    controls.dampingFactor = 0.1
    controls.minDistance = 15
    controls.maxDistance = 500
    controls.update()

    stateRef.current = { scene, camera, renderer, controls, tiles, buildingECEF, upDir, eastDir, northDir }
    window._3d = stateRef.current

    // Click handler
    const raycaster = new THREE.Raycaster()
    const mouse = new THREE.Vector2()
    renderer.domElement.addEventListener('click', (e) => {
      const rect = renderer.domElement.getBoundingClientRect()
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
      raycaster.setFromCamera(mouse, camera)
      const hits = raycaster.intersectObjects(panelMeshesRef.current, false)
      if (hits.length > 0 && hits[0].object.userData.panelData) {
        const d = hits[0].object.userData.panelData
        setClickTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, ...d })
        setTimeout(() => setClickTooltip(null), 5000)
      } else { setClickTooltip(null) }
    })

    // Wait for tiles
    let checkCount = 0
    const checkInterval = setInterval(() => {
      if (++checkCount >= 20) {
        clearInterval(checkInterval)
        setTilesReady(true)
        setLoading(false)
        console.log('[ThreeMap3D] Tiles ready')
      }
    }, 500)

    function animate() {
      animFrameRef.current = requestAnimationFrame(animate)
      if (controls) controls.update()
      camera.updateMatrixWorld(true)
      tiles.setCamera(camera)
      tiles.setResolutionFromRenderer(camera, renderer)
      tiles.update()
      renderer.render(scene, camera)
    }
    animate()

    const onResize = () => {
      const w = containerRef.current?.clientWidth || W
      camera.aspect = w / H; camera.updateProjectionMatrix()
      renderer.setSize(w, H)
    }
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      clearInterval(checkInterval)
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      tiles.dispose(); controls?.dispose(); renderer.dispose()
      renderer.domElement.remove()
    }
  }, [lat, lng, apiKey])

  // Place panels via raycasting
  useEffect(() => {
    const { scene, tiles, buildingECEF } = stateRef.current
    if (!scene || !tiles || !panels.length || !tilesReady) return

    panelMeshesRef.current.forEach(m => { scene.remove(m); m.geometry.dispose() })
    panelMeshesRef.current = []

    const selectedPanels = panels.slice(0, panelCount)
    const panelW = panelDimensions?.width ? panelDimensions.width / 1000 : 1.045
    const panelH = panelDimensions?.length ? panelDimensions.length / 1000 : 1.879

    const panelMaterial = new THREE.MeshStandardMaterial({
      map: createPanelTexture(), metalness: 0.3, roughness: 0.6, side: THREE.DoubleSide,
    })

    const raycaster = new THREE.Raycaster()
    let placed = 0

    selectedPanels.forEach((panel, i) => {
      if (!panel.lat || !panel.lng) return

      // Panel position in ECEF — ray from 100m above to 10m below
      const above = latLngToECEF(panel.lat, panel.lng, 100)
      const below = latLngToECEF(panel.lat, panel.lng, -10)
      const dir = below.clone().sub(above).normalize()
      raycaster.set(above, dir)
      raycaster.far = 200

      const hits = raycaster.intersectObject(tiles.group, true)
      if (hits.length === 0) return

      const hit = hits[0]
      const normal = hit.face.normal.clone().transformDirection(hit.object.matrixWorld).normalize()

      const geom = new THREE.PlaneGeometry(panelW, panelH)
      const mesh = new THREE.Mesh(geom, panelMaterial)
      mesh.position.copy(hit.point).addScaledVector(normal, 0.15)

      const lookTarget = hit.point.clone().add(normal)
      mesh.lookAt(lookTarget)

      const segIdx = panel.segment_index || 0
      const azimuth = segments[segIdx]?.azimuth_deg || 180
      mesh.rotateZ(-(azimuth - 180) * DEG2RAD)

      mesh.userData.panelData = {
        panelNum: i + 1, wattage: panelCapacityW || 400,
        faceName: panel.face_name || `Roof Face ${segIdx + 1}`,
        kwhPerYear: (panel.yearly_energy_kwh || 0).toFixed(0),
      }
      scene.add(mesh)
      panelMeshesRef.current.push(mesh)
      placed++
    })

    console.log(`[ThreeMap3D] Placed ${placed}/${selectedPanels.length} panels`)
  }, [panels, panelCount, segments, panelDimensions, tilesReady])

  const selectedPanels = panels.slice(0, panelCount)
  const calcTotalKwh = selectedPanels.reduce((s, p) => s + (p.yearly_energy_kwh || 0), 0) || totalKwh
  const totalKw = (panelCount * panelCapacityW) / 1000

  return (
    <div className="space-y-3">
      <div className="relative">
        <div ref={containerRef} className="w-full rounded-lg border border-gray-200 bg-gray-900" style={{ height: '450px' }} />
        {!loading && !error && (
          <div className="absolute top-2 left-2 bg-black/65 text-white rounded-lg px-3 py-2 space-y-0.5 pointer-events-none">
            <div className="text-sm font-bold text-solar-400">{panelCount} panels · {totalKw.toFixed(1)} kW</div>
            <div className="text-xs text-gray-300">{calcTotalKwh.toFixed(0)} kWh/yr estimated</div>
          </div>
        )}
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
        {clickTooltip && (
          <div className="absolute bg-gray-900/95 text-white text-xs rounded-lg shadow-xl border border-gray-500 p-3 min-w-[190px]"
            style={{ left: clickTooltip.x + 15, top: Math.max(8, clickTooltip.y - 10), zIndex: 50 }}>
            <button onClick={() => setClickTooltip(null)}
              className="absolute top-1.5 right-2 text-gray-400 hover:text-white text-base leading-none">×</button>
            <div className="font-semibold text-solar-400 mb-1.5">Panel #{clickTooltip.panelNum}</div>
            <div className="text-gray-300 space-y-0.5">
              <div>{clickTooltip.wattage} W</div>
              <div>{clickTooltip.faceName}</div>
              <div>{clickTooltip.kwhPerYear} kWh/yr</div>
            </div>
          </div>
        )}
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="font-medium text-gray-700">Panel Count</span>
            <span className="text-solar-600 font-bold">{panelCount} panels</span>
          </div>
          <input type="range" min="1" max={maxPanels} value={panelCount}
            onChange={e => onPanelCountChange?.(parseInt(e.target.value))} className="w-full accent-solar-600" />
          <div className="flex justify-between text-xs text-gray-400"><span>1</span><span>{maxPanels} max</span></div>
        </div>
        <div className="grid grid-cols-4 gap-2 text-center">
          {[
            { val: panelCount, label: 'Panels' }, { val: totalKw.toFixed(1), label: 'kW DC' },
            { val: calcTotalKwh.toFixed(0), label: 'kWh/yr' },
            { val: carbonOffset ? (calcTotalKwh * carbonOffset / 1e6).toFixed(1) : '—', label: 't CO₂/yr' },
          ].map(({ val, label }) => (
            <div key={label} className="bg-gray-50 rounded-lg p-2">
              <div className="text-lg font-bold text-gray-900">{val}</div>
              <div className="text-xs text-gray-500">{label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
*/
