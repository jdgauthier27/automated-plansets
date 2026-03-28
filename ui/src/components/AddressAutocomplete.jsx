import { useState, useEffect, useRef } from 'react'

/**
 * Google Places Autocomplete input for address entry.
 * Loads the Google Maps Places library and attaches autocomplete to the input.
 * Returns the selected place's address, lat, and lng.
 * Gracefully degrades to a plain text input if no API key or script fails.
 */
export default function AddressAutocomplete({ value, onChange, apiKey, placeholder }) {
  const inputRef = useRef(null)
  const autocompleteRef = useRef(null)
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // Load Google Maps Places library
  useEffect(() => {
    if (!apiKey) {
      setLoadError(true)
      return
    }
    if (window.google?.maps?.places) {
      setLoaded(true)
      return
    }

    // Check if script is already loading
    if (document.querySelector('script[src*="maps.googleapis.com/maps/api/js"]')) {
      // Wait for it to load
      let elapsed = 0
      const check = setInterval(() => {
        elapsed += 200
        if (window.google?.maps?.places) {
          setLoaded(true)
          clearInterval(check)
        } else if (elapsed > 10000) {
          setLoadError(true)
          clearInterval(check)
        }
      }, 200)
      return () => clearInterval(check)
    }

    const script = document.createElement('script')
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places,geometry`
    script.async = true
    script.onload = () => {
      if (window.google?.maps?.places) {
        setLoaded(true)
      } else {
        setLoadError(true)
      }
    }
    script.onerror = () => setLoadError(true)
    document.head.appendChild(script)
  }, [apiKey])

  // Attach autocomplete to input
  useEffect(() => {
    if (!loaded || !inputRef.current || autocompleteRef.current) return

    try {
      const autocomplete = new window.google.maps.places.Autocomplete(inputRef.current, {
        types: ['address'],
        fields: ['formatted_address', 'geometry', 'address_components'],
      })

      autocomplete.addListener('place_changed', () => {
        const place = autocomplete.getPlace()
        if (place.geometry) {
          const lat = place.geometry.location.lat()
          const lng = place.geometry.location.lng()
          onChange({
            address: place.formatted_address || value,
            latitude: lat,
            longitude: lng,
            addressConfirmed: false,
            streetViewB64: null,
            satelliteB64: null,
            placeSelected: true,
          })
        }
      })

      autocompleteRef.current = autocomplete
    } catch {
      setLoadError(true)
    }
  }, [loaded])

  return (
    <div className="flex-1">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={e => onChange({
          address: e.target.value,
          addressConfirmed: false,
          streetViewB64: null,
          satelliteB64: null,
          latitude: 0,
          longitude: 0,
          placeSelected: false,
        })}
        placeholder={placeholder || "Start typing an address..."}
        className="w-full border border-gray-300 rounded-lg px-3 py-2"
        autoComplete="off"
        data-testid="address-input"
      />
      {loadError && (
        <p className="text-xs text-amber-600 mt-1">
          Address suggestions unavailable — type the full address manually and click Verify.
        </p>
      )}
    </div>
  )
}
