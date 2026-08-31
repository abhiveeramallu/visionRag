import React, { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp, ShieldAlert } from 'lucide-react'

export default function ConflictBadge({ conflict }) {
  const [expanded, setExpanded] = useState(false)

  const getSeverityStyle = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'high':
        return 'bg-red-50 border-red-300 text-red-900'
      case 'medium':
        return 'bg-yellow-50 border-yellow-300 text-yellow-900'
      default:
        return 'bg-orange-50 border-orange-200 text-orange-800'
    }
  }

  return (
    <div className={`border rounded-xl p-3 text-xs space-y-2 ${getSeverityStyle(conflict.severity)}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2 font-bold">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span>Cross-Modal Conflict Detected ({conflict.conflict_type || 'Disagreement'})</span>
        </div>

        <div className="flex items-center space-x-2">
          <span className="px-2 py-0.5 rounded text-[10px] uppercase font-mono font-bold bg-white/70 border border-current">
            {conflict.severity || 'medium'} severity
          </span>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1 hover:bg-black/5 rounded transition-colors"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      <p className="text-[11px] opacity-90">
        The system detected contradicting claims between sources ({conflict.sources?.join(' vs ') || 'ASR vs OCR'}).
      </p>

      {expanded && conflict.claims && conflict.claims.length > 0 && (
        <div className="mt-2 pt-2 border-t border-current/20 space-y-1.5 font-mono text-[11px] animate-fade-in">
          {conflict.claims.map((claim, idx) => (
            <div key={idx} className="bg-white/80 p-2 rounded border border-current/10">
              <span className="font-semibold text-gray-700">Claim {idx + 1}: </span>
              <span className="text-gray-900">{claim}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
