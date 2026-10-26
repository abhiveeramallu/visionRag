import React, { useState, useEffect, useRef } from 'react'
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom'
import {
  querySource, getSource, getSources, getSourceConversation,
  newSourceConversation, getSuggestedQuestions
} from '../services/api'
import MessageBubble from '../components/MessageBubble'
import RetrievalStrategyPanel from '../components/RetrievalStrategyPanel'
import ConflictCompare from '../components/ConflictCompare'
import {
  Send, Loader2, MessageSquare, ChevronDown, ChevronRight,
  Activity, ShieldCheck, History, AlertTriangle, Layers, Plus,
  RefreshCw, BookOpen, AlertCircle, Sparkles, ExternalLink
} from 'lucide-react'

function TracePanel({ trace, abstained, latencyMs }) {
  const [open, setOpen] = useState(false)
  if (!trace) return null

  return (
    <div className="max-w-3xl ml-12 card p-3 bg-gray-50/70 border border-gray-200 text-xs">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-ink-700 font-semibold hover:text-ink-900 transition-colors"
      >
        <span className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary-600" />
          Retrieval & Verification Trace
          {abstained ? (
            <span className="badge-amber text-[10px] py-0">Abstained</span>
          ) : (
            <span className="badge-green text-[10px] py-0">Grounded</span>
          )}
        </span>
        <span className="flex items-center gap-2 text-ink-400 font-normal">
          <span>{latencyMs ? `${latencyMs.toFixed(1)} ms` : ''}</span>
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </span>
      </button>

      {open && (
        <div className="mt-3 pt-3 border-t border-gray-200 space-y-3 font-sans">
          {/* 1. Dynamic Routing */}
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-ink-400 block">
              Dynamic Query Routing
            </span>
            <div className="p-2 bg-white rounded-lg border border-gray-100 flex items-center justify-between">
              <div>
                <span className="font-semibold text-ink-800">
                  Type: {trace.routing?.query_type || 'General'}
                </span>
                <p className="text-[11px] text-ink-500 mt-0.5">
                  {trace.routing?.explanation || 'Routed based on linguistic cues and target modality.'}
                </p>
              </div>
              <span className="badge-blue text-[10px] uppercase">
                {trace.routing?.strategy_used || 'hybrid'}
              </span>
            </div>
          </div>

          {/* 2. VEKG Lineage Resolution */}
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-ink-400 flex items-center gap-1">
              <History className="w-3.5 h-3.5 text-primary-600" />
              VEKG Lineage Resolution
            </span>
            <div className="p-2 bg-white rounded-lg border border-gray-100 text-[11px] text-ink-700">
              {trace.lineage_resolution?.applied ? (
                <div className="space-y-1">
                  <span className="text-emerald-700 font-semibold block">
                    &bull; Superseded claim substituted with active correction:
                  </span>
                  {trace.lineage_resolution.substitutions?.map((sub, i) => (
                    <div key={i} className="pl-2 border-l-2 border-emerald-400 text-ink-600 font-mono text-[10px]">
                      {sub.old_id} &rarr; {sub.new_id} ({sub.reason || 'Correction'})
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-ink-500 italic">
                  No superseded versions in candidate set; direct verified units retained.
                </span>
              )}
            </div>
          </div>

          {/* 3. Sufficiency Gate Decision */}
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold tracking-wider text-ink-400 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-primary-600" />
              Evidence Sufficiency Gate
            </span>
            <div className={`p-2 rounded-lg border text-[11px] ${
              trace.sufficiency_gate?.abstained
                ? 'bg-amber-50 border-amber-200 text-amber-800'
                : 'bg-white border-gray-100 text-ink-700'
            }`}>
              <div className="flex items-center justify-between">
                <span className="font-semibold">
                  Decision: {trace.sufficiency_gate?.abstained ? 'Abstain (Safe)' : 'Proceed with Grounded Generation'}
                </span>
              </div>
              <p className="mt-0.5 text-ink-500">
                Reason: {trace.sufficiency_gate?.reason}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Chat() {
  const { sourceId: routeSourceId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const urlSourceId = routeSourceId || searchParams.get('source_id')

  const [sources, setSources] = useState([])
  const [selectedSource, setSelectedSource] = useState(null)
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [suggestedQuestions, setSuggestedQuestions] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState(null)

  const activeSourceRef = useRef(null)
  const messagesEndRef = useRef(null)

  // 1. Load sources list on mount
  useEffect(() => {
    getSources()
      .then((data) => {
        const list = data || []
        setSources(list)

        // Select source based on URL param or first completed source
        let target = null
        if (urlSourceId) {
          target = list.find((s) => s.id === urlSourceId)
        }
        if (!target) {
          target = list.find((s) => s.status === 'completed') || list[0]
          if (target) {
            navigate(`/chat?source_id=${target.id}`, { replace: true })
          }
        }
        setSelectedSource(target || null)
      })
      .catch((err) => {
        console.error('Failed to load sources:', err)
        setError('Failed to load sources list.')
      })
  }, [])

  // 2. React to URL changes (when user selects another source or navigates)
  useEffect(() => {
    if (urlSourceId && sources.length > 0) {
      const match = sources.find((s) => s.id === urlSourceId)
      if (match && match.id !== selectedSource?.id) {
        setSelectedSource(match)
      }
    }
  }, [urlSourceId, sources])

  // 3. Load isolated conversation history and suggestions whenever selected source changes
  useEffect(() => {
    if (!selectedSource) {
      setMessages([])
      setConversationId(null)
      return
    }

    const currentId = selectedSource.id
    activeSourceRef.current = currentId

    // Clear previous messages immediately to prevent visual bleed across sources
    setMessages([])
    setSuggestedQuestions([])
    setError(null)

    if (selectedSource.status !== 'completed') {
      return
    }

    setLoadingHistory(true)

    // Load source conversation from backend
    getSourceConversation(currentId)
      .then((res) => {
        if (activeSourceRef.current === currentId) {
          setConversationId(res.id)
          setMessages(res.messages || [])
        }
      })
      .catch((err) => {
        if (activeSourceRef.current === currentId) {
          console.error('Failed to load conversation history:', err)
          setError(err.message || 'Failed to load chat history')
        }
      })
      .finally(() => {
        if (activeSourceRef.current === currentId) {
          setLoadingHistory(false)
        }
      })

    // Load suggested questions based on source concepts
    getSuggestedQuestions(currentId)
      .then((res) => {
        if (activeSourceRef.current === currentId) {
          setSuggestedQuestions(res.questions || [])
        }
      })
      .catch((err) => console.error('Failed to load suggested questions:', err))
  }, [selectedSource?.id, selectedSource?.status])

  // Scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Handle changing source from dropdown
  const handleSourceChange = (e) => {
    const newId = e.target.value
    if (!newId || newId === selectedSource?.id) return
    navigate(`/chat?source_id=${newId}`)
    const target = sources.find((s) => s.id === newId)
    setSelectedSource(target || null)
  }

  // Handle "New Chat" action scoped to selected source
  const handleNewChat = async () => {
    if (!selectedSource || selectedSource.status !== 'completed') return
    const targetId = selectedSource.id
    setLoading(true)
    try {
      const res = await newSourceConversation(targetId)
      if (activeSourceRef.current === targetId) {
        setConversationId(res.id)
        setMessages([])
      }
    } catch (err) {
      console.error('Failed to start new chat session:', err)
      setError(err.message || 'Failed to create new chat session')
    } finally {
      setLoading(false)
    }
  }

  // Send message with race-condition prevention
  const handleSend = async (queryText = input) => {
    const text = queryText.trim()
    if (!text || loading || !selectedSource || selectedSource.status !== 'completed') return

    const targetSourceId = selectedSource.id
    const targetConvId = conversationId

    const userMsg = {
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await querySource(targetSourceId, text, 5, true, true, targetConvId)

      // Guard against race conditions if user switched sources while query was in flight
      if (activeSourceRef.current !== targetSourceId) {
        return
      }

      const botMsg = {
        role: 'assistant',
        content: res.answer,
        evidence: res.evidence || [],
        conflicts: res.conflicts || [],
        confidence: res.confidence,
        strategy: res.retrieval_strategy_used,
        abstained: res.abstained || false,
        latency_ms: res.latency_ms,
        trace: res.trace,
        created_at: new Date().toISOString(),
      }

      if (res.conversation_id && !conversationId) {
        setConversationId(res.conversation_id)
      }

      setMessages((prev) => [...prev, botMsg])
    } catch (err) {
      if (activeSourceRef.current !== targetSourceId) return
      const errorMsg = {
        role: 'assistant',
        content: `Error retrieving answer: ${err.message || 'Server error'}`,
        evidence: [],
        conflicts: [],
        abstained: true,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      if (activeSourceRef.current === targetSourceId) {
        setLoading(false)
      }
    }
  }

  const handleTimestampClick = () => {}

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-4xl mx-auto space-y-3">
      {/* Source Selector Header Bar */}
      <div className="card p-3 bg-white border border-gray-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 flex-shrink-0">
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary-100 text-primary-700 flex items-center justify-center flex-shrink-0">
            <MessageSquare className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-ink-900 uppercase tracking-wider">
                Active Source Scope:
              </span>
              {selectedSource && (
                <span
                  className={`text-[11px] px-2 py-0.2 rounded-full font-semibold ${
                    selectedSource.status === 'completed'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : selectedSource.status === 'failed'
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}
                >
                  {selectedSource.status === 'completed' ? 'Verified & Ready' : selectedSource.status}
                </span>
              )}
            </div>
            {/* Dropdown Selector */}
            {sources.length > 0 ? (
              <select
                value={selectedSource?.id || ''}
                onChange={handleSourceChange}
                className="mt-1 w-full max-w-md bg-gray-50 border border-gray-200 text-xs text-ink-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary-500 font-medium truncate"
              >
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title} ({s.id.slice(0, 8)}) &middot; {s.status}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-xs text-ink-400 mt-1">No ingested sources available.</p>
            )}
          </div>
        </div>

        {/* New Chat Button */}
        <div className="flex items-center gap-2 self-end sm:self-center">
          <button
            onClick={handleNewChat}
            disabled={!selectedSource || selectedSource.status !== 'completed' || loading}
            className="btn-secondary py-1.5 px-3 text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
            title="Start fresh conversation for this source"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
          {selectedSource && (
            <Link
              to={`/source/${selectedSource.id}`}
              className="p-1.5 rounded-lg border border-gray-200 text-ink-400 hover:text-ink-700 text-xs"
              title="View source metadata and media"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>
      </div>

      {/* Main Chat Messages Container */}
      <div className="flex-1 overflow-y-auto px-1 space-y-3">
        {/* State: No Sources Available */}
        {sources.length === 0 && (
          <div className="card p-12 text-center space-y-3">
            <BookOpen className="w-8 h-8 mx-auto text-ink-300" />
            <h3 className="font-bold text-ink-800 text-sm">No Sources Available</h3>
            <p className="text-xs text-ink-500 max-w-sm mx-auto">
              Please upload a lecture PDF, video, or YouTube link from Home to begin asking verified questions.
            </p>
            <Link to="/" className="btn-primary inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold mt-2">
              Add Learning Material
            </Link>
          </div>
        )}

        {/* State: Selected Source Not Completed */}
        {selectedSource && selectedSource.status !== 'completed' && (
          <div className="card p-8 text-center space-y-2 border-amber-200 bg-amber-50/50">
            <AlertCircle className="w-6 h-6 text-amber-600 mx-auto" />
            <h3 className="font-bold text-amber-900 text-sm">
              Source Processing Incomplete
            </h3>
            <p className="text-xs text-amber-700 max-w-md mx-auto">
              "{selectedSource.title}" is currently in status <strong>{selectedSource.status}</strong>. AI Chat retrieval will become available once extraction and indexing finish.
            </p>
            {selectedSource.status === 'processing' && (
              <Link
                to={`/processing/${selectedSource.id}`}
                className="btn-primary inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold mt-2"
              >
                View Processing Status
              </Link>
            )}
          </div>
        )}

        {/* State: Loading History */}
        {loadingHistory && (
          <div className="flex items-center justify-center py-12 text-xs text-ink-400 gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
            <span>Loading conversation session for {selectedSource?.title}...</span>
          </div>
        )}

        {/* Suggested Questions (when message history is empty) */}
        {!loadingHistory && selectedSource?.status === 'completed' && messages.length === 0 && (
          <div className="space-y-3 py-4">
            <div className="text-center space-y-1 mb-4">
              <Sparkles className="w-6 h-6 text-primary-600 mx-auto" />
              <h2 className="text-sm font-bold text-ink-900">
                Ask about {selectedSource.title}
              </h2>
              <p className="text-xs text-ink-500 max-w-md mx-auto">
                Questions are verified against this source's multimodal knowledge units and errata lineage.
              </p>
            </div>

            <div className="grid sm:grid-cols-2 gap-2 max-w-2xl mx-auto">
              {(suggestedQuestions.length > 0
                ? suggestedQuestions
                : [
                    'What are the core concepts covered in this material?',
                    'Explain any formulas or algorithms derived.',
                    'Were any mistakes or errata corrected?',
                    'Summarize the key takeaways for an exam.',
                  ]
              ).map((q) => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  className="text-left text-xs bg-white border border-gray-200 text-ink-700 p-3 rounded-xl hover:border-primary-400 hover:bg-primary-50/40 transition-colors shadow-xs"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages List */}
        {!loadingHistory &&
          messages.map((msg, idx) => (
            <div key={msg.id || idx} className="space-y-2">
              <MessageBubble message={msg} onTimestampClick={handleTimestampClick} />
              {msg.role === 'assistant' && msg.evidence?.length > 0 && (
                <div className="max-w-3xl ml-12">
                  <RetrievalStrategyPanel strategyUsed={msg.strategy} />
                </div>
              )}
              {msg.role === 'assistant' && msg.conflicts?.length > 0 && (
                <div className="max-w-3xl ml-12">
                  <ConflictCompare conflict={msg.conflicts[0]} />
                </div>
              )}
              {msg.role === 'assistant' && msg.trace && (
                <TracePanel
                  trace={msg.trace}
                  abstained={msg.abstained}
                  latencyMs={msg.latency_ms}
                />
              )}
            </div>
          ))}

        {loading && (
          <div className="flex items-center gap-3 text-ink-500 text-xs py-3 px-4 bg-white border border-gray-200 rounded-2xl max-w-xs shadow-xs">
            <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
            <span>Searching verified knowledge in {selectedSource?.title}...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend()
        }}
        className="relative flex items-center pt-2 flex-shrink-0"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            selectedSource && selectedSource.status === 'completed'
              ? `Ask a question about ${selectedSource.title}...`
              : 'Select a completed source to chat...'
          }
          disabled={loading || !selectedSource || selectedSource.status !== 'completed'}
          className="w-full pl-4 pr-12 py-3.5 bg-white border border-gray-300 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 shadow-sm disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading || !selectedSource || selectedSource.status !== 'completed'}
          className="absolute right-2 p-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-40 transition-colors shadow-xs"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </form>
    </div>
  )
}
