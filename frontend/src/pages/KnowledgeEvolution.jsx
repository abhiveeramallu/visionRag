import React, { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { History, ArrowDown, AlertTriangle, CheckCircle2, XCircle, ArrowLeft, Loader2 } from 'lucide-react'
import { mockGradientDescentEvolution, formatTimestamp } from '../data/mockData'
import DemoDataBadge from '../components/DemoDataBadge'
import { getSourceEvolution, getSource, getKnowledgeUnitEvidence } from '../services/api'

const STATUS_META = {
  superseded: { badge: 'badge-red', icon: XCircle, label: 'Superseded', border: 'border-red-200 bg-red-50/50', text: 'text-ink-800' },
  verified: { badge: 'badge-green', icon: CheckCircle2, label: 'Verified', border: 'border-green-300 bg-green-50/50 shadow-sm', text: 'text-ink-900' },
  active: { badge: 'badge-blue', icon: History, label: 'Active', border: 'border-blue-200 bg-blue-50/50', text: 'text-ink-900' },
  disputed: { badge: 'badge-yellow', icon: AlertTriangle, label: 'Disputed', border: 'border-yellow-300 bg-yellow-50/50', text: 'text-ink-900' },
}

function RealEvolution({ chain, evidenceByVersion }) {
  const versions = chain.versions
  return (
    <>
      <div className="card p-8 space-y-0">
        <div className="text-center">
          <span className="inline-block text-[11px] font-semibold uppercase tracking-wider text-ink-400 mb-3">
            {chain.concept}
          </span>
        </div>

        {versions.map((v, i) => {
          const meta = STATUS_META[v.status] || STATUS_META.active
          const Icon = meta.icon
          return (
            <React.Fragment key={v.id}>
              <div className={`border-2 ${meta.border} rounded-2xl p-5 max-w-md mx-auto text-center space-y-2`}>
                <span className={`${meta.badge} inline-flex items-center gap-1`}>
                  <Icon className="w-3 h-3" /> {meta.label}
                </span>
                <p className="text-xs font-semibold text-ink-500">Version {v.version}</p>
                <p className={`font-mono text-lg font-bold ${meta.text}`}>{v.content}</p>
                <p className="text-xs text-ink-500 flex items-center justify-center gap-1">
                  {v.page ? `Page ${v.page}` : formatTimestamp(v.timestamp_start)} &middot; {Math.round((v.confidence || 0) * 100)}% confidence
                </p>
                {v.correction_reason && (
                  <p className="text-xs text-ink-600 pt-2 border-t border-current/20 leading-relaxed">
                    {v.correction_reason}
                  </p>
                )}
              </div>
              {i < versions.length - 1 && (
                <div className="flex flex-col items-center py-3">
                  <ArrowDown className="w-5 h-5 text-ink-300" />
                </div>
              )}
            </React.Fragment>
          )
        })}
      </div>

      <div className="card space-y-4">
        <h2 className="text-sm font-bold text-ink-900">Verified evidence behind the latest version</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          {(evidenceByVersion[versions[versions.length - 1].id] || []).map((e) => (
            <div key={e.id} className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">{(e.modality || 'text').toUpperCase()}</p>
              <p className="text-sm font-mono text-ink-800 line-clamp-3">{e.text}</p>
              <p className="text-xs text-ink-500">Confidence: {Math.round((e.confidence || 0) * 100)}%</p>
            </div>
          ))}
          {(evidenceByVersion[versions[versions.length - 1].id] || []).length === 0 && (
            <p className="text-xs text-ink-400 col-span-2 text-center py-4">No separate evidence segments recorded for this version.</p>
          )}
        </div>
      </div>
    </>
  )
}

function MockEvolution() {
  const data = mockGradientDescentEvolution
  const [v1, v2] = data.versions
  const cmp = data.evidence_comparison
  return (
    <>
      <div className="card p-8 space-y-0">
        <div className="text-center">
          <span className="inline-block text-[11px] font-semibold uppercase tracking-wider text-ink-400 mb-3">
            {data.concept}
          </span>
        </div>

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

        <div className="max-w-md mx-auto">
          <div className="flex items-center gap-2 justify-center bg-amber-50 border border-amber-200 text-amber-900 rounded-xl px-4 py-2.5 text-xs font-semibold">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            Correction detected at {formatTimestamp(data.correction_detected_at)}
          </div>
        </div>

        <div className="flex flex-col items-center py-3">
          <ArrowDown className="w-5 h-5 text-ink-300" />
        </div>

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
    </>
  )
}

export default function KnowledgeEvolution() {
  const navigate = useNavigate()
  const { conceptId: sourceId } = useParams() // route param is a real source id when reached from real pages
  const [loading, setLoading] = useState(!!sourceId)
  const [chain, setChain] = useState(null)
  const [evidenceByVersion, setEvidenceByVersion] = useState({})
  const [sourceTitle, setSourceTitle] = useState('')
  const [usingDemo, setUsingDemo] = useState(!sourceId)

  useEffect(() => {
    if (!sourceId) return
    let cancelled = false

    async function load() {
      try {
        const [chains, source] = await Promise.all([
          getSourceEvolution(sourceId),
          getSource(sourceId),
        ])
        if (cancelled) return
        if (!chains || chains.length === 0) {
          setUsingDemo(true)
          setLoading(false)
          return
        }
        const firstChain = chains[0]
        setChain(firstChain)
        setSourceTitle(source?.title || '')

        const latest = firstChain.versions[firstChain.versions.length - 1]
        const evidence = await getKnowledgeUnitEvidence(latest.id).catch(() => [])
        if (!cancelled) {
          setEvidenceByVersion({ [latest.id]: evidence })
          setUsingDemo(false)
          setLoading(false)
        }
      } catch {
        if (!cancelled) {
          setUsingDemo(true)
          setLoading(false)
        }
      }
    }

    load()
    return () => { cancelled = true }
  }, [sourceId])

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
            {usingDemo ? `${mockGradientDescentEvolution.concept} · ${mockGradientDescentEvolution.source_title}` : `${chain?.concept || ''} · ${sourceTitle}`}
          </p>
        </div>
        <DemoDataBadge label={usingDemo ? 'Demo evolution graph' : 'Real correction chain'} className={usingDemo ? '' : 'bg-green-50 text-green-700 border-green-200'} />
      </div>

      {loading ? (
        <div className="card flex items-center justify-center gap-2 py-16 text-ink-400 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading version history...
        </div>
      ) : usingDemo ? (
        <MockEvolution />
      ) : (
        <RealEvolution chain={chain} evidenceByVersion={evidenceByVersion} />
      )}
    </div>
  )
}
