import React from 'react'
import {
  CheckCircle2,
  Loader2,
  AlertTriangle,
  Clock,
  ArrowRight,
  FileCheck,
  RotateCw,
  TimerOff,
} from 'lucide-react'
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

export default function ProcessingStatus({
  jobStatus,
  sourceId,
  isStalled = false,
  onRetry = null,
  isRetrying = false,
}) {
  if (!jobStatus) return null

  const isCompleted = jobStatus.status === 'completed'
  const isFailed = jobStatus.status === 'failed'
  const isTimedOut = jobStatus.status === 'timed_out'
  const progressPercent = Math.round((jobStatus.progress || 0) * 100)
  const activeStepIndex = isCompleted
    ? STEPS.length - 1
    : Math.min(STEPS.length - 2, Math.floor((progressPercent / 100) * (STEPS.length - 1)))

  const formatElapsed = (sec) => {
    if (!sec || sec < 0) return '0s'
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  return (
    <div className="card space-y-8">
      <div className="text-center space-y-1.5">
        <h2 className="text-xl font-extrabold text-ink-900">
          {isCompleted
            ? 'Your material is ready'
            : isTimedOut
            ? 'Processing timed out'
            : isFailed
            ? 'Processing hit a snag'
            : isStalled
            ? 'Processing appears stalled'
            : 'Building verified knowledge...'}
        </h2>
        <p className="text-sm text-ink-500">
          {isCompleted
            ? 'All modalities extracted, cross-verified, and indexed.'
            : isTimedOut
            ? 'A processing stage took longer than expected. You can retry with one click.'
            : isFailed
            ? 'We could not finish processing this source. Click below to retry.'
            : isStalled
            ? 'No progress updates in over 90 seconds. The background task may have been interrupted.'
            : 'Extracting, verifying, and linking evidence across every modality.'}
        </p>
      </div>

      <div className="space-y-2">
        <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-2.5 rounded-full transition-all duration-500 ${
              isFailed || isTimedOut
                ? 'bg-red-500'
                : isCompleted
                ? 'bg-green-500'
                : isStalled
                ? 'bg-amber-500'
                : 'bg-primary-500 progress-animated'
            }`}
            style={{ width: `${Math.max(4, progressPercent)}%` }}
          />
        </div>
        <div className="flex justify-between items-center text-xs text-ink-500">
          <span className="font-medium text-ink-700">{jobStatus.current_step || 'Initializing...'}</span>
          <div className="flex items-center gap-3">
            {jobStatus.elapsed_seconds !== undefined && (
              <span className="text-ink-400">Elapsed: {formatElapsed(jobStatus.elapsed_seconds)}</span>
            )}
            <span className="font-mono font-semibold text-ink-800">{progressPercent}%</span>
          </div>
        </div>
      </div>

      {/* Stalled warning banner */}
      {isStalled && !isCompleted && !isFailed && !isTimedOut && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="space-y-0.5">
            <p className="font-bold flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              Heartbeat warning
            </p>
            <p className="text-amber-700">
              Last server heartbeat was {Math.round(jobStatus.last_heartbeat_seconds_ago || 90)}s ago.
            </p>
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              disabled={isRetrying}
              className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5 font-semibold bg-white hover:bg-amber-100 border-amber-300 text-amber-900"
            >
              {isRetrying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCw className="w-3.5 h-3.5" />}
              Restart Ingestion
            </button>
          )}
        </div>
      )}

      {/* Failed banner */}
      {isFailed && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs space-y-3">
          <div className="space-y-1">
            <p className="font-bold flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-red-600" />
              Processing failed
            </p>
            <p className="font-mono text-red-700">{jobStatus.error || 'An unexpected error occurred during ingestion.'}</p>
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              disabled={isRetrying}
              className="py-2 px-4 rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700 disabled:opacity-50 text-xs flex items-center gap-1.5 transition-colors"
            >
              {isRetrying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCw className="w-3.5 h-3.5" />}
              Retry Ingestion
            </button>
          )}
        </div>
      )}

      {/* Timed out banner */}
      {isTimedOut && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs space-y-3">
          <div className="space-y-1">
            <p className="font-bold flex items-center gap-1.5">
              <TimerOff className="w-4 h-4 text-rose-600" />
              Stage timeout
            </p>
            <p className="text-rose-700">{jobStatus.error || 'A processing stage exceeded its time limit.'}</p>
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              disabled={isRetrying}
              className="py-2 px-4 rounded-lg bg-rose-600 text-white font-semibold hover:bg-rose-700 disabled:opacity-50 text-xs flex items-center gap-1.5 transition-colors"
            >
              {isRetrying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCw className="w-3.5 h-3.5" />}
              Retry Ingestion
            </button>
          )}
        </div>
      )}

      {/* Visual step timeline */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-y-5 gap-x-2">
        {STEPS.map((step, idx) => {
          const done = isCompleted || idx < activeStepIndex
          const current = !isCompleted && idx === activeStepIndex && !isFailed && !isTimedOut
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
