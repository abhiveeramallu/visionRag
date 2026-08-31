import React, { useState } from 'react'
import { RotateCw, CheckCircle, HelpCircle, ArrowLeft, ArrowRight } from 'lucide-react'

export default function FlashCard({ card, cardNumber, total, onNext, onPrev }) {
  const [isFlipped, setIsFlipped] = useState(false)

  const handleFlip = () => {
    setIsFlipped(!isFlipped)
  }

  const handleNext = (e) => {
    e.stopPropagation()
    setIsFlipped(false)
    if (onNext) onNext()
  }

  const handlePrev = (e) => {
    e.stopPropagation()
    setIsFlipped(false)
    if (onPrev) onPrev()
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="flex justify-between items-center text-xs font-semibold text-gray-500">
        <span>Card {cardNumber} of {total}</span>
        <span className="bg-primary-50 text-primary-700 px-2.5 py-1 rounded-full font-mono">
          {card.concept || 'Educational Concept'}
        </span>
      </div>

      <div
        onClick={handleFlip}
        className="card-flip-wrapper h-80 w-full cursor-pointer select-none"
      >
        <div className={`card-flip-inner w-full h-full ${isFlipped ? 'flipped' : ''}`}>
          {/* Front */}
          <div className="card-face card-front absolute inset-0 card flex flex-col justify-between p-8 border-2 border-primary-100 hover:border-primary-300 transition-all shadow-md bg-gradient-to-b from-white to-primary-50/20 rounded-2xl">
            <div className="flex justify-between items-start">
              <span className="text-xs font-bold uppercase tracking-wider text-primary-600 bg-primary-100 px-2.5 py-1 rounded-md">
                Question / Prompt
              </span>
              <RotateCw className="w-4 h-4 text-gray-400" />
            </div>

            <div className="my-auto text-center">
              <h3 className="text-xl font-bold text-gray-900 leading-snug">{card.front}</h3>
            </div>

            <p className="text-xs text-center text-gray-400 font-medium">Click card to flip answer 🔄</p>
          </div>

          {/* Back */}
          <div className="card-face card-back absolute inset-0 card flex flex-col justify-between p-8 border-2 border-accent-200 shadow-md bg-gradient-to-b from-white to-accent-50/30 rounded-2xl">
            <div className="flex justify-between items-start">
              <span className="text-xs font-bold uppercase tracking-wider text-accent-700 bg-accent-100 px-2.5 py-1 rounded-md">
                Verified Answer
              </span>
              <RotateCw className="w-4 h-4 text-gray-400" />
            </div>

            <div className="my-auto text-center space-y-3">
              <p className="text-lg font-medium text-gray-900 leading-relaxed">{card.back}</p>
            </div>

            <p className="text-xs text-center text-gray-400 font-medium">Click card to see question 🔄</p>
          </div>
        </div>
      </div>

      {/* Navigation Controls */}
      <div className="flex justify-between items-center pt-2">
        <button
          onClick={handlePrev}
          disabled={cardNumber <= 1}
          className="btn-secondary px-4 py-2 flex items-center space-x-2 text-sm disabled:opacity-40"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Previous</span>
        </button>

        <button
          onClick={handleFlip}
          className="btn-outline px-6 py-2 text-sm font-semibold flex items-center space-x-2"
        >
          <RotateCw className="w-4 h-4" />
          <span>{isFlipped ? 'Show Question' : 'Flip Answer'}</span>
        </button>

        <button
          onClick={handleNext}
          disabled={cardNumber >= total}
          className="btn-primary px-4 py-2 flex items-center space-x-2 text-sm disabled:opacity-40"
        >
          <span>Next</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
