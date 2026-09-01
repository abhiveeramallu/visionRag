import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getSummary, getSources } from '../services/api'
import { FileText, Copy, Download, Loader2, Sparkles, Check } from 'lucide-react'
import SourceSelect from '../components/SourceSelect'
import GenerationNotice from '../components/GenerationNotice'
import { usePersistedState, readPersistedState } from '../hooks/usePersistedState'

export default function Summary() {
  const { sourceId } = useParams()
  const [sources, setSources] = useState([])
  const [activeSourceId, setActiveSourceId] = useState(sourceId || null)

  // Persisted per-source so a generated summary is still there after
  // navigating away and back, instead of resetting to blank every time.
  const [saved, setSaved] = usePersistedState(
    `visionrag:summary:${activeSourceId || 'none'}`,
    { activeType: 'overall', topicInput: '', summaryData: null }
  )
  const activeType = saved.activeType
  const topicInput = saved.topicInput
  const summaryData = saved.summaryData
  const setActiveType = (v) => setSaved((s) => ({ ...s, activeType: v }))
  const setTopicInput = (v) => setSaved((s) => ({ ...s, topicInput: v }))
  const setSummaryData = (v) => setSaved((s) => ({ ...s, summaryData: v }))

  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const fetchSummary = async (type = activeType, topic = topicInput, targetId = activeSourceId) => {
    if (!targetId) return
    setLoading(true)
    try {
      const res = await getSummary(targetId, type, topic || null)
      setSummaryData(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    getSources()
      .then((data) => {
        const completed = (data || []).filter((s) => s.status === 'completed')
        setSources(completed)
        if (sourceId) {
          setActiveSourceId(sourceId)
          // Only auto-generate if nothing is cached for this source yet —
          // otherwise navigating back here would silently overwrite what's saved.
          if (!summaryData) fetchSummary('overall', '', sourceId)
        } else if (!activeSourceId && completed.length > 0) {
          setActiveSourceId(completed[0].id)
        }
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId])

  const handleSourceChange = (id) => {
    setActiveSourceId(id)
    // usePersistedState re-syncs to this source's own cached summary (if
    // any) once the key updates; only force a fresh fetch when it doesn't.
    const cached = readPersistedState(`visionrag:summary:${id}`, null)
    if (!cached?.summaryData) {
      fetchSummary(activeType, activeType === 'topic' ? topicInput : '', id)
    }
  }

  const handleCopy = () => {
    if (summaryData?.content) {
      navigator.clipboard.writeText(summaryData.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleDownload = () => {
    if (summaryData?.content) {
      const blob = new Blob([summaryData.content], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `summary-${activeType}-${(activeSourceId || '').slice(0, 6)}.md`
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 py-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 flex items-center space-x-2">
            <FileText className="w-6 h-6 text-primary-600 inline" />
            <span>Educational Summary</span>
          </h1>
          <p className="text-xs text-gray-500 mt-1">Generated from verified knowledge units.</p>
        </div>

        {summaryData && (
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

      <div className="card p-4 bg-gray-50/50">
        <SourceSelect sources={sources} value={activeSourceId} onChange={handleSourceChange} />
        {sources.length === 0 && (
          <p className="text-xs text-gray-400 mt-2">No processed sources yet — upload something first.</p>
        )}
      </div>

      {/* Tabs */}
      <div className="card p-2 bg-gray-100 flex flex-wrap gap-2 rounded-xl">
        <button
          onClick={() => {
            setActiveType('overall')
            fetchSummary('overall')
          }}
          disabled={!activeSourceId}
          className={`flex-1 py-2 rounded-lg text-xs font-semibold disabled:opacity-40 ${
            activeType === 'overall' ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Quick Summary
        </button>

        <button
          onClick={() => {
            setActiveType('topic')
          }}
          disabled={!activeSourceId}
          className={`flex-1 py-2 rounded-lg text-xs font-semibold disabled:opacity-40 ${
            activeType === 'topic' ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Topic-wise Summary
        </button>

        <button
          onClick={() => {
            setActiveType('timestamped')
            fetchSummary('timestamped')
          }}
          disabled={!activeSourceId}
          className={`flex-1 py-2 rounded-lg text-xs font-semibold disabled:opacity-40 ${
            activeType === 'timestamped' ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Exam Revision Summary
        </button>
      </div>

      {/* Topic Input if activeType === 'topic' */}
      {activeType === 'topic' && (
        <div className="card p-4 flex items-center space-x-3 bg-gray-50/50">
          <input
            type="text"
            value={topicInput}
            onChange={(e) => setTopicInput(e.target.value)}
            placeholder="Enter topic name (e.g. Newton-Raphson, Merge Sort, Integration)..."
            className="input text-xs flex-1"
          />
          <button
            onClick={() => fetchSummary('topic', topicInput)}
            disabled={!topicInput.trim() || loading}
            className="btn-primary py-2 px-4 text-xs font-semibold shadow-xs"
          >
            Generate Topic Summary
          </button>
        </div>
      )}

      {/* Content Display */}
      {loading ? (
        <div className="card text-center py-16 text-gray-500 text-sm flex items-center justify-center space-x-2">
          <Loader2 className="w-5 h-5 animate-spin text-primary-600" />
          <span>Generating educational summary...</span>
        </div>
      ) : summaryData ? (
        <div className="space-y-3">
          {summaryData.error && <GenerationNotice message={summaryData.error} />}
          <div className="card p-8 space-y-4 shadow-sm border-gray-200">
          {summaryData.error && (
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Verified evidence</p>
          )}
          <div className="prose max-w-none text-sm text-gray-800 leading-relaxed whitespace-pre-wrap font-sans">
            {summaryData.content}
          </div>

          {summaryData.sections && summaryData.sections.length > 0 && (
            <div className="space-y-3 pt-6 border-t border-gray-100">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500">
                Timestamped Sections
              </h3>
              {summaryData.sections.map((sec, idx) => (
                <div key={idx} className="bg-gray-50 p-3 rounded-lg border border-gray-200 space-y-1">
                  <span className="font-mono text-xs font-bold text-primary-600">{sec.title}</span>
                  <p className="text-xs text-gray-700">{sec.content}</p>
                </div>
              ))}
            </div>
          )}
          </div>
        </div>
      ) : (
        <div className="card text-center py-12 text-gray-500 text-sm">
          Click a tab above to generate a summary.
        </div>
      )}
    </div>
  )
}
