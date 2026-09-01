import React from 'react'
import { useNavigate } from 'react-router-dom'
import { History, ArrowDown, AlertTriangle, CheckCircle2, XCircle, ArrowLeft } from 'lucide-react'
import { mockGradientDescentEvolution, formatTimestamp } from '../data/mockData'
import DemoDataBadge from '../components/DemoDataBadge'

export default function KnowledgeEvolution() {
  const navigate = useNavigate()
  const data = mockGradientDescentEvolution
  const [v1, v2] = data.versions
  const cmp = data.evidence_comparison

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-8">
      <div className="flex items-center justify-between flex-wrap gap-3 border-b border-gray-200 pb-4">
        <div>
          <button onClick={() => navigate(-1)} className="text-xs text-ink-500 hover:text-primary-600 flex items-center gap-1 mb-2">
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </button>
          <h1 className="text-2xl font-extrabold text-ink-900 flex items-center gap-2">
            <History className="w-6 h-6 text-primary-600" />
            Knowledge Evolution
          </h1>
          <p className="text-sm text-ink-500 mt-1">
            {data.concept} &middot; {data.source_title}
          </p>
        </div>
        <DemoDataBadge label="Demo evolution graph" />
      </div>

      {/* Version timeline */}
      <div className="card p-8 space-y-0">
        <div className="text-center">
          <span className="inline-block text-[11px] font-semibold uppercase tracking-wider text-ink-400 mb-3">
            {data.concept}
          </span>
        </div>

        {/* Version 1 */}
        <div className="border-2 border-red-200 bg-red-50/50 rounded-2xl p-5 max-w-md mx-auto text-center space-y-2">
          <span className="badge-red inline-flex items-center gap-1">
            <XCircle className="w-3 h-3" /> Superseded
          </span>
          <p className="text-xs font-semibold text-ink-500">Version {v1.version}</p>
          <p className="font-mono text-xl font-bold text-ink-800">{v1.content}</p>
          <p className="text-xs text-ink-500 flex items-center justify-center gap-1">
            {formatTimestamp(v1.timestamp_start)} &middot; {Math.round(v1.confidence * 100)}% confidence
          </p>
        </div>

        <div className="flex flex-col items-center py-3">
          <ArrowDown className="w-5 h-5 text-ink-300" />
        </div>

        {/* Correction detected */}
        <div className="max-w-md mx-auto">
          <div className="flex items-center gap-2 justify-center bg-amber-50 border border-amber-200 text-amber-900 rounded-xl px-4 py-2.5 text-xs font-semibold">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            Correction detected at {formatTimestamp(data.correction_detected_at)}
          </div>
        </div>

        <div className="flex flex-col items-center py-3">
          <ArrowDown className="w-5 h-5 text-ink-300" />
        </div>

        {/* Version 2 */}
        <div className="border-2 border-green-300 bg-green-50/50 rounded-2xl p-5 max-w-md mx-auto text-center space-y-2 shadow-sm">
          <span className="badge-green inline-flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Verified
          </span>
          <p className="text-xs font-semibold text-ink-500">Version {v2.version}</p>
          <p className="font-mono text-xl font-bold text-ink-900">{v2.content}</p>
          <p className="text-xs text-ink-500">
            {formatTimestamp(v2.timestamp_start)} &middot; {Math.round(v2.confidence * 100)}% confidence
          </p>
          {v2.correction_reason && (
            <p className="text-xs text-ink-600 pt-2 border-t border-green-200 leading-relaxed">
              {v2.correction_reason}
            </p>
          )}
        </div>
      </div>

      {/* Why this version was selected */}
      <div className="card space-y-4">
        <h2 className="text-sm font-bold text-ink-900">Why the newer version was selected</h2>

        <div className="grid sm:grid-cols-2 gap-3">
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-1">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Speech (ASR)</p>
            <p className="text-sm font-mono text-ink-800">{cmp.speech.text}</p>
            <p className="text-xs text-ink-500">Confidence: {Math.round(cmp.speech.confidence * 100)}%</p>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-1">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Whiteboard (OCR)</p>
            <p className="text-sm font-mono text-ink-800">{cmp.whiteboard.text}</p>
            <p className="text-xs text-ink-500">Confidence: {Math.round(cmp.whiteboard.confidence * 100)}%</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-100">
          <div className="text-center">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Visual Consistency</p>
            <p className="text-lg font-bold text-green-700 mt-1">{cmp.visual_consistency}</p>
          </div>
          <div className="text-center">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Final Confidence</p>
            <p className="text-lg font-bold text-primary-700 mt-1">{Math.round(cmp.final_confidence * 100)}%</p>
          </div>
        </div>
      </div>
    </div>
  )
}
