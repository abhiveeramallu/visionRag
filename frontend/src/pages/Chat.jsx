import React, { useState, useEffect, useRef } from 'react'
import { useParams } from 'react'
import { querySource, getSource } from '../services/api'
import MessageBubble from '../components/MessageBubble'
import { Send, Loader2, Sparkles, MessageSquare, Bot, HelpCircle } from 'lucide-react'

export default function Chat() {
  const { sourceId } = useParams()
  const [source, setSource] = useState(null)
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Hello! I am VisionRAG-X. Ask me any question about your educational material. All answers will be grounded in verified evidence with timestamp/page citations.',
      evidence: [],
      conflicts: [],
      confidence: 1.0,
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    if (sourceId) {
      getSource(sourceId)
        .then((data) => setSource(data))
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
      const res = await querySource(sourceId, text)
      const botMsg = {
        role: 'assistant',
        content: res.answer,
        evidence: res.evidence || [],
        conflicts: res.conflicts || [],
        confidence: res.confidence || 0.8,
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

  const handleQuickQuestion = (qText) => {
    handleSend(qText)
  }

  const handleTimestampClick = (seconds) => {
    alert(`Timestamp clicked: ${seconds} seconds. (In full deployment, this will seek the video player)`)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-4xl mx-auto">
      {/* Source Info Header */}
      {source && (
        <div className="bg-white border border-gray-200 rounded-xl p-3 px-4 mb-4 flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-2">
            <MessageSquare className="w-4 h-4 text-primary-600" />
            <span className="text-xs font-bold text-gray-900">{source.title || 'Educational Material'}</span>
            <span className="badge bg-primary-50 text-primary-700 text-[10px] uppercase font-mono">
              {source.source_type}
            </span>
          </div>
          <span className="text-xs text-gray-400 font-mono">Source ID: {sourceId.slice(0, 8)}...</span>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto px-2 space-y-4">
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} message={msg} onTimestampClick={handleTimestampClick} />
        ))}

        {loading && (
          <div className="flex items-center space-x-3 text-gray-500 text-xs py-3 px-4 bg-white border border-gray-200 rounded-2xl max-w-xs animate-pulse">
            <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
            <span>Executing RAG & verified citation search...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Suggestion Chips */}
      <div className="pt-2 pb-2 flex flex-wrap gap-2">
        {[
          'Summarize main topics',
          'What are the key formulas?',
          'Where is time complexity explained?',
          'What are the main definitions?',
        ].map((chip, idx) => (
          <button
            key={idx}
            onClick={() => handleQuickQuestion(chip)}
            disabled={loading}
            className="text-xs bg-white border border-gray-200 text-gray-700 px-3 py-1 rounded-full hover:border-primary-400 hover:text-primary-600 transition-colors shadow-2xs font-medium"
          >
            💡 {chip}
          </button>
        ))}
      </div>

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend()
        }}
        className="relative flex items-center mt-1"
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
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  )
}
