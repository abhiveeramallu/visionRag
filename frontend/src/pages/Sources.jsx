import React, { useEffect, useState } from 'react'
import { Library, Search as SearchIcon } from 'lucide-react'
import { getSources } from '../services/api'
import { mockSources } from '../data/mockData'
import SourceCard from '../components/SourceCard'
import DemoDataBadge from '../components/DemoDataBadge'

const TYPE_OPTIONS = ['all', 'youtube', 'video', 'audio', 'pdf', 'ppt', 'image']
const STATUS_OPTIONS = ['all', 'completed', 'processing', 'failed']

export default function Sources() {
  const [sources, setSources] = useState(null)
  const [usingDemo, setUsingDemo] = useState(false)
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  useEffect(() => {
    getSources()
      .then((data) => {
        const list = data || []
        if (list.length > 0) {
          setSources(list)
        } else {
          setSources(mockSources)
          setUsingDemo(true)
        }
      })
      .catch(() => {
        setSources(mockSources)
        setUsingDemo(true)
      })
  }, [])

  const filtered = (sources || []).filter((s) => {
    if (query && !s.title.toLowerCase().includes(query.toLowerCase())) return false
    if (typeFilter !== 'all' && s.source_type !== typeFilter) return false
    if (statusFilter !== 'all') {
      const isProcessing = s.status !== 'completed' && s.status !== 'failed'
      if (statusFilter === 'processing' && !isProcessing) return false
      if (statusFilter === 'completed' && s.status !== 'completed') return false
      if (statusFilter === 'failed' && s.status !== 'failed') return false
    }
    return true
  })

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-ink-900 flex items-center gap-2">
            <Library className="w-6 h-6 text-primary-600" />
            My Sources
            {usingDemo && <DemoDataBadge />}
          </h1>
          <p className="text-sm text-ink-500 mt-1">All your uploaded and linked learning material.</p>
        </div>
      </div>

      <div className="card p-4 flex flex-wrap items-center gap-3 bg-gray-50/50">
        <div className="relative flex-1 min-w-[200px]">
          <SearchIcon className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by title..."
            className="input pl-9"
          />
        </div>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="select">
          {TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>{t === 'all' ? 'All Types' : t.toUpperCase()}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="select">
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s[0].toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
      </div>

      {sources === null ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4].map((i) => <div key={i} className="card h-52 animate-pulse bg-gray-100 border-0" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-16 text-ink-500 text-sm">No sources match your filters.</div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((s) => <SourceCard key={s.id} source={s} />)}
        </div>
      )}
    </div>
  )
}
