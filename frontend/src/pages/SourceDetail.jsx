import React, { useEffect, useState, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Youtube, FileVideo, Music, FileText, Layers, Image as ImageIcon,
  Send, Loader2, Clock, ShieldCheck, History, Sparkles,
} from 'lucide-react'
import { getSource, querySource } from '../services/api'
import { mockSources, mockGradientDescentEvolution, mockChatExchange, formatTimestamp } from '../data/mockData'
import MessageBubble from '../components/MessageBubble'
import RetrievalStrategyPanel from '../components/RetrievalStrategyPanel'
import ConflictCompare from '../components/ConflictCompare'
import DemoDataBadge from '../components/DemoDataBadge'

const TYPE_META = {
  youtube: { icon: Youtube, label: 'YouTube Video' },
  video: { icon: FileVideo, label: 'Video' },
  audio: { icon: Music, label: 'Audio' },
  pdf: { icon: FileText, label: 'PDF' },
  ppt: { icon: Layers, label: 'PPT / PPTX' },
  image: { icon: ImageIcon, label: 'Image' },
}

function MediaPanel({ source }) {
  const meta = TYPE_META[source.source_type] || TYPE_META.pdf
  const Icon = meta.icon

  return (
    <div className="card p-0 overflow-hidden flex flex-col">
      <div className="aspect-video bg-ink-900 flex items-center justify-center relative">
        {source.source_type === 'youtube' && source.url ? (
          <iframe
            className="w-full h-full"
            src={source.url.replace('watch?v=', 'embed/')}
            title={source.title}
            allowFullScreen
          />
        ) : source.source_type === 'video' && source.url ? (
          <video className="w-full h-full" controls src={source.url} />
        ) : source.source_type === 'image' && source.url ? (
          <img className="w-full h-full object-contain bg-black" src={source.url} alt={source.title} />
        ) : (
          <div className="text-center text-white/70 px-6">
            <Icon className="w-10 h-10 mx-auto mb-2 opacity-80" />
            <p className="text-sm font-medium">{meta.label} preview</p>
            {source.num_pages && <p className="text-xs mt-1 opacity-70">{source.num_pages} pages</p>}
          </div>
        )}
      </div>

      {(source.source_type === 'pdf' || source.source_type === 'ppt') && source.num_pages ? (
        <div className="p-4 flex items-center justify-between text-xs text-ink-500 border-t border-gray-100">
          <span>{source.num_pages} pages</span>
          <span className="text-ink-400">Ask a question to jump to the cited page</span>
        </div>
      ) : null}
    </div>
  )
}

const MODALITY_LABEL = {
  formula: 'Formula / Whiteboard',
  ocr: 'On-screen Text (OCR)',
  asr: 'Speech (Transcript)',
  text: 'Document Text',
  code: 'Code Block',
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
  const firstLine = (item.text || '').split('\n').find((l) => l.trim().length > 0) || ''
  return firstLine.replace(/\s+/g, ' ').trim().slice(0, 80) || 'Retrieved evidence'
}

function EvidencePanel({ evidence, sourceId }) {
  const hasEvidence = evidence && evidence.length > 0
  const primary = hasEvidence ? evidence[0] : null

  return (
    <div className="card space-y-4">
      <h3 className="text-sm font-bold text-ink-900 flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-primary-600" />
        Knowledge Evidence
      </h3>

      {!hasEvidence ? (
        <div className="text-center py-10 text-ink-400 text-xs">
          Ask a question in the chat to see grounded evidence here.
        </div>
      ) : (
        <>
          <div className="space-y-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Topic</p>
              <p className="text-base font-bold text-ink-900 mt-0.5">{evidenceTopic(primary)}</p>
            </div>

            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Evidence Snippet</p>
              <p className="font-mono text-xs text-ink-800 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap">
                {primary.text}
              </p>
            </div>

            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Source</p>
              <p className="text-sm text-ink-700 mt-0.5">{MODALITY_LABEL[primary.modality] || primary.modality}</p>
            </div>

            <div className="flex items-center gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Location</p>
                <p className="text-sm text-ink-700 mt-0.5 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-ink-400" />
                  {evidenceLocation(primary)}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Confidence</p>
                <p className="text-sm font-semibold text-green-700 mt-0.5">
                  {Math.round((primary.confidence ?? 0) * 100)}%
                </p>
              </div>
            </div>

            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Status</p>
              <span className={`${STATUS_BADGE_CLASS[primary.status] || 'badge-gray'} mt-1 inline-block capitalize`}>
                {primary.status || 'unverified'}
              </span>
            </div>
          </div>

          <Link
            to={`/knowledge-evolution/${sourceId}`}
            className="btn-secondary w-full py-2 text-xs font-semibold flex items-center justify-center gap-1.5"
          >
            <History className="w-3.5 h-3.5" />
            View Knowledge History
          </Link>
        </>
      )}
    </div>
  )
}

export default function SourceDetail() {
  const { sourceId } = useParams()
  const [source, setSource] = useState(null)
  const [usingDemo, setUsingDemo] = useState(false)
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Ask about this lecture — I will ground every answer in verified evidence with a timestamp or page citation.',
      evidence: [],
      conflicts: [],
      confidence: 1,
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [lastStrategy, setLastStrategy] = useState(null)
  const [lastEvidence, setLastEvidence] = useState([])
  const bottomRef = useRef(null)

  useEffect(() => {
    getSource(sourceId)
      .then((data) => setSource(data))
      .catch(() => {
        const demo = mockSources.find((s) => s.id === sourceId) || mockSources[0]
        setSource(demo)
        setUsingDemo(true)
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
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: res.answer,
        evidence: res.evidence || [],
        conflicts: res.conflicts || [],
        confidence: res.confidence ?? 0.8,
        strategy: res.retrieval_strategy_used,
      }])
      setLastStrategy(res.retrieval_strategy_used)
      setLastEvidence(res.evidence || [])
    } catch (err) {
      // Demo fallback so the 3-column layout is fully explorable without a live backend.
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
    return <div className="flex items-center justify-center py-24 text-ink-400"><Loader2 className="w-6 h-6 animate-spin" /></div>
  }

  return (
    <div className="space-y-4 pb-8">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-extrabold text-ink-900">{source.title}</h1>
          <p className="text-xs text-ink-500 mt-0.5">Verified knowledge base for this source</p>
        </div>
        {usingDemo && <DemoDataBadge label="Demo evidence" />}
      </div>

      <div className="grid lg:grid-cols-[1.1fr_1.3fr_0.9fr] gap-4 items-start">
        <MediaPanel source={source} />

        <div className="card flex flex-col h-[600px]">
          <h2 className="text-sm font-bold text-ink-900 mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary-600" />
            Ask about this lecture
          </h2>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {messages.map((m, i) => (
              <div key={i} className="space-y-2">
                <MessageBubble message={m} onTimestampClick={() => {}} />
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
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Searching verified knowledge...
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={(e) => { e.preventDefault(); handleSend() }} className="relative mt-3 flex-shrink-0">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. What is gradient descent?"
              disabled={loading}
              className="w-full pl-4 pr-11 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-40"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>

        <EvidencePanel evidence={lastEvidence} sourceId={source.id} />
      </div>
    </div>
  )
}
