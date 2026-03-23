import { useState, useRef, useEffect } from 'react'

/**
 * Interactive satellite map where the user can click to pick the correct building.
 * Uses a Google Maps Static API image as the base, with a click handler that
 * converts pixel coordinates to lat/lng.
 *
 * Props:
 *   centerLat, centerLng — initial map center (from geocoding)
 *   zoom — map zoom level (default 20 for rooftop detail)
 *   onPick(lat, lng) — called when user clicks to select a location
 */
export default function MapPicker({ centerLat, centerLng, zoom = 20, onPick }) {
  const imgRef = useRef(null)
  const [pin, setPin] = useState(null) // { x, y, lat, lng }
  const [confirmed, setConfirmed] = useState(false)

  // Google Maps Static API image dimensions (640x480 @ scale 2 = 1280x960 actual,
  // but displayed at container width). We use 640x480 display size.
  const IMG_W = 640
  const IMG_H = 480

  // Meters per pixel at this zoom level and latitude
  const metersPerPx = (156543.03392 * Math.cos((centerLat * Math.PI) / 180)) / Math.pow(2, zoom)

  const handleClick = (e) => {
    if (confirmed) return
    const rect = imgRef.current.getBoundingClientRect()
    const clickX = e.clientX - rect.left
    const clickY = e.clientY - rect.top

    // Convert click position to offset from center in pixels
    const displayW = rect.width
    const displayH = rect.height
    const offsetX = (clickX - displayW / 2) / displayW * IMG_W
    const offsetY = (clickY - displayH / 2) / displayH * IMG_H

    // Convert pixel offset to lat/lng offset
    const dLng = (offsetX * metersPerPx) / (111319.5 * Math.cos((centerLat * Math.PI) / 180))
    const dLat = -(offsetY * metersPerPx) / 111319.5

    const newLat = centerLat + dLat
    const newLng = centerLng + dLng

    setPin({
      x: (clickX / displayW) * 100, // percentage for positioning
      y: (clickY / displayH) * 100,
      lat: newLat,
      lng: newLng,
    })
  }

  const handleConfirm = () => {
    if (pin) {
      setConfirmed(true)
      onPick(pin.lat, pin.lng)
    }
  }

  // Build satellite image URL
  const satUrl = `/api/address/satellite?lat=${centerLat}&lng=${centerLng}&zoom=${zoom}`

  return (
    <div className="space-y-3">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-blue-800 text-sm font-medium">
        Click on the correct building in the satellite view below to set the location.
      </div>

      <div
        className="relative cursor-crosshair rounded-lg overflow-hidden border border-gray-300 shadow-sm"
        onClick={handleClick}
        style={{ maxWidth: '100%' }}
      >
        <img
          ref={imgRef}
          src={satUrl}
          alt="Satellite view — click to select building"
          className="w-full"
          draggable={false}
        />

        {/* Pin marker */}
        {pin && (
          <div
            className="absolute pointer-events-none"
            style={{
              left: `${pin.x}%`,
              top: `${pin.y}%`,
              transform: 'translate(-50%, -100%)',
            }}
          >
            <div className="flex flex-col items-center">
              <svg width="30" height="40" viewBox="0 0 30 40">
                <path d="M15 0C6.7 0 0 6.7 0 15c0 11.3 15 25 15 25s15-13.7 15-25C30 6.7 23.3 0 15 0z" fill="#dc2626" stroke="#991b1b" strokeWidth="1"/>
                <circle cx="15" cy="14" r="6" fill="white"/>
              </svg>
            </div>
          </div>
        )}

        {/* Original center crosshair (faint) */}
        <div
          className="absolute pointer-events-none opacity-30"
          style={{ left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }}
        >
          <div className="w-6 h-6 border-2 border-yellow-400 rounded-full"></div>
        </div>
      </div>

      {pin && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">
            Selected: {pin.lat.toFixed(6)}, {pin.lng.toFixed(6)}
          </span>
          {!confirmed ? (
            <button
              onClick={handleConfirm}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
            >
              Confirm This Location
            </button>
          ) : (
            <span className="text-green-600 text-sm font-medium">Location confirmed</span>
          )}
        </div>
      )}

      {!pin && (
        <p className="text-xs text-gray-500 text-center">
          Yellow circle shows the original geocoded position. Click on the correct building to move the pin.
        </p>
      )}
    </div>
  )
}
