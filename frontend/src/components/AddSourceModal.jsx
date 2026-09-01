import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, Youtube, Upload as UploadIcon, AlertCircle } from 'lucide-react'
import YouTubeInput from './YouTubeInput'
import FileUpload from './FileUpload'
import { ingestYouTube, uploadFile } from '../services/api'

export default function AddSourceModal({ open, onClose }) {
  const [activeTab, setActiveTab] = useState('youtube')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) {
      setError('')
      setLoading(false)
      setProgress(0)
    }
  }, [open])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    if (open) document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const handleYouTubeSubmit = async (url, title) => {
    setLoading(true)
    setError('')
    try {
      const res = await ingestYouTube(url, title)
      if (res.source_id) {
        onClose()
        navigate(`/processing/${res.source_id}`)
      }
    } catch (err) {
      setError(err.message || 'Failed to submit YouTube video')
    } finally {
      setLoading(false)
    }
  }

  const handleFileSubmit = async (file) => {
    setLoading(true)
    setError('')
    setProgress(0)
    try {
      const res = await uploadFile(file, (p) => setProgress(p))
      if (res.source_id) {
        onClose()
        navigate(`/processing/${res.source_id}`)
      }
    } catch (err) {
      setError(err.message || 'Failed to upload file')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-base font-bold text-ink-900">Add Learning Material</h2>
            <p className="text-xs text-ink-500 mt-0.5">YouTube, video, audio, PDF, PPT/PPTX, or image</p>
          </div>
          <button onClick={onClose} className="p-1.5 text-ink-400 hover:text-ink-700 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div className="card p-1.5 bg-gray-100 flex gap-1.5 rounded-xl border-0 shadow-none">
            <button
              onClick={() => { setActiveTab('youtube'); setError('') }}
              className={`flex-1 py-2 rounded-lg text-sm font-semibold flex items-center justify-center gap-1.5 transition-all ${
                activeTab === 'youtube' ? 'bg-white text-ink-900 shadow-xs' : 'text-ink-500 hover:text-ink-900'
              }`}
            >
              <Youtube className="w-4 h-4 text-red-600" />
              YouTube URL
            </button>
            <button
              onClick={() => { setActiveTab('file'); setError('') }}
              className={`flex-1 py-2 rounded-lg text-sm font-semibold flex items-center justify-center gap-1.5 transition-all ${
                activeTab === 'file' ? 'bg-white text-ink-900 shadow-xs' : 'text-ink-500 hover:text-ink-900'
              }`}
            >
              <UploadIcon className="w-4 h-4 text-primary-600" />
              Upload File
            </button>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-500" />
              <span>{error}</span>
            </div>
          )}

          {activeTab === 'youtube' ? (
            <YouTubeInput onSubmit={handleYouTubeSubmit} isLoading={loading} />
          ) : (
            <FileUpload onFile={handleFileSubmit} isUploading={loading} progress={progress} error={error} />
          )}
        </div>
      </div>
    </div>
  )
}
