import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import Upload from './pages/Upload'
import Processing from './pages/Processing'
import Chat from './pages/Chat'
import KnowledgeView from './pages/KnowledgeView'
import Summary from './pages/Summary'
import Quiz from './pages/Quiz'
import Flashcards from './pages/Flashcards'
import Notes from './pages/Notes'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/processing/:sourceId" element={<Processing />} />
          <Route path="/knowledge/:sourceId" element={<KnowledgeView />} />
          <Route path="/chat/:sourceId" element={<Chat />} />
          <Route path="/summary/:sourceId" element={<Summary />} />
          <Route path="/quiz/:sourceId" element={<Quiz />} />
          <Route path="/flashcards/:sourceId" element={<Flashcards />} />
          <Route path="/notes/:sourceId" element={<Notes />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
