import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PersonsPage from './pages/PersonsPage'
import TrainingPage from './pages/TrainingPage'
import EventsPage from './pages/EventsPage'
import FrigateImportPage from './pages/FrigateImportPage'
import LoginGate, { logout } from './components/LoginGate'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LoginGate>
        <Router>
          <div className="min-h-screen bg-gray-900 text-white">
            {/* Header */}
            <header className="bg-gray-800 border-b border-gray-700">
              <div className="max-w-7xl mx-auto px-4 py-4">
                <div className="flex items-center justify-between mb-4">
                  <h1 className="text-2xl font-bold">Face Recognition System</h1>
                  <button
                    onClick={logout}
                    className="text-sm text-gray-400 hover:text-gray-200"
                  >
                    Abmelden
                  </button>
                </div>
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
              </Routes>
            </main>
          </div>
        </Router>
      </LoginGate>
    </QueryClientProvider>
  )
}

export default App
