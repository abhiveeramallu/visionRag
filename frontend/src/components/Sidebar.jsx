import React, { useEffect, useState, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Home, Database, MessageSquare, Share2, BarChart3,
  X, Loader2, Library, Search, RotateCw, ChevronRight,
} from 'lucide-react'
import { getSources } from '../services/api'
import { mockSources } from '../data/mockData'

const NAV_ITEMS = [
  { to: '/', label: 'Home / Sources', icon: Home, match: (p) => p === '/' || p.startsWith('/sources') || p.startsWith('/source/') },
  { to: '/knowledge-units', label: 'Knowledge Units', icon: Database, match: (p) => p.startsWith('/knowledge-units') },
  { to: '/knowledge-graph', label: 'Knowledge Graph / VEKG', icon: Share2, match: (p) => p.startsWith('/knowledge-graph') || p.startsWith('/knowledge-evolution') },
  { to: '/chat', label: 'AI Chat', icon: MessageSquare, match: (p) => p.startsWith('/chat') },
  { to: '/evaluation', label: 'Evaluation', icon: BarChart3, match: (p) => p.startsWith('/evaluation') },
]

export default function Sidebar({ open, onClose }) {
  const location = useLocation()
  const [sources, setSources] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [usingDemo, setUsingDemo] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Determine active source ID from URL (/source/:id or /chat?source_id=:id)
  const activeSourceId = (() => {
    if (location.pathname.startsWith('/source/')) {
      return location.pathname.replace('/source/', '').split('/')[0]
    }
    const params = new URLSearchParams(location.search)
    return params.get('source_id')
  })()

  const fetchSources = useCallback(async (manual = false) => {
    if (manual) setIsRefreshing(true)
    else setLoading(true)
    setError(null)

    try {
      const data = await getSources()
      const list = data || []
      if (list.length > 0) {
        setSources(list)
        setUsingDemo(false)
      } else {
        setSources(mockSources)
        setUsingDemo(true)
      }
    } catch (err) {
      console.warn('Failed to load live sources, using demo fallback:', err)
      setSources(mockSources)
      setUsingDemo(true)
    } finally {
      setLoading(false)
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchSources()
  }, [fetchSources])

  const filteredSources = (sources || []).filter((s) => {
    if (!searchQuery.trim()) return true
    return (s.title || '').toLowerCase().includes(searchQuery.trim().toLowerCase())
  })

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed lg:sticky top-0 left-0 h-screen w-64 bg-white border-r border-gray-200 flex flex-col z-50
          transform transition-transform duration-200 lg:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between px-5 h-16 border-b border-gray-100 flex-shrink-0">
          <Link to="/" className="flex items-center gap-2.5" onClick={onClose}>
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm shadow-xs">
              V
            </div>
            <span className="font-bold text-[15px] text-ink-900 tracking-tight">VisionRAG-X</span>
          </Link>
          <button onClick={onClose} className="lg:hidden p-1 text-ink-400 hover:text-ink-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5 flex flex-col">
          <div className="space-y-0.5">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              const active = item.match(location.pathname)
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={onClose}
                  className={`nav-link ${active ? 'nav-link-active' : ''}`}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>

          <div className="pt-5 mt-4 border-t border-gray-100 flex-1 flex flex-col min-h-0">
            <div className="px-3 mb-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-400 flex items-center gap-1.5">
                Sources
                {sources && <span className="font-mono text-[10px] text-ink-500">({sources.length})</span>}
                {usingDemo && <span className="text-amber-600 normal-case font-medium text-[10px]">(demo)</span>}
              </span>
              <button
                onClick={() => fetchSources(true)}
                disabled={isRefreshing}
                title="Refresh sources list"
                className="p-1 text-ink-400 hover:text-ink-700 transition-colors rounded hover:bg-gray-100"
              >
                <RotateCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin text-primary-600' : ''}`} />
              </button>
            </div>

            {/* In-sidebar source search filter */}
            <div className="px-2 mb-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-ink-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter sources..."
                  className="w-full pl-8 pr-2.5 py-1 text-xs bg-gray-50 border border-gray-200 rounded-md text-ink-800 placeholder-ink-400 focus:outline-none focus:ring-1 focus:ring-primary-500 focus:bg-white transition-colors"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-ink-400 hover:text-ink-700"
                  >
                    ×
                  </button>
                )}
              </div>
            </div>

            {/* Scrollable Sources List */}
            <div className="flex-1 overflow-y-auto space-y-0.5 pr-1 max-h-[320px]">
              {loading && sources === null ? (
                <div className="px-3 py-3 text-xs text-ink-400 flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-primary-600" />
                  Loading sources...
                </div>
              ) : filteredSources.length === 0 ? (
                <div className="px-3 py-4 text-center text-xs text-ink-400">
                  {searchQuery ? 'No sources match search' : 'No sources uploaded yet'}
                </div>
              ) : (
                filteredSources.map((s) => {
                  const isSelected = s.id === activeSourceId
                  return (
                    <Link
                      key={s.id}
                      to={`/source/${s.id}`}
                      onClick={onClose}
                      title={s.title}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-colors group ${
                        isSelected
                          ? 'bg-primary-50 text-primary-800 font-medium border-l-2 border-primary-600'
                          : 'text-ink-600 hover:bg-gray-100 hover:text-ink-900'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                          isSelected
                            ? 'bg-primary-600 ring-2 ring-primary-200'
                            : s.status === 'failed'
                            ? 'bg-red-400'
                            : s.status === 'processing'
                            ? 'bg-amber-400 animate-pulse'
                            : 'bg-primary-400'
                        }`}
                      />
                      <span className="truncate flex-1">{s.title}</span>
                      {isSelected && <ChevronRight className="w-3 h-3 text-primary-600 flex-shrink-0" />}
                    </Link>
                  )
                })
              )}
            </div>

            {/* Direct link to View All Sources Library */}
            <div className="pt-2 mt-2 border-t border-gray-100 px-2">
              <Link
                to="/sources"
                onClick={onClose}
                className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs font-semibold text-primary-600 hover:bg-primary-50 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Library className="w-3.5 h-3.5" />
                  View all sources
                </span>
                {sources && (
                  <span className="text-[11px] bg-primary-100 text-primary-700 px-1.5 py-0.2 rounded-full font-mono">
                    {sources.length}
                  </span>
                )}
              </Link>
            </div>
          </div>
        </nav>
      </aside>
    </>
  )
}
