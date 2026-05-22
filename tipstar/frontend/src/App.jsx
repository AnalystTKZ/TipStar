import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import CommandCenter from './pages/CommandCenter'
import ApprovalInbox from './pages/ApprovalInbox'
import KnowledgeBase from './pages/KnowledgeBase'
import Analytics from './pages/Analytics'
import PostHistory from './pages/PostHistory'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Navigate to="/command-center" replace />} />
            <Route path="/command-center" element={<CommandCenter />} />
            <Route path="/inbox" element={<ApprovalInbox />} />
            <Route path="/knowledge" element={<KnowledgeBase />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/history" element={<PostHistory />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
