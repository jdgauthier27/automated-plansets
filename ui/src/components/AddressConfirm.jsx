import { useState } from 'react'
import MapPicker from './MapPicker'
import AddressAutocomplete from './AddressAutocomplete'

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
        setError(data.detail || 'Geocoding failed — you can proceed with manual confirmation below.')
      }
    } catch (e) {
      setError('Could not reach verification service. You can proceed with manual confirmation below.')
    }
    setLoading(false)
  }

  const handleManualConfirm = () => {
    onUpdate({ addressConfirmed: true })
    setManualMode(false)
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
            className="px-4 py-2 bg-solar-600 hover:bg-solar-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 whitespace-nowrap"
          >
            {loading ? 'Checking...' : 'Verify Address'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-yellow-800 text-sm">
          {error}
          {!manualMode && (
            <button
              onClick={() => setManualMode(true)}
              className="ml-2 underline text-yellow-700 hover:text-yellow-900"
            >
              Enter coordinates manually
            </button>
          )}
        </div>
      )}

      {/* Street View + Satellite confirmation */}
      {hasImages && !confirmed && (
        <div className="space-y-3">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-blue-800 text-sm font-medium">
            Confirm this is the correct building and location. You must verify before proceeding.
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
              Yes, correct building & location
            </button>
            <button
              onClick={() => {
                setMapPickerMode(true)
                onUpdate({ streetViewB64: null, satelliteB64: null, addressConfirmed: false })
              }}
              className="flex-1 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 px-4 py-2.5 rounded-lg text-sm font-medium"
            >
              No, wrong building
            </button>
          </div>
        </div>
      )}

      {/* Interactive map picker — shown when user says "wrong building" */}
      {mapPickerMode && !confirmed && geocodedLat !== 0 && (
        <MapPicker
          centerLat={geocodedLat}
          centerLng={geocodedLng}
          zoom={20}
          onPick={(lat, lng) => {
            onUpdate({ latitude: lat, longitude: lng, addressConfirmed: true })
            setMapPickerMode(false)
          }}
        />
      )}

      {/* Manual coordinate entry */}
      {manualMode && !confirmed && !mapPickerMode && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
          <p className="text-sm font-medium text-gray-700">Manual Location Entry</p>
          <p className="text-xs text-gray-500">Enter the exact coordinates, or adjust the address and try verification again.</p>
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
          <button
            onClick={handleManualConfirm}
            disabled={!latitude || !longitude}
            className="w-full bg-solar-600 hover:bg-solar-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          >
            Confirm Location Manually
          </button>
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
