import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Plus, Menu } from 'lucide-react'

export default function Topbar({ onMenuClick, onAddSource }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  const handleSearch = (e) => {
    e.preventDefault()
    navigate(`/search${query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ''}`)
  }

  return (
    <header className="sticky top-0 z-30 bg-white/90 backdrop-blur border-b border-gray-200 h-16 flex items-center gap-3 px-4 sm:px-6">
      <button onClick={onMenuClick} className="lg:hidden p-1.5 text-ink-500 hover:text-ink-900">
        <Menu className="w-5 h-5" />
      </button>

      <form onSubmit={handleSearch} className="flex-1 max-w-lg">
        <div className="relative">
          <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search all your sources..."
            className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-colors"
          />
        </div>
      </form>

      <div className="flex-1" />

      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={onAddSource}
          className="btn-primary py-2 px-3.5 text-sm font-semibold flex items-center gap-1.5 shadow-xs"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Add Source</span>
        </button>
      </div>
    </header>
  )
}
