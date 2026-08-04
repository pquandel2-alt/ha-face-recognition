import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { frigateAPI, personsAPI } from '../api'

const NO_IMAGE_SRC =
  'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23333" width="100" height="100"/%3E%3Ctext fill="%23666" text-anchor="middle" dy=".3em" x="50" y="50"%3ENo image%3C/text%3E%3C/svg%3E'

// The API requires a custom Basic-Auth header, so a plain <img src="/api/..."> can't
// authenticate — fetch the bytes via the authenticated axios instance instead and
// render them as an object URL.
function FrigateThumbnail({ eventId, className }) {
  const [src, setSrc] = useState(null)

  useEffect(() => {
    let objectUrl
    let cancelled = false
    api
      .get(`/frigate/thumbnail/${eventId}`, { responseType: 'blob' })
      .then((res) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(res.data)
        setSrc(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setSrc(NO_IMAGE_SRC)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [eventId])

  return <img src={src || NO_IMAGE_SRC} alt={`Event ${eventId}`} className={className} />
}

export default function FrigateImportPage() {
  const queryClient = useQueryClient()
  const [selectedPersonId, setSelectedPersonId] = useState(null)
  const [selectedEventIds, setSelectedEventIds] = useState([])

  const { data: frigateHealth } = useQuery({
    queryKey: ['frigate_health'],
    queryFn: () => frigateAPI.health().then((r) => r.data),
    refetchInterval: 5000,
  })

  const { data: snapshots = [], isLoading: loadingSnapshots } = useQuery({
    queryKey: ['frigate_snapshots'],
    queryFn: () => frigateAPI.listSnapshots(50).then((r) => r.data),
    enabled: frigateHealth?.healthy ?? false,
  })

  const { data: persons = [] } = useQuery({
    queryKey: ['persons'],
    queryFn: () => personsAPI.list().then((r) => r.data),
  })

  const importMutation = useMutation({
    mutationFn: async ({ eventId, personId }) => {
      return frigateAPI.importSnapshot(eventId, personId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['persons'] })
      queryClient.invalidateQueries({ queryKey: ['training_status'] })
      setSelectedEventIds([])
    },
  })

  const handleToggleEvent = (eventId) => {
    setSelectedEventIds((prev) =>
      prev.includes(eventId) ? prev.filter((id) => id !== eventId) : [...prev, eventId]
    )
  }

  const handleImport = async () => {
    if (!selectedPersonId || selectedEventIds.length === 0) return

    for (const eventId of selectedEventIds) {
      await importMutation.mutateAsync({ eventId, personId: selectedPersonId })
    }
  }

  if (!frigateHealth) {
    return <div className="text-center py-8">Checking Frigate connection...</div>
  }

  if (!frigateHealth.healthy) {
    return (
      <div className="bg-red-900 border border-red-600 p-4 rounded-lg">
        <h2 className="text-xl font-bold text-red-200 mb-2">Frigate Not Available</h2>
        <p className="text-red-100">
          Could not connect to Frigate API at{' '}
          <span className="font-mono">{frigateHealth.url}</span>
        </p>
        <p className="text-red-100 text-sm mt-2">
          Make sure Frigate is running and the URL is correct in .env
        </p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Frigate Import</h2>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Sidebar: Select Person */}
        <div className="lg:col-span-1">
          <div className="bg-gray-800 p-6 rounded-lg sticky top-8">
            <h3 className="font-bold mb-4">Target Person</h3>
            <div className="space-y-2">
              {persons.map((person) => (
                <button
                  key={person.id}
                  onClick={() => setSelectedPersonId(person.id)}
                  className={`w-full text-left px-4 py-2 rounded transition ${
                    selectedPersonId === person.id
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                  }`}
                >
                  {person.name}
                </button>
              ))}
            </div>

            {selectedEventIds.length > 0 && (
              <button
                onClick={handleImport}
                disabled={!selectedPersonId || importMutation.isPending}
                className="w-full mt-4 bg-green-600 hover:bg-green-700 disabled:opacity-50 px-4 py-2 rounded font-medium"
              >
                {importMutation.isPending
                  ? `Importing ${selectedEventIds.length}...`
                  : `Import ${selectedEventIds.length} Images`}
              </button>
            )}
          </div>
        </div>

        {/* Main: Snapshot Gallery */}
        <div className="lg:col-span-3">
          {loadingSnapshots ? (
            <div className="text-center py-8">Loading snapshots...</div>
          ) : snapshots.events && snapshots.events.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {snapshots.events.map((event) => (
                <label
                  key={event.id}
                  className={`relative rounded-lg overflow-hidden cursor-pointer transition ${
                    selectedEventIds.includes(event.id)
                      ? 'ring-2 ring-blue-500'
                      : 'ring-1 ring-gray-600'
                  }`}
                >
                  <FrigateThumbnail eventId={event.id} className="w-full h-40 object-cover" />

                  <div className="absolute inset-0 bg-black bg-opacity-30 hover:bg-opacity-40 transition flex items-center justify-center">
                    <input
                      type="checkbox"
                      checked={selectedEventIds.includes(event.id)}
                      onChange={() => handleToggleEvent(event.id)}
                      className="w-6 h-6"
                    />
                  </div>

                  <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 px-2 py-1 text-xs">
                    <p className="text-gray-200">{event.camera}</p>
                    <p className="text-gray-400">{new Date(event.start * 1000).toLocaleTimeString()}</p>
                  </div>
                </label>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-400 py-12">
              No recent person events found in Frigate
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
