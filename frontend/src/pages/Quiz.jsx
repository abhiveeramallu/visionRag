import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { generateQuiz, getSources } from '../services/api'
import QuizCard from '../components/QuizCard'
import { HelpCircle, Loader2, Sparkles, Trophy, RotateCcw } from 'lucide-react'
import SourceSelect from '../components/SourceSelect'
import GenerationNotice from '../components/GenerationNotice'

export default function Quiz() {
  const { sourceId } = useParams()
  const [quizType, setQuizType] = useState('mcq')
  const [difficulty, setDifficulty] = useState('medium')
  const [numQuestions, setNumQuestions] = useState(5)
  const [topic, setTopic] = useState('')
  const [quizData, setQuizData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [score, setScore] = useState(0)
  const [completed, setCompleted] = useState(false)

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
    setQuizData(null)
    setCompleted(false)
  }

  const handleGenerate = async () => {
    const targetId = activeSourceId
    if (!targetId) return
    setLoading(true)
    setCompleted(false)
    setCurrentIndex(0)
    setScore(0)
    try {
      const res = await generateQuiz(targetId, quizType, difficulty, numQuestions, topic || null)
      setQuizData(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleAnswer = (userAnswer, isCorrect) => {
    // isCorrect comes from QuizCard's own verdict — the same one shown to
    // the student as "Correct!"/"Incorrect" — so the tally can never disagree
    // with what was actually displayed (it previously recomputed this with a
    // stricter, different comparison and could silently disagree).
    if (isCorrect) setScore((prev) => prev + 1)
    // Advancing now happens only when the student clicks "Next" in QuizCard
    // (see handleNext) — no more auto-advancing on a blind timer.
  }

  const handleNext = () => {
    if (currentIndex + 1 < quizData.questions.length) {
      setCurrentIndex((prev) => prev + 1)
    } else {
      setCompleted(true)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 py-4">
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-extrabold text-gray-900 flex items-center space-x-2">
          <HelpCircle className="w-6 h-6 text-primary-600 inline" />
          <span>Interactive Quiz Generator</span>
        </h1>
        <p className="text-xs text-gray-500 mt-1">Generate grounded educational quizzes from verified material.</p>
      </div>

      {/* Config Panel */}
      <div className="card p-5 space-y-4 bg-gray-50/50">
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">Quiz Settings</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <SourceSelect sources={sources} value={activeSourceId} onChange={handleSourceChange} />

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Question Type</label>
            <select
              value={quizType}
              onChange={(e) => setQuizType(e.target.value)}
              className="select text-xs w-full"
            >
              <option value="mcq">Multiple Choice (MCQ)</option>
              <option value="true_false">True / False</option>
              <option value="fill_blank">Fill in the Blank</option>
              <option value="short_answer">Short Answer</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Difficulty</label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="select text-xs w-full"
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Questions Count</label>
            <select
              value={numQuestions}
              onChange={(e) => setNumQuestions(Number(e.target.value))}
              className="select text-xs w-full"
            >
              <option value={3}>3 Questions</option>
              <option value={5}>5 Questions</option>
              <option value={10}>10 Questions</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1">Topic (Optional)</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Merge Sort"
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
          <span>{loading ? 'Generating Grounded Quiz...' : 'Generate New Quiz'}</span>
        </button>

        {sources.length === 0 && (
          <p className="text-xs text-gray-400 text-center">No processed sources yet — upload something first.</p>
        )}
      </div>

      {/* Quiz Area */}
      {quizData?.error && <GenerationNotice message={quizData.error} />}

      {quizData && quizData.questions && quizData.questions.length > 0 && !completed && (
        <QuizCard
          // Force a fresh component instance per question — without a key
          // tied to the question, React reuses the same instance across
          // questions and its internal "submitted"/selected-option state
          // bleeds into the next question instead of resetting.
          key={quizData.questions[currentIndex].question_id || currentIndex}
          question={quizData.questions[currentIndex]}
          questionNumber={currentIndex + 1}
          total={quizData.questions.length}
          isLast={currentIndex + 1 >= quizData.questions.length}
          onAnswer={handleAnswer}
          onNext={handleNext}
        />
      )}

      {/* Quiz Completed Results */}
      {completed && quizData && (
        <div className="card p-8 text-center space-y-4 shadow-md bg-gradient-to-b from-white to-green-50/30">
          <div className="w-16 h-16 rounded-full bg-green-100 text-green-600 mx-auto flex items-center justify-center">
            <Trophy className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Quiz Completed!</h2>
          <p className="text-base text-gray-700">
            You scored <span className="font-bold text-primary-600">{score}</span> out of{' '}
            <span className="font-bold">{quizData.questions.length}</span> (
            {Math.round((score / quizData.questions.length) * 100)}%)
          </p>

          <button
            onClick={handleGenerate}
            className="btn-primary py-2.5 px-6 font-semibold text-xs inline-flex items-center space-x-2"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Retake / Generate New Quiz</span>
          </button>
        </div>
      )}
    </div>
  )
}
