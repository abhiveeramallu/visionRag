import React from 'react'
import { Link } from 'react-router-dom'
import {
  Upload, Youtube, FileVideo, Music, FileText,
  AlertTriangle, ShieldCheck, Database, Layers,
  HelpCircle, Sparkles, ArrowRight, BookOpen
} from 'lucide-react'

export default function Home() {
  return (
    <div className="space-y-12 py-4">
      {/* Hero Banner */}
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-primary-50 border border-primary-200 text-primary-700 text-xs font-semibold">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Verified Multimodal RAG Prototype</span>
        </div>

        <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 tracking-tight leading-tight">
          VisionRAG-X
        </h1>
        <p className="text-lg text-gray-600 leading-relaxed font-normal">
          A Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval from Educational Content.
        </p>

        {/* Experimental Research Disclaimer */}
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs text-left flex items-start space-x-3 shadow-xs">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Research Prototype Notice: </span>
            <span className="text-amber-800">
              The novel contributions of VisionRAG-X (ASR+OCR extraction, cross-modal conflict detection, VKEG graph evolution, hybrid indexing, and dynamic routing) are experimental modules designed for evaluation against baselines. No scientific performance claims are implied prior to benchmark evaluation.
            </span>
          </div>
        </div>

        <div className="pt-4 flex justify-center space-x-4">
          <Link
            to="/upload"
            className="btn-primary px-6 py-3 rounded-xl text-base font-semibold shadow-md flex items-center space-x-2"
          >
            <Upload className="w-5 h-5" />
            <span>Upload Material / YouTube URL</span>
            <ArrowRight className="w-4 h-4 ml-1" />
          </Link>
        </div>
      </div>

      {/* Multimodal Input Formats */}
      <div className="space-y-4">
        <h2 className="text-center text-xs font-bold text-gray-400 uppercase tracking-widest">
          Supported Educational Inputs
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {[
            { icon: Youtube, label: 'YouTube URLs', color: 'text-red-600 bg-red-50' },
            { icon: FileVideo, label: 'MP4 / MKV Video', color: 'text-purple-600 bg-purple-50' },
            { icon: Music, label: 'MP3 / WAV Audio', color: 'text-blue-600 bg-blue-50' },
            { icon: FileText, label: 'PDF Documents', color: 'text-rose-600 bg-rose-50' },
            { icon: Layers, label: 'PPT / PPTX Slides', color: 'text-orange-600 bg-orange-50' },
            { icon: Sparkles, label: 'Educational Images', color: 'text-emerald-600 bg-emerald-50' },
          ].map((item, idx) => {
            const Icon = item.icon
            return (
              <div
                key={idx}
                className="card p-4 text-center space-y-2 hover:border-primary-300 transition-colors flex flex-col items-center justify-center"
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${item.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <span className="text-xs font-semibold text-gray-800">{item.label}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Core Research Contributions */}
      <div className="space-y-6">
        <div className="text-center space-y-1">
          <h2 className="text-2xl font-bold text-gray-900">Research Novelties & Features</h2>
          <p className="text-xs text-gray-500">Experimental modules supporting verified RAG and active student learning.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <div className="card space-y-3 border-t-4 border-t-primary-600">
            <div className="w-9 h-9 rounded-lg bg-primary-50 text-primary-600 flex items-center justify-center font-bold">
              1
            </div>
            <h3 className="font-bold text-gray-900">Multimodal ASR + OCR Extraction</h3>
            <p className="text-xs text-gray-600 leading-relaxed">
              WhisperX speech recognition combined with PaddleOCR visual text extraction across video frames, slides, and PDFs.
            </p>
          </div>

          <div className="card space-y-3 border-t-4 border-t-amber-500">
            <div className="w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
              2
            </div>
            <h3 className="font-bold text-gray-900">Cross-Modal Conflict Detection</h3>
            <p className="text-xs text-gray-600 leading-relaxed">
              Experimental conflict detector identifying disagreements between spoken ASR and written OCR (e.g. O(n log n) vs O(n²)).
            </p>
          </div>

          <div className="card space-y-3 border-t-4 border-t-purple-600">
            <div className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
              3
            </div>
            <h3 className="font-bold text-gray-900">Verified Knowledge Graph (VKEG)</h3>
            <p className="text-xs text-gray-600 leading-relaxed">
              Evolutionary knowledge graph preserving history, tracking superseded formulas, and building verified lineage chains.
            </p>
          </div>

          <div className="card space-y-3 border-t-4 border-t-blue-600">
            <div className="w-9 h-9 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
              4
            </div>
            <h3 className="font-bold text-gray-900">Hybrid Indexing & Dynamic Routing</h3>
            <p className="text-xs text-gray-600 leading-relaxed">
              Combines Qdrant vector embeddings with BM25 lexical search and transparent rule-based query classification.
            </p>
          </div>

          <div className="card space-y-3 border-t-4 border-t-emerald-600">
            <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
              5
            </div>
            <h3 className="font-bold text-gray-900">Provenance-Aware Answer Generation</h3>
            <p className="text-xs text-gray-600 leading-relaxed">
              LLM answers strictly cited with clickable video timestamps and page numbers, highlighting unverified or superseded facts.
            </p>
          </div>

          <div className="card space-y-3 border-t-4 border-t-indigo-600">
            <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
              6
            </div>
            <h3 className="font-bold text-gray-900">Active Learning Suite</h3>
            <p className="text-xs text-gray-600 leading-relaxed">
              Automatic generation of timestamped summaries, adaptive quizzes (MCQ/Fill-blank), 3D flip flashcards, and revision notes.
            </p>
          </div>
        </div>
      </div>

      {/* Footer info */}
      <div className="text-center text-xs text-gray-400 border-t border-gray-200 pt-6 space-y-1">
        <p>VisionRAG-X Final Year Research Project Prototype</p>
        <p>Built with FastAPI, Qdrant, PostgreSQL, WhisperX, PaddleOCR & React</p>
      </div>
    </div>
  )
}
