import React, { useState } from 'react'
import { useParams } from 'react'
import { generateNotes } from '../services/api'
import { FileCode, Copy, Download, Loader2, Sparkles, Check } from 'lucide-react'

export default function Notes() {
  const { sourceId } = useParams()
  const [notesType, setNotesType] = useState('concise') // 'concise' | 'detailed' | 'revision'
  const [topic, setTopic] = useState('')
  const [notesData, setNotesData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const res = await generateNotes(sourceId, notesType, topic || null)
      setNotesData(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    if (notesData?.content) {
      navigator.clipboard.writeText(notesData.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleDownload = () => {
    if (notesData?.content) {
      const blob = new Blob([notesData.content], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `notes-${notesType}-${sourceId.slice(0, 6)}.md`
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 py-4">
      <div className="flex items-center justify-between border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 flex items-center space-x-2">
            <FileCode className="w-6 h-6 text-primary-600 inline" />
            <span>AI Revision Notes</span>
          </h1>
          <p className="text-xs text-gray-500 mt-1">Generate concise, detailed, or revision-focused study notes.</p>
        </div>

        {notesData && (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleCopy}
              className="btn-secondary py-1.5 px-3 text-xs flex items-center space-x-1"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>
            <button
              onClick={handleDownload}
              className="btn-outline py-1.5 px-3 text-xs flex items-center space-x-1"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download .md</span>
            </button>
          </div>
        )}
      </div>

      {/* Config Panel */}
      <div className="card p-5 space-y-4 bg-gray-50/50">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Notes Format</label>
            <select
              value={notesType}
              onChange={(e) => setNotesType(e.target.value)}
              className="select text-xs w-full"
            >
              <option value="concise">Concise Bullet Points</option>
              <option value="detailed">Detailed Study Guide</option>
              <option value="revision">Exam Revision Sheet</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Topic Filter (Optional)</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Asymptotic Notation"
              className="input text-xs w-full"
            />
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          className="w-full btn-primary py-2.5 text-xs font-semibold shadow-xs flex items-center justify-center space-x-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          <span>{loading ? 'Generating Notes...' : 'Generate Study Notes'}</span>
        </button>
      </div>

      {/* Content Display */}
      {loading ? (
        <div className="card text-center py-16 text-gray-500 text-sm flex items-center justify-center space-x-2">
          <Loader2 className="w-5 h-5 animate-spin text-primary-600" />
          <span>Generating notes...</span>
        </div>
      ) : notesData ? (
        <div className="card p-8 space-y-4 shadow-sm border-gray-200">
          <div className="prose max-w-none text-sm text-gray-800 leading-relaxed whitespace-pre-wrap font-sans">
            {notesData.content}
          </div>
        </div>
      ) : (
        <div className="card text-center py-12 text-gray-500 text-sm">
          Click "Generate Study Notes" to generate notes.
        </div>
      )}
    </div>
  )
}
