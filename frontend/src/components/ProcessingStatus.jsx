import React from 'react'
import { CheckCircle2, Loader2, AlertTriangle, Clock, ArrowRight, FileCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

const STEPS = [
  { label: 'Source received' },
  { label: 'Audio extraction' },
  { label: 'Frame extraction' },
  { label: 'Speech recognition' },
  { label: 'OCR analysis' },
  { label: 'Visual analysis' },
  { label: 'Cross-modal verification' },
  { label: 'Knowledge graph construction' },
  { label: 'Indexing' },
  { label: 'Ready' },
]

export default function ProcessingStatus({ jobStatus, sourceId }) {
  if (!jobStatus) return null

  const isCompleted = jobStatus.status === 'completed'
  const isFailed = jobStatus.status === 'failed'
  const progressPercent = Math.round((jobStatus.progress || 0) * 100)
  const activeStepIndex = isCompleted
    ? STEPS.length - 1
    : Math.min(STEPS.length - 2, Math.floor((progressPercent / 100) * (STEPS.length - 1)))

  return (
    <div className="card space-y-8">
      <div className="text-center space-y-1.5">
        <h2 className="text-xl font-extrabold text-ink-900">
          {isFailed ? 'Processing hit a snag' : isCompleted ? 'Your material is ready' : 'Building verified knowledge...'}
        </h2>
        <p className="text-sm text-ink-500">
          {isFailed
            ? 'We could not finish processing this source.'
            : isCompleted
            ? 'All modalities extracted, cross-verified, and indexed.'
            : 'Extracting, verifying, and linking evidence across every modality.'}
        </p>
      </div>

      <div className="space-y-2">
        <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-2.5 rounded-full transition-all duration-500 ${
              isFailed ? 'bg-red-500' : isCompleted ? 'bg-green-500' : 'bg-primary-500 progress-animated'
            }`}
            style={{ width: `${Math.max(4, progressPercent)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-ink-500">
          <span>{jobStatus.current_step || 'Initializing...'}</span>
          <span className="font-mono font-semibold">{progressPercent}%</span>
        </div>
      </div>

      {isFailed && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs space-y-1">
          <p className="font-bold flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4" />
            Processing failed
          </p>
          <p className="font-mono text-red-700">{jobStatus.error || 'An unexpected error occurred.'}</p>
        </div>
      )}

      {/* Visual step timeline */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-y-5 gap-x-2">
        {STEPS.map((step, idx) => {
          const done = isCompleted || idx < activeStepIndex
          const current = !isCompleted && idx === activeStepIndex && !isFailed
          return (
            <div key={step.label} className="flex flex-col items-center text-center gap-2">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 border-2 ${
                  done
                    ? 'bg-green-500 border-green-500 text-white'
                    : current
                    ? 'bg-primary-50 border-primary-500 text-primary-600'
                    : 'bg-gray-50 border-gray-200 text-gray-300'
                }`}
              >
                {done ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : current ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Clock className="w-4 h-4" />
                )}
              </div>
              <span className={`text-[11px] leading-tight ${done || current ? 'text-ink-800 font-medium' : 'text-ink-400'}`}>
                {step.label}
              </span>
            </div>
          )
        })}
      </div>

      {isCompleted && (
        <div className="pt-4 border-t border-gray-100 flex flex-col sm:flex-row gap-3">
          <Link
            to={`/source/${sourceId}`}
            className="flex-1 btn-primary py-2.5 flex items-center justify-center gap-2 text-sm font-semibold"
          >
            <span>Start Learning</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to={`/knowledge/${sourceId}`}
            className="btn-secondary py-2.5 px-4 flex items-center justify-center gap-2 text-sm font-medium"
          >
            <FileCheck className="w-4 h-4" />
            <span>View Knowledge Units</span>
          </Link>
        </div>
      )}
    </div>
  )
}
