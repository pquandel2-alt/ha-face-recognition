import { useEffect, useState } from 'react'
import api from '../api'

const hasStoredCredentials = () =>
  Boolean(localStorage.getItem('auth_username') && localStorage.getItem('auth_password'))

const clearStoredCredentials = () => {
  localStorage.removeItem('auth_username')
  localStorage.removeItem('auth_password')
}

export default function LoginGate({ children }) {
  const [checking, setChecking] = useState(true)
  const [authed, setAuthed] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!hasStoredCredentials()) {
      setChecking(false)
      return
    }
    api
      .get('/persons')
      .then(() => setAuthed(true))
      .catch(() => clearStoredCredentials())
      .finally(() => setChecking(false))
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setChecking(true)
    localStorage.setItem('auth_username', username)
    localStorage.setItem('auth_password', password)
    try {
      await api.get('/persons')
      setAuthed(true)
    } catch (err) {
      clearStoredCredentials()
      setError('Benutzername oder Passwort falsch.')
    } finally {
      setChecking(false)
    }
  }

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white">
        Lade...
      </div>
    )
  }

  if (!authed) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white">
        <form onSubmit={handleSubmit} className="bg-gray-800 p-8 rounded-lg w-80 space-y-4">
          <h1 className="text-xl font-bold">Anmelden</h1>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <input
            className="w-full px-3 py-2 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:border-blue-500"
            placeholder="Benutzername"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
          <input
            type="password"
            className="w-full px-3 py-2 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:border-blue-500"
            placeholder="Passwort"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-500 py-2 rounded font-medium"
          >
            Anmelden
          </button>
        </form>
      </div>
    )
  }

  return children
}

export function logout() {
  clearStoredCredentials()
  window.location.reload()
}
