import React, { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Share2,
  ChevronRight,
  History,
  X,
  Clock,
  Loader2,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Layers,
  ArrowRight,
  ExternalLink,
  BookOpen,
  AlertCircle,
  FileText,
  Link2,
} from 'lucide-react'
import { getSources, getKnowledgeGraph } from '../services/api'
import { mockKnowledgeGraph, formatTimestamp } from '../data/mockData'
import DemoDataBadge from '../components/DemoDataBadge'

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

function ModalityBadge({ modality }) {
  const mod = (modality || 'text').toLowerCase()
  const colors = {
    formula: 'bg-purple-50 text-purple-700 border-purple-200',
    code: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    ocr: 'bg-amber-50 text-amber-700 border-amber-200',
    asr: 'bg-teal-50 text-teal-700 border-teal-200',
    vision: 'bg-pink-50 text-pink-700 border-pink-200',
    text: 'bg-gray-50 text-gray-700 border-gray-200',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-[11px] font-medium border uppercase tracking-wide ${colors[mod] || colors.text}`}>
      {mod}
    </span>
  )
}

function NodeDetail({ node, edges = [], allNodes = [], onClose }) {
  if (!node) {
    return (
      <div className="card h-full flex flex-col items-center justify-center text-center text-ink-400 text-sm p-12">
        <Share2 className="w-10 h-10 text-gray-300 mb-3" />
        <p className="font-medium text-ink-700">No Concept Selected</p>
        <p className="text-xs text-ink-400 mt-1 max-w-xs">
          Select any concept node from the knowledge graph to view its extracted content, source citations, confidence, and relationship lineage.
        </p>
      </div>
    )
  }

  // Find incoming and outgoing edges for this node
  const nodeEdges = edges.filter((e) => e.source === node.id || e.target === node.id)
  const incomingCorrections = edges.filter((e) => e.target === node.id && (e.relation === 'corrects' || e.relation === 'supersedes'))
  const outgoingCorrections = edges.filter((e) => e.source === node.id && (e.relation === 'corrects' || e.relation === 'supersedes'))
  const conflicts = edges.filter((e) => (e.source === node.id || e.target === node.id) && e.relation === 'conflicts_with')

  return (
    <div className="card h-full space-y-5 relative">
      <button onClick={onClose} className="absolute top-4 right-4 text-ink-400 hover:text-ink-700 lg:hidden">
        <X className="w-4 h-4" />
      </button>

      <div>
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <StatusBadge status={node.status} version={node.version} />
          <ModalityBadge modality={node.modality} />
        </div>
        <h2 className="text-lg font-extrabold text-ink-900 mt-1 leading-snug">{node.label}</h2>
        <p className="text-xs text-ink-400 mt-0.5">ID: {node.id}</p>
      </div>

      <div>
        <p className="text-[11px] font-bold uppercase tracking-wider text-ink-500 mb-1">Content / Definition</p>
        <div className="p-3 bg-gray-50 border border-gray-100 rounded-lg text-sm text-ink-800 leading-relaxed font-mono whitespace-pre-wrap max-h-60 overflow-y-auto">
          {node.definition || node.content}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-1 border-t border-gray-100">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-ink-500">Source Document</p>
          <p className="text-sm font-semibold text-ink-800 mt-0.5 truncate" title={node.source_title || node.source}>
            {node.source_title || node.source || 'Default Source'}
          </p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-ink-500">Location</p>
          <p className="text-sm font-semibold text-ink-800 mt-0.5 flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-ink-400" />
            {node.page ? `Page ${node.page}` : node.slide ? `Slide ${node.slide}` : formatTimestamp(node.timestamp_start) || '—'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-1 border-t border-gray-100">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-ink-500">Extraction Confidence</p>
          <p className="text-lg font-extrabold text-emerald-600 mt-0.5">
            {Math.round((node.confidence ?? 0.5) * 100)}%
          </p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-ink-500">Supporting Evidence</p>
          <p className="text-lg font-extrabold text-ink-900 mt-0.5">
            {node.evidence_count ?? 1} item{node.evidence_count === 1 ? '' : 's'}
          </p>
        </div>
      </div>

      {/* Relationships */}
      <div className="space-y-3 pt-1 border-t border-gray-100">
        <p className="text-[11px] font-bold uppercase tracking-wider text-ink-500">Graph Relationships</p>

        {outgoingCorrections.length > 0 && (
          <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-lg text-xs space-y-1">
            <div className="flex items-center gap-1.5 font-bold text-emerald-800">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
              <span>Corrects Earlier Version</span>
            </div>
            {outgoingCorrections.map((e) => (
              <p key={e.id} className="text-emerald-700 leading-normal">
                {e.reason || 'Updates and supersedes previous version.'}
              </p>
            ))}
          </div>
        )}

        {incomingCorrections.length > 0 && (
          <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-xs space-y-1">
            <div className="flex items-center gap-1.5 font-bold text-amber-800">
              <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
              <span>Superseded by Errata / Newer Version</span>
            </div>
            {incomingCorrections.map((e) => (
              <p key={e.id} className="text-amber-700 leading-normal">
                {e.reason || 'This unit was superseded by a verified correction later in the document.'}
              </p>
            ))}
          </div>
        )}

        {conflicts.length > 0 && (
          <div className="p-3 bg-rose-50/70 border border-rose-200 rounded-lg text-xs space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-rose-800">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
              <span>Cross-Modal Conflict Detected</span>
            </div>
            {conflicts.map((c) => (
              <div key={c.id} className="text-rose-700 space-y-1 bg-white/70 p-2 rounded border border-rose-100">
                <div className="flex items-center justify-between">
                  <p className="font-semibold">{c.conflict_type || 'Disagreement'}</p>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${c.resolved ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                    {c.resolved ? 'Resolved' : 'Disputed'}
                  </span>
                </div>
                {c.severity && <p className="text-[10px] text-rose-600 uppercase font-semibold">Severity: {c.severity}</p>}
                {c.claims && c.claims.length > 0 && (
                  <ul className="list-disc list-inside mt-0.5 space-y-0.5 font-mono text-[11px]">
                    {c.claims.map((cl, i) => (
                      <li key={i}>{cl}</li>
                    ))}
                  </ul>
                )}
                {c.resolution && (
                  <p className="text-[11px] text-ink-600 mt-1 pt-1 border-t border-rose-100">
                    <strong>Resolution:</strong> {c.resolution}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {nodeEdges.length === 0 && (
          <p className="text-xs text-ink-400">No conflict or correction edges for this unit — verified stable knowledge.</p>
        )}
      </div>

      {node.source_id && (
        <div className="pt-2">
          <Link
            to={`/knowledge-evolution/${node.source_id}`}
            className="btn-outline w-full py-2 text-xs font-semibold flex items-center justify-center gap-1.5"
          >
            <History className="w-3.5 h-3.5" />
            View Version History & Lineage
          </Link>
        </div>
      )}
    </div>
  )
}

export default function KnowledgeGraph() {
  const [selected, setSelected] = useState(null)
  const [sources, setSources] = useState([])
  const [sourceFilter, setSourceFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [graphData, setGraphData] = useState({ nodes: [], edges: [], summary: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showDemoFixture, setShowDemoFixture] = useState(false)

  const fetchGraph = async () => {
    setLoading(true)
    setError(null)
    try {
      const srcList = await getSources()
      const completed = (srcList || []).filter((s) => s.status === 'completed')
      setSources(completed)

      if (completed.length === 0) {
        setGraphData({ nodes: [], edges: [], summary: { total_nodes: 0, total_edges: 0 } })
        setLoading(false)
        return
      }

      const activeSourceId = sourceFilter === 'all' ? null : sourceFilter
      const graph = await getKnowledgeGraph(activeSourceId)
      setGraphData(graph || { nodes: [], edges: [], summary: {} })
      if (graph?.nodes?.length > 0 && !selected) {
        setSelected(graph.nodes[0])
      }
    } catch (err) {
      console.error('Failed to load knowledge graph:', err)
      setError(err.message || 'Failed to load knowledge graph from server.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchGraph()
  }, [sourceFilter])

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    if (showDemoFixture) {
      return []
    }
    return (graphData.nodes || []).filter((n) => {
      if (statusFilter !== 'all' && n.status !== statusFilter) return false
      return true
    })
  }, [graphData.nodes, statusFilter, showDemoFixture])

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-ink-900 flex items-center gap-2">
            <Share2 className="w-6 h-6 text-primary-600" />
            Knowledge Graph
          </h1>
          <p className="text-sm text-ink-500 mt-1">
            Real knowledge units, concept hierarchies, correction lineages, and detected cross-modal conflicts.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {showDemoFixture && <DemoDataBadge label="Demo Mock Fixture" />}
          <button
            onClick={() => {
              if (showDemoFixture) {
                setShowDemoFixture(false)
                fetchGraph()
              } else {
                fetchGraph()
              }
            }}
            disabled={loading}
            className="btn-outline text-xs flex items-center gap-1.5 py-1.5 px-3"
            title="Refresh graph from database"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Control bar */}
      {!loading && !error && sources.length > 0 && (
        <div className="flex items-center justify-between flex-wrap gap-3 p-4 bg-gray-50 border border-gray-200 rounded-xl">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-xs font-semibold text-ink-600">Source:</label>
              <select
                value={sourceFilter}
                onChange={(e) => {
                  setSourceFilter(e.target.value)
                  setSelected(null)
                }}
                className="select text-xs py-1 px-2.5 h-8"
              >
                <option value="all">All Sources ({sources.length})</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title} ({s.source_type?.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs font-semibold text-ink-600">Status:</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="select text-xs py-1 px-2.5 h-8"
              >
                <option value="all">All Statuses ({graphData.nodes?.length || 0})</option>
                <option value="active">Active</option>
                <option value="verified">Verified Correction</option>
                <option value="superseded">Superseded</option>
                <option value="disputed">Disputed / Conflict</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-medium text-ink-600 flex-wrap">
            <span>
              Nodes: <strong className="text-ink-900">{graphData.nodes?.length || 0}</strong>
            </span>
            <span>
              Lineage Edges: <strong className="text-emerald-700">{graphData.summary?.lineage_edges ?? graphData.summary?.correction_edges ?? 0}</strong>
            </span>
            <span>
              Conflicts: <strong className="text-rose-700">{graphData.summary?.conflict_edges || 0}</strong>
            </span>
            <span>
              Concept Links: <strong className="text-slate-700">{graphData.summary?.related_edges || 0}</strong>
            </span>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="card flex flex-col items-center justify-center gap-3 py-20 text-ink-500 text-sm">
          <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
          <p className="font-semibold text-ink-800">Loading Knowledge Graph...</p>
          <p className="text-xs text-ink-400">Querying verified knowledge units and relationship lineages from stored sources.</p>
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <div className="card p-8 border-rose-200 bg-rose-50/50 text-center space-y-3">
          <AlertTriangle className="w-10 h-10 text-rose-500 mx-auto" />
          <h3 className="text-base font-bold text-rose-900">Failed to load Knowledge Graph</h3>
          <p className="text-xs text-rose-700 max-w-md mx-auto">{error}</p>
          <button onClick={fetchGraph} className="btn-primary text-xs px-4 py-2 mt-2">
            Retry Connection
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && sources.length === 0 && !showDemoFixture && (
        <div className="card p-12 text-center space-y-4 max-w-xl mx-auto">
          <div className="w-14 h-14 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto text-primary-600">
            <BookOpen className="w-7 h-7" />
          </div>
          <h2 className="text-lg font-bold text-ink-900">No Ingested Sources Available</h2>
          <p className="text-sm text-ink-500 leading-relaxed">
            The knowledge graph displays verified concepts, mathematical formulas, code blocks, and correction lineages derived from processed course materials.
          </p>
          <div className="flex items-center justify-center gap-3 pt-2">
            <Link to="/upload" className="btn-primary text-xs px-4 py-2 flex items-center gap-1.5">
              <FileText className="w-4 h-4" />
              Upload Source Document (PDF)
            </Link>
            <button
              onClick={() => setShowDemoFixture(true)}
              className="btn-outline text-xs px-4 py-2 text-ink-600"
            >
              View Demo Fixture
            </button>
          </div>
        </div>
      )}

      {/* Real Data View */}
      {!loading && !error && sources.length > 0 && (
        <div className="grid lg:grid-cols-[1.3fr_1fr] gap-6 items-start">
          {/* Graph Nodes & Relationship List */}
          <div className="space-y-4">
            {/* Relationship Categories: Lineages, Conflicts, Concept Links */}
            {graphData.edges && graphData.edges.length > 0 && (
              <div className="space-y-3">
                {/* 1. Verified Version Lineages & Corrections */}
                {graphData.edges.filter((e) => e.relation === 'corrects' || e.relation === 'supersedes').length > 0 && (
                  <div className="card p-4 bg-gradient-to-r from-emerald-50/60 to-teal-50/60 border border-emerald-200">
                    <div className="flex items-center gap-2 text-emerald-800 font-bold text-xs uppercase tracking-wider mb-2">
                      <Layers className="w-4 h-4 text-emerald-600" />
                      <span>
                        Verified Version Lineages & Corrections (
                        {graphData.edges.filter((e) => e.relation === 'corrects' || e.relation === 'supersedes').length})
                      </span>
                    </div>
                    <div className="space-y-2">
                      {graphData.edges
                        .filter((e) => e.relation === 'corrects' || e.relation === 'supersedes')
                        .map((e) => (
                          <div
                            key={e.id}
                            className="p-2.5 bg-white border border-emerald-100 rounded-lg text-xs flex items-start gap-2 shadow-sm"
                          >
                            <ArrowRight className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-bold text-ink-900">{e.source_label || 'Verified Version'}</span>
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800">
                                  {e.label}
                                </span>
                                <span className="font-semibold text-ink-600 line-through">
                                  {e.target_label || 'Superseded Version'}
                                </span>
                              </div>
                              {e.reason && <p className="text-[11px] text-ink-500">{e.reason}</p>}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* 2. Cross-Modal Conflicts */}
                {graphData.edges.filter((e) => e.relation === 'conflicts_with').length > 0 && (
                  <div className="card p-4 bg-gradient-to-r from-rose-50/70 to-orange-50/70 border border-rose-200">
                    <div className="flex items-center gap-2 text-rose-800 font-bold text-xs uppercase tracking-wider mb-2">
                      <AlertTriangle className="w-4 h-4 text-rose-600" />
                      <span>
                        Detected Cross-Modal Conflicts (
                        {graphData.edges.filter((e) => e.relation === 'conflicts_with').length})
                      </span>
                    </div>
                    <div className="space-y-2">
                      {graphData.edges
                        .filter((e) => e.relation === 'conflicts_with')
                        .map((e) => (
                          <div
                            key={e.id}
                            className="p-2.5 bg-white border border-rose-100 rounded-lg text-xs space-y-1 shadow-sm"
                          >
                            <div className="flex items-center justify-between flex-wrap gap-1">
                              <div className="flex items-center gap-1.5 font-bold text-ink-900">
                                <span className="text-rose-700 font-semibold">{e.source_label}</span>
                                {e.source !== e.target && (
                                  <>
                                    <span className="text-ink-400">&harr;</span>
                                    <span className="text-rose-700 font-semibold">{e.target_label}</span>
                                  </>
                                )}
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-800">
                                  {e.conflict_type || 'Conflict'}
                                </span>
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                    e.resolved ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                                  }`}
                                >
                                  {e.resolved ? 'Resolved' : 'Disputed'}
                                </span>
                              </div>
                            </div>
                            {e.claims && e.claims.length > 0 && (
                              <ul className="list-disc list-inside text-[11px] text-ink-600 font-mono space-y-0.5">
                                {e.claims.map((cl, i) => (
                                  <li key={i}>{cl}</li>
                                ))}
                              </ul>
                            )}
                            {e.resolution && (
                              <p className="text-[11px] text-ink-500 italic">Resolution: {e.resolution}</p>
                            )}
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* 3. Concept Topic Associations */}
                {graphData.edges.filter((e) => e.relation === 'related_to').length > 0 && (
                  <div className="card p-4 bg-slate-50/70 border border-slate-200">
                    <div className="flex items-center gap-2 text-slate-700 font-bold text-xs uppercase tracking-wider mb-2">
                      <Link2 className="w-4 h-4 text-slate-500" />
                      <span>
                        Concept Topic Associations (
                        {graphData.edges.filter((e) => e.relation === 'related_to').length})
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {graphData.edges
                        .filter((e) => e.relation === 'related_to')
                        .map((e) => (
                          <div
                            key={e.id}
                            className="p-2 bg-white border border-slate-200 rounded-lg text-xs flex items-center justify-between shadow-sm"
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-ink-800">{e.source_label}</span>
                              <span className="text-ink-400">&bull;</span>
                              <span className="font-semibold text-ink-800">{e.target_label}</span>
                            </div>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600">
                              {e.label}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Concept Nodes Grid */}
            <div className="card space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-gray-100">
                <h3 className="text-xs font-bold uppercase tracking-wider text-ink-500">
                  Concept Nodes ({filteredNodes.length})
                </h3>
                <span className="text-xs text-ink-400">Click a concept to inspect details</span>
              </div>

              <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                {filteredNodes.map((node) => {
                  const isSelected = selected?.id === node.id
                  const hasCorrection = node.previous_version_id || node.status === 'superseded' || node.status === 'verified'
                  return (
                    <div
                      key={node.id}
                      onClick={() => setSelected(node)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                        isSelected
                          ? 'border-primary-500 bg-primary-50/50 shadow-sm ring-1 ring-primary-500/20'
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              node.status === 'verified'
                                ? 'bg-emerald-500'
                                : node.status === 'superseded'
                                ? 'bg-amber-500'
                                : node.status === 'disputed'
                                ? 'bg-rose-500'
                                : 'bg-primary-600'
                            }`}
                          />
                          <h4
                            className={`text-sm truncate font-bold ${
                              isSelected ? 'text-primary-900' : 'text-ink-900'
                            } ${node.status === 'superseded' ? 'line-through text-ink-500' : ''}`}
                          >
                            {node.label}
                          </h4>
                        </div>
                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          <StatusBadge status={node.status} version={node.version} />
                          <ModalityBadge modality={node.modality} />
                        </div>
                      </div>

                      <p className="text-xs text-ink-600 mt-2 line-clamp-2 leading-relaxed">
                        {node.definition || node.content}
                      </p>

                      <div className="flex items-center justify-between text-[11px] text-ink-400 mt-2.5 pt-2 border-t border-gray-100">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {node.page ? `Page ${node.page}` : formatTimestamp(node.timestamp_start) || 'Doc'}
                        </span>
                        <div className="flex items-center gap-2">
                          <span>Confidence: <strong className="text-emerald-700">{Math.round((node.confidence ?? 0.5) * 100)}%</strong></span>
                          {hasCorrection && (
                            <span className="flex items-center gap-0.5 text-amber-600 font-semibold" title="Has version lineage">
                              <History className="w-3 h-3" />
                              Lineage
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Node Detail Inspector */}
          <div className="sticky top-6">
            <NodeDetail
              node={selected}
              edges={graphData.edges}
              allNodes={graphData.nodes}
              onClose={() => setSelected(null)}
            />
          </div>
        </div>
      )}
    </div>
  )
}
