import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getSummary, getSources } from '../services/api'
import { FileText, Copy, Download, Loader2, Sparkles, Check } from 'lucide-react'

export default function Summary() {
  const { sourceId } = useParams()
  const [activeType, setActiveType] = useState('overall') // 'overall' | 'topic' | 'timestamped'
  const [topicInput, setTopicInput] = useState('')
  const [summaryData, setSummaryData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const [activeSourceId, setActiveSourceId] = useState(sourceId || null)

  const fetchSummary = async (type = activeType, topic = topicInput) => {
    const targetId = sourceId || activeSourceId
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
    if (sourceId) {
      setActiveSourceId(sourceId)
      fetchSummary('overall')
    } else {
      getSources()
        .then((sources) => {
          const completed = sources.find((s) => s.status === 'completed') || sources[0]
          if (completed) {
            setActiveSourceId(completed.id)
          }
        })
        .catch(() => {})
    }
  }, [sourceId])

  const handleCopy = () => {
    if (summaryData?.content) {
      navigator.clipboard.writeText(summaryData.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleDownload = () => {
    const currentId = sourceId || activeSourceId || ''
    if (summaryData?.content) {
      const blob = new Blob([summaryData.content], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `summary-${activeType}-${currentId.slice(0, 6)}.md`
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

      {/* Tabs */}
      <div className="card p-2 bg-gray-100 flex flex-wrap gap-2 rounded-xl">
        <button
          onClick={() => {
            setActiveType('overall')
            fetchSummary('overall')
          }}
          className={`flex-1 py-2 rounded-lg text-xs font-semibold ${
            activeType === 'overall' ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Quick Summary
        </button>

        <button
          onClick={() => {
            setActiveType('topic')
          }}
          className={`flex-1 py-2 rounded-lg text-xs font-semibold ${
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
          className={`flex-1 py-2 rounded-lg text-xs font-semibold ${
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
        <div className="card p-8 space-y-4 shadow-sm border-gray-200">
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
      ) : (
        <div className="card text-center py-12 text-gray-500 text-sm">
          Click a tab above to generate a summary.
        </div>
      )}
    </div>
  )
}
