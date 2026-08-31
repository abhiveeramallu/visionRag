import React from 'react'
import { CheckCircle2, Clock, AlertTriangle, Loader2, FileCheck, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

const STEPS = [
  { key: 'Downloading', label: 'Download / Load Material' },
  { key: 'Extracting audio and frames', label: 'Extract Audio & Video Frames' },
  { key: 'Transcribing audio (ASR)', label: 'WhisperX ASR Transcription' },
  { key: 'Running OCR', label: 'PaddleOCR Vision & Document Extraction' },
  { key: 'Aligning modalities', label: 'Multimodal Temporal/Page Alignment' },
  { key: 'Creating knowledge units', label: 'VKEG Knowledge Units & Conflict Detection' },
  { key: 'Indexing knowledge units', label: 'Qdrant Hybrid Vector Indexing' },
]

export default function ProcessingStatus({ jobStatus, sourceId }) {
  if (!jobStatus) return null

  const isCompleted = jobStatus.status === 'completed'
  const isFailed = jobStatus.status === 'failed'
  const progressPercent = Math.round((jobStatus.progress || 0) * 100)

  return (
    <div className="card space-y-6">
      <div className="flex items-center justify-between border-b border-gray-100 pb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-900 flex items-center space-x-2">
            {isCompleted ? (
              <CheckCircle2 className="w-5 h-5 text-green-500" />
            ) : isFailed ? (
              <AlertTriangle className="w-5 h-5 text-red-500" />
            ) : (
              <Loader2 className="w-5 h-5 text-primary-600 animate-spin" />
            )}
            <span>Processing Educational Material</span>
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">Source ID: {jobStatus.source_id || sourceId}</p>
        </div>

        <div className="text-right">
          <span
            className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase ${
              isCompleted
                ? 'bg-green-100 text-green-800'
                : isFailed
                ? 'bg-red-100 text-red-800'
                : 'bg-primary-100 text-primary-800'
            }`}
          >
            {jobStatus.status}
          </span>
          <p className="text-xs text-gray-500 mt-1 font-mono">{progressPercent}%</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden shadow-inner">
          <div
            className={`h-3 rounded-full transition-all duration-500 ${
              isCompleted
                ? 'bg-green-500'
                : isFailed
                ? 'bg-red-500'
                : 'bg-gradient-to-r from-primary-500 to-accent-500 progress-animated'
            }`}
            style={{ width: `${Math.max(5, progressPercent)}%` }}
          ></div>
        </div>
        <p className="text-xs font-medium text-gray-700">
          Current Step: <span className="text-primary-600 font-semibold">{jobStatus.current_step || 'Initializing...'}</span>
        </p>
      </div>

      {/* Error Message */}
      {isFailed && (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-800 text-xs space-y-1">
          <p className="font-bold flex items-center space-x-1">
            <AlertTriangle className="w-4 h-4 text-red-600 inline mr-1" />
            <span>Processing Failed</span>
          </p>
          <p className="font-mono text-red-700">{jobStatus.error || 'An unexpected error occurred.'}</p>
        </div>
      )}

      {/* Step Breakdown */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Pipeline Steps</p>
        <div className="space-y-1.5">
          {STEPS.map((step, idx) => {
            const isDone = isCompleted || progressPercent > (idx + 1) * 14
            const isCurrent = jobStatus.current_step && jobStatus.current_step.includes(step.key.split(' ')[0])
            return (
              <div
                key={step.key}
                className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-xs transition-colors ${
                  isDone
                    ? 'bg-green-50 text-green-900 font-medium'
                    : isCurrent
                    ? 'bg-primary-50 text-primary-900 border border-primary-200 font-semibold'
                    : 'bg-gray-50 text-gray-400'
                }`}
              >
                {isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0" />
                ) : isCurrent ? (
                  <Loader2 className="w-4 h-4 text-primary-600 animate-spin flex-shrink-0" />
                ) : (
                  <Clock className="w-4 h-4 text-gray-300 flex-shrink-0" />
                )}
                <span>{step.label}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Complete Action Buttons */}
      {isCompleted && (
        <div className="pt-4 border-t border-gray-100 flex flex-col sm:flex-row gap-3">
          <Link
            to={`/chat/${sourceId}`}
            className="flex-1 btn-primary py-2.5 flex items-center justify-center space-x-2 text-sm font-semibold shadow-sm"
          >
            <span>Start Learning with AI Chat</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to={`/knowledge/${sourceId}`}
            className="btn-secondary py-2.5 px-4 flex items-center justify-center space-x-2 text-sm font-medium"
          >
            <FileCheck className="w-4 h-4" />
            <span>View VKEG Knowledge Graph</span>
          </Link>
        </div>
      )}
    </div>
  )
}
