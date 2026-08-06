import { useEffect, useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { Check, X, AlertTriangle } from 'lucide-react'
import { recognitionAPI, personsAPI } from '../api'
import AuthImage from '../components/AuthImage'

export default function EventsPage() {
  const queryClient = useQueryClient()
  const [selections, setSelections] = useState({}) // { [eventId]: personId }

  const { data: events = [], isLoading } = useQuery({
    queryKey: ['recognition_events'],
    queryFn: () => recognitionAPI.getEvents(50).then((r) => r.data),
    refetchInterval: 5000,
  })

  const { data: persons = [] } = useQuery({
    queryKey: ['persons'],
    queryFn: () => personsAPI.list().then((r) => r.data),
  })

  const confirmMutation = useMutation({
    mutationFn: ({ eventId, personId }) => recognitionAPI.confirmEvent(eventId, personId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recognition_events'] })
      queryClient.invalidateQueries({ queryKey: ['persons'] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (eventId) => recognitionAPI.rejectEvent(eventId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['recognition_events'] }),
  })

  useEffect(() => {
    // WebSocket is only a signal to refetch the REST list — it stays the
    // single source of truth, so late-arriving Frigate comparison data
    // (attached asynchronously once Frigate finalizes its own verdict)
    // always shows up, even for already-rendered rows.
    // Resolve relative to the current document URL (not an absolute "/api/..."
    // path) so this still finds the app when served under HA Ingress's
    // dynamic path prefix (/api/hassio_ingress/<token>/).
    const wsUrl = new URL('api/ws/events', window.location.href)
    wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:'

    const ws = new WebSocket(wsUrl.href)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'recognition' || data.type === 'frigate_comparison') {
          queryClient.invalidateQueries({ queryKey: ['recognition_events'] })
        }
      } catch (e) {
        console.error('Error parsing WebSocket message:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [queryClient])

  if (isLoading && events.length === 0) {
    return <div className="text-center py-8">Loading...</div>
  }

  const selectedPersonId = (event) =>
    selections[event.id] ?? (event.person_id != null ? String(event.person_id) : '')

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Recognition Events</h2>

      <div className="space-y-2">
        {events.map((event) => {
          const hasFrigateVerdict = event.frigate_sub_label != null
          const disagrees =
            hasFrigateVerdict &&
            event.frigate_sub_label.toLowerCase() !== event.person_name.toLowerCase()

          return (
            <div
              key={event.id}
              className={`card p-4 ${disagrees ? 'ring-1 ring-warning-border' : ''}`}
            >
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  {event.has_image && (
                    <AuthImage
                      url={recognitionAPI.eventImageUrl(event.id)}
                      className="w-16 h-16 rounded object-cover flex-shrink-0"
                    />
                  )}
                  <div className="min-w-0">
                    <h3 className="text-lg font-bold">
                      <span
                        className={
                          event.person_name === 'unknown'
                            ? 'text-danger'
                            : event.person_name === 'uncertain'
                            ? 'text-warning'
                            : 'text-success'
                        }
                      >
                        {event.person_name}
                      </span>
                    </h3>
                    <p className="text-gray-400 text-sm">
                      Camera: <span className="font-mono">{event.camera}</span>
                    </p>
                    {(event.recognition_duration_ms != null || event.frigate_recognition_duration_ms != null) && (
                      <p className="text-gray-500 text-xs font-mono">
                        {event.recognition_duration_ms != null &&
                          `Erkennung: ${event.recognition_duration_ms.toFixed(0)} ms`}
                        {event.recognition_duration_ms != null && event.frigate_recognition_duration_ms != null && ' · '}
                        {event.frigate_recognition_duration_ms != null &&
                          `Frigate: ${event.frigate_recognition_duration_ms.toFixed(0)} ms`}
                      </p>
                    )}
                    {hasFrigateVerdict && (
                      <p className={`text-sm mt-1 flex items-center gap-1 ${disagrees ? 'text-warning' : 'text-gray-400'}`}>
                        {disagrees && <AlertTriangle size={14} />}
                        Frigate sagt: <span className="font-semibold">{event.frigate_sub_label}</span>
                        {event.frigate_sub_label_score != null &&
                          ` (${(event.frigate_sub_label_score * 100).toFixed(1)}%)`}
                        {disagrees && ' — Abweichung!'}
                      </p>
                    )}
                  </div>
                </div>

                <div className="text-right flex-shrink-0">
                  <div className="text-2xl font-bold text-accent">
                    {(event.confidence * 100).toFixed(1)}%
                  </div>
                  <p className="text-gray-400 text-sm">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              </div>

              {event.has_image && (
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
                  {event.verdict === 'confirmed' && (
                    <span className="chip-success">
                      <Check size={14} /> Bestätigt — als Trainingsbild übernommen
                    </span>
                  )}
                  {event.verdict === 'rejected' && (
                    <span className="chip-danger">
                      <X size={14} /> Abgelehnt — falsche Erkennung
                    </span>
                  )}
                  {!event.verdict && (
                    <>
                      <select
                        className="bg-surface-hover border border-border text-sm rounded px-2 py-1"
                        value={selectedPersonId(event)}
                        onChange={(e) =>
                          setSelections((prev) => ({ ...prev, [event.id]: e.target.value }))
                        }
                      >
                        <option value="">-- Person wählen --</option>
                        {persons.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                      <button
                        className="btn-success py-1"
                        disabled={!selectedPersonId(event) || confirmMutation.isPending}
                        onClick={() =>
                          confirmMutation.mutate({
                            eventId: event.id,
                            personId: Number(selectedPersonId(event)),
                          })
                        }
                      >
                        Trainieren
                      </button>
                      <button
                        className="btn-danger py-1"
                        disabled={rejectMutation.isPending}
                        onClick={() => rejectMutation.mutate(event.id)}
                      >
                        Falsch erkannt
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {events.length === 0 && (
        <div className="text-center text-gray-400 py-12">
          No events yet. Wait for face detections or upload test images.
        </div>
      )}
    </div>
  )
}
