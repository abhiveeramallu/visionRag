import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Share2, ChevronRight, History, X, Clock } from 'lucide-react'
import { mockKnowledgeGraph, formatTimestamp } from '../data/mockData'
import DemoDataBadge from '../components/DemoDataBadge'

function TreeNode({ node, depth, selectedId, onSelect }) {
  const [expanded, setExpanded] = useState(depth < 1)
  const hasChildren = node.children && node.children.length > 0
  const isSelected = selectedId === node.id

  return (
    <div>
      <div
        className={`flex items-center gap-1.5 py-1.5 rounded-lg cursor-pointer group ${
          isSelected ? 'bg-primary-50' : 'hover:bg-gray-50'
        }`}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => onSelect(node)}
      >
        {hasChildren ? (
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v) }}
            className="p-0.5 text-ink-400 hover:text-ink-700 flex-shrink-0"
          >
            <ChevronRight className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-90' : ''}`} />
          </button>
        ) : (
          <span className="w-4 flex-shrink-0" />
        )}
        <span
          className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${depth === 0 ? 'bg-primary-600' : depth === 1 ? 'bg-primary-400' : 'bg-ink-300'}`}
        />
        <span className={`text-sm ${isSelected ? 'font-semibold text-primary-700' : depth === 0 ? 'font-bold text-ink-900' : 'text-ink-700'}`}>
          {node.label}
        </span>
        {node.hasCorrectionHistory && (
          <History className="w-3 h-3 text-amber-500 flex-shrink-0" title="Has correction history" />
        )}
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} depth={depth + 1} selectedId={selectedId} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  )
}

function NodeDetail({ node, onClose }) {
  if (!node) {
    return (
      <div className="card h-full flex items-center justify-center text-center text-ink-400 text-sm p-8">
        Select a concept from the graph to see its definition, evidence, and confidence.
      </div>
    )
  }

  return (
    <div className="card h-full space-y-4 relative">
      <button onClick={onClose} className="absolute top-4 right-4 text-ink-400 hover:text-ink-700 lg:hidden">
        <X className="w-4 h-4" />
      </button>

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Concept</p>
        <h2 className="text-lg font-bold text-ink-900 mt-0.5">{node.label}</h2>
      </div>

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Definition</p>
        <p className="text-sm text-ink-700 leading-relaxed mt-1">{node.definition}</p>
      </div>

      {node.children && node.children.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Related Concepts</p>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {node.children.map((c) => (
              <span key={c.id} className="text-xs px-2 py-1 rounded-lg bg-gray-100 text-ink-600 font-medium">
                {c.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {node.source && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Evidence</p>
            <p className="text-sm text-ink-700 mt-0.5">{node.source}</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Timestamp</p>
            <p className="text-sm text-ink-700 mt-0.5 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-ink-400" /> {formatTimestamp(node.timestamp_start) || '—'}
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Confidence</p>
          <p className="text-lg font-bold text-green-700 mt-0.5">{Math.round(node.confidence * 100)}%</p>
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Evidence Count</p>
          <p className="text-lg font-bold text-ink-900 mt-0.5">{node.evidence_count}</p>
        </div>
      </div>

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Correction History</p>
        {node.hasCorrectionHistory ? (
          <Link
            to="/knowledge-evolution/gradient-descent"
            className="btn-outline w-full mt-2 py-2 text-xs font-semibold flex items-center justify-center gap-1.5"
          >
            <History className="w-3.5 h-3.5" />
            View correction history
          </Link>
        ) : (
          <p className="text-xs text-ink-400 mt-1">No corrections recorded — stable since first extraction.</p>
        )}
      </div>
    </div>
  )
}

export default function KnowledgeGraph() {
  const [selected, setSelected] = useState(null)

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center justify-between flex-wrap gap-3 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-ink-900 flex items-center gap-2">
            <Share2 className="w-6 h-6 text-primary-600" />
            Knowledge Graph
          </h1>
          <p className="text-sm text-ink-500 mt-1">Explore how concepts across your sources connect.</p>
        </div>
        <DemoDataBadge label="Demo graph" />
      </div>

      <div className="grid lg:grid-cols-[1.2fr_1fr] gap-4 items-start">
        <div className="card">
          <TreeNode node={mockKnowledgeGraph} depth={0} selectedId={selected?.id} onSelect={setSelected} />
        </div>

        <NodeDetail node={selected} onClose={() => setSelected(null)} />
      </div>
    </div>
  )
}
