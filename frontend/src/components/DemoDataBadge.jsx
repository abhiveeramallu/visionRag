import React from 'react'
import { FlaskConical } from 'lucide-react'

/**
 * Marks a section as sourced from src/data/mockData.js rather than a live
 * API response — keeps demo content visually distinct from real backend data.
 */
export default function DemoDataBadge({ label = 'Demo data', className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide bg-amber-50 text-amber-700 border border-amber-200 ${className}`}
      title="This section uses sample data for demonstration — not a live model response."
    >
      <FlaskConical className="w-3 h-3" />
      {label}
    </span>
  )
}
