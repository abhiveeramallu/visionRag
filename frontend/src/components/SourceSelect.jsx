import React from 'react'
import { Library } from 'lucide-react'

/**
 * Dropdown for picking which completed source a study tool (Summary, Quiz,
 * Flashcards, Notes) generates against — instead of silently auto-picking
 * one behind the scenes.
 */
export default function SourceSelect({ sources, value, onChange, label = 'Source' }) {
  if (!sources || sources.length === 0) return null

  return (
    <div>
      <label className="block text-[11px] font-semibold text-gray-600 mb-1 flex items-center gap-1">
        <Library className="w-3 h-3" /> {label}
      </label>
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        className="select text-xs w-full"
      >
        {sources.map((s) => (
          <option key={s.id} value={s.id}>
            {s.title} ({s.source_type?.toUpperCase()})
          </option>
        ))}
      </select>
    </div>
  )
}
