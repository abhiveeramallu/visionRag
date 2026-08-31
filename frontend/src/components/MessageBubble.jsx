import React, { useState } from 'react'
import { User, Bot, ChevronDown, ChevronUp, ShieldCheck, AlertCircle, Clock, FileText } from 'lucide-react'
import EvidenceCard from './EvidenceCard'
import ConflictBadge from './ConflictBadge'

export default function MessageBubble({ message, onTimestampClick }) {
  const [showEvidence, setShowEvidence] = useState(false)
  const isUser = message.role === 'user'

  // Render clickable timestamp spans in text (e.g., "14:32" or "at 04:15")
  const renderTextWithTimestamps = (text) => {
    if (!text) return ''
    const tsRegex = /\b(\d{1,2}:\d{2}(?::\d{2})?)\b/g
    const parts = []
    let lastIndex = 0
    let match

    while ((match = tsRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index))
      }
      const tsStr = match[1]
      // Convert MM:SS or HH:MM:SS to total seconds
      const seconds = tsStr.split(':').reduce((acc, time) => 60 * acc + +time, 0)

      parts.push(
        <span
          key={match.index}
          onClick={() => onTimestampClick && onTimestampClick(seconds)}
          className="timestamp-link inline-flex items-center space-x-0.5 bg-blue-50 px-1.5 py-0.5 rounded text-blue-700 font-mono text-xs border border-blue-200 hover:bg-blue-100 transition-colors"
          title={`Jump to ${tsStr}`}
        >
          <Clock className="w-3 h-3 inline mr-0.5" />
          {tsStr}
        </span>
      )
      lastIndex = match.index + match[0].length
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex))
    }

    return parts
  }

  if (isUser) {
    return (
      <div className="flex justify-end my-3">
        <div className="flex items-start max-w-xl space-x-2">
          <div className="bg-primary-600 text-white rounded-2xl rounded-tr-none px-4 py-3 shadow-sm">
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-primary-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start my-4">
      <div className="flex items-start max-w-3xl space-x-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center text-white text-sm font-bold shadow-sm flex-shrink-0">
          <Bot className="w-5 h-5" />
        </div>

        <div className="space-y-3 flex-1">
          {/* Answer Card */}
          <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-none p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-gray-100 pb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center space-x-1">
                <ShieldCheck className="w-3.5 h-3.5 text-primary-600 inline mr-1" />
                VisionRAG-X Verified Response
              </span>
              {message.confidence !== undefined && (
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                  Confidence: {(message.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>

            <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
              {renderTextWithTimestamps(message.content)}
            </div>

            {/* Conflicts list */}
            {message.conflicts && message.conflicts.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-gray-100">
                {message.conflicts.map((conflict, i) => (
                  <ConflictBadge key={i} conflict={conflict} />
                ))}
              </div>
            )}
          </div>

          {/* Evidence Drawer Toggle */}
          {message.evidence && message.evidence.length > 0 && (
            <div className="space-y-2">
              <button
                onClick={() => setShowEvidence(!showEvidence)}
                className="flex items-center space-x-2 text-xs font-medium text-primary-600 hover:text-primary-800 bg-primary-50 hover:bg-primary-100 px-3 py-1.5 rounded-lg border border-primary-200 transition-colors"
              >
                <FileText className="w-3.5 h-3.5" />
                <span>
                  {showEvidence ? 'Hide' : 'View'} Provenance Evidence ({message.evidence.length} items)
                </span>
                {showEvidence ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {showEvidence && (
                <div className="grid gap-2 grid-cols-1 sm:grid-cols-2 pt-1 animate-fade-in">
                  {message.evidence.map((item, idx) => (
                    <EvidenceCard key={idx} evidence={item} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
