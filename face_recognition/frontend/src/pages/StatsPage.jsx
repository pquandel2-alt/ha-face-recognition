import { useQuery } from '@tanstack/react-query'
import { statsAPI } from '../api'

function Bar({ label, count, max }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  return (
    <div className="mb-2">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-300">{label}</span>
        <span className="text-gray-400 font-mono">{count}</span>
      </div>
      <div className="w-full bg-gray-700 rounded h-2">
        <div className="bg-blue-500 h-2 rounded" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function StatsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: () => statsAPI.get().then((r) => r.data),
    refetchInterval: 15000,
  })

  if (isLoading || !data) return <div className="text-center py-8">Loading...</div>

  const maxPerson = Math.max(0, ...data.by_person.map((p) => p.count))
  const maxCamera = Math.max(0, ...data.by_camera.map((c) => c.count))
  const maxDay = Math.max(0, ...data.by_day.map((d) => d.count))

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Statistics</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-800 p-4 rounded-lg text-center">
          <div className="text-3xl font-bold">{data.total_events}</div>
          <div className="text-gray-400 text-sm">Recognition Events</div>
        </div>
        <div className="bg-gray-800 p-4 rounded-lg text-center">
          <div className="text-3xl font-bold">{(data.avg_confidence * 100).toFixed(0)}%</div>
          <div className="text-gray-400 text-sm">Avg. Confidence</div>
        </div>
        <div className="bg-gray-800 p-4 rounded-lg text-center">
          <div className="text-3xl font-bold">{data.persons_trained}</div>
          <div className="text-gray-400 text-sm">Trained Persons</div>
        </div>
        <div className="bg-gray-800 p-4 rounded-lg text-center">
          <div className="text-3xl font-bold">{data.persons_total}</div>
          <div className="text-gray-400 text-sm">Total Persons</div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <div className="bg-gray-800 p-6 rounded-lg">
          <h3 className="text-lg font-bold mb-4">By Person</h3>
          {data.by_person.length === 0 && <p className="text-gray-400 text-sm">No events yet.</p>}
          {data.by_person.map((p) => (
            <Bar key={p.person_name} label={p.person_name} count={p.count} max={maxPerson} />
          ))}
        </div>

        <div className="bg-gray-800 p-6 rounded-lg">
          <h3 className="text-lg font-bold mb-4">By Camera</h3>
          {data.by_camera.length === 0 && <p className="text-gray-400 text-sm">No events yet.</p>}
          {data.by_camera.map((c) => (
            <Bar key={c.camera} label={c.camera} count={c.count} max={maxCamera} />
          ))}
        </div>
      </div>

      <div className="bg-gray-800 p-6 rounded-lg">
        <h3 className="text-lg font-bold mb-4">Last 14 Days</h3>
        <div className="flex items-end gap-2 h-32">
          {data.by_day.map((d) => (
            <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full bg-blue-500 rounded-t"
                style={{
                  height: maxDay > 0 ? `${Math.max(2, (d.count / maxDay) * 100)}%` : '2%',
                }}
                title={`${d.date}: ${d.count}`}
              />
              <span className="text-[10px] text-gray-500 rotate-45 origin-left whitespace-nowrap">
                {d.date.slice(5)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
