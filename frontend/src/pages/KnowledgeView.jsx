import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getKnowledge, getSource, getSources } from '../services/api'
import { Database, Filter, AlertTriangle, ShieldCheck, Clock, FileText, CheckCircle2 } from 'lucide-react'
import ConflictBadge from '../components/ConflictBadge'

export default function KnowledgeView() {
  const { sourceId } = useParams()
  const [units, setUnits] = useState([])
  const [source, setSource] = useState(null)
  const [loading, setLoading] = useState(true)
  const [modalityFilter, setModalityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const [activeSourceId, setActiveSourceId] = useState(sourceId || null)

  useEffect(() => {
    const targetId = sourceId || activeSourceId
    if (targetId) {
      setLoading(true)
      Promise.all([getSource(targetId), getKnowledge(targetId)])
        .then(([srcData, kuData]) => {
          setSource(srcData)
          setUnits(kuData || [])
        })
        .catch((err) => console.error(err))
        .finally(() => setLoading(false))
    } else {
      getSources()
        .then((sources) => {
          const completed = sources.find((s) => s.status === 'completed') || sources[0]
          if (completed) {
            setActiveSourceId(completed.id)
          } else {
            setLoading(false)
          }
        })
        .catch(() => setLoading(false))
    }
  }, [sourceId, activeSourceId])

  const filteredUnits = units.filter((u) => {
    if (modalityFilter !== 'all' && u.modality !== modalityFilter) return false
    if (statusFilter !== 'all' && u.status !== statusFilter) return false
    return true
  })

  const stats = {
    total: units.length,
    active: units.filter((u) => u.status === 'active').length,
    verified: units.filter((u) => u.status === 'verified').length,
    disputed: units.filter((u) => u.status === 'disputed').length,
    superseded: units.filter((u) => u.status === 'superseded').length,
  }

  return (
    <div className="space-y-6 py-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 flex items-center space-x-2">
            <Database className="w-6 h-6 text-primary-600 inline" />
            <span>Verified Knowledge Evolution Graph (VKEG)</span>
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Source: <span className="font-semibold text-gray-800">{source?.title || sourceId}</span>
          </p>
        </div>

        {/* Stats Row */}
        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2.5 py-1 rounded-lg bg-gray-100 font-semibold text-gray-700">
            Total Units: {stats.total}
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-green-100 font-semibold text-green-800">
            Active: {stats.active}
          </span>
          {stats.disputed > 0 && (
            <span className="px-2.5 py-1 rounded-lg bg-yellow-100 font-semibold text-yellow-800">
              Disputed: {stats.disputed}
            </span>
          )}
          {stats.superseded > 0 && (
            <span className="px-2.5 py-1 rounded-lg bg-red-100 font-semibold text-red-800">
              Superseded: {stats.superseded}
            </span>
          )}
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="card p-4 flex flex-wrap items-center justify-between gap-4 bg-gray-50/50">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <span className="text-xs font-semibold text-gray-700">Filter Modality:</span>
            <select
              value={modalityFilter}
              onChange={(e) => setModalityFilter(e.target.value)}
              className="select text-xs"
            >
              <option value="all">All Modalities</option>
              <option value="asr">ASR (Speech)</option>
              <option value="ocr">OCR (Visual Text)</option>
              <option value="formula">Formulas</option>
              <option value="code">Code</option>
              <option value="text">Document Text</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold text-gray-700">Filter Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="select text-xs"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="verified">Verified</option>
              <option value="disputed">Disputed</option>
              <option value="superseded">Superseded</option>
            </select>
          </div>
        </div>

        <span className="text-xs text-gray-500 font-medium">
          Showing {filteredUnits.length} of {units.length} knowledge units
        </span>
      </div>

      {/* Knowledge Unit Cards Grid */}
      {loading ? (
        <div className="text-center py-12 text-gray-500 text-sm">Loading Knowledge Units...</div>
      ) : filteredUnits.length === 0 ? (
        <div className="card text-center py-12 text-gray-500 text-sm">
          No knowledge units match the selected filters.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {filteredUnits.map((unit) => (
            <div key={unit.id} className="card p-4 space-y-3 relative hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-bold text-gray-900 block">{unit.concept}</span>
                  <span className="text-[11px] text-gray-400 font-mono">ID: {unit.id.slice(0, 8)}...</span>
                </div>

                <div className="flex items-center space-x-1.5">
                  <span className="badge bg-blue-50 text-blue-800 uppercase text-[10px] font-mono border border-blue-200">
                    {unit.modality}
                  </span>
                  <span
                    className={`badge text-[10px] uppercase font-mono border ${
                      unit.status === 'verified'
                        ? 'bg-green-100 text-green-800 border-green-300'
                        : unit.status === 'superseded'
                        ? 'bg-red-100 text-red-800 border-red-300'
                        : unit.status === 'disputed'
                        ? 'bg-yellow-100 text-yellow-800 border-yellow-300'
                        : 'bg-gray-100 text-gray-700 border-gray-300'
                    }`}
                  >
                    {unit.status}
                  </span>
                </div>
              </div>

              <p className="text-xs text-gray-800 leading-relaxed font-sans line-clamp-3 bg-gray-50 p-2.5 rounded-lg border border-gray-100">
                "{unit.content}"
              </p>

              <div className="flex items-center justify-between text-[11px] text-gray-500 pt-1 border-t border-gray-100 font-mono">
                <span>
                  📍 {unit.timestamp_start !== null && unit.timestamp_start !== undefined ? `${Math.floor(unit.timestamp_start / 60)}:${Math.floor(unit.timestamp_start % 60).toString().padStart(2, '0')}` : unit.page ? `Page ${unit.page}` : 'Doc'}
                </span>
                <span>Confidence: {(unit.confidence * 100).toFixed(0)}%</span>
                <span>v{unit.version}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
