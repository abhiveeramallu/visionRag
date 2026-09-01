import React, { useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search as SearchIcon, Filter, FileText, Clock } from 'lucide-react'
import { mockSearchResults, formatTimestamp } from '../data/mockData'
import DemoDataBadge from '../components/DemoDataBadge'

const MODALITIES = ['all', 'asr', 'ocr', 'text', 'vision']

export default function Search() {
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') || '')
  const [modality, setModality] = useState('all')
  const [minConfidence, setMinConfidence] = useState(0)

  const results = useMemo(() => {
    return mockSearchResults.filter((r) => {
      if (modality !== 'all' && r.modality !== modality) return false
      if (r.confidence < minConfidence) return false
      if (query.trim()) {
        const hay = `${r.snippet} ${r.source_title}`.toLowerCase()
        if (!hay.includes(query.trim().toLowerCase())) return false
      }
      return true
    })
  }, [query, modality, minConfidence])

  const handleSubmit = (e) => {
    e.preventDefault()
    setParams(query ? { q: query } : {})
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-8">
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-extrabold text-ink-900 flex items-center gap-2">
          <SearchIcon className="w-6 h-6 text-primary-600" />
          Search all sources
        </h1>
        <p className="text-sm text-ink-500 mt-1">
          e.g. "Find every lecture where Newton-Raphson was discussed."
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search across every source, transcript, and page..."
          className="input flex-1"
        />
        <button type="submit" className="btn-primary px-5 text-sm font-semibold">Search</button>
      </form>

      <div className="card p-4 flex flex-wrap items-center gap-4 bg-gray-50/50">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-ink-500" />
          <span className="text-xs font-semibold text-ink-700">Modality:</span>
          <select value={modality} onChange={(e) => setModality(e.target.value)} className="select text-xs">
            {MODALITIES.map((m) => <option key={m} value={m}>{m === 'all' ? 'All' : m.toUpperCase()}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-ink-700">Min. Confidence:</span>
          <input
            type="range" min="0" max="1" step="0.05"
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
            className="w-32"
          />
          <span className="text-xs text-ink-500 font-mono">{Math.round(minConfidence * 100)}%</span>
        </div>
        <span className="text-xs text-ink-400">Source, Topic, and Date filters coming soon.</span>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-ink-700">{results.length} results</p>
          <DemoDataBadge label="Demo search index" />
        </div>

        {results.length === 0 ? (
          <div className="card text-center py-12 text-ink-400 text-sm">No results match your filters.</div>
        ) : (
          results.map((r, i) => (
            <div key={i} className="card p-4 flex items-start justify-between gap-4 hover:shadow-md transition-shadow">
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-primary-50 text-primary-600 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink-900 flex items-center gap-2">
                    {r.source_title}
                    <span className="text-primary-600 font-mono text-xs flex items-center gap-0.5">
                      <Clock className="w-3 h-3" />
                      {r.page ? `Page ${r.page}` : formatTimestamp(r.timestamp_start)}
                    </span>
                  </p>
                  <p className="text-xs text-ink-600 mt-1 font-mono leading-relaxed line-clamp-2">{r.snippet}</p>
                  <span className="badge-blue mt-2 inline-block uppercase text-[10px]">{r.modality}</span>
                </div>
              </div>
              <span className="text-xs font-semibold text-ink-500 flex-shrink-0">{Math.round(r.confidence * 100)}%</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
