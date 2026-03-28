import { useState } from 'react'
import MapPicker from './MapPicker'
import AddressAutocomplete from './AddressAutocomplete'

function Spinner({ className = 'w-4 h-4' }) {
  return (
    <div className={`${className} border-2 border-current border-t-transparent rounded-full animate-spin`} />
  )
}

export default function AddressConfirm({ address, streetViewB64, confirmed, latitude, longitude, satelliteB64, apiKey, onUpdate }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [manualMode, setManualMode] = useState(false)
  const [mapPickerMode, setMapPickerMode] = useState(false)
  const [geocodedLat, setGeocodedLat] = useState(0)
  const [geocodedLng, setGeocodedLng] = useState(0)

  const handleValidate = async () => {
    if (!address || address.length < 5) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/address/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address }),
      })
      const data = await res.json()
      if (res.ok) {
        setGeocodedLat(data.lat)
        setGeocodedLng(data.lng)
        onUpdate({
          latitude: data.lat,
          longitude: data.lng,
          address: data.formatted_address || address,
          streetViewB64: data.street_view_b64,
          satelliteB64: data.satellite_b64,
          addressConfirmed: false,
        })
      } else {
        setError(data.detail || 'Geocoding failed — you can try again or enter coordinates manually.')
      }
    } catch (e) {
      setError('Could not reach verification service. Check your connection and try again, or enter coordinates manually.')
    }
    setLoading(false)
  }

  const handleManualConfirm = () => {
    onUpdate({ addressConfirmed: true })
    setManualMode(false)
  }

  const handleTryDifferentAddress = () => {
    onUpdate({
      streetViewB64: null,
      satelliteB64: null,
      addressConfirmed: false,
      address: '',
      latitude: 0,
      longitude: 0,
    })
    setMapPickerMode(false)
    setError(null)
  }

  const hasImages = streetViewB64 || satelliteB64

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Project Address</h2>
      <p className="text-sm text-gray-500">
        Enter the project address and verify it to confirm the correct building before proceeding.
      </p>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Street Address</label>
        <div className="flex gap-2">
          <AddressAutocomplete
            value={address}
            onChange={onUpdate}
            apiKey={apiKey}
            placeholder="Start typing an address..."
          />
          <button
            onClick={handleValidate}
            disabled={loading || address.length < 5}
            className="px-4 py-2 bg-solar-600 hover:bg-solar-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap flex items-center gap-2"
          >
            {loading && <Spinner />}
            {loading ? 'Verifying...' : 'Verify Address'}
          </button>
        </div>
      </div>

      {/* Loading indicator */}
      {loading && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-blue-800 text-sm flex items-center gap-2">
          <Spinner className="w-4 h-4 text-blue-600" />
          Looking up address and fetching Street View and satellite images...
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-2">
          <p className="text-red-800 text-sm font-medium">{error}</p>
          <div className="flex gap-2">
            <button
              onClick={handleValidate}
              disabled={address.length < 5}
              className="text-sm px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg font-medium"
            >
              Retry
            </button>
            {!manualMode && (
              <button
                onClick={() => setManualMode(true)}
                className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium"
              >
                Enter coordinates manually
              </button>
            )}
          </div>
        </div>
      )}

      {/* Street View + Satellite confirmation */}
      {hasImages && !confirmed && !loading && (
        <div className="space-y-3">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-blue-800 text-sm font-medium">
            Is this the correct building? Confirm to proceed or try a different address.
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Street View */}
            {streetViewB64 && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1 uppercase tracking-wider">
                  Street View — Building
                </label>
                <img
                  src={`data:image/jpeg;base64,${streetViewB64}`}
                  alt="Street View of the property"
                  className="w-full rounded-lg border border-gray-200 shadow-sm"
                />
              </div>
            )}

            {/* Satellite / Map Overview */}
            {satelliteB64 && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1 uppercase tracking-wider">
                  Map Overview — Location & Roof
                </label>
                <img
                  src={`data:image/jpeg;base64,${satelliteB64}`}
                  alt="Satellite view of the property"
                  className="w-full rounded-lg border border-gray-200 shadow-sm"
                />
              </div>
            )}
          </div>

          {latitude !== 0 && (
            <div className="text-xs text-gray-400 text-center">
              Coordinates: {latitude.toFixed(6)}, {longitude.toFixed(6)}
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={() => onUpdate({ addressConfirmed: true })}
              className="flex-1 bg-green-600 hover:bg-green-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium"
            >
              Confirm — Correct Building
            </button>
            <button
              onClick={() => {
                setMapPickerMode(true)
                onUpdate({ streetViewB64: null, satelliteB64: null, addressConfirmed: false })
              }}
              className="px-4 py-2.5 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-lg text-sm font-medium"
            >
              Pick on Map
            </button>
            <button
              onClick={handleTryDifferentAddress}
              className="px-4 py-2.5 bg-gray-50 hover:bg-gray-100 text-gray-600 border border-gray-200 rounded-lg text-sm font-medium"
            >
              Try Different Address
            </button>
          </div>
        </div>
      )}

      {/* Interactive map picker — shown when user says "wrong building" */}
      {mapPickerMode && !confirmed && geocodedLat !== 0 && (
        <div className="space-y-2">
          <MapPicker
            centerLat={geocodedLat}
            centerLng={geocodedLng}
            zoom={20}
            onPick={(lat, lng) => {
              onUpdate({ latitude: lat, longitude: lng, addressConfirmed: true })
              setMapPickerMode(false)
            }}
          />
          <button
            onClick={() => {
              setMapPickerMode(false)
              handleValidate()
            }}
            className="text-sm text-gray-500 hover:text-gray-700 underline"
          >
            &larr; Back to address verification
          </button>
        </div>
      )}

      {/* Manual coordinate entry — fallback option */}
      {manualMode && !confirmed && !mapPickerMode && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-700">Manual Location Entry</p>
            <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">Fallback</span>
          </div>
          <p className="text-xs text-gray-500">Enter the exact coordinates if address lookup is unavailable.</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Latitude</label>
              <input
                type="number" step="0.0001"
                value={latitude || ''}
                onChange={e => onUpdate({ latitude: parseFloat(e.target.value) || 0 })}
                placeholder="45.4628"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Longitude</label>
              <input
                type="number" step="0.0001"
                value={longitude || ''}
                onChange={e => onUpdate({ longitude: parseFloat(e.target.value) || 0 })}
                placeholder="-75.7618"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleManualConfirm}
              disabled={!latitude || !longitude}
              className="flex-1 bg-solar-600 hover:bg-solar-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Confirm Location Manually
            </button>
            <button
              onClick={() => setManualMode(false)}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-sm font-medium"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Prompt to verify */}
      {!hasImages && !loading && !confirmed && !manualMode && !error && address.length > 5 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-amber-800 text-sm">
          Click "Verify Address" to confirm the correct building via Street View and satellite map before proceeding.
        </div>
      )}

      {/* Confirmed */}
      {confirmed && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-green-800 text-sm flex items-center gap-2">
          <span className="text-green-600 text-lg">&#10003;</span>
          <span>Address and building confirmed{latitude ? ` (${latitude.toFixed(4)}, ${longitude.toFixed(4)})` : ''}</span>
        </div>
      )}
    </div>
  )
}
