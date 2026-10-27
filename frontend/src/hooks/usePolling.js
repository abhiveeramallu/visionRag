import { useState, useEffect, useRef, useCallback } from 'react'
import { getStatus } from '../services/api'

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'timed_out', 'cancelled'])

export function usePolling(sourceId, interval = 2000) {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const timerRef = useRef(null)
  const consecutiveErrorsRef = useRef(0)

  const resetPolling = useCallback(() => {
    setDone(false)
    setError(null)
    consecutiveErrorsRef.current = 0
  }, [])

  useEffect(() => {
    if (!sourceId || done) return

    const poll = async () => {
      try {
        const data = await getStatus(sourceId)
        consecutiveErrorsRef.current = 0
        setError(null)
        setStatus(data)

        if (TERMINAL_STATUSES.has(data.status)) {
          setDone(true)
          if (timerRef.current) clearInterval(timerRef.current)
        }
      } catch (err) {
        consecutiveErrorsRef.current += 1
        // Only surface error and stop if 5 consecutive polls fail
        if (consecutiveErrorsRef.current >= 5) {
          setError(err.message || 'Lost connection to server')
          if (timerRef.current) clearInterval(timerRef.current)
        }
      }
    }

    poll()
    timerRef.current = setInterval(poll, interval)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [sourceId, interval, done])

  const isStalled = Boolean(
    status?.is_stalled ||
    (status?.status === 'processing' && (status?.last_heartbeat_seconds_ago > 90))
  )

  return { status, error, done, isStalled, resetPolling }
}
