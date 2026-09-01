import React from 'react'
import { AlertTriangle, Eye, GitCompare } from 'lucide-react'

/**
 * Shown instead of a confident answer when evidence conflicts and the system
 * cannot resolve which version is correct — VisionRAG-X never invents an
 * answer in this case.
 */
export default function ConflictCompare({ conflict, onViewEvidence, onCompareSources }) {
  const claims = conflict?.claims || []
  const versionA = claims[0] || 'Version A'
  const versionB = claims[1] || 'Version B'
  const sources = conflict?.sources || ['Speech', 'Whiteboard']

  return (
    <div className="border border-amber-200 bg-amber-50 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2 text-amber-900 font-bold text-sm">
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        <span>Conflicting evidence detected</span>
      </div>

      <div className="grid sm:grid-cols-2 gap-2.5">
        <div className="bg-white rounded-lg border border-amber-200 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-400 mb-1">{sources[0] || 'Source A'}</p>
          <p className="text-xs text-ink-800 font-mono leading-relaxed">{versionA}</p>
        </div>
        <div className="bg-white rounded-lg border border-amber-200 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-400 mb-1">{sources[1] || 'Source B'}</p>
          <p className="text-xs text-ink-800 font-mono leading-relaxed">{versionB}</p>
        </div>
      </div>

      <p className="text-xs text-amber-900 leading-relaxed">
        VisionRAG-X could not confidently determine the correct version.
      </p>

      <div className="flex gap-2 pt-1">
        <button
          onClick={onViewEvidence}
          className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5"
        >
          <Eye className="w-3.5 h-3.5" />
          View evidence
        </button>
        <button
          onClick={onCompareSources}
          className="btn-outline py-1.5 px-3 text-xs flex items-center gap-1.5"
        >
          <GitCompare className="w-3.5 h-3.5" />
          Compare sources
        </button>
      </div>
    </div>
  )
}
