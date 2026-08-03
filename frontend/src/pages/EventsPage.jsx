import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { recognitionAPI } from '../api'

export default function EventsPage() {
  const [liveEvents, setLiveEvents] = useState([])

  const { data: events = [], isLoading } = useQuery({
    queryKey: ['recognition_events'],
    queryFn: () => recognitionAPI.getEvents(50).then((r) => r.data),
    refetchInterval: 5000,
  })

  useEffect(() => {
    // Connect to WebSocket for live updates
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/ws/events`

    const ws = new WebSocket(wsUrl)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'recognition') {
          setLiveEvents((prev) => [data, ...prev.slice(0, 49)])
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
  }, [])

  const allEvents = liveEvents.length > 0 ? liveEvents : events

  if (isLoading && allEvents.length === 0) {
    return <div className="text-center py-8">Loading...</div>
  }

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Recognition Events</h2>

      <div className="space-y-2">
        {allEvents.map((event, idx) => (
          <div key={idx} className="bg-gray-800 p-4 rounded-lg">
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
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-blue-400">
                  {(event.confidence * 100).toFixed(1)}%
                </div>
                <p className="text-gray-400 text-sm">
                  {event.timestamp
                    ? new Date(event.timestamp).toLocaleTimeString()
                    : new Date(event.time).toLocaleTimeString()}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {allEvents.length === 0 && (
        <div className="text-center text-gray-400 py-12">
          No events yet. Wait for face detections or upload test images.
        </div>
      )}
    </div>
  )
}
