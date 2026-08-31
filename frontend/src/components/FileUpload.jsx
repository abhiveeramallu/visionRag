import React, { useState, useRef } from 'react'
import { Upload, FileVideo, Music, FileText, Image as ImageIcon, CheckCircle, AlertCircle } from 'lucide-react'

export default function FileUpload({ onFile, isUploading, progress, error }) {
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const fileInputRef = useRef(null)

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setDragOver(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      setSelectedFile(file)
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0])
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (selectedFile && onFile) {
      onFile(selectedFile)
    }
  }

  const getFileIcon = (filename) => {
    const ext = filename ? filename.split('.').pop().toLowerCase() : ''
    if (['mp4', 'mkv'].includes(ext)) return <FileVideo className="w-8 h-8 text-purple-600" />
    if (['mp3', 'wav'].includes(ext)) return <Music className="w-8 h-8 text-blue-600" />
    if (['pdf', 'ppt', 'pptx'].includes(ext)) return <FileText className="w-8 h-8 text-red-600" />
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return <ImageIcon className="w-8 h-8 text-green-600" />
    return <Upload className="w-8 h-8 text-gray-500" />
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 ${
          dragOver
            ? 'border-primary-500 bg-primary-50 scale-[1.01]'
            : selectedFile
            ? 'border-green-400 bg-green-50/30'
            : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50/50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".mp4,.mkv,.mp3,.wav,.pdf,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp"
          onChange={handleFileChange}
          disabled={isUploading}
        />

        <div className="flex flex-col items-center justify-center space-y-3">
          {selectedFile ? (
            <>
              {getFileIcon(selectedFile.name)}
              <div>
                <p className="font-semibold text-gray-900">{selectedFile.name}</p>
                <p className="text-xs text-gray-500">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
              <p className="text-xs text-primary-600 underline">Click or drag to change file</p>
            </>
          ) : (
            <>
              <div className="w-12 h-12 rounded-full bg-primary-100 flex items-center justify-center text-primary-600">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <p className="font-medium text-gray-900">Drag & drop your file here, or browse</p>
                <p className="text-xs text-gray-500 mt-1">
                  Supports MP4, MKV, MP3, WAV, PDF, PPT/PPTX, Images
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {isUploading && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-gray-600 font-medium">
            <span>Uploading...</span>
            <span>{progress || 0}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress || 0}%` }}
            ></div>
          </div>
        </div>
      )}

      <button
        type="submit"
        disabled={!selectedFile || isUploading}
        className="w-full btn-primary py-3 flex items-center justify-center space-x-2 text-base font-semibold shadow-sm"
      >
        <Upload className="w-5 h-5" />
        <span>{isUploading ? 'Uploading Material...' : 'Process Material'}</span>
      </button>
    </form>
  )
}
