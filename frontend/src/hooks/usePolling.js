import { useState, useEffect, useRef } from 'react'
import { getStatus } from '../services/api'

export function usePolling(sourceId, interval = 2000) {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => {
    if (!sourceId || done) return

    const poll = async () => {
      try {
        const data = await getStatus(sourceId)
        setStatus(data)
        if (data.status === 'completed' || data.status === 'failed') {
          setDone(true)
          if (timerRef.current) clearInterval(timerRef.current)
        }
      } catch (err) {
        setError(err.message)
        if (timerRef.current) clearInterval(timerRef.current)
      }
    }

    poll()
    timerRef.current = setInterval(poll, interval)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [sourceId, interval, done])

  return { status, error, done }
}
