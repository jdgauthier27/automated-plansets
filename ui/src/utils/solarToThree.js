/**
 * solarToThree.js — Solar API → THREE.js coordinate transform
 *
 * Converts Google Solar API roof data (lat, lng, pitch, azimuth, elevation)
 * into correct THREE.js mesh position + rotation for ThreeJSOverlayView
 * with upAxis='Y'.
 *
 * Coordinate system (ThreeJSOverlayView, upAxis='Y'):
 *   +Y = up (altitude)
 *   +X = east
 *   -Z = north
 *   +Z = south
 *
 * Reference: googlemaps-samples/js-solar-potential (Google's official impl)
 */

import { PlaneGeometry, MeshBasicMaterial, Mesh, DoubleSide } from 'three'

const DEG2RAD = Math.PI / 180

/**
 * Transform Solar API roof segment data into THREE.js position + rotation.
 *
 * @param {object} overlay - ThreeJSOverlayView instance
 * @param {object} params
 * @param {number} params.lat - Panel center latitude
 * @param {number} params.lng - Panel center longitude
 * @param {number} params.altitudeAboveGround - Height above ground in meters
 * @param {number} params.pitchDeg - Roof pitch in degrees (0 = flat, 90 = vertical)
 * @param {number} params.azimuthDeg - Compass bearing the roof faces (0=N, 90=E, 180=S, 270=W)
 * @param {number} params.widthM - Panel width in meters
 * @param {number} params.heightM - Panel height in meters
 * @returns {{ position: Vector3, rotation: { x: number, y: number, z: number, order: string } }}
 */
export function solarToThreeTransform(overlay, {
  lat, lng,
  altitudeAboveGround = 7,
  pitchDeg = 15,
  azimuthDeg = 180,
  widthM = 1.045,
  heightM = 1.879,
}) {
  // ── Step 1: Convert lat/lng/altitude → local THREE.js Vector3 ──
  // ThreeJSOverlayView handles all WGS84 → local Cartesian math internally.
  // altitude = meters above ground (since anchor.altitude = 0)
  const position = overlay.latLngAltitudeToVector3({
    lat,
    lng,
    altitude: altitudeAboveGround,
  })

  console.log('[solarToThree] ── RAW INPUT ──')
  console.log(`  lat=${lat}, lng=${lng}`)
  console.log(`  altitudeAboveGround=${altitudeAboveGround}m`)
  console.log(`  pitch=${pitchDeg}°, azimuth=${azimuthDeg}°`)
  console.log(`  panel size=${widthM}m × ${heightM}m`)

  console.log('[solarToThree] ── POSITION (local coords) ──')
  console.log(`  x=${position.x.toFixed(4)}, y=${position.y.toFixed(4)}, z=${position.z.toFixed(4)}`)

  // ── Step 2: Compute rotation ──
  //
  // PlaneGeometry default: lies in XY plane, normal = +Z
  // With upAxis='Y', we need the panel to:
  //   1. Lay flat (normal → +Y) by rotating -90° around X
  //   2. Rotate to face the correct compass direction (around Y)
  //   3. Tilt by roof pitch (around the local X axis after azimuth)
  //
  // Euler order MUST be 'YXZ' so azimuth (Y) applies first,
  // then pitch+flat (X), then nothing on Z.
  //
  // Azimuth math (Y rotation):
  //   After laying flat, the panel's "downslope" direction points +Z (south).
  //   To rotate it to face azimuthDeg:
  //     azimuth 180° (S) → Y rotation = 0°     (+Z stays +Z)
  //     azimuth 270° (W) → Y rotation = -90°   (+Z → -X)
  //     azimuth   0° (N) → Y rotation = 180°   (+Z → -Z)
  //     azimuth  90° (E) → Y rotation = 90°    (+Z → +X)
  //   Formula: rotY = -(azimuthDeg - 180) * DEG2RAD

  const rotY = -(azimuthDeg - 180) * DEG2RAD
  const rotX = -Math.PI / 2 + pitchDeg * DEG2RAD  // lay flat + tilt by pitch
  const rotZ = 0

  console.log('[solarToThree] ── ROTATION ──')
  console.log(`  Euler order: YXZ`)
  console.log(`  rotX=${(rotX / DEG2RAD).toFixed(2)}° (flat + pitch)`)
  console.log(`  rotY=${(rotY / DEG2RAD).toFixed(2)}° (azimuth)`)
  console.log(`  rotZ=0°`)

  return {
    position,
    rotation: { x: rotX, y: rotY, z: rotZ, order: 'YXZ' },
  }
}


