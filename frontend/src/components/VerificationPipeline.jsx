import React from 'react'
import { ArrowRight, ShieldCheck } from 'lucide-react'

const NORMAL_RAG = ['Raw Content', 'Retrieve', 'Generate']
const VISIONRAG_X = [
  'Multimodal Extraction',
  'Conflict Detection',
  'Knowledge Verification',
  'Knowledge Evolution',
  'Hybrid Retrieval',
  'Evidence-based Generation',
]

export default function VerificationPipeline({ compact = false }) {
  return (
    <div className={compact ? 'space-y-3' : 'card space-y-5'}>
      <div className="flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-primary-600" />
        <h3 className={compact ? 'text-xs font-bold text-ink-900' : 'text-sm font-bold text-ink-900'}>
          Verified Knowledge, not just Retrieval
        </h3>
      </div>

      <div className="space-y-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-400 mb-1.5">Normal RAG</p>
          <div className="flex flex-wrap items-center gap-1.5">
            {NORMAL_RAG.map((step, i) => (
              <React.Fragment key={step}>
                <span className="px-2.5 py-1 rounded-lg bg-gray-100 text-ink-600 text-[11px] font-medium">
                  {step}
                </span>
                {i < NORMAL_RAG.length - 1 && <ArrowRight className="w-3 h-3 text-gray-300" />}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-primary-600 mb-1.5">VisionRAG-X</p>
          <div className="flex flex-wrap items-center gap-1.5">
            {VISIONRAG_X.map((step, i) => (
              <React.Fragment key={step}>
                <span className="px-2.5 py-1 rounded-lg bg-primary-50 text-primary-800 text-[11px] font-semibold border border-primary-100">
                  {step}
                </span>
                {i < VISIONRAG_X.length - 1 && <ArrowRight className="w-3 h-3 text-primary-300" />}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
