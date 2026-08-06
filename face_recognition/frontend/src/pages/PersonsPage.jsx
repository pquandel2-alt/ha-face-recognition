import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { personsAPI } from '../api'
import PersonCard from '../components/PersonCard'

export default function PersonsPage() {
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [expandedPerson, setExpandedPerson] = useState(null)

  const { data: persons = [], isLoading } = useQuery({
    queryKey: ['persons'],
    queryFn: () => personsAPI.list().then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (name) => personsAPI.create(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['persons'] })
      setNewName('')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => personsAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['persons'] })
      setExpandedPerson(null)
    },
  })

  const handleCreate = (e) => {
    e.preventDefault()
    if (newName.trim()) {
      createMutation.mutate(newName)
    }
  }

  if (isLoading) return <div className="text-center py-8">Loading...</div>

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Manage Persons</h2>

      {/* Add Person Form */}
      <div className="card p-6 mb-8">
        <form onSubmit={handleCreate} className="flex gap-2">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Person name..."
            className="flex-1 bg-surface-hover text-white px-4 py-2 rounded border border-border focus:border-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="btn-primary"
          >
            {createMutation.isPending ? 'Creating...' : 'Add Person'}
          </button>
        </form>
        {createMutation.error && (
          <div className="text-danger mt-2">{createMutation.error.response?.data?.detail || 'Error creating person'}</div>
        )}
      </div>

      {/* Persons List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {persons.map((person) => (
          <PersonCard
            key={person.id}
            person={person}
            expanded={expandedPerson === person.id}
            onToggle={() => setExpandedPerson(expandedPerson === person.id ? null : person.id)}
            onDelete={() => deleteMutation.mutate(person.id)}
            onImageCountChange={() => queryClient.invalidateQueries({ queryKey: ['persons'] })}
          />
        ))}
      </div>

      {persons.length === 0 && (
        <div className="text-center text-gray-400 py-12">
          No persons yet. Create one to get started!
        </div>
      )}
    </div>
  )
}
