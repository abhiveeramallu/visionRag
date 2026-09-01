import { useState, useEffect, useRef } from 'react'

function readKey(key, initialValue) {
  try {
    const stored = window.localStorage.getItem(key)
    return stored !== null ? JSON.parse(stored) : initialValue
  } catch {
    return initialValue
  }
}

/** One-off read of a persisted key outside the hook's render lifecycle. */
export function readPersistedState(key, initialValue = null) {
  return readKey(key, initialValue)
}

/**
 * Like useState, but backed by localStorage under `key` — survives
 * navigating away and back (route components fully unmount on navigation,
 * so plain useState resets). If `key` itself changes (e.g. switching which
 * source it's tracking) the value re-syncs from that key's stored entry
 * rather than carrying over the previous key's value. Falls back silently
 * to plain in-memory state if localStorage is unavailable.
 */
export function usePersistedState(key, initialValue) {
  const [value, setValue] = useState(() => readKey(key, initialValue))
  const lastKey = useRef(key)

  useEffect(() => {
    if (lastKey.current !== key) {
      lastKey.current = key
      setValue(readKey(key, initialValue))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  useEffect(() => {
    try {
      if (value === null || value === undefined) {
        window.localStorage.removeItem(key)
      } else {
        window.localStorage.setItem(key, JSON.stringify(value))
      }
    } catch {
      // ignore — persistence is a nice-to-have, not a hard requirement
    }
  }, [key, value])

  return [value, setValue]
}
