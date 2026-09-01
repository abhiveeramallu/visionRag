import React from 'react'
import { AlertTriangle } from 'lucide-react'

/**
 * Shown when AI generation (summary/notes/quiz/flashcards) failed — e.g. LLM
 * quota exhausted or not configured. Kept visually distinct from generated
 * content so an error never masquerades as a real answer/question/card.
 */
export default function GenerationNotice({ message }) {
  if (!message) return null
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex items-start gap-2.5 text-sm text-amber-900">
      <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-600" />
      <span>{message}</span>
    </div>
  )
}
