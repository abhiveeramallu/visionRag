import React, { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { querySource, getSource, getSources } from '../services/api'
import MessageBubble from '../components/MessageBubble'
import RetrievalStrategyPanel from '../components/RetrievalStrategyPanel'
import ConflictCompare from '../components/ConflictCompare'
import { Send, Loader2, MessageSquare } from 'lucide-react'

const EXAMPLE_QUESTIONS = [
  'Explain this lecture in simple terms.',
  'What formula did the professor derive?',
  'Where was backpropagation explained?',
  'Compare supervised and unsupervised learning.',
  'What mistakes did the instructor correct?',
  'Give me the important topics for the exam.',
]

export default function Chat() {
  const { sourceId } = useParams()
  const [source, setSource] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const [activeSourceId, setActiveSourceId] = useState(sourceId || null)

  useEffect(() => {
    if (sourceId) {
      setActiveSourceId(sourceId)
      getSource(sourceId)
        .then((data) => setSource(data))
        .catch(() => {})
    } else {
      getSources()
        .then((sources) => {
          const completed = sources.find((s) => s.status === 'completed') || sources[0]
          if (completed) {
            setActiveSourceId(completed.id)
            setSource(completed)
          }
        })
        .catch(() => {})
    }
  }, [sourceId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (queryText = input) => {
    const text = queryText.trim()
    if (!text || loading) return

    const userMsg = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await querySource(activeSourceId || sourceId, text)
      const botMsg = {
        role: 'assistant',
        content: res.answer,
        evidence: res.evidence || [],
        conflicts: res.conflicts || [],
        confidence: res.confidence ?? 0.8,
        strategy: res.retrieval_strategy_used,
      }
      setMessages((prev) => [...prev, botMsg])
    } catch (err) {
      const errorMsg = {
        role: 'assistant',
        content: `Error retrieving answer: ${err.message || 'Server error'}`,
        evidence: [],
        conflicts: [],
        confidence: 0,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  const handleTimestampClick = () => {}

  const currentId = sourceId || activeSourceId

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-4xl mx-auto">
      <div className="mb-4">
        <h1 className="text-xl font-extrabold text-ink-900 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary-600" />
          Ask your knowledge base
        </h1>
        {source && (
          <p className="text-xs text-ink-500 mt-1">
            {source.title || 'Educational Material'}
            {currentId && <span className="text-ink-300"> &middot; {currentId.slice(0, 8)}</span>}
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-1 space-y-3">
        {messages.length === 0 && (
          <div className="grid sm:grid-cols-2 gap-2 pb-2">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="text-left text-xs bg-white border border-gray-200 text-ink-700 px-3.5 py-2.5 rounded-xl hover:border-primary-400 hover:bg-primary-50/50 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className="space-y-2">
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
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 text-ink-500 text-xs py-3 px-4 bg-white border border-gray-200 rounded-2xl max-w-xs">
            <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
            <span>Searching verified knowledge...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend()
        }}
        className="relative flex items-center mt-3"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your educational material..."
          disabled={loading}
          className="w-full pl-4 pr-12 py-3.5 bg-white border border-gray-300 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 shadow-sm"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="absolute right-2 p-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-40 transition-colors shadow-xs"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </form>
    </div>
  )
}
