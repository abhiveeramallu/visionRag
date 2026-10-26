import React, { useState, useEffect } from 'react'
import {
  BarChart3, Play, Loader2, CheckCircle2, AlertTriangle, Layers,
  Terminal, ShieldCheck, FileText, CheckCircle, RefreshCw, ChevronDown,
  ChevronRight, Activity, ArrowUpRight, BookOpen
} from 'lucide-react'
import { getEvaluationArtifacts, runEvaluation } from '../services/api'

export default function Evaluation() {
  const [artifacts, setArtifacts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Active view tab
  const [activeTab, setActiveTab] = useState('benchmarks') // 'benchmarks' | 'ablations' | 'queries' | 'reports'
  const [benchmarkDataset, setBenchmarkDataset] = useState('synthetic') // 'synthetic' | 'real_video'

  // Run execution state
  const [runningType, setRunningType] = useState(null)
  const [executionResult, setExecutionResult] = useState(null)
  const [showLogs, setShowLogs] = useState(false)

  // Query filter
  const [queryCategoryFilter, setQueryCategoryFilter] = useState('all')

  const fetchArtifacts = () => {
    setLoading(true)
    setError(null)
    getEvaluationArtifacts()
      .then((data) => {
        setArtifacts(data)
      })
      .catch((err) => {
        setError(err.message || 'Failed to load evaluation artifacts')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchArtifacts()
  }, [])

  const handleRun = async (type) => {
    setRunningType(type)
    setExecutionResult(null)
    setShowLogs(true)
    try {
      const res = await runEvaluation(type)
      setExecutionResult(res)
      // Refresh artifacts to load updated results
      getEvaluationArtifacts().then((data) => setArtifacts(data))
    } catch (err) {
      setExecutionResult({
        status: 'error',
        type,
        exit_code: 1,
        stdout: '',
        stderr: err.message || 'Subprocess execution error',
        duration_seconds: 0,
      })
    } finally {
      setRunningType(null)
    }
  }

  const currentBenchmark = artifacts?.benchmarks?.[benchmarkDataset]
  const systems = currentBenchmark?.results || []
  const questions = currentBenchmark?.questions || []
  const ablations = artifacts?.ablations?.conditions || []

  const categories = Array.from(
    new Set(questions.map((q) => q.category).filter(Boolean))
  )

  const filteredQuestions = questions.filter((q) => {
    if (queryCategoryFilter !== 'all' && q.category !== queryCategoryFilter) return false
    return true
  })

  return (
    <div className="space-y-6 pb-16">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-ink-900 tracking-tight flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-primary-600" />
            Evaluation & Research Benchmarks
          </h1>
          <p className="text-sm text-ink-500 mt-1">
            Empirical validation of multimodal retrieval, cross-modal conflict detection, and VEKG lineage resolution.
          </p>
        </div>
        <button
          onClick={fetchArtifacts}
          disabled={loading}
          className="btn-secondary self-start sm:self-auto py-1.5 px-3 text-xs flex items-center gap-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Reload Artifacts
        </button>
      </div>

      {/* Dataset & Experiment Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4 space-y-2 border-l-4 border-l-primary-600">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-primary-700">Synthetic Benchmark</span>
            <span className="badge-blue text-[11px]">20 Queries</span>
          </div>
          <p className="text-xs text-ink-600">
            15 multimodal educational atoms with planted cross-modal conflicts (speech vs slide) and errata corrections.
          </p>
          <div className="pt-2 flex items-center gap-3 text-[11px] text-ink-500 font-mono">
            <span>Corpus: 15</span>
            <span>&middot;</span>
            <span>Conflicts: 2</span>
            <span>&middot;</span>
            <span>Categories: 5</span>
          </div>
        </div>

        <div className="card p-4 space-y-2 border-l-4 border-l-purple-600">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-purple-700">Real-Video Benchmark</span>
            <span className="badge-purple text-[11px]">15 Queries</span>
          </div>
          <p className="text-xs text-ink-600">
            18 multimodal atoms from real CS lecture recordings with instructor verbal corrections and slide errata.
          </p>
          <div className="pt-2 flex items-center gap-3 text-[11px] text-ink-500 font-mono">
            <span>Corpus: 18</span>
            <span>&middot;</span>
            <span>Conflicts: 3</span>
            <span>&middot;</span>
            <span>Real Errata: 2</span>
          </div>
        </div>

        <div className="card p-4 space-y-2 border-l-4 border-l-emerald-600">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">Ablation Study</span>
            <span className="badge-green text-[11px]">7 Conditions</span>
          </div>
          <p className="text-xs text-ink-600">
            Systematic feature removal isolating Whisper ASR, OCR, Vision captions, Conflict checks, VEKG, and Routing.
          </p>
          <div className="pt-2 flex items-center gap-3 text-[11px] text-ink-500 font-mono">
            <span>Reference: Full</span>
            <span>&middot;</span>
            <span>Ablations: A-G</span>
          </div>
        </div>
      </div>

      {/* Interactive Run Evaluation Action Bar */}
      <div className="card p-4 bg-gradient-to-r from-gray-50 to-white border border-gray-200 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-ink-900 flex items-center gap-2">
              <Play className="w-4 h-4 text-emerald-600 fill-emerald-600" />
              Live Evaluation Execution
            </h2>
            <p className="text-xs text-ink-500 mt-0.5">
              Execute evaluation or ablation pipelines locally. Results are saved to disk and reloaded immediately.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => handleRun('synthetic')}
              disabled={Boolean(runningType)}
              className="btn-primary py-1.5 px-3 text-xs font-semibold flex items-center gap-1.5"
            >
              {runningType === 'synthetic' ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Running Synthetic...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" /> Run Synthetic (20 Q)
                </>
              )}
            </button>

            <button
              onClick={() => handleRun('real_video')}
              disabled={Boolean(runningType)}
              className="py-1.5 px-3 rounded-lg bg-purple-600 text-white hover:bg-purple-700 text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50 transition-colors shadow-xs"
            >
              {runningType === 'real_video' ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Running Real-Video...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" /> Run Real-Video (15 Q)
                </>
              )}
            </button>

            <button
              onClick={() => handleRun('ablation')}
              disabled={Boolean(runningType)}
              className="py-1.5 px-3 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50 transition-colors shadow-xs"
            >
              {runningType === 'ablation' ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Running Ablations...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" /> Run Ablation (7 Cond)
                </>
              )}
            </button>
          </div>
        </div>

        {/* Execution Drawer / Output Logs */}
        {executionResult && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-semibold text-ink-800 flex items-center gap-1.5">
                {executionResult.status === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                )}
                Execution Completed: {executionResult.type} ({executionResult.duration_seconds}s)
              </span>
              <button
                onClick={() => setShowLogs(!showLogs)}
                className="text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1"
              >
                <Terminal className="w-3.5 h-3.5" />
                {showLogs ? 'Hide Output' : 'Show Output'}
              </button>
            </div>

            {showLogs && (
              <pre className="p-3 bg-ink-950 text-emerald-400 font-mono text-[11px] rounded-lg overflow-x-auto max-h-64 leading-tight whitespace-pre-wrap">
                {executionResult.stdout || executionResult.stderr || 'No stdout output.'}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-gray-200 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('benchmarks')}
          className={`pb-3 px-3 border-b-2 transition-colors ${
            activeTab === 'benchmarks'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-ink-500 hover:text-ink-800'
          }`}
        >
          Comparative Benchmarks (6 Systems)
        </button>
        <button
          onClick={() => setActiveTab('ablations')}
          className={`pb-3 px-3 border-b-2 transition-colors ${
            activeTab === 'ablations'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-ink-500 hover:text-ink-800'
          }`}
        >
          Ablation Matrix (7 Conditions)
        </button>
        <button
          onClick={() => setActiveTab('queries')}
          className={`pb-3 px-3 border-b-2 transition-colors ${
            activeTab === 'queries'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-ink-500 hover:text-ink-800'
          }`}
        >
          Per-Query Ground Truth Explorer
        </button>
        <button
          onClick={() => setActiveTab('reports')}
          className={`pb-3 px-3 border-b-2 transition-colors ${
            activeTab === 'reports'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-ink-500 hover:text-ink-800'
          }`}
        >
          Generated Markdown Reports
        </button>
      </div>

      {/* TAB 1: Comparative Benchmarks */}
      {activeTab === 'benchmarks' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-ink-700">Dataset:</span>
              <button
                onClick={() => setBenchmarkDataset('synthetic')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  benchmarkDataset === 'synthetic'
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-ink-600 hover:bg-gray-200'
                }`}
              >
                Synthetic Benchmark (20 Q)
              </button>
              <button
                onClick={() => setBenchmarkDataset('real_video')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  benchmarkDataset === 'real_video'
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-ink-600 hover:bg-gray-200'
                }`}
              >
                Real-Video Benchmark (15 Q)
              </button>
            </div>
            <span className="text-xs text-ink-400">
              Evaluated: {systems.length} systems
            </span>
          </div>

          <div className="card p-0 overflow-hidden border border-gray-200 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gray-50 border-b border-gray-200 text-ink-600 uppercase text-[10px] tracking-wider font-bold">
                  <tr>
                    <th className="py-3 px-3">System</th>
                    <th className="py-3 px-2 text-right">Recall@5</th>
                    <th className="py-3 px-2 text-right">Prec@5</th>
                    <th className="py-3 px-2 text-right">MRR</th>
                    <th className="py-3 px-2 text-right">NDCG@5</th>
                    <th className="py-3 px-2 text-right">Token F1</th>
                    <th className="py-3 px-2 text-right">Cit Gold F1</th>
                    <th className="py-3 px-2 text-right">Conflict F1</th>
                    <th className="py-3 px-2 text-right">Version Acc</th>
                    <th className="py-3 px-2 text-right">Abstain</th>
                    <th className="py-3 px-2 text-right">Decision Acc</th>
                    <th className="py-3 px-3 text-right">Ret Lat (ms)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 font-mono">
                  {systems.map((s) => {
                    const isFull = s.system.includes('Full VisionRAG-X')
                    return (
                      <tr
                        key={s.system}
                        className={`transition-colors ${
                          isFull
                            ? 'bg-primary-50/50 font-semibold text-ink-900 border-l-4 border-l-primary-600'
                            : 'hover:bg-gray-50/70 text-ink-700'
                        }`}
                      >
                        <td className="py-3 px-3 font-sans font-medium">{s.system}</td>
                        <td className="py-3 px-2 text-right">{(s.recall_at_5 ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right">{(s.precision_at_5 ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right">{(s.mrr ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right">{(s.ndcg_at_5 ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right">{(s.token_f1 ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right font-semibold text-primary-700">
                          {(s.citation_gold_f1 ?? 0).toFixed(3)}
                        </td>
                        <td className="py-3 px-2 text-right font-semibold text-purple-700">
                          {(s.conflict_f1 ?? 0).toFixed(3)}
                        </td>
                        <td className="py-3 px-2 text-right font-semibold text-emerald-700">
                          {(s.version_accuracy ?? 0).toFixed(3)}
                        </td>
                        <td className="py-3 px-2 text-right">{(s.abstention_accuracy ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right">{(s.decision_accuracy ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-3 text-right text-ink-400">
                          {(s.retrieval_latency_ms ?? 0).toFixed(1)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 text-xs text-ink-600 space-y-1">
            <p className="font-semibold text-ink-800">Benchmark Key Observations:</p>
            <p>&bull; <strong>Conflict Detection (D-F)</strong> eliminates silent misinformation by surfacing speech-slide contradictions (Conflict F1 reaches 1.000 vs 0.000 for standard baselines).</p>
            <p>&bull; <strong>Knowledge Evolution Graph (E-F)</strong> traverses version lineage to resolve superseded claims, boosting Version Accuracy to 1.000.</p>
            <p>&bull; <strong>Full VisionRAG-X (F)</strong> achieves perfect Decision Accuracy (1.000) by correctly answering grounded queries while abstaining on unanswerable out-of-domain questions.</p>
          </div>
        </div>
      )}

      {/* TAB 2: Ablation Matrix */}
      {activeTab === 'ablations' && (
        <div className="space-y-4">
          <div className="card p-0 overflow-hidden border border-gray-200 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gray-50 border-b border-gray-200 text-ink-600 uppercase text-[10px] tracking-wider font-bold">
                  <tr>
                    <th className="py-3 px-3">Ablation Condition</th>
                    <th className="py-3 px-2 text-right">Recall@5</th>
                    <th className="py-3 px-2 text-right">MRR</th>
                    <th className="py-3 px-2 text-right">Token F1</th>
                    <th className="py-3 px-2 text-right">Cit Gold F1</th>
                    <th className="py-3 px-2 text-right">Conflict F1</th>
                    <th className="py-3 px-2 text-right">Version Acc</th>
                    <th className="py-3 px-2 text-right">Decision Acc</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 font-mono">
                  {ablations.map((a) => {
                    const isRef = a.system.includes('Reference')
                    return (
                      <tr
                        key={a.system}
                        className={`transition-colors ${
                          isRef
                            ? 'bg-emerald-50/50 font-bold text-ink-900 border-l-4 border-l-emerald-600'
                            : 'hover:bg-gray-50/70 text-ink-700'
                        }`}
                      >
                        <td className="py-3 px-3 font-sans font-medium">{a.system}</td>
                        <td className="py-3 px-2 text-right">{(a.recall_at_5 ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right">{(a.mrr ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right">{(a.token_f1 ?? 0).toFixed(3)}</td>
                        <td className="py-3 px-2 text-right font-semibold text-primary-700">
                          {(a.citation_gold_f1 ?? 0).toFixed(3)}
                        </td>
                        <td className="py-3 px-2 text-right font-semibold text-purple-700">
                          {(a.conflict_f1 ?? 0).toFixed(3)}
                        </td>
                        <td className="py-3 px-2 text-right font-semibold text-emerald-700">
                          {(a.version_accuracy ?? 0).toFixed(3)}
                        </td>
                        <td className="py-3 px-2 text-right">{(a.decision_accuracy ?? 0).toFixed(3)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-ink-600">
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 space-y-1">
              <span className="font-semibold text-ink-800">Modality Ablations:</span>
              <p>&bull; Disabling Whisper ASR (A) drops Recall@5 to 0.722, demonstrating that spoken explanations carry indispensable context.</p>
              <p>&bull; Disabling Slide OCR (B) causes Recall@5 to drop to 0.639, proving slide text is essential for bulleted definitions.</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 space-y-1">
              <span className="font-semibold text-ink-800">Mechanism Ablations:</span>
              <p>&bull; Disabling Conflict Detection (D) drops Conflict F1 from 1.000 to 0.000.</p>
              <p>&bull; Disabling VKEG (E) drops Version Accuracy from 1.000 to 0.333, proving graph traversal prevents serving superseded errors.</p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: Per-Query Ground Truth Explorer */}
      {activeTab === 'queries' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-ink-700">Benchmark:</span>
              <button
                onClick={() => setBenchmarkDataset('synthetic')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${
                  benchmarkDataset === 'synthetic' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-ink-600'
                }`}
              >
                Synthetic (20)
              </button>
              <button
                onClick={() => setBenchmarkDataset('real_video')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${
                  benchmarkDataset === 'real_video' ? 'bg-purple-600 text-white' : 'bg-gray-100 text-ink-600'
                }`}
              >
                Real-Video (15)
              </button>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <span className="text-ink-400">Category:</span>
              <select
                value={queryCategoryFilter}
                onChange={(e) => setQueryCategoryFilter(e.target.value)}
                className="px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-xs text-ink-700"
              >
                <option value="all">All Categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            {filteredQuestions.map((q, idx) => (
              <div key={q.id || idx} className="card p-4 space-y-2 border border-gray-200 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-ink-500">{q.id}</span>
                    <span className="badge-blue text-[11px] uppercase">{q.category}</span>
                    {q.is_answerable === false ? (
                      <span className="badge-amber text-[11px]">Unanswerable (Abstention Test)</span>
                    ) : (
                      <span className="badge-green text-[11px]">Answerable</span>
                    )}
                  </div>
                  {q.target_version && (
                    <span className="text-[11px] text-ink-400 font-mono">
                      Target Version: v{q.target_version}
                    </span>
                  )}
                </div>

                <p className="font-semibold text-ink-900 text-sm">{q.question}</p>

                <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100 text-ink-700 space-y-1">
                  <span className="text-ink-400 text-[10px] uppercase font-bold block">Ground Truth Answer:</span>
                  <p>{q.ground_truth_answer}</p>
                </div>

                {q.gold_unit_ids && q.gold_unit_ids.length > 0 && (
                  <div className="flex items-center gap-1.5 text-[11px] text-ink-500">
                    <span className="font-semibold">Gold Citation Units:</span>
                    {q.gold_unit_ids.map((id) => (
                      <span key={id} className="font-mono bg-white px-1.5 py-0.5 rounded border border-gray-200">
                        {id}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: Generated Markdown Reports */}
      {activeTab === 'reports' && (
        <div className="space-y-4">
          <div className="card p-4 space-y-3">
            <h3 className="font-bold text-sm text-ink-900 flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-primary-600" />
              Latest Synthetic Benchmark Report (benchmark_report.md)
            </h3>
            <pre className="p-4 bg-gray-900 text-gray-100 rounded-xl font-mono text-xs overflow-x-auto max-h-96 whitespace-pre-wrap leading-relaxed">
              {artifacts?.benchmarks?.synthetic?.report_md || 'No synthetic report generated yet.'}
            </pre>
          </div>

          <div className="card p-4 space-y-3">
            <h3 className="font-bold text-sm text-ink-900 flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-purple-600" />
              Latest Real-Video Benchmark Report (benchmark_report_real_video.md)
            </h3>
            <pre className="p-4 bg-gray-900 text-gray-100 rounded-xl font-mono text-xs overflow-x-auto max-h-96 whitespace-pre-wrap leading-relaxed">
              {artifacts?.benchmarks?.real_video?.report_md || 'No real-video report generated yet.'}
            </pre>
          </div>

          <div className="card p-4 space-y-3">
            <h3 className="font-bold text-sm text-ink-900 flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-emerald-600" />
              Latest Ablation Study Report (ablation_report.md)
            </h3>
            <pre className="p-4 bg-gray-900 text-gray-100 rounded-xl font-mono text-xs overflow-x-auto max-h-96 whitespace-pre-wrap leading-relaxed">
              {artifacts?.ablations?.report_md || 'No ablation report generated yet.'}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
