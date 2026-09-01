import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Bell, Plus, Menu } from 'lucide-react'
import { mockNotifications } from '../data/mockData'

export default function Topbar({ onMenuClick, onAddSource }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [notifOpen, setNotifOpen] = useState(false)
  const notifRef = useRef(null)
  const unreadCount = mockNotifications.filter((n) => n.unread).length

  useEffect(() => {
    const onClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

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

        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setNotifOpen((v) => !v)}
            className="relative p-2 rounded-lg text-ink-500 hover:bg-gray-100 hover:text-ink-900"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500 ring-2 ring-white" />
            )}
          </button>
          {notifOpen && (
            <div className="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                <span className="text-sm font-semibold text-ink-900">Notifications</span>
                <span className="text-[10px] font-semibold uppercase tracking-wide bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded-full">
                  Demo
                </span>
              </div>
              <div className="max-h-80 overflow-y-auto divide-y divide-gray-50">
                {mockNotifications.map((n) => (
                  <div key={n.id} className="px-4 py-3 hover:bg-gray-50">
                    <div className="flex items-start gap-2">
                      {n.unread && <span className="w-1.5 h-1.5 rounded-full bg-primary-500 mt-1.5 flex-shrink-0" />}
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-ink-900">{n.title}</p>
                        <p className="text-xs text-ink-500 mt-0.5 leading-relaxed">{n.detail}</p>
                        <p className="text-[10px] text-ink-400 mt-1">{n.time}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <button
          onClick={() => navigate('/settings')}
          className="w-8 h-8 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-bold flex-shrink-0"
        >
          ST
        </button>
      </div>
    </header>
  )
}
