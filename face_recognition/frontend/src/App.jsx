import { HashRouter as Router, Routes, Route, Link } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PersonsPage from './pages/PersonsPage'
import TrainingPage from './pages/TrainingPage'
import EventsPage from './pages/EventsPage'
import FrigateImportPage from './pages/FrigateImportPage'
import StatsPage from './pages/StatsPage'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="min-h-screen bg-gray-900 text-white">
          {/* Header */}
          <header className="bg-gray-800 border-b border-gray-700">
            <div className="max-w-7xl mx-auto px-4 py-4">
              <h1 className="text-2xl font-bold mb-4">Face Recognition System</h1>
              <nav className="flex gap-6">
                <Link
                  to="/"
                  className="text-blue-400 hover:text-blue-300 font-medium"
                >
                  Persons
                </Link>
                <Link
                  to="/training"
                  className="text-blue-400 hover:text-blue-300 font-medium"
                >
                  Training
                </Link>
                <Link
                  to="/events"
                  className="text-blue-400 hover:text-blue-300 font-medium"
                >
                  Events
                </Link>
                <Link
                  to="/frigate"
                  className="text-blue-400 hover:text-blue-300 font-medium"
                >
                  Frigate Import
                </Link>
                <Link
                  to="/stats"
                  className="text-blue-400 hover:text-blue-300 font-medium"
                >
                  Stats
                </Link>
              </nav>
            </div>
          </header>

          {/* Main Content */}
          <main className="max-w-7xl mx-auto px-4 py-8">
            <Routes>
              <Route path="/" element={<PersonsPage />} />
              <Route path="/training" element={<TrainingPage />} />
              <Route path="/events" element={<EventsPage />} />
              <Route path="/frigate" element={<FrigateImportPage />} />
              <Route path="/stats" element={<StatsPage />} />
            </Routes>
          </main>
        </div>
      </Router>
    </QueryClientProvider>
  )
}

export default App
