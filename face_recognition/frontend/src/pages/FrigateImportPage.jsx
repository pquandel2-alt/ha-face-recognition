import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { frigateAPI, personsAPI } from '../api'
import AuthImage from '../components/AuthImage'

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
          <div key={name} className="card p-6">
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
                  className="bg-surface-hover border border-border rounded px-3 py-2 text-sm"
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
                  className="text-sm text-accent hover:text-accent-hover"
                >
                  {filenames.every((f) => selected.has(f)) ? 'Alle abwählen' : 'Alle auswählen'}
                </button>

                <button
                  onClick={() => handleImport(name)}
                  disabled={selected.size === 0 || importMutation.isPending}
                  className="btn-success"
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
                    selected.has(filename) ? 'ring-2 ring-accent' : 'ring-1 ring-border'
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
  const [grouped, setGrouped] = useState(false)

  const { data: snapshots = [], isLoading: loadingSnapshots } = useQuery({
    queryKey: ['frigate_snapshots'],
    queryFn: () => frigateAPI.listSnapshots(50).then((r) => r.data),
    enabled: !grouped,
  })

  const { data: clusterData, isLoading: loadingClusters } = useQuery({
    queryKey: ['frigate_snapshot_clusters'],
    queryFn: () => frigateAPI.clusterSnapshots(50).then((r) => r.data),
    enabled: grouped,
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
      queryClient.invalidateQueries({ queryKey: ['frigate_snapshot_clusters'] })
      setSelectedEventIds([])
    },
  })

  const handleToggleEvent = (eventId) => {
    setSelectedEventIds((prev) =>
      prev.includes(eventId) ? prev.filter((id) => id !== eventId) : [...prev, eventId]
    )
  }

  const handleToggleCluster = (events) => {
    const ids = events.map((e) => e.id)
    setSelectedEventIds((prev) => {
      const allSelected = ids.every((id) => prev.includes(id))
      if (allSelected) return prev.filter((id) => !ids.includes(id))
      return [...new Set([...prev, ...ids])]
    })
  }

  const handleImport = async () => {
    if (!selectedPersonId || selectedEventIds.length === 0) return
    for (const eventId of selectedEventIds) {
      await importMutation.mutateAsync({ eventId, personId: selectedPersonId })
    }
  }

  const renderEventThumb = (event) => (
    <label
      key={event.id}
      className={`relative rounded-lg overflow-hidden cursor-pointer transition ${
        selectedEventIds.includes(event.id) ? 'ring-2 ring-accent' : 'ring-1 ring-border'
      }`}
    >
      <AuthImage url={`/frigate/thumbnail/${event.id}`} className="w-full h-40 object-cover" />

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
  )

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
      <div className="lg:col-span-1">
        <div className="bg-surface-raised p-6 rounded-lg sticky top-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold">Zielperson</h3>
            <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={grouped}
                onChange={(e) => setGrouped(e.target.checked)}
              />
              Gruppieren
            </label>
          </div>
          <div className="space-y-2">
            {persons.map((person) => (
              <button
                key={person.id}
                onClick={() => setSelectedPersonId(person.id)}
                className={`w-full text-left px-4 py-2 rounded transition ${
                  selectedPersonId === person.id
                    ? 'bg-accent text-white'
                    : 'bg-surface-hover text-gray-200 hover:bg-border'
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
              className="w-full mt-4 btn-success"
            >
              {importMutation.isPending
                ? `Importiere ${selectedEventIds.length}...`
                : `${selectedEventIds.length} Bilder importieren`}
            </button>
          )}
        </div>
      </div>

      <div className="lg:col-span-3">
        {!grouped ? (
          loadingSnapshots ? (
            <div className="text-center py-8">Lade Ereignisse...</div>
          ) : snapshots.events && snapshots.events.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {snapshots.events.map((event) => renderEventThumb(event))}
            </div>
          ) : (
            <div className="text-center text-gray-400 py-12">
              Keine aktuellen Personen-Ereignisse in Frigate gefunden
            </div>
          )
        ) : loadingClusters ? (
          <div className="text-center py-8">
            Analysiere Ähnlichkeiten... (kann bei vielen Ereignissen etwas dauern)
          </div>
        ) : (clusterData?.clusters?.length || 0) === 0 &&
          (clusterData?.unclustered?.length || 0) === 0 ? (
          <div className="text-center text-gray-400 py-12">
            Keine aktuellen Personen-Ereignisse in Frigate gefunden
          </div>
        ) : (
          <div className="space-y-8">
            {clusterData.clusters.map((cluster) => (
              <div key={cluster.cluster_id}>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-200">
                    Gruppe {cluster.cluster_id + 1}{' '}
                    <span className="text-gray-400 font-normal">
                      ({cluster.count} ähnliche Bilder)
                    </span>
                  </h4>
                  <button
                    onClick={() => handleToggleCluster(cluster.events)}
                    className="text-sm text-accent hover:text-accent-hover"
                  >
                    {cluster.events.every((e) => selectedEventIds.includes(e.id))
                      ? 'Gruppe abwählen'
                      : 'Gruppe auswählen'}
                  </button>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {cluster.events.map((event) => renderEventThumb(event))}
                </div>
              </div>
            ))}

            {clusterData.unclustered.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-400 mb-3">
                  Ohne eindeutige Gruppe ({clusterData.unclustered.length})
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {clusterData.unclustered.map((event) => renderEventThumb(event))}
                </div>
              </div>
            )}
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
      <div className="bg-danger-bg border border-danger-border p-4 rounded-lg">
        <h2 className="text-xl font-bold text-danger mb-2">Frigate nicht erreichbar</h2>
        <p className="text-danger">
          Verbindung zur Frigate-API unter{' '}
          <span className="font-mono">{frigateHealth.url}</span> fehlgeschlagen.
        </p>
        <p className="text-danger text-sm mt-2">
          Prüfe, ob Frigate läuft und die URL in den Add-on-Optionen korrekt ist.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Frigate Import</h2>

      <div className="flex gap-4 mb-8 border-b border-border">
        <button
          onClick={() => setTab('faces')}
          className={`pb-3 px-1 font-medium ${
            tab === 'faces'
              ? 'text-accent border-b-2 border-accent'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Trainierte Gesichter (aus Frigate)
        </button>
        <button
          onClick={() => setTab('events')}
          className={`pb-3 px-1 font-medium ${
            tab === 'events'
              ? 'text-accent border-b-2 border-accent'
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
