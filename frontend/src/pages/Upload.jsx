import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Youtube, Upload as UploadIcon, AlertCircle } from 'lucide-react'
import YouTubeInput from '../components/YouTubeInput'
import FileUpload from '../components/FileUpload'
import { ingestYouTube, uploadFile } from '../services/api'

export default function Upload() {
  const [activeTab, setActiveTab] = useState('youtube') // 'youtube' | 'file'
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleYouTubeSubmit = async (url, title) => {
    setLoading(true)
    setError('')
    try {
      const res = await ingestYouTube(url, title)
      if (res.source_id) {
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
        navigate(`/processing/${res.source_id}`)
      }
    } catch (err) {
      setError(err.message || 'Failed to upload file')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 py-4">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-extrabold text-gray-900">Upload Educational Material</h1>
        <p className="text-sm text-gray-600">
          Provide a YouTube URL or upload video, audio, PDF, PPT, or images to begin indexing.
        </p>
      </div>

      {/* Tabs */}
      <div className="card p-2 bg-gray-100 flex space-x-2 rounded-xl">
        <button
          onClick={() => { setActiveTab('youtube'); setError('') }}
          className={`flex-1 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center space-x-2 transition-all ${
            activeTab === 'youtube'
              ? 'bg-white text-gray-900 shadow-xs'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Youtube className="w-4 h-4 text-red-600" />
          <span>YouTube Video URL</span>
        </button>

        <button
          onClick={() => { setActiveTab('file'); setError('') }}
          className={`flex-1 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center space-x-2 transition-all ${
            activeTab === 'file'
              ? 'bg-white text-gray-900 shadow-xs'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <UploadIcon className="w-4 h-4 text-primary-600" />
          <span>Upload File (Video / PDF / Audio)</span>
        </button>
      </div>

      {/* Form Content */}
      <div className="card p-6 shadow-sm border-gray-200">
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs flex items-center space-x-2">
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

      <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-500 space-y-1">
        <p className="font-semibold text-gray-700">📌 Processing Pipeline Note:</p>
        <p>
          Uploaded files are processed asynchronously using background workers (FFmpeg, WhisperX, PaddleOCR, Qdrant). You will be redirected to the status monitor automatically.
        </p>
      </div>
    </div>
  )
}
