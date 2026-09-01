import React, { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Home, Library, MessageSquare, FileText, HelpCircle, Layers,
  StickyNote, Share2, ShieldCheck, X, Loader2,
} from 'lucide-react'
import { getSources } from '../services/api'
import { mockSources } from '../data/mockData'

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: Home, match: (p) => p === '/' },
  { to: '/sources', label: 'My Sources', icon: Library, match: (p) => p.startsWith('/sources') },
  { to: '/chat', label: 'AI Chat', icon: MessageSquare, match: (p) => p.startsWith('/chat') },
  { to: '/summary', label: 'Summaries', icon: FileText, match: (p) => p.startsWith('/summary') },
  { to: '/quiz', label: 'Quizzes', icon: HelpCircle, match: (p) => p.startsWith('/quiz') },
  { to: '/flashcards', label: 'Flashcards', icon: Layers, match: (p) => p.startsWith('/flashcards') },
  { to: '/notes', label: 'Notes', icon: StickyNote, match: (p) => p.startsWith('/notes') },
  { to: '/knowledge-graph', label: 'Knowledge Graph', icon: Share2, match: (p) => p.startsWith('/knowledge') },
]

export default function Sidebar({ open, onClose }) {
  const location = useLocation()
  const [recentSources, setRecentSources] = useState(null)
  const [usingDemo, setUsingDemo] = useState(false)

  useEffect(() => {
    getSources()
      .then((data) => {
        const list = data || []
        if (list.length > 0) {
          setRecentSources(list.slice(0, 4))
        } else {
          setRecentSources(mockSources.slice(0, 4))
          setUsingDemo(true)
        }
      })
      .catch(() => {
        setRecentSources(mockSources.slice(0, 4))
        setUsingDemo(true)
      })
  }, [])

  const sources = recentSources

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
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm">
              V
            </div>
            <span className="font-bold text-[15px] text-ink-900 tracking-tight">VisionRAG-X</span>
          </Link>
          <button onClick={onClose} className="lg:hidden p-1 text-ink-400 hover:text-ink-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
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

          <div className="pt-5 mt-4 border-t border-gray-100">
            <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-400 mb-2 flex items-center gap-1.5">
              Recent Sources
              {usingDemo && <span className="text-amber-600 normal-case font-medium">(demo)</span>}
            </p>
            {sources === null ? (
              <div className="px-3 py-2 text-xs text-ink-400 flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading...
              </div>
            ) : (
              <div className="space-y-0.5">
                {sources.map((s) => (
                  <Link
                    key={s.id}
                    to={`/source/${s.id}`}
                    onClick={onClose}
                    className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-ink-600 hover:bg-gray-100 hover:text-ink-900 transition-colors"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-primary-400 flex-shrink-0" />
                    <span className="truncate">{s.title}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </nav>

        <div className="flex-shrink-0 border-t border-gray-100 p-4 space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-bold flex-shrink-0">
              ST
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-ink-900 truncate">Student Account</p>
              <p className="text-[11px] text-ink-400 truncate">Guest workspace</p>
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between text-[11px] text-ink-500">
              <span className="flex items-center gap-1">
                <ShieldCheck className="w-3 h-3 text-primary-600" /> Storage
              </span>
              <span>2.4 GB / 10 GB</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: '24%' }} />
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
