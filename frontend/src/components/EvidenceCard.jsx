import React, { useState } from 'react'
import { Clock, FileText, Code, Eye, Calculator, ChevronDown, ChevronUp } from 'lucide-react'

export default function EvidenceCard({ evidence }) {
  const [expanded, setExpanded] = useState(false)

  const getModalityBadge = (modality) => {
    const mod = (modality || '').toLowerCase()
    switch (mod) {
      case 'asr':
        return { label: 'ASR Audio', bg: 'bg-blue-100 text-blue-800 border-blue-200', icon: Clock }
      case 'ocr':
        return { label: 'OCR Text', bg: 'bg-green-100 text-green-800 border-green-200', icon: FileText }
      case 'vision':
        return { label: 'Vision Scene', bg: 'bg-purple-100 text-purple-800 border-purple-200', icon: Eye }
      case 'formula':
        return { label: 'Formula', bg: 'bg-orange-100 text-orange-800 border-orange-200', icon: Calculator }
      case 'code':
        return { label: 'Code', bg: 'bg-gray-100 text-gray-800 border-gray-200', icon: Code }
      default:
        return { label: mod.toUpperCase() || 'Text', bg: 'bg-gray-100 text-gray-700 border-gray-200', icon: FileText }
    }
  }

  const badge = getModalityBadge(evidence.modality)
  const Icon = badge.icon
  const confidencePercent = Math.round((evidence.confidence || 0.5) * 100)

  const formatLocation = () => {
    if (evidence.timestamp_start !== undefined && evidence.timestamp_start !== null) {
      const m = Math.floor(evidence.timestamp_start / 60)
      const s = Math.floor(evidence.timestamp_start % 60)
      return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    }
    if (evidence.page) return `Page ${evidence.page}`
    if (evidence.slide) return `Slide ${evidence.slide}`
    return 'Document'
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-3 shadow-xs hover:shadow-sm transition-shadow space-y-2 text-xs">
      <div className="flex items-center justify-between">
        <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-md border text-[11px] font-semibold ${badge.bg}`}>
          <Icon className="w-3 h-3" />
          <span>{badge.label}</span>
        </span>

        <span className="font-mono text-gray-500 font-medium">
          📍 {formatLocation()}
        </span>
      </div>

      <p className={`text-gray-700 leading-relaxed font-sans ${expanded ? '' : 'line-clamp-2'}`}>
        "{evidence.text || evidence.content}"
      </p>

      <div className="flex items-center justify-between pt-1 border-t border-gray-100 text-[11px] text-gray-500">
        <div className="flex items-center space-x-2">
          <span>Confidence:</span>
          <div className="w-12 bg-gray-200 rounded-full h-1.5 overflow-hidden inline-block">
            <div
              className={`h-1.5 rounded-full ${
                confidencePercent > 80 ? 'bg-green-500' : confidencePercent > 60 ? 'bg-yellow-500' : 'bg-red-500'
              }`}
              style={{ width: `${confidencePercent}%` }}
            ></div>
          </div>
          <span className="font-mono font-semibold">{confidencePercent}%</span>
        </div>

        {(evidence.text || evidence.content || '').length > 80 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-primary-600 hover:text-primary-800 font-medium flex items-center space-x-0.5"
          >
            <span>{expanded ? 'Less' : 'More'}</span>
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        )}
      </div>
    </div>
  )
}
