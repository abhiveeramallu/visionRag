import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { generateFlashcards, getSources } from '../services/api'
import FlashCard from '../components/FlashCard'
import { Layers, Loader2, Sparkles, Download, Shuffle } from 'lucide-react'
import SourceSelect from '../components/SourceSelect'
import GenerationNotice from '../components/GenerationNotice'

export default function Flashcards() {
  const { sourceId } = useParams()
  const [numCards, setNumCards] = useState(10)
  const [topic, setTopic] = useState('')
  const [cardsData, setCardsData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)

  const [sources, setSources] = useState([])
  const [activeSourceId, setActiveSourceId] = useState(sourceId || null)

  useEffect(() => {
    getSources()
      .then((data) => {
        const done = (data || []).filter((s) => s.status === 'completed')
        setSources(done)
        if (!sourceId && !activeSourceId && done.length > 0) {
          setActiveSourceId(done[0].id)
        }
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId])

  const handleSourceChange = (id) => {
    setActiveSourceId(id)
    setCardsData(null)
  }

  const handleGenerate = async () => {
    const targetId = activeSourceId
    if (!targetId) return
    setLoading(true)
    setCurrentIndex(0)
    try {
      const res = await generateFlashcards(targetId, numCards, topic || null)
      setCardsData(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleShuffle = () => {
    if (cardsData?.cards) {
      const shuffled = [...cardsData.cards].sort(() => Math.random() - 0.5)
      setCardsData({ ...cardsData, cards: shuffled })
      setCurrentIndex(0)
    }
  }

  const handleDownloadCSV = () => {
    const currentId = sourceId || activeSourceId || ''
    if (cardsData?.cards) {
      const csvContent =
        'data:text/csv;charset=utf-8,' +
        ['Front,Back,Concept']
          .concat(
            cardsData.cards.map(
              (c) => `"${c.front.replace(/"/g, '""')}","${c.back.replace(/"/g, '""')}","${c.concept}"`
            )
          )
          .join('\n')
      const encodedUri = encodeURI(csvContent)
      const link = document.createElement('a')
      link.setAttribute('href', encodedUri)
      link.setAttribute('download', `flashcards-${currentId.slice(0, 6)}.csv`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 py-4">
      <div className="flex items-center justify-between border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 flex items-center space-x-2">
            <Layers className="w-6 h-6 text-primary-600 inline" />
            <span>Interactive Flashcards</span>
          </h1>
          <p className="text-xs text-gray-500 mt-1">Generated from verified knowledge units.</p>
        </div>

        {cardsData?.cards && (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleShuffle}
              className="btn-secondary py-1.5 px-3 text-xs flex items-center space-x-1"
            >
              <Shuffle className="w-3.5 h-3.5" />
              <span>Shuffle</span>
            </button>
            <button
              onClick={handleDownloadCSV}
              className="btn-outline py-1.5 px-3 text-xs flex items-center space-x-1"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>
          </div>
        )}
      </div>

      {/* Config Panel */}
      <div className="card p-5 space-y-4 bg-gray-50/50">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <SourceSelect sources={sources} value={activeSourceId} onChange={handleSourceChange} />

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Number of Cards</label>
            <select
              value={numCards}
              onChange={(e) => setNumCards(Number(e.target.value))}
              className="select text-xs w-full"
            >
              <option value={5}>5 Cards</option>
              <option value={10}>10 Cards</option>
              <option value={20}>20 Cards</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Topic Filter (Optional)</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Newton-Raphson"
              className="input text-xs w-full"
            />
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading || !activeSourceId}
          className="w-full btn-primary py-2.5 text-xs font-semibold shadow-xs flex items-center justify-center space-x-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          <span>{loading ? 'Generating Flashcards...' : 'Generate Flashcards'}</span>
        </button>

        {sources.length === 0 && (
          <p className="text-xs text-gray-400 text-center">No processed sources yet — upload something first.</p>
        )}
      </div>

      {/* Flashcard Component */}
      {cardsData?.error && <GenerationNotice message={cardsData.error} />}

      {cardsData && cardsData.cards && cardsData.cards.length > 0 ? (
        <FlashCard
          card={cardsData.cards[currentIndex]}
          cardNumber={currentIndex + 1}
          total={cardsData.cards.length}
          onNext={() => setCurrentIndex((prev) => Math.min(prev + 1, cardsData.cards.length - 1))}
          onPrev={() => setCurrentIndex((prev) => Math.max(prev - 1, 0))}
        />
      ) : !cardsData?.error ? (
        <div className="card text-center py-16 text-gray-500 text-sm">
          Click "Generate Flashcards" to start studying.
        </div>
      ) : null}
    </div>
  )
}
