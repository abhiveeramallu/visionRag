import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { usePolling } from '../hooks/usePolling'
import ProcessingStatus from '../components/ProcessingStatus'
import { getSource } from '../services/api'
import { FileText, Youtube, Film, Music } from 'lucide-react'

export default function Processing() {
  const { sourceId } = useParams()
  const navigate = useNavigate()
  const { status: jobStatus, error: pollError } = usePolling(sourceId, 2000)
  const [sourceInfo, setSourceInfo] = useState(null)
  const [countdown, setCountdown] = useState(5)

  useEffect(() => {
    if (sourceId) {
      getSource(sourceId)
        .then((data) => setSourceInfo(data))
        .catch(() => {})
    }
  }, [sourceId])

  // Auto navigate to chat on completion
  useEffect(() => {
    if (jobStatus?.status === 'completed') {
      const timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(timer)
            navigate(`/chat/${sourceId}`)
            return 0
          }
          return prev - 1
        })
      }, 1000)
      return () => clearInterval(timer)
    }
  }, [jobStatus, sourceId, navigate])

  return (
    <div className="max-w-2xl mx-auto space-y-6 py-4">
      {sourceInfo && (
        <div className="card p-4 flex items-center justify-between bg-primary-50/50 border-primary-100">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center text-primary-700 font-bold">
              {sourceInfo.source_type === 'youtube' ? (
                <Youtube className="w-5 h-5 text-red-600" />
              ) : sourceInfo.source_type === 'video' ? (
                <Film className="w-5 h-5 text-purple-600" />
              ) : sourceInfo.source_type === 'audio' ? (
                <Music className="w-5 h-5 text-blue-600" />
              ) : (
                <FileText className="w-5 h-5 text-green-600" />
              )}
            </div>
            <div>
              <h2 className="font-bold text-gray-900 text-sm">{sourceInfo.title || 'Educational Material'}</h2>
              <p className="text-xs text-gray-500 capitalize">
                Type: {sourceInfo.source_type} • Status: {sourceInfo.status}
              </p>
            </div>
          </div>
        </div>
      )}

      {jobStatus?.status === 'completed' && (
        <div className="p-3 rounded-xl bg-green-50 border border-green-200 text-green-800 text-xs text-center font-medium">
          Processing Complete! Auto-redirecting to AI Chat in {countdown} seconds...
        </div>
      )}

      <ProcessingStatus jobStatus={jobStatus} sourceId={sourceId} />
    </div>
  )
}
