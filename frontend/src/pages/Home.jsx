import React, { useState, useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Upload, Youtube, FileVideo, Music, FileText, Layers, Image as ImageIcon,
  ArrowRight, Loader2, AlertCircle,
} from 'lucide-react'
import { getSources, uploadFile, ingestYouTube } from '../services/api'
import { mockSources } from '../data/mockData'
import SourceCard from '../components/SourceCard'
import DemoDataBadge from '../components/DemoDataBadge'
import VerificationPipeline from '../components/VerificationPipeline'

const MAX_HOME_SOURCES = 5

const FORMATS = [
  { icon: Youtube, label: 'YouTube', color: 'text-red-600 bg-red-50' },
  { icon: FileVideo, label: 'Video', color: 'text-purple-600 bg-purple-50' },
  { icon: Music, label: 'Audio', color: 'text-blue-600 bg-blue-50' },
  { icon: FileText, label: 'PDF', color: 'text-rose-600 bg-rose-50' },
  { icon: Layers, label: 'PPT/PPTX', color: 'text-orange-600 bg-orange-50' },
  { icon: ImageIcon, label: 'Image', color: 'text-emerald-600 bg-emerald-50' },
]

function AddLearningMaterialCard() {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')

  const submitFile = async (file) => {
    setLoading(true)
    setError('')
    setProgress(0)
    try {
      const res = await uploadFile(file, (p) => setProgress(p))
      if (res.source_id) navigate(`/processing/${res.source_id}`)
    } catch (err) {
      setError(err.message || 'Failed to upload file')
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) submitFile(file)
  }

  const handleAnalyzeUrl = async (e) => {
    e.preventDefault()
    if (!youtubeUrl.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await ingestYouTube(youtubeUrl.trim())
      if (res.source_id) navigate(`/processing/${res.source_id}`)
    } catch (err) {
      setError(err.message || 'Failed to analyze YouTube URL')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-lg font-bold text-ink-900">Add Learning Material</h2>
        <div className="flex items-center gap-2 flex-wrap">
          {FORMATS.map((f) => {
            const Icon = f.icon
            return (
              <span
                key={f.label}
                className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium ${f.color}`}
              >
                <Icon className="w-3 h-3" /> {f.label}
              </span>
            )
          })}
        </div>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={(e) => { e.preventDefault(); setDragOver(false) }}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl py-12 px-6 text-center cursor-pointer transition-all ${
          dragOver ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".mp4,.mkv,.mp3,.wav,.pdf,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp"
          onChange={(e) => e.target.files?.[0] && submitFile(e.target.files[0])}
          disabled={loading}
        />
        <div className="w-12 h-12 rounded-full bg-primary-100 text-primary-600 flex items-center justify-center mx-auto mb-3">
          {loading ? <Loader2 className="w-6 h-6 animate-spin" /> : <Upload className="w-6 h-6" />}
        </div>
        <p className="font-semibold text-ink-900">
          {loading ? `Uploading... ${progress}%` : 'Drop your learning material here'}
        </p>
        <p className="text-sm text-ink-500 mt-1">or choose a file</p>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-gray-200" />
        <span className="text-xs text-ink-400 font-medium">or</span>
        <div className="flex-1 h-px bg-gray-200" />
      </div>

      <form onSubmit={handleAnalyzeUrl} className="flex gap-2">
        <input
          type="url"
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          placeholder="Paste YouTube URL..."
          disabled={loading}
          className="input flex-1"
        />
        <button
          type="submit"
          disabled={!youtubeUrl.trim() || loading}
          className="btn-primary px-5 text-sm font-semibold flex items-center gap-1.5 whitespace-nowrap"
        >
          Analyze <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}

export default function Home() {
  const [sources, setSources] = useState(null)
  const [usingDemo, setUsingDemo] = useState(false)

  useEffect(() => {
    getSources()
      .then((data) => {
        const list = data || []
        if (list.length > 0) {
          setSources(list)
        } else {
          setSources(mockSources)
          setUsingDemo(true)
        }
      })
      .catch(() => {
        setSources(mockSources)
        setUsingDemo(true)
      })
  }, [])

  return (
    <div className="space-y-8 pb-8">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-ink-900 tracking-tight">Good afternoon 👋</h1>
        <p className="text-ink-500 mt-1">Continue learning from your verified knowledge.</p>
      </div>

      <AddLearningMaterialCard />

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-ink-900 flex items-center gap-2">
            Your Learning Sources
            {usingDemo && <DemoDataBadge />}
          </h2>
          {sources && sources.length > MAX_HOME_SOURCES && (
            <Link to="/sources" className="text-xs font-semibold text-primary-600 hover:text-primary-700 flex items-center gap-1">
              View all ({sources.length}) <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>

        {sources === null ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="card h-52 animate-pulse bg-gray-100 border-0" />
            ))}
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {sources.slice(0, MAX_HOME_SOURCES).map((s) => (
              <SourceCard key={s.id} source={s} />
            ))}
          </div>
        )}
      </div>

      <VerificationPipeline />
    </div>
  )
}
