import React, { useEffect, useState, useRef, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Youtube, FileVideo, Music, FileText, Layers, Image as ImageIcon,
  Send, Loader2, Clock, ShieldCheck, History, Sparkles, AlertCircle,
  Play, Pause, Volume2, ChevronLeft, ChevronRight, Download, Filter,
} from 'lucide-react'
import { getSource, querySource, getKnowledge } from '../services/api'
import { mockSources, mockChatExchange, formatTimestamp } from '../data/mockData'
import MessageBubble from '../components/MessageBubble'
import RetrievalStrategyPanel from '../components/RetrievalStrategyPanel'
import ConflictCompare from '../components/ConflictCompare'
import DemoDataBadge from '../components/DemoDataBadge'

const TYPE_META = {
  youtube: { icon: Youtube, label: 'YouTube Video', color: 'text-red-600' },
  video: { icon: FileVideo, label: 'Video', color: 'text-purple-600' },
  audio: { icon: Music, label: 'Audio', color: 'text-blue-600' },
  pdf: { icon: FileText, label: 'PDF', color: 'text-rose-600' },
  ppt: { icon: Layers, label: 'PPT / PPTX', color: 'text-orange-600' },
  image: { icon: ImageIcon, label: 'Image', color: 'text-emerald-600' },
}

const MODALITY_LABEL = {
  formula: 'Formula / Whiteboard',
  ocr: 'On-screen Text (OCR)',
  asr: 'Speech (Transcript)',
  text: 'Document Text',
  code: 'Code Block',
  vision: 'Visual Description',
}

const STATUS_BADGE_CLASS = {
  verified: 'badge-green',
  active: 'badge-blue',
  disputed: 'badge-red',
  superseded: 'badge-gray',
}

function evidenceLocation(item) {
  if (item.timestamp_start != null) return formatTimestamp(item.timestamp_start)
  if (item.page != null) return `Page ${item.page}`
  if (item.slide != null) return `Slide ${item.slide}`
  return '—'
}

function evidenceTopic(item) {
  const firstLine = (item.text || item.content || '').split('\n').find((l) => l.trim().length > 0) || ''
  return firstLine.replace(/\s+/g, ' ').trim().slice(0, 80) || 'Retrieved evidence'
}

// ---------------------------------------------------------------------------
// Type-Specific Media Previews
// ---------------------------------------------------------------------------

