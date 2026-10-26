import React, { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Database, Search, Filter, ShieldCheck, AlertTriangle, History,
  FileText, Code, CheckCircle, ChevronRight, Layers, ExternalLink,
  Loader2, Sparkles, BookOpen, Clock, AlertCircle, RefreshCw
} from 'lucide-react'
import { getKnowledgeUnits, getKnowledgeUnitDetail, getSources } from '../services/api'
import { formatTimestamp } from '../data/mockData'

const MODALITIES = [
  { id: 'all', label: 'All Modalities' },
  { id: 'ocr', label: 'OCR (Slides)' },
  { id: 'asr', label: 'ASR (Speech)' },
  { id: 'formula', label: 'Formula' },
  { id: 'code', label: 'Code' },
  { id: 'diagram', label: 'Diagram / Vision' },
]

const STATUSES = [
  { id: 'all', label: 'All Statuses' },
  { id: 'verified', label: 'Verified' },
  { id: 'active', label: 'Active' },
  { id: 'superseded', label: 'Superseded' },
  { id: 'disputed', label: 'Disputed' },
]

function ModalityBadge({ modality }) {
  const mod = (modality || 'text').toLowerCase()
  const styles = {
    formula: 'bg-purple-50 text-purple-700 border-purple-200',
    code: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    asr: 'bg-blue-50 text-blue-700 border-blue-200',
    ocr: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    diagram: 'bg-amber-50 text-amber-700 border-amber-200',
    vision: 'bg-amber-50 text-amber-700 border-amber-200',
    text: 'bg-gray-50 text-gray-700 border-gray-200',
  }
  const cls = styles[mod] || styles.text
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border uppercase tracking-wide ${cls}`}>
      {mod}
    </span>
  )
}

function StatusBadge({ status, version }) {
  switch (status) {
    case 'verified':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle className="w-3 h-3 text-emerald-600" />
          Verified (v{version || 1})
        </span>
      )
    case 'superseded':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 line-through">
          <History className="w-3 h-3 text-amber-600" />
          Superseded (v{version || 1})
        </span>
      )
    case 'disputed':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <AlertTriangle className="w-3 h-3 text-rose-600" />
          Disputed
        </span>
      )
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          Active (v{version || 1})
        </span>
      )
  }
}

function formatLocation(unit) {
  if (unit.page != null) return `Page ${unit.page}`
  if (unit.slide != null) return `Slide ${unit.slide}`
  if (unit.timestamp_start != null) {
    const start = formatTimestamp(unit.timestamp_start)
    const end = unit.timestamp_end != null ? formatTimestamp(unit.timestamp_end) : null
    return end ? `${start} - ${end}` : start
  }
  return 'Document'
}

export default function KnowledgeUnits() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialKuId = searchParams.get('id')

  const [units, setUnits] = useState([])
  const [total, setTotal] = useState(0)
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters
  const [search, setSearch] = useState('')
  const [selectedSource, setSelectedSource] = useState('all')
  const [selectedModality, setSelectedModality] = useState('all')
  const [selectedStatus, setSelectedStatus] = useState('all')

  // Selected Unit Detail
  const [selectedUnitId, setSelectedUnitId] = useState(initialKuId || null)
  const [unitDetail, setUnitDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Load sources for filter dropdown
  useEffect(() => {
    getSources()
      .then((data) => setSources(data || []))
      .catch((err) => console.error('Failed to load sources:', err))
  }, [])

  // Load knowledge units matching filters
  const fetchUnits = () => {
    setLoading(true)
    setError(null)
    const params = {
      limit: 100,
      offset: 0,
    }
    if (search.trim()) params.search = search.trim()
    if (selectedSource !== 'all') params.source_id = selectedSource
    if (selectedModality !== 'all') params.modality = selectedModality
    if (selectedStatus !== 'all') params.status = selectedStatus

    getKnowledgeUnits(params)
      .then((res) => {
        setUnits(res.items || [])
        setTotal(res.total || 0)
        // If no unit is selected yet and units exist, pick the first
        if (!selectedUnitId && res.items && res.items.length > 0) {
          setSelectedUnitId(res.items[0].id)
        }
      })
      .catch((err) => {
        setError(err.message || 'Failed to fetch knowledge units')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchUnits()
  }, [selectedSource, selectedModality, selectedStatus])

  // Handle search submit
  const handleSearchSubmit = (e) => {
    e.preventDefault()
    fetchUnits()
  }

  // Load selected unit detail
  useEffect(() => {
    if (!selectedUnitId) {
      setUnitDetail(null)
      return
    }
    setDetailLoading(true)
    getKnowledgeUnitDetail(selectedUnitId)
      .then((data) => setUnitDetail(data))
      .catch((err) => console.error('Failed to fetch unit detail:', err))
      .finally(() => setDetailLoading(false))
  }, [selectedUnitId])

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-ink-900 tracking-tight flex items-center gap-2">
            <Database className="w-6 h-6 text-primary-600" />
            Knowledge Units
          </h1>
          <p className="text-sm text-ink-500 mt-1">
            Multimodal knowledge atoms extracted from lectures, slides, and transcripts with lineage and confidence.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink-500 font-medium">
            {total} {total === 1 ? 'atom' : 'atoms'} indexed
          </span>
          <button
            onClick={fetchUnits}
            className="p-2 rounded-lg border border-gray-200 text-ink-600 hover:text-ink-900 hover:bg-gray-50 text-xs flex items-center gap-1"
            title="Refresh knowledge units"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card p-4 space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search concepts, formulas, code, or explanations..."
              className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <button type="submit" className="btn-primary px-4 text-xs font-semibold">
            Search
          </button>
        </form>

        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-100 text-xs">
          <span className="text-ink-400 font-medium flex items-center gap-1 mr-1">
            <Filter className="w-3.5 h-3.5" /> Filters:
          </span>

          {/* Source Filter */}
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-ink-700 text-xs focus:outline-none"
          >
            <option value="all">All Sources</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>

          {/* Modality Filter */}
          <select
            value={selectedModality}
            onChange={(e) => setSelectedModality(e.target.value)}
            className="px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-ink-700 text-xs focus:outline-none"
          >
            {MODALITIES.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-ink-700 text-xs focus:outline-none"
          >
            {STATUSES.map((s) => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Split Layout: List on Left, Inspector on Right */}
      {loading ? (
        <div className="flex items-center justify-center py-24 text-ink-400 gap-2">
          <Loader2 className="w-6 h-6 animate-spin text-primary-600" />
          <span className="text-sm font-medium">Loading knowledge atoms...</span>
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      ) : units.length === 0 ? (
        <div className="card p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-gray-100 text-ink-400 flex items-center justify-center mx-auto">
            <BookOpen className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-ink-800">No Knowledge Units Found</h3>
          <p className="text-xs text-ink-500 max-w-md mx-auto">
            {sources.length === 0
              ? 'No learning materials have been uploaded yet. Ingest a PDF or YouTube lecture to extract verified knowledge atoms.'
              : 'No knowledge units match your active filter criteria. Try clearing search filters.'}
          </p>
          {sources.length === 0 && (
            <Link to="/" className="btn-primary inline-flex items-center gap-1 px-4 py-2 text-xs font-semibold mt-2">
              Add Learning Material
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Units List (7 cols) */}
          <div className="lg:col-span-7 space-y-3">
            {units.map((u) => {
              const isSelected = u.id === selectedUnitId
              return (
                <div
                  key={u.id}
                  onClick={() => setSelectedUnitId(u.id)}
                  className={`card p-4 cursor-pointer transition-all border text-left ${
                    isSelected
                      ? 'border-primary-500 ring-2 ring-primary-100 bg-primary-50/20 shadow-sm'
                      : 'border-gray-200 hover:border-gray-300 hover:shadow-xs'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-sm text-ink-900">{u.concept}</span>
                      <ModalityBadge modality={u.modality} />
                      <StatusBadge status={u.status} version={u.version} />
                    </div>
                    <span className="text-[11px] font-mono text-ink-400">
                      {(u.confidence * 100).toFixed(0)}% conf
                    </span>
                  </div>

                  <p className="text-xs text-ink-700 line-clamp-2 font-mono bg-white p-2 rounded border border-gray-100 mb-2">
                    {u.content}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-ink-400">
                    <span className="truncate max-w-[200px]" title={u.source_title}>
                      {u.source_title}
                    </span>
                    <div className="flex items-center gap-3">
                      <span>{formatLocation(u)}</span>
                      <span>{u.evidence_count} evidence</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Unit Inspector Pane (5 cols) */}
          <div className="lg:col-span-5 sticky top-20">
            {detailLoading ? (
              <div className="card p-12 text-center text-ink-400">
                <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-primary-600" />
                <span className="text-xs">Loading unit details...</span>
              </div>
            ) : unitDetail ? (
              <div className="card p-5 space-y-5">
                <div className="border-b border-gray-100 pb-3 flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-ink-900">{unitDetail.concept}</h2>
                    <div className="flex items-center gap-2 mt-1">
                      <ModalityBadge modality={unitDetail.modality} />
                      <StatusBadge status={unitDetail.status} version={unitDetail.version} />
                    </div>
                  </div>
                  <Link
                    to="/knowledge-graph"
                    className="p-1.5 rounded-lg border border-gray-200 text-ink-500 hover:text-primary-600 hover:border-primary-300 text-xs flex items-center gap-1"
                    title="View in Knowledge Graph"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Link>
                </div>

                {/* Stored Content */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-400 mb-1.5">
                    Extracted Content
                  </h3>
                  <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 font-mono text-xs text-ink-800 whitespace-pre-wrap leading-relaxed">
                    {unitDetail.content}
                  </div>
                </div>

                {/* Provenance & Location */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                    <span className="text-ink-400 block text-[10px] uppercase font-semibold">Location</span>
                    <span className="font-medium text-ink-800">{formatLocation(unitDetail)}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                    <span className="text-ink-400 block text-[10px] uppercase font-semibold">Extraction Conf</span>
                    <span className="font-mono font-medium text-ink-800">
                      {(unitDetail.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Lineage / Version Chain */}
                {unitDetail.lineage && unitDetail.lineage.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-400 mb-2 flex items-center gap-1">
                      <History className="w-3.5 h-3.5" /> Version Lineage (VEKG)
                    </h3>
                    <div className="space-y-2 border-l-2 border-primary-200 pl-3 ml-1.5">
                      {unitDetail.lineage.map((v) => (
                        <div
                          key={v.id}
                          onClick={() => setSelectedUnitId(v.id)}
                          className={`p-2 rounded-lg text-xs cursor-pointer transition-colors ${
                            v.id === unitDetail.id
                              ? 'bg-primary-50 border border-primary-300 font-medium'
                              : 'bg-gray-50 border border-gray-100 hover:bg-gray-100'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-ink-900">v{v.version || 1} &middot; {v.status}</span>
                            {v.id === unitDetail.id && (
                              <span className="text-[10px] bg-primary-600 text-white px-1.5 py-0.2 rounded font-medium">
                                current
                              </span>
                            )}
                          </div>
                          {v.correction_reason && (
                            <p className="text-[11px] text-amber-700 mt-1">
                              Reason: {v.correction_reason}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Supporting Raw Evidence */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-400 mb-2 flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" /> Supporting Evidence ({unitDetail.evidence?.length || 0})
                  </h3>
                  {!unitDetail.evidence || unitDetail.evidence.length === 0 ? (
                    <p className="text-xs text-ink-400 italic">No direct raw evidence segments attached.</p>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {unitDetail.evidence.map((ev) => (
                        <div key={ev.id} className="p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-xs space-y-1">
                          <div className="flex items-center justify-between text-[11px] text-ink-500">
                            <ModalityBadge modality={ev.modality} />
                            <span>{(ev.confidence * 100).toFixed(0)}% conf</span>
                          </div>
                          <p className="text-ink-700 font-mono text-[11px]">{ev.text}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Overlapping Conflicts */}
                {unitDetail.conflicts && unitDetail.conflicts.length > 0 && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 space-y-2">
                    <h3 className="text-xs font-bold text-rose-800 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-rose-600" />
                      Associated Cross-Modal Conflict ({unitDetail.conflicts.length})
                    </h3>
                    {unitDetail.conflicts.map((c) => (
                      <div key={c.id} className="text-xs text-rose-900 space-y-1">
                        <span className="font-semibold">{c.conflict_type}</span>
                        {c.claims && c.claims.length > 0 && (
                          <div className="space-y-1 text-[11px] text-rose-800">
                            {c.claims.map((claim, idx) => (
                              <p key={idx} className="bg-white/70 p-1.5 rounded border border-rose-100">
                                {claim}
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
