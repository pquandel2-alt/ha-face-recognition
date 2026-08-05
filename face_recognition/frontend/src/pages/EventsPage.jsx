import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { recognitionAPI } from '../api'

export default function EventsPage() {
  const queryClient = useQueryClient()

  const { data: events = [], isLoading } = useQuery({
    queryKey: ['recognition_events'],
    queryFn: () => recognitionAPI.getEvents(50).then((r) => r.data),
    refetchInterval: 5000,
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
              className={`bg-gray-800 p-4 rounded-lg ${
                disagrees ? 'ring-2 ring-orange-500' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold">
                    <span
                      className={
                        event.person_name === 'unknown'
                          ? 'text-red-400'
                          : event.person_name === 'uncertain'
                          ? 'text-yellow-400'
                          : 'text-green-400'
                      }
                    >
                      {event.person_name}
                    </span>
                  </h3>
                  <p className="text-gray-400 text-sm">
                    Camera: <span className="font-mono">{event.camera}</span>
                  </p>
                  {hasFrigateVerdict && (
                    <p className={`text-sm mt-1 ${disagrees ? 'text-orange-400' : 'text-gray-400'}`}>
                      Frigate sagt: <span className="font-semibold">{event.frigate_sub_label}</span>
                      {event.frigate_sub_label_score != null &&
                        ` (${(event.frigate_sub_label_score * 100).toFixed(1)}%)`}
                      {disagrees && ' — Abweichung!'}
                    </p>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-blue-400">
                    {(event.confidence * 100).toFixed(1)}%
                  </div>
                  <p className="text-gray-400 text-sm">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              </div>
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
