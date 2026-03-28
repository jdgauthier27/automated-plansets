import { useState, useRef } from 'react'

function Spinner({ className = 'w-4 h-4' }) {
  return (
    <div className={`${className} border-2 border-current border-t-transparent rounded-full animate-spin`} />
  )
}

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
  const [imgLoading, setImgLoading] = useState(true)
  const [imgError, setImgError] = useState(false)

  // Google Maps Static API image dimensions (640x480 @ scale 2 = 1280x960 actual,
  // but displayed at container width). We use 640x480 display size.
  const IMG_W = 640
  const IMG_H = 480

  // Meters per pixel at this zoom level and latitude
  const metersPerPx = (156543.03392 * Math.cos((centerLat * Math.PI) / 180)) / Math.pow(2, zoom)

  const handleClick = (e) => {
    if (confirmed || imgLoading || imgError) return
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
        Click on the satellite image to select your building's location.
      </div>

      {/* Loading state */}
      {imgLoading && !imgError && (
        <div className="flex items-center justify-center gap-2 py-12 bg-gray-50 rounded-lg border border-gray-200">
          <Spinner className="w-5 h-5 text-gray-500" />
          <span className="text-sm text-gray-500">Loading satellite image...</span>
        </div>
      )}

      {/* Error state */}
      {imgError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center space-y-2">
          <p className="text-red-800 text-sm font-medium">Failed to load satellite image.</p>
          <p className="text-red-600 text-xs">The satellite imagery service may be temporarily unavailable.</p>
          <button
            onClick={() => { setImgError(false); setImgLoading(true) }}
            className="mt-2 text-sm px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg font-medium"
          >
            Retry
          </button>
        </div>
      )}

      <div
        className={`relative cursor-crosshair rounded-lg overflow-hidden border border-gray-300 shadow-sm ${imgLoading || imgError ? 'hidden' : ''}`}
        onClick={handleClick}
        style={{ maxWidth: '100%' }}
      >
        <img
          ref={imgRef}
          src={satUrl}
          alt="Satellite view — click to select building"
          className="w-full"
          draggable={false}
          onLoad={() => setImgLoading(false)}
          onError={() => { setImgLoading(false); setImgError(true) }}
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

      {pin && !imgError && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">
            Selected: {pin.lat.toFixed(6)}, {pin.lng.toFixed(6)}
          </span>
          {!confirmed ? (
            <button
              onClick={handleConfirm}
              className="bg-green-600 hover:bg-green-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-sm"
            >
              Confirm This Location
            </button>
          ) : (
            <span className="text-green-600 text-sm font-medium">Location confirmed</span>
          )}
        </div>
      )}

      {!pin && !imgLoading && !imgError && (
        <p className="text-xs text-gray-500 text-center">
          Yellow circle shows the original geocoded position. Click on the correct building to place the red pin.
        </p>
      )}
    </div>
  )
}