/**
 * Create a single red test square on the roof.
 * This is the "Mission 1" diagnostic — one 2×2m red square that should
 * sit perfectly flush on the target roof plane.
 *
 * @param {object} overlay - ThreeJSOverlayView instance
 * @param {object} roofSegment - Solar API roof segment data
 * @param {number} roofSegment.center.latitude
 * @param {number} roofSegment.center.longitude
 * @param {number} roofSegment.pitch_deg
 * @param {number} roofSegment.azimuth_deg
 * @param {number} roofSegment.height_m - planeHeightAtCenterMeters from API
 * @param {number} [groundElevation] - Ground elevation for altitude calc
 * @returns {Mesh} The red square mesh (already added to overlay.scene)
 */
export function createRedSquareTest(overlay, roofSegment, groundElevation = 0) {
  console.log('═══════════════════════════════════════════════════')
  console.log('[RED SQUARE TEST] Starting "Mission 1" diagnostic')
  console.log('═══════════════════════════════════════════════════')

  console.log('[RED SQUARE TEST] ── RAW SOLAR API SEGMENT ──')
  console.log(JSON.stringify(roofSegment, null, 2))

  const lat = roofSegment.center?.latitude || roofSegment.center?.lat
  const lng = roofSegment.center?.longitude || roofSegment.center?.lng
  const pitchDeg = roofSegment.pitch_deg ?? roofSegment.pitchDegrees ?? 15
  const azimuthDeg = roofSegment.azimuth_deg ?? roofSegment.azimuthDegrees ?? 180
  const heightM = roofSegment.height_m ?? roofSegment.planeHeightAtCenterMeters ?? 7

  if (!lat || !lng) {
    console.error('[RED SQUARE TEST] FATAL: No lat/lng in segment center!')
    return null
  }

  // Altitude above ground from Solar API's planeHeightAtCenterMeters.
  // This value is ABSOLUTE MSL elevation — must subtract ground elevation
  // to get height above ground for ThreeJSOverlayView (where anchor altitude=0
  // means ground level).
  let altAboveGround
  if (groundElevation > 0 && heightM > 100) {
    // Both are absolute MSL — subtract to get above-ground
    altAboveGround = heightM - groundElevation
    console.log(`[RED SQUARE TEST] MSL→relative: ${heightM.toFixed(1)}m - ${groundElevation.toFixed(1)}m = ${altAboveGround.toFixed(2)}m above ground`)
  } else if (heightM < 30) {
    // Small value — likely already relative to ground
    altAboveGround = heightM
    console.log(`[RED SQUARE TEST] height_m=${heightM.toFixed(1)}m appears relative, using as-is`)
  } else {
    // No ground elevation available — use rough estimate
    altAboveGround = 7
    console.log(`[RED SQUARE TEST] No ground elevation, fallback to 7m`)
  }

  console.log(`[RED SQUARE TEST] Using altitude=${altAboveGround.toFixed(2)}m above ground`)

  // ── Create the red square ──
  const SQUARE_SIZE = 2 // 2×2 meters

  const { position, rotation } = solarToThreeTransform(overlay, {
    lat,
    lng,
    altitudeAboveGround: altAboveGround,
    pitchDeg,
    azimuthDeg,
    widthM: SQUARE_SIZE,
    heightM: SQUARE_SIZE,
  })

  const geometry = new PlaneGeometry(SQUARE_SIZE, SQUARE_SIZE)
  const material = new MeshBasicMaterial({
    color: 0xff0000,
    side: DoubleSide,
    transparent: true,
    opacity: 0.85,
    depthTest: true,
  })

  const mesh = new Mesh(geometry, material)
  mesh.position.copy(position)
  mesh.rotation.order = rotation.order
  mesh.rotation.x = rotation.x
  mesh.rotation.y = rotation.y
  mesh.rotation.z = rotation.z

  console.log('[RED SQUARE TEST] ── FINAL MESH STATE ──')
  console.log(`  position: (${mesh.position.x.toFixed(4)}, ${mesh.position.y.toFixed(4)}, ${mesh.position.z.toFixed(4)})`)
  console.log(`  rotation: order=${mesh.rotation.order}, x=${(mesh.rotation.x/DEG2RAD).toFixed(2)}°, y=${(mesh.rotation.y/DEG2RAD).toFixed(2)}°, z=${(mesh.rotation.z/DEG2RAD).toFixed(2)}°`)
  console.log(`  geometry: ${SQUARE_SIZE}m × ${SQUARE_SIZE}m PlaneGeometry`)
  console.log(`  material: RED, double-sided, 85% opacity`)

  overlay.scene.add(mesh)
  overlay.requestRedraw()

  console.log('[RED SQUARE TEST] ✓ Red square added to scene')
  console.log('═══════════════════════════════════════════════════')

  return mesh
}