function MediaPanel({
  source,
  audioRef,
  videoRef,
  currentSlide,
  setCurrentSlide,
  totalSlides,
  slideKnowledgeUnits,
  onSeek,
}) {
  const meta = TYPE_META[source.source_type] || TYPE_META.pdf
  const Icon = meta.icon
  const mediaUrl = source.media_url || source.url
  const [mediaError, setMediaError] = useState(null)

  // Audio preview
  if (source.source_type === 'audio') {
    return (
      <div className="card p-0 overflow-hidden flex flex-col border border-gray-200">
        <div className="bg-gradient-to-br from-ink-900 via-ink-800 to-primary-950 p-5 text-white flex flex-col justify-between min-h-[220px]">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-primary-600 flex items-center justify-center text-white shadow-md flex-shrink-0">
              <Music className="w-6 h-6" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-bold text-sm text-white truncate">{source.title}</p>
              <p className="text-xs text-white/70 mt-0.5">
                {source.duration ? `${Math.floor(source.duration / 60)}m ${Math.floor(source.duration % 60)}s duration` : 'Audio track'}
                {mediaUrl ? ' · Ready to stream' : ' · Media unavailable'}
              </p>
            </div>
          </div>

          <div className="my-4">
            {mediaUrl ? (
              <audio
                ref={audioRef}
                controls
                src={mediaUrl}
                className="w-full rounded shadow-sm focus:outline-none"
                preload="metadata"
                onError={() => setMediaError('Unable to play audio. The file could not be streamed or format is unsupported.')}
              />
            ) : (
              <div className="p-3 bg-red-900/40 rounded-lg text-xs text-red-200 border border-red-700/50">
                No audio stream URL available for this source.
              </div>
            )}
            {mediaError && (
              <p className="text-xs text-red-300 mt-2 flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                {mediaError}
              </p>
            )}
          </div>

          <div className="flex items-center justify-between text-[11px] text-white/60 border-t border-white/10 pt-2.5">
            <span className="flex items-center gap-1.5">
              <Volume2 className="w-3.5 h-3.5 text-primary-400" />
              HTML5 Audio Player · HTTP Range Seeking
            </span>
            <span className="text-primary-300 font-medium">Click timestamps to seek</span>
          </div>
        </div>
      </div>
    )
  }

  // Video preview
  if (source.source_type === 'video') {
    return (
      <div className="card p-0 overflow-hidden flex flex-col border border-gray-200">
        <div className="aspect-video bg-black flex items-center justify-center relative">
          {mediaUrl ? (
            <video
              ref={videoRef}
              controls
              src={mediaUrl}
              className="w-full h-full object-contain"
              preload="metadata"
              onError={() => setMediaError('Unable to load video. Range request failed or unsupported codec.')}
            />
          ) : (
            <div className="text-center text-white/70 px-6">
              <FileVideo className="w-10 h-10 mx-auto mb-2 opacity-80" />
              <p className="text-sm font-medium">Video file not available</p>
            </div>
          )}
        </div>
        {mediaError && (
          <div className="p-3 bg-red-50 text-red-700 text-xs border-t border-red-200 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 text-red-500" />
            {mediaError}
          </div>
        )}
      </div>
    )
  }

  // YouTube preview
  if (source.source_type === 'youtube') {
    return (
      <div className="card p-0 overflow-hidden flex flex-col border border-gray-200">
        <div className="aspect-video bg-ink-900 flex items-center justify-center relative">
          {source.url ? (
            <iframe
              className="w-full h-full"
              src={source.url.replace('watch?v=', 'embed/')}
              title={source.title}
              allowFullScreen
            />
          ) : (
            <div className="text-center text-white/70 px-6">
              <Youtube className="w-10 h-10 mx-auto mb-2 opacity-80 text-red-500" />
              <p className="text-sm font-medium">YouTube stream unavailable</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // PDF Document preview
  if (source.source_type === 'pdf') {
    return (
      <div className="card p-0 overflow-hidden flex flex-col border border-gray-200">
        <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between text-xs">
          <span className="font-semibold text-ink-800 flex items-center gap-1.5">
            <FileText className="w-4 h-4 text-red-600" />
            PDF Document {source.num_pages ? `(${source.num_pages} pages)` : ''}
          </span>
          {mediaUrl && (
            <a
              href={mediaUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-semibold text-primary-600 hover:text-primary-800 flex items-center gap-1"
            >
              Open PDF in new tab ↗
            </a>
          )}
        </div>
        <div className="h-[420px] bg-gray-900 relative">
          {mediaUrl ? (
            <object
              data={mediaUrl}
              type="application/pdf"
              className="w-full h-full"
            >
              <iframe
                src={mediaUrl}
                className="w-full h-full border-0"
                title={source.title}
              />
            </object>
          ) : (
            <div className="text-center text-white/70 py-24 px-6">
              <FileText className="w-10 h-10 mx-auto mb-2 opacity-80" />
              <p className="text-sm font-medium">PDF preview unavailable</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // PPT / PPTX Slide Navigation & Content Preview
  if (source.source_type === 'ppt') {
    const currentSlideKUs = (slideKnowledgeUnits || []).filter(
      (ku) => (ku.slide || ku.page) === currentSlide
    )
    const effectiveTotal = totalSlides || source.num_pages || 10

    return (
      <div className="card p-0 overflow-hidden flex flex-col border border-gray-200">
        <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between text-xs flex-wrap gap-2">
          <span className="font-semibold text-ink-800 flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-orange-600" />
            Slide {currentSlide} of {effectiveTotal}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setCurrentSlide(Math.max(1, currentSlide - 1))}
              disabled={currentSlide <= 1}
              className="p-1 rounded bg-white border border-gray-200 text-ink-700 hover:bg-gray-100 disabled:opacity-40"
              title="Previous Slide"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="font-mono text-xs text-ink-600 px-1">
              {currentSlide} / {effectiveTotal}
            </span>
            <button
              onClick={() => setCurrentSlide(Math.min(effectiveTotal, currentSlide + 1))}
              disabled={currentSlide >= effectiveTotal}
              className="p-1 rounded bg-white border border-gray-200 text-ink-700 hover:bg-gray-100 disabled:opacity-40"
              title="Next Slide"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
            {mediaUrl && (
              <a
                href={mediaUrl}
                download={source.title}
                className="ml-2 px-2.5 py-1 bg-primary-50 text-primary-700 hover:bg-primary-100 rounded text-xs font-semibold flex items-center gap-1 transition-colors"
              >
                <Download className="w-3 h-3" />
                PPTX
              </a>
            )}
          </div>
        </div>

        {/* Slide quick picker selector */}
        <div className="px-3 py-1.5 bg-white border-b border-gray-100 flex items-center gap-1 overflow-x-auto">
          {Array.from({ length: effectiveTotal }, (_, i) => i + 1).map((num) => (
            <button
              key={num}
              onClick={() => setCurrentSlide(num)}
              className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                num === currentSlide
                  ? 'bg-primary-600 text-white font-bold'
                  : 'bg-gray-100 text-ink-600 hover:bg-gray-200'
              }`}
            >
              {num}
            </button>
          ))}
        </div>

        {/* Slide Extracted Text & KUs */}
        <div className="p-4 bg-white min-h-[300px] max-h-[420px] overflow-y-auto space-y-3">
          {currentSlideKUs.length === 0 ? (
            <div className="text-center py-12 text-ink-400 text-xs">
              <Layers className="w-8 h-8 mx-auto mb-2 opacity-50 text-orange-500" />
              <p className="font-medium text-ink-700">Slide {currentSlide}</p>
              <p className="mt-1">No discrete text or formula units indexed for this slide.</p>
            </div>
          ) : (
            currentSlideKUs.map((ku) => (
              <div
                key={ku.id}
                className="p-3 rounded-lg border border-gray-200 bg-gray-50/70 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-primary-700 uppercase tracking-wider text-[10px]">
                    {MODALITY_LABEL[ku.modality] || ku.modality}
                  </span>
                  <span className={`${STATUS_BADGE_CLASS[ku.status] || 'badge-gray'} text-[10px]`}>
                    {ku.status}
                  </span>
                </div>
                {ku.concept && (
                  <p className="font-bold text-ink-900 text-xs">{ku.concept}</p>
                )}
                <div className="font-mono text-ink-800 whitespace-pre-wrap leading-relaxed text-[11px] bg-white p-2.5 rounded border border-gray-100">
                  {ku.content}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    )
  }

  // Image preview
  if (source.source_type === 'image') {
    return (
      <div className="card p-0 overflow-hidden flex flex-col border border-gray-200">
        <div className="aspect-video bg-black flex items-center justify-center p-2">
          {mediaUrl ? (
            <img
              src={mediaUrl}
              alt={source.title}
              className="max-h-full max-w-full object-contain mx-auto"
            />
          ) : (
            <div className="text-center text-white/70 px-6">
              <ImageIcon className="w-10 h-10 mx-auto mb-2 opacity-80" />
              <p className="text-sm font-medium">Image unavailable</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Fallback
  return (
    <div className="card p-0 overflow-hidden flex flex-col border border-gray-200">
      <div className="aspect-video bg-ink-900 flex items-center justify-center text-white/70 p-6 text-center">
        <div>
          <Icon className="w-10 h-10 mx-auto mb-2 opacity-80" />
          <p className="text-sm font-medium">{meta.label} Preview</p>
          <p className="text-xs text-white/50 mt-1">{source.title}</p>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Knowledge Evidence Panel: Query Citations + All Indexed Units
// ---------------------------------------------------------------------------

function EvidencePanel({
  evidence,
  sourceId,
  source,
  knowledgeUnits,
  kusLoading,
  kusError,
  onSeek,
  onSelectSlide,
}) {
  const [tab, setTab] = useState('query')
  const [modalityFilter, setModalityFilter] = useState('all')

  const hasQueryEvidence = evidence && evidence.length > 0
  const primaryEvidence = hasQueryEvidence ? evidence[0] : null

  const filteredKUs = useMemo(() => {
    if (!knowledgeUnits) return []
    if (modalityFilter === 'all') return knowledgeUnits
    return knowledgeUnits.filter((ku) => (ku.modality || '').toLowerCase() === modalityFilter.toLowerCase())
  }, [knowledgeUnits, modalityFilter])

  return (
    <div className="card space-y-4 border border-gray-200 flex flex-col h-[600px]">
      <div className="flex items-center justify-between border-b border-gray-100 pb-3 flex-shrink-0">
        <h3 className="text-sm font-bold text-ink-900 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-primary-600" />
          Knowledge Evidence
        </h3>
        <div className="flex items-center bg-gray-100 p-0.5 rounded-lg text-xs">
          <button
            onClick={() => setTab('query')}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
              tab === 'query'
                ? 'bg-white text-ink-900 shadow-xs'
                : 'text-ink-500 hover:text-ink-900'
            }`}
          >
            Query Evidence
          </button>
          <button
            onClick={() => setTab('all')}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors flex items-center gap-1 ${
              tab === 'all'
                ? 'bg-white text-ink-900 shadow-xs'
                : 'text-ink-500 hover:text-ink-900'
            }`}
          >
            All Units
            {knowledgeUnits && (
              <span className="font-mono text-[10px] bg-primary-100 text-primary-700 px-1 rounded-full">
                {knowledgeUnits.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {tab === 'query' ? (
        <div className="flex-1 overflow-y-auto space-y-3 pr-1">
          {!hasQueryEvidence ? (
            <div className="text-center py-12 px-4 space-y-3">
              <div className="w-10 h-10 rounded-full bg-primary-50 text-primary-600 flex items-center justify-center mx-auto">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <p className="font-semibold text-xs text-ink-800">Query-Dependent Grounding</p>
              <p className="text-xs text-ink-500 leading-relaxed">
                Ask a question in AI Chat to retrieve and inspect grounded verification evidence.
              </p>
              {knowledgeUnits && knowledgeUnits.length > 0 && (
                <button
                  onClick={() => setTab('all')}
                  className="mt-2 text-xs font-semibold text-primary-600 hover:text-primary-800 underline"
                >
                  Explore {knowledgeUnits.length} indexed units for this source &rarr;
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Topic</p>
                <p className="text-sm font-bold text-ink-900 mt-0.5">{evidenceTopic(primaryEvidence)}</p>
              </div>

              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Evidence Snippet</p>
                <p className="font-mono text-xs text-ink-800 bg-gray-50 border border-gray-200 rounded-lg p-3 mt-1 max-h-36 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                  {primaryEvidence.text || primaryEvidence.content}
                </p>
              </div>

              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Modality</p>
                <span className="inline-block mt-0.5 font-medium text-xs text-primary-800 bg-primary-50 px-2 py-0.5 rounded border border-primary-100">
                  {MODALITY_LABEL[primaryEvidence.modality] || primaryEvidence.modality}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Location</p>
                  <button
                    onClick={() => {
                      if (primaryEvidence.timestamp_start != null && onSeek) {
                        onSeek(primaryEvidence.timestamp_start)
                      } else if (primaryEvidence.slide != null && onSelectSlide) {
                        onSelectSlide(primaryEvidence.slide)
                      }
                    }}
                    className="text-xs font-medium text-primary-700 hover:text-primary-900 mt-0.5 flex items-center gap-1 underline"
                  >
                    <Clock className="w-3.5 h-3.5 text-primary-500" />
                    {evidenceLocation(primaryEvidence)}
                  </button>
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Confidence</p>
                  <p className="text-xs font-semibold text-green-700 mt-0.5">
                    {Math.round((primaryEvidence.confidence ?? 0.95) * 100)}% verified
                  </p>
                </div>
              </div>

              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Status</p>
                <span className={`${STATUS_BADGE_CLASS[primaryEvidence.status] || 'badge-green'} mt-1 inline-block capitalize text-[10px]`}>
                  {primaryEvidence.status || 'verified'}
                </span>
              </div>

              {evidence.length > 1 && (
                <div className="pt-2 border-t border-gray-100 space-y-1.5">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                    Additional Retrieved Fragments ({evidence.length - 1})
                  </p>
                  <div className="space-y-1 max-h-24 overflow-y-auto">
                    {evidence.slice(1).map((item, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          if (item.timestamp_start != null && onSeek) onSeek(item.timestamp_start)
                        }}
                        className="w-full text-left p-1.5 rounded hover:bg-gray-100 text-[11px] text-ink-700 truncate block font-mono"
                      >
                        [{MODALITY_LABEL[item.modality]?.split(' ')[0] || item.modality}] {item.text?.slice(0, 50)}...
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto flex flex-col min-h-0 space-y-2 pr-1">
          {/* Modality Filter Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 flex-shrink-0">
            {['all', 'asr', 'ocr', 'text', 'formula', 'code'].map((m) => (
              <button
                key={m}
                onClick={() => setModalityFilter(m)}
                className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold transition-colors ${
                  modalityFilter === m
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-ink-600 hover:bg-gray-200'
                }`}
              >
                {m}
              </button>
            ))}
          </div>

          {kusLoading ? (
            <div className="flex-1 flex items-center justify-center text-ink-400 text-xs py-10">
              <Loader2 className="w-4 h-4 animate-spin text-primary-600 mr-2" />
              Loading source knowledge units...
            </div>
          ) : kusError ? (
            <div className="text-center py-10 text-xs text-red-600">
              <AlertCircle className="w-5 h-5 mx-auto mb-1 text-red-500" />
              Failed to load Knowledge Units for this source.
            </div>
          ) : filteredKUs.length === 0 ? (
            <div className="text-center py-10 text-xs text-ink-400">
              No knowledge units matching filter "{modalityFilter}".
            </div>
          ) : (
            <div className="space-y-2 overflow-y-auto flex-1">
              {filteredKUs.map((ku) => (
                <div
                  key={ku.id}
                  className="p-2.5 rounded-lg border border-gray-200 bg-gray-50/60 hover:bg-white hover:border-primary-200 transition-colors text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-primary-700 uppercase tracking-wider text-[10px]">
                      {MODALITY_LABEL[ku.modality] || ku.modality}
                    </span>
                    <button
                      onClick={() => {
                        if (ku.timestamp_start != null && onSeek) onSeek(ku.timestamp_start)
                        else if (ku.slide != null && onSelectSlide) onSelectSlide(ku.slide)
                      }}
                      className="font-mono text-[10px] text-ink-500 hover:text-primary-700 flex items-center gap-1 underline"
                    >
                      <Clock className="w-3 h-3" />
                      {evidenceLocation(ku)}
                    </button>
                  </div>
                  {ku.concept && (
                    <p className="font-bold text-ink-900 text-xs">{ku.concept}</p>
                  )}
                  <p className="font-mono text-[11px] text-ink-800 line-clamp-3 bg-white p-2 rounded border border-gray-100 leading-relaxed">
                    {ku.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="pt-2 border-t border-gray-100 flex-shrink-0">
        <Link
          to={`/knowledge-evolution/${sourceId}`}
          className="btn-secondary w-full py-2 text-xs font-semibold flex items-center justify-center gap-1.5"
        >
          <History className="w-3.5 h-3.5" />
          View Knowledge History
        </Link>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Source Detail Component
// ---------------------------------------------------------------------------

export default function SourceDetail() {
  const { sourceId } = useParams()
  const [source, setSource] = useState(null)
  const [usingDemo, setUsingDemo] = useState(false)
  const [knowledgeUnits, setKnowledgeUnits] = useState([])
  const [kusLoading, setKusLoading] = useState(true)
  const [kusError, setKusError] = useState(false)
  const [currentSlide, setCurrentSlide] = useState(1)

  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Ask about this lecture — I will ground every answer in verified evidence with a timestamp or page citation.',
      evidence: [],
      conflicts: [],
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [lastStrategy, setLastStrategy] = useState(null)
  const [lastEvidence, setLastEvidence] = useState([])

  const bottomRef = useRef(null)
  const audioRef = useRef(null)
  const videoRef = useRef(null)

  // Handle seeking across media players (audio / video)
  const handleSeek = (seconds) => {
    if (seconds == null) return
    if (audioRef.current) {
      audioRef.current.currentTime = seconds
      audioRef.current.play().catch(() => {})
    }
    if (videoRef.current) {
      videoRef.current.currentTime = seconds
      videoRef.current.play().catch(() => {})
    }
  }

  // Load source metadata
  useEffect(() => {
    // Reset state for newly selected source to maintain strict isolation
    setSource(null)
    setMessages([
      {
        role: 'assistant',
        content: 'Ask about this lecture — I will ground every answer in verified evidence with a timestamp or page citation.',
        evidence: [],
        conflicts: [],
      },
    ])
    setLastEvidence([])
    setLastStrategy(null)
    setKnowledgeUnits([])
    setCurrentSlide(1)

    getSource(sourceId)
      .then((data) => {
        setSource(data)
        setUsingDemo(false)
      })
      .catch(() => {
        const demo = mockSources.find((s) => s.id === sourceId) || mockSources[0]
        setSource(demo)
        setUsingDemo(true)
      })
  }, [sourceId])

  // Load source Knowledge Units for evidence discovery
  useEffect(() => {
    if (!sourceId) return
    setKusLoading(true)
    setKusError(false)

    getKnowledge(sourceId)
      .then((data) => {
        setKnowledgeUnits(data || [])
      })
      .catch((err) => {
        console.warn('Failed to load knowledge units for source:', err)
        setKusError(true)
      })
      .finally(() => {
        setKusLoading(false)
      })
  }, [sourceId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (text = input) => {
    const q = text.trim()
    if (!q || loading) return
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    setInput('')
    setLoading(true)

    try {
      const res = await querySource(sourceId, q)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          evidence: res.evidence || [],
          conflicts: res.conflicts || [],
          confidence: res.confidence,
          strategy: res.retrieval_strategy_used,
        },
      ])
      setLastStrategy(res.retrieval_strategy_used)
      setLastEvidence(res.evidence || [])
    } catch (err) {
      const demoAnswer = {
        role: 'assistant',
        content: mockChatExchange.answer,
        evidence: mockChatExchange.evidence,
        conflicts: [],
        confidence: mockChatExchange.confidence,
        strategy: mockChatExchange.retrieval_strategy_used,
        demo: true,
      }
      setMessages((prev) => [...prev, demoAnswer])
      setLastStrategy(mockChatExchange.retrieval_strategy_used)
      setLastEvidence(mockChatExchange.evidence)
      setUsingDemo(true)
    } finally {
      setLoading(false)
    }
  }

  if (!source) {
    return (
      <div className="flex items-center justify-center py-24 text-ink-400">
        <Loader2 className="w-6 h-6 animate-spin text-primary-600 mr-2" />
        Loading source...
      </div>
    )
  }

  // Modality summary breakdown
  const summary = source.metadata?.modalities_summary || {}
  const totalUnits = summary.total_units || knowledgeUnits.length || 0

  return (
    <div className="space-y-4 pb-8">
      {/* Source Header Banner */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-extrabold text-ink-900">{source.title}</h1>
            <span
              className={`text-[11px] font-semibold px-2 py-0.5 rounded-full capitalize ${
                source.status === 'completed'
                  ? 'bg-green-100 text-green-700'
                  : source.status === 'failed'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-amber-100 text-amber-700 animate-pulse'
              }`}
            >
              {source.status}
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-ink-500 mt-1">
            <span>Verified multimodal knowledge base</span>
            {totalUnits > 0 && (
              <>
                <span>•</span>
                <span className="font-medium text-ink-700">
                  {totalUnits} Knowledge Units indexed
                </span>
              </>
            )}
            {source.duration && (
              <>
                <span>•</span>
                <span>
                  {Math.floor(source.duration / 60)}m {Math.floor(source.duration % 60)}s duration
                </span>
              </>
            )}
            {source.num_pages && (
              <>
                <span>•</span>
                <span>{source.num_pages} pages</span>
              </>
            )}
          </div>
        </div>
        {usingDemo && <DemoDataBadge label="Demo evidence" />}
      </div>

      {/* 3-Column Layout: Media Preview | AI Chat | Knowledge Evidence */}
      <div className="grid lg:grid-cols-[1.1fr_1.3fr_0.9fr] gap-4 items-start">
        <MediaPanel
          source={source}
          audioRef={audioRef}
          videoRef={videoRef}
          currentSlide={currentSlide}
          setCurrentSlide={setCurrentSlide}
          totalSlides={source.num_pages || 10}
          slideKnowledgeUnits={knowledgeUnits}
          onSeek={handleSeek}
        />

        {/* Source-Scoped AI Chat */}
        <div className="card flex flex-col h-[600px] border border-gray-200">
          <div className="flex items-center justify-between mb-3 border-b border-gray-100 pb-2.5">
            <h2 className="text-sm font-bold text-ink-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary-600" />
              Ask about this lecture
            </h2>
            <Link
              to={`/chat?source_id=${source.id}`}
              className="text-xs font-semibold text-primary-600 hover:text-primary-800"
            >
              Open Full AI Chat &rarr;
            </Link>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {messages.map((m, i) => (
              <div key={i} className="space-y-2">
                <MessageBubble
                  message={m}
                  onTimestampClick={(ts) => handleSeek(ts)}
                />
                {m.role === 'assistant' && m.evidence?.length > 0 && (
                  <RetrievalStrategyPanel strategyUsed={m.strategy} />
                )}
                {m.role === 'assistant' && m.conflicts?.length > 0 && (
                  <ConflictCompare conflict={m.conflicts[0]} />
                )}
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-2 text-ink-400 text-xs py-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-primary-600" />
                Searching verified knowledge...
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={(e) => { e.preventDefault(); handleSend() }} className="relative mt-3 flex-shrink-0">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. What is the main thesis or theorem?"
              disabled={loading}
              className="w-full pl-4 pr-11 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-ink-900 placeholder-ink-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-colors"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-40 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>

        <EvidencePanel
          evidence={lastEvidence}
          sourceId={source.id}
          source={source}
          knowledgeUnits={knowledgeUnits}
          kusLoading={kusLoading}
          kusError={kusError}
          onSeek={handleSeek}
          onSelectSlide={(slide) => setCurrentSlide(slide)}
        />
      </div>
    </div>
  )
}
