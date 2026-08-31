import React, { useState } from 'react'
import { Youtube, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react'

export default function YouTubeInput({ onSubmit, isLoading }) {
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [urlError, setUrlError] = useState('')

  const validateUrl = (val) => {
    if (!val) return ''
    if (!val.includes('youtube.com') && !val.includes('youtu.be')) {
      return 'Please enter a valid YouTube video URL'
    }
    return ''
  }

  const handleChange = (e) => {
    const val = e.target.value
    setUrl(val)
    setUrlError(validateUrl(val))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const err = validateUrl(url)
    if (err) {
      setUrlError(err)
      return
    }
    if (url && onSubmit) {
      onSubmit(url, title || null)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
          YouTube Video URL
        </label>
        <div className="relative rounded-lg shadow-sm">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-red-600">
            <Youtube className="w-5 h-5" />
          </div>
          <input
            type="url"
            value={url}
            onChange={handleChange}
            placeholder="https://www.youtube.com/watch?v=..."
            required
            disabled={isLoading}
            className={`w-full pl-10 pr-4 py-3 border rounded-lg text-sm focus:outline-none focus:ring-2 ${
              urlError
                ? 'border-red-300 focus:ring-red-500'
                : url && !urlError
                ? 'border-green-300 focus:ring-green-500'
                : 'border-gray-300 focus:ring-primary-500'
            }`}
          />
          {url && !urlError && (
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center text-green-500 pointer-events-none">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          )}
        </div>
        {urlError && (
          <p className="text-xs text-red-600 flex items-center space-x-1 mt-1">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>{urlError}</span>
          </p>
        )}
      </div>

      <div className="space-y-1">
        <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
          Custom Title <span className="text-gray-400 font-normal">(Optional)</span>
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. CS50 Lecture 3: Algorithms"
          disabled={isLoading}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>

      <button
        type="submit"
        disabled={!url || !!urlError || isLoading}
        className="w-full btn-primary py-3 flex items-center justify-center space-x-2 text-base font-semibold shadow-sm"
      >
        <span>{isLoading ? 'Ingesting Video...' : 'Process YouTube Video'}</span>
        <ArrowRight className="w-5 h-5" />
      </button>
    </form>
  )
}
