import React from 'react'
import { Link, useLocation, useParams, useNavigate } from 'react-router-dom'
import {
  BookOpen, Upload, MessageSquare, FileText,
  HelpCircle, Layers, FileCode, Database, Cpu
} from 'lucide-react'

export default function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()
  
  // Extract sourceId if present in route params or path
  const pathMatch = location.pathname.match(/\/(chat|summary|quiz|flashcards|notes|knowledge|processing)\/([^/]+)/)
  const sourceId = pathMatch ? pathMatch[2] : null

  const isActive = (path) => location.pathname === path || (sourceId && location.pathname.startsWith(`${path}/${sourceId}`))

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link to="/" className="flex items-center space-x-2">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-primary-600 to-accent-500 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                V
              </div>
              <div>
                <span className="font-bold text-lg text-gray-900 bg-gradient-to-r from-primary-600 to-accent-600 bg-clip-text text-transparent">
                  VisionRAG-X
                </span>
                <span className="ml-2 text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold border border-blue-200">
                  Research Prototype
                </span>
              </div>
            </Link>

            <div className="hidden md:flex space-x-1">
              <Link
                to="/"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  location.pathname === '/' ? 'text-primary-600 bg-primary-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                Home
              </Link>
              <Link
                to="/upload"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  location.pathname === '/upload' ? 'text-primary-600 bg-primary-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                Upload Material
              </Link>
            </div>
          </div>

          {sourceId && (
            <div className="flex items-center space-x-1 overflow-x-auto py-2">
              <Link
                to={`/chat/${sourceId}`}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium ${
                  isActive('/chat') ? 'bg-primary-600 text-white shadow-sm' : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>Chat</span>
              </Link>

              <Link
                to={`/knowledge/${sourceId}`}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium ${
                  isActive('/knowledge') ? 'bg-primary-600 text-white shadow-sm' : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                <span>VKEG Graph</span>
              </Link>

              <Link
                to={`/summary/${sourceId}`}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium ${
                  isActive('/summary') ? 'bg-primary-600 text-white shadow-sm' : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Summary</span>
              </Link>

              <Link
                to={`/quiz/${sourceId}`}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium ${
                  isActive('/quiz') ? 'bg-primary-600 text-white shadow-sm' : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Quiz</span>
              </Link>

              <Link
                to={`/flashcards/${sourceId}`}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium ${
                  isActive('/flashcards') ? 'bg-primary-600 text-white shadow-sm' : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Flashcards</span>
              </Link>

              <Link
                to={`/notes/${sourceId}`}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium ${
                  isActive('/notes') ? 'bg-primary-600 text-white shadow-sm' : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <FileCode className="w-3.5 h-3.5" />
                <span>Notes</span>
              </Link>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
