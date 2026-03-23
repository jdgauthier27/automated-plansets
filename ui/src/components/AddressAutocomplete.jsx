import { useState, useEffect, useRef } from 'react'

/**
 * Google Places Autocomplete input for address entry.
 * Loads the Google Maps Places library and attaches autocomplete to the input.
 * Returns the selected place's address, lat, and lng.
 */
export default function AddressAutocomplete({ value, onChange, apiKey, placeholder }) {
  const inputRef = useRef(null)
  const autocompleteRef = useRef(null)
  const [loaded, setLoaded] = useState(false)

  // Load Google Maps Places library
  useEffect(() => {
    if (!apiKey) return
    if (window.google?.maps?.places) {
      setLoaded(true)
      return
    }

    // Check if script is already loading
    if (document.querySelector('script[src*="maps.googleapis.com/maps/api/js"]')) {
      // Wait for it to load
      const check = setInterval(() => {
        if (window.google?.maps?.places) {
          setLoaded(true)
          clearInterval(check)
        }
      }, 200)
      return () => clearInterval(check)
    }

    const script = document.createElement('script')
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places,geometry`
    script.async = true
    script.onload = () => setLoaded(true)
    document.head.appendChild(script)
  }, [apiKey])

  // Attach autocomplete to input
  useEffect(() => {
    if (!loaded || !inputRef.current || autocompleteRef.current) return

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
  }, [loaded])

  return (
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
      className="flex-1 border border-gray-300 rounded-lg px-3 py-2"
      autoComplete="off"
      data-testid="address-input"
    />
  )
}
