import React, { useState } from 'react'
import { ChevronDown, ChevronUp, CheckCircle2, Circle, Route } from 'lucide-react'

const STRATEGIES = {
  semantic: { label: 'Semantic Search', keys: ['semantic', 'graph', 'hybrid'] },
  keyword: { label: 'Keyword Search (BM25)', keys: ['keyword', 'lexical', 'hybrid'] },
  graph: { label: 'Knowledge Graph', keys: ['graph', 'hybrid'] },
  timestamp: { label: 'Timestamp Search', keys: ['timestamp', 'temporal'] },
}

/**
 * "Why this answer?" — shows which retrieval routes were used without
 * exposing raw technical internals to the student by default.
 */
export default function RetrievalStrategyPanel({ strategyUsed }) {
  const [open, setOpen] = useState(false)
  const strategy = (strategyUsed || 'semantic+graph').toLowerCase()

  const activeKeys = Object.entries(STRATEGIES).filter(([, cfg]) =>
    cfg.keys.some((k) => strategy.includes(k))
  )
  const active = activeKeys.length > 0 ? activeKeys : [['semantic', STRATEGIES.semantic]]

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3.5 py-2 bg-gray-50 hover:bg-gray-100 text-xs font-semibold text-ink-700 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Route className="w-3.5 h-3.5 text-primary-600" />
          Why this answer? &middot; Evidence &amp; Verification
        </span>
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {open && (
        <div className="p-3.5 space-y-2.5 text-xs animate-fade-in">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Retrieval Strategy</p>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(STRATEGIES).map(([key, cfg]) => {
              const isActive = active.some(([k]) => k === key)
              return (
                <div key={key} className="flex items-center gap-1.5 text-ink-600">
                  {isActive ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                  ) : (
                    <Circle className="w-3.5 h-3.5 text-gray-300 flex-shrink-0" />
                  )}
                  <span className={isActive ? 'font-medium text-ink-900' : ''}>{cfg.label}</span>
                </div>
              )
            })}
          </div>
          <div className="pt-2 border-t border-gray-100 flex items-center justify-between">
            <span className="text-ink-500">Selected Route</span>
            <span className="font-mono font-semibold text-primary-700 bg-primary-50 px-2 py-0.5 rounded">
              {active.map(([, c]) => c.label.split(' ')[0]).join(' + ')}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
