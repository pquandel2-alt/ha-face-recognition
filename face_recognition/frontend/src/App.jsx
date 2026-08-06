import { HashRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import PersonsPage from './pages/PersonsPage'
import TrainingPage from './pages/TrainingPage'
import EventsPage from './pages/EventsPage'
import FrigateImportPage from './pages/FrigateImportPage'
import StatsPage from './pages/StatsPage'
import SettingsPage from './pages/SettingsPage'

const queryClient = new QueryClient()

const NAV_ITEMS = [
  { to: '/', label: 'Persons' },
  { to: '/training', label: 'Training' },
  { to: '/events', label: 'Events' },
  { to: '/frigate', label: 'Frigate Import' },
  { to: '/stats', label: 'Stats' },
  { to: '/settings', label: 'Settings' },
]

function NavLink({ to, children }) {
  const location = useLocation()
  const active = location.pathname === to
  return (
    <Link
      to={to}
      className={`font-medium transition ${
        active ? 'text-accent' : 'text-gray-400 hover:text-gray-200'
      }`}
    >
      {children}
    </Link>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="min-h-screen bg-surface text-gray-100">
          {/* Header */}
          <header className="bg-surface-header border-b border-border">
            <div className="max-w-7xl mx-auto px-4 py-4">
              <h1 className="text-2xl font-bold mb-4">Face Recognition System</h1>
              <nav className="flex gap-6">
                {NAV_ITEMS.map((item) => (
                  <NavLink key={item.to} to={item.to}>
                    {item.label}
                  </NavLink>
                ))}
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
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </main>
        </div>
      </Router>
    </QueryClientProvider>
  )
}

export default App
