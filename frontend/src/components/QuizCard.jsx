import React, { useState } from 'react'
import { CheckCircle2, XCircle, HelpCircle, ArrowRight, BookOpen } from 'lucide-react'

export default function QuizCard({ question, questionNumber, total, onAnswer }) {
  const [selectedOption, setSelectedOption] = useState('')
  const [userText, setUserText] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const isMCQ = question.question_type === 'mcq'
  const isTF = question.question_type === 'true_false'
  const isFill = question.question_type === 'fill_blank'
  const isShort = question.question_type === 'short_answer'

  const handleSubmit = (e) => {
    e.preventDefault()
    if (submitted) return
    setSubmitted(true)
    const userAns = isMCQ || isTF ? selectedOption : userText
    if (onAnswer) onAnswer(userAns)
  }

  const handleNext = () => {
    setSubmitted(false)
    setSelectedOption('')
    setUserText('')
  }

  const isCorrect = () => {
    if (!submitted) return false
    const userAns = (isMCQ || isTF ? selectedOption : userText).trim().toLowerCase()
    const correctAns = (question.answer || '').trim().toLowerCase()
    return userAns === correctAns || correctAns.includes(userAns)
  }

  return (
    <div className="card space-y-6 max-w-2xl mx-auto shadow-md border-primary-100">
      <div className="flex justify-between items-center border-b border-gray-100 pb-3">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Question {questionNumber} of {total}
        </span>
        <span className="badge bg-primary-100 text-primary-800 uppercase font-mono text-[10px]">
          {question.difficulty || 'medium'} • {question.question_type}
        </span>
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-bold text-gray-900 leading-snug">
          {question.question}
        </h3>

        <form onSubmit={handleSubmit} className="space-y-3">
          {/* MCQ Options */}
          {isMCQ && question.options && (
            <div className="space-y-2">
              {question.options.map((opt, idx) => {
                const optLetter = opt.charAt(0)
                const isSelected = selectedOption === opt
                const isAnswer = question.answer && question.answer.startsWith(optLetter)

                let bgClass = 'border-gray-200 hover:border-primary-400 bg-white'
                if (submitted) {
                  if (isAnswer) bgClass = 'border-green-500 bg-green-50 text-green-900 font-semibold'
                  else if (isSelected && !isAnswer) bgClass = 'border-red-500 bg-red-50 text-red-900'
                } else if (isSelected) {
                  bgClass = 'border-primary-600 bg-primary-50 text-primary-900 font-semibold'
                }

                return (
                  <label
                    key={idx}
                    className={`flex items-center space-x-3 p-3.5 rounded-xl border cursor-pointer transition-all ${bgClass}`}
                  >
                    <input
                      type="radio"
                      name="mcq-option"
                      value={opt}
                      checked={selectedOption === opt}
                      onChange={(e) => !submitted && setSelectedOption(e.target.value)}
                      disabled={submitted}
                      className="text-primary-600 focus:ring-primary-500 h-4 w-4"
                    />
                    <span className="text-sm font-medium">{opt}</span>
                  </label>
                )
              })}
            </div>
          )}

          {/* True / False */}
          {isTF && (
            <div className="grid grid-cols-2 gap-4">
              {['True', 'False'].map((val) => {
                const isSelected = selectedOption === val
                const isAnswer = (question.answer || '').toLowerCase() === val.toLowerCase()
                let btnClass = 'border-gray-300 hover:border-primary-400 bg-white'
                if (submitted) {
                  if (isAnswer) btnClass = 'border-green-500 bg-green-50 text-green-900 font-bold'
                  else if (isSelected && !isAnswer) btnClass = 'border-red-500 bg-red-50 text-red-900'
                } else if (isSelected) {
                  btnClass = 'border-primary-600 bg-primary-50 font-bold'
                }

                return (
                  <button
                    key={val}
                    type="button"
                    onClick={() => !submitted && setSelectedOption(val)}
                    className={`py-4 rounded-xl border text-base font-semibold transition-all ${btnClass}`}
                  >
                    {val}
                  </button>
                )
              })}
            </div>
          )}

          {/* Fill in Blank / Short Answer */}
          {(isFill || isShort) && (
            <div className="space-y-2">
              <textarea
                rows={isShort ? 3 : 1}
                value={userText}
                onChange={(e) => setUserText(e.target.value)}
                placeholder="Type your answer here..."
                disabled={submitted}
                className="w-full p-3 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
            </div>
          )}

          {!submitted ? (
            <button
              type="submit"
              disabled={isMCQ || isTF ? !selectedOption : !userText.trim()}
              className="w-full btn-primary py-3 font-semibold shadow-sm"
            >
              Submit Answer
            </button>
          ) : null}
        </form>
      </div>

      {/* Answer & Explanation Box */}
      {submitted && (
        <div className="pt-4 border-t border-gray-100 space-y-3 animate-fade-in">
          <div
            className={`p-4 rounded-xl border flex items-start space-x-3 ${
              isCorrect() ? 'bg-green-50 border-green-200 text-green-900' : 'bg-red-50 border-red-200 text-red-900'
            }`}
          >
            {isCorrect() ? (
              <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            )}
            <div className="space-y-1">
              <p className="font-bold text-sm">
                {isCorrect() ? 'Correct!' : 'Incorrect'}
              </p>
              <p className="text-xs font-semibold">
                Correct Answer: <span className="font-mono">{question.answer}</span>
              </p>
              {question.explanation && (
                <p className="text-xs mt-2 text-gray-700 leading-relaxed">
                  <span className="font-semibold">Explanation: </span>
                  {question.explanation}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
