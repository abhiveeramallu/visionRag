import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import AddSourceModal from './components/AddSourceModal'
import Home from './pages/Home'
import Sources from './pages/Sources'
import SourceDetail from './pages/SourceDetail'
import Upload from './pages/Upload'
import Processing from './pages/Processing'
import Chat from './pages/Chat'
import KnowledgeView from './pages/KnowledgeView'
import KnowledgeGraph from './pages/KnowledgeGraph'
import KnowledgeEvolution from './pages/KnowledgeEvolution'
import Summary from './pages/Summary'
import Quiz from './pages/Quiz'
import Flashcards from './pages/Flashcards'
import Notes from './pages/Notes'
import Search from './pages/Search'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [addSourceOpen, setAddSourceOpen] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar onMenuClick={() => setSidebarOpen(true)} onAddSource={() => setAddSourceOpen(true)} />

        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/sources" element={<Sources />} />
            <Route path="/source/:sourceId" element={<SourceDetail />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/processing/:sourceId" element={<Processing />} />
            <Route path="/knowledge" element={<KnowledgeView />} />
            <Route path="/knowledge/:sourceId" element={<KnowledgeView />} />
            <Route path="/knowledge-graph" element={<KnowledgeGraph />} />
            <Route path="/knowledge-evolution" element={<KnowledgeEvolution />} />
            <Route path="/knowledge-evolution/:conceptId" element={<KnowledgeEvolution />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/chat/:sourceId" element={<Chat />} />
            <Route path="/summary" element={<Summary />} />
            <Route path="/summary/:sourceId" element={<Summary />} />
            <Route path="/quiz" element={<Quiz />} />
            <Route path="/quiz/:sourceId" element={<Quiz />} />
            <Route path="/flashcards" element={<Flashcards />} />
            <Route path="/flashcards/:sourceId" element={<Flashcards />} />
            <Route path="/notes" element={<Notes />} />
            <Route path="/notes/:sourceId" element={<Notes />} />
            <Route path="/search" element={<Search />} />
          </Routes>
        </main>
      </div>

      <AddSourceModal open={addSourceOpen} onClose={() => setAddSourceOpen(false)} />
    </div>
  )
}

export default App
