import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Youtube, FileVideo, Music, FileText, Layers, Image as ImageIcon,
  ArrowRight, Loader2, ShieldCheck, Trash2, Check, X,
} from 'lucide-react'
import { formatDuration } from '../data/mockData'
import { deleteSource } from '../services/api'

const TYPE_META = {
  youtube: { icon: Youtube, label: 'YouTube Video', color: 'text-red-600 bg-red-50' },
  video: { icon: FileVideo, label: 'Video', color: 'text-purple-600 bg-purple-50' },
  audio: { icon: Music, label: 'Audio', color: 'text-blue-600 bg-blue-50' },
  pdf: { icon: FileText, label: 'PDF', color: 'text-rose-600 bg-rose-50' },
  ppt: { icon: Layers, label: 'PPT / PPTX', color: 'text-orange-600 bg-orange-50' },
  image: { icon: ImageIcon, label: 'Image', color: 'text-emerald-600 bg-emerald-50' },
}

export default function SourceCard({ source, onDeleted }) {
  const meta = TYPE_META[source.source_type] || TYPE_META.pdf
  const Icon = meta.icon
  const isProcessing = source.status && source.status !== 'completed' && source.status !== 'failed'
  const confidence = source.confidence ?? source.metadata?.confidence
  const knowledgeUnits = source.knowledge_units ?? source.metadata?.knowledge_units

  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  const handleDelete = async () => {
    setDeleting(true)
    setError('')
    try {
      await deleteSource(source.id)
      onDeleted?.(source.id)
    } catch (err) {
      setError(err.message || 'Failed to delete')
      setDeleting(false)
      setConfirming(false)
    }
  }

  return (
    <div className="card p-5 flex flex-col gap-3 hover:shadow-md hover:border-primary-200 transition-all relative">
      <div className="flex items-start justify-between">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${meta.color}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex items-center gap-1.5">
          {isProcessing ? (
            <span className="badge bg-primary-50 text-primary-700 flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" /> Processing
            </span>
          ) : source.status === 'failed' ? (
            <span className="badge-red">Failed</span>
          ) : (
            <span className="badge-green flex items-center gap-1">
              <ShieldCheck className="w-3 h-3" /> Processed
            </span>
          )}

          {onDeleted && !confirming && (
            <button
              onClick={() => setConfirming(true)}
              title="Delete source"
              className="p-1 rounded-md text-ink-300 hover:text-red-600 hover:bg-red-50 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {confirming ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 py-4">
          <p className="text-xs text-ink-700 font-medium px-2">
            Delete "{source.title}" and all its knowledge units? This cannot be undone.
          </p>
          {error && <p className="text-[11px] text-red-600">{error}</p>}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setConfirming(false)}
              disabled={deleting}
              className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1"
            >
              <X className="w-3.5 h-3.5" /> Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="py-1.5 px-3 text-xs font-semibold rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 flex items-center gap-1"
            >
              {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              Delete
            </button>
          </div>
        </div>
      ) : (
        <>
          <div>
            <h3 className="font-bold text-ink-900 text-sm leading-snug line-clamp-2">{source.title}</h3>
            <p className="text-xs text-ink-500 mt-1">{meta.label}</p>
          </div>

          <div className="flex items-center gap-3 text-xs text-ink-500">
            {source.duration ? <span>{formatDuration(source.duration)}</span> : null}
            {source.num_pages ? <span>{source.num_pages} pages</span> : null}
            {knowledgeUnits !== undefined && knowledgeUnits !== null && (
              <span>{knowledgeUnits} knowledge units</span>
            )}
          </div>

          {confidence !== undefined && confidence !== null && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-[11px] text-ink-500">
                <span>Confidence</span>
                <span className="font-semibold text-ink-700">{Math.round(confidence * 100)}%</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-1.5 rounded-full ${confidence > 0.85 ? 'bg-green-500' : confidence > 0.65 ? 'bg-yellow-500' : 'bg-red-500'}`}
                  style={{ width: `${Math.round(confidence * 100)}%` }}
                />
              </div>
            </div>
          )}

          <Link
            to={isProcessing ? `/processing/${source.id}` : `/source/${source.id}`}
            className="mt-1 btn-secondary py-2 text-xs font-semibold flex items-center justify-center gap-1.5"
          >
            {isProcessing ? 'View Progress' : 'Open'}
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </>
      )}
    </div>
  )
}
