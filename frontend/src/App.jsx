import { useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import AddSourceModal from './components/AddSourceModal'
import Home from './pages/Home'
import Sources from './pages/Sources'
import SourceDetail from './pages/SourceDetail'
import Upload from './pages/Upload'
import Processing from './pages/Processing'
import Chat from './pages/Chat'
import KnowledgeUnits from './pages/KnowledgeUnits'
import KnowledgeGraph from './pages/KnowledgeGraph'
import KnowledgeEvolution from './pages/KnowledgeEvolution'
import Evaluation from './pages/Evaluation'
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
            {/* 1. Home / Sources */}
            <Route path="/" element={<Home />} />
            <Route path="/sources" element={<Sources />} />
            <Route path="/source/:sourceId" element={<SourceDetail />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/processing/:sourceId" element={<Processing />} />

            {/* 2. Knowledge Units */}
            <Route path="/knowledge-units" element={<KnowledgeUnits />} />
            <Route path="/knowledge-units/:kuId" element={<KnowledgeUnits />} />
            <Route path="/knowledge" element={<KnowledgeUnits />} />
            <Route path="/knowledge/:sourceId" element={<KnowledgeUnits />} />

            {/* 3. Knowledge Graph / VEKG */}
            <Route path="/knowledge-graph" element={<KnowledgeGraph />} />
            <Route path="/knowledge-evolution" element={<KnowledgeEvolution />} />
            <Route path="/knowledge-evolution/:conceptId" element={<KnowledgeEvolution />} />

            {/* 4. AI Chat */}
            <Route path="/chat" element={<Chat />} />
            <Route path="/chat/:sourceId" element={<Chat />} />

            {/* 5. Evaluation */}
            <Route path="/evaluation" element={<Evaluation />} />

            {/* Utility */}
            <Route path="/search" element={<Search />} />

            {/* Redirects for removed obsolete features */}
            <Route path="/summary/*" element={<Navigate to="/" replace />} />
            <Route path="/quiz/*" element={<Navigate to="/" replace />} />
            <Route path="/flashcards/*" element={<Navigate to="/" replace />} />
            <Route path="/notes/*" element={<Navigate to="/" replace />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>

      <AddSourceModal open={addSourceOpen} onClose={() => setAddSourceOpen(false)} />
    </div>
  )
}

export default App
