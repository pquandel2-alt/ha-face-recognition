import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { frigateAPI, personsAPI } from '../api'

const NO_IMAGE_SRC =
  'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23333" width="100" height="100"/%3E%3Ctext fill="%23666" text-anchor="middle" dy=".3em" x="50" y="50"%3ENo image%3C/text%3E%3C/svg%3E'

// The API requires a custom Basic-Auth header, so a plain <img src="/api/..."> can't
// authenticate — fetch the bytes via the authenticated axios instance instead and
// render them as an object URL.
function AuthImage({ url, className }) {
  const [src, setSrc] = useState(null)

  useEffect(() => {
    let objectUrl
    let cancelled = false
    api
      .get(url, { responseType: 'blob' })
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
  }, [url])

  return <img src={src || NO_IMAGE_SRC} alt="" className={className} />
}

function TrainedFacesTab() {
  const queryClient = useQueryClient()
  const [selections, setSelections] = useState({}) // { [name]: Set(filenames) }
  const [targets, setTargets] = useState({}) // { [name]: personId | 'new' }

  const { data: facesData, isLoading: loadingFaces } = useQuery({
    queryKey: ['frigate_faces'],
    queryFn: () => frigateAPI.listTrainedFaces().then((r) => r.data),
  })

  const { data: persons = [] } = useQuery({
    queryKey: ['persons'],
    queryFn: () => personsAPI.list().then((r) => r.data),
  })

  const createPersonMutation = useMutation({
    mutationFn: (name) => personsAPI.create(name).then((r) => r.data),
  })

  const importMutation = useMutation({
    mutationFn: ({ name, filenames, personId }) =>
      frigateAPI.importTrainedFaces(name, filenames, personId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['persons'] })
      queryClient.invalidateQueries({ queryKey: ['training_status'] })
      // Backend excludes already-imported filenames from this list, so
      // refetching removes what was just imported from the gallery.
      queryClient.invalidateQueries({ queryKey: ['frigate_faces'] })
    },
  })

  const matchingPersonId = (frigateName) => {
    const match = persons.find(
      (p) => p.name.toLowerCase() === frigateName.toLowerCase()
    )
    return match ? match.id : 'new'
  }

  const toggleFile = (name, filename) => {
    setSelections((prev) => {
      const current = new Set(prev[name] || [])
      if (current.has(filename)) current.delete(filename)
      else current.add(filename)
      return { ...prev, [name]: current }
    })
  }

  const toggleAll = (name, filenames) => {
    setSelections((prev) => {
      const current = prev[name] || new Set()
      const allSelected = filenames.every((f) => current.has(f))
      return { ...prev, [name]: allSelected ? new Set() : new Set(filenames) }
    })
  }

  const handleImport = async (name) => {
    const selected = Array.from(selections[name] || [])
    if (selected.length === 0) return

    let personId = targets[name] ?? matchingPersonId(name)
    if (personId === 'new') {
      const created = await createPersonMutation.mutateAsync(name)
      personId = created.id
    }

    await importMutation.mutateAsync({ name, filenames: selected, personId })
    setSelections((prev) => ({ ...prev, [name]: new Set() }))
  }

  const names = facesData?.names || []
  const faces = facesData?.faces || {}

  if (loadingFaces) {
    return <div className="text-center py-8">Lade trainierte Gesichter aus Frigate...</div>
  }

  if (names.length === 0) {
    return (
      <div className="text-center text-gray-400 py-12">
        Frigate hat noch keine trainierten Gesichter (Face Recognition in Frigate einrichten
        und dort Gesichter zuweisen).
      </div>
    )
  }

  return (
    <div className="space-y-10">
      {names.map((name) => {
        const filenames = faces[name] || []
        const selected = selections[name] || new Set()
        const target = targets[name] ?? matchingPersonId(name)

        return (
          <div key={name} className="bg-gray-800 rounded-lg p-6">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
              <h3 className="text-xl font-bold">
                {name} <span className="text-gray-400 font-normal">({filenames.length} Bilder)</span>
              </h3>

              <div className="flex items-center gap-3">
                <select
                  value={target}
                  onChange={(e) =>
                    setTargets((prev) => ({
                      ...prev,
                      [name]: e.target.value === 'new' ? 'new' : Number(e.target.value),
                    }))
                  }
                  className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
                >
                  <option value="new">Neue Person "{name}" anlegen</option>
                  {persons.map((p) => (
                    <option key={p.id} value={p.id}>
                      Zu „{p.name}" hinzufügen
                    </option>
                  ))}
                </select>

                <button
                  onClick={() => toggleAll(name, filenames)}
                  className="text-sm text-blue-400 hover:text-blue-300"
                >
                  {filenames.every((f) => selected.has(f)) ? 'Alle abwählen' : 'Alle auswählen'}
                </button>

                <button
                  onClick={() => handleImport(name)}
                  disabled={selected.size === 0 || importMutation.isPending}
                  className="bg-green-600 hover:bg-green-700 disabled:opacity-50 px-4 py-2 rounded font-medium text-sm"
                >
                  {importMutation.isPending
                    ? 'Importiere...'
                    : `${selected.size} Bild${selected.size === 1 ? '' : 'er'} importieren`}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3">
              {filenames.map((filename) => (
                <label
                  key={filename}
                  className={`relative rounded-lg overflow-hidden cursor-pointer transition ${
                    selected.has(filename) ? 'ring-2 ring-blue-500' : 'ring-1 ring-gray-600'
                  }`}
                >
                  <AuthImage
                    url={`/frigate/faces/${name}/${filename}`}
                    className="w-full h-24 object-cover"
                  />
                  <div className="absolute inset-0 bg-black bg-opacity-20 hover:bg-opacity-30 transition flex items-center justify-center">
                    <input
                      type="checkbox"
                      checked={selected.has(filename)}
                      onChange={() => toggleFile(name, filename)}
                      className="w-5 h-5"
                    />
                  </div>
                </label>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function EventSnapshotsTab() {
  const queryClient = useQueryClient()
  const [selectedPersonId, setSelectedPersonId] = useState(null)
  const [selectedEventIds, setSelectedEventIds] = useState([])

  const { data: snapshots = [], isLoading: loadingSnapshots } = useQuery({
    queryKey: ['frigate_snapshots'],
    queryFn: () => frigateAPI.listSnapshots(50).then((r) => r.data),
  })

  const { data: persons = [] } = useQuery({
    queryKey: ['persons'],
    queryFn: () => personsAPI.list().then((r) => r.data),
  })

  const importMutation = useMutation({
    mutationFn: async ({ eventId, personId }) => frigateAPI.importSnapshot(eventId, personId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['persons'] })
      queryClient.invalidateQueries({ queryKey: ['training_status'] })
      // Backend excludes already-imported events from this list, so
      // refetching removes what was just imported from the gallery.
      queryClient.invalidateQueries({ queryKey: ['frigate_snapshots'] })
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
      <div className="lg:col-span-1">
        <div className="bg-gray-800 p-6 rounded-lg sticky top-8">
          <h3 className="font-bold mb-4">Zielperson</h3>
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
                ? `Importiere ${selectedEventIds.length}...`
                : `${selectedEventIds.length} Bilder importieren`}
            </button>
          )}
        </div>
      </div>

      <div className="lg:col-span-3">
        {loadingSnapshots ? (
          <div className="text-center py-8">Lade Ereignisse...</div>
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
                <AuthImage
                  url={`/frigate/thumbnail/${event.id}`}
                  className="w-full h-40 object-cover"
                />

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
            Keine aktuellen Personen-Ereignisse in Frigate gefunden
          </div>
        )}
      </div>
    </div>
  )
}

export default function FrigateImportPage() {
  const [tab, setTab] = useState('faces')

  const { data: frigateHealth } = useQuery({
    queryKey: ['frigate_health'],
    queryFn: () => frigateAPI.health().then((r) => r.data),
    refetchInterval: 5000,
  })

  if (!frigateHealth) {
    return <div className="text-center py-8">Prüfe Frigate-Verbindung...</div>
  }

  if (!frigateHealth.healthy) {
    return (
      <div className="bg-red-900 border border-red-600 p-4 rounded-lg">
        <h2 className="text-xl font-bold text-red-200 mb-2">Frigate nicht erreichbar</h2>
        <p className="text-red-100">
          Verbindung zur Frigate-API unter{' '}
          <span className="font-mono">{frigateHealth.url}</span> fehlgeschlagen.
        </p>
        <p className="text-red-100 text-sm mt-2">
          Prüfe, ob Frigate läuft und die URL in den Add-on-Optionen korrekt ist.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Frigate Import</h2>

      <div className="flex gap-4 mb-8 border-b border-gray-700">
        <button
          onClick={() => setTab('faces')}
          className={`pb-3 px-1 font-medium ${
            tab === 'faces'
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Trainierte Gesichter (aus Frigate)
        </button>
        <button
          onClick={() => setTab('events')}
          className={`pb-3 px-1 font-medium ${
            tab === 'events'
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Personen-Ereignisse
        </button>
      </div>

      {tab === 'faces' ? <TrainedFacesTab /> : <EventSnapshotsTab />}
    </div>
  )
}
