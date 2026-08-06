import { useQuery } from '@tanstack/react-query'
import { statsAPI } from '../api'

function CpuChart({ samples, cpuCount }) {
  if (samples.length === 0) {
    return <p className="text-gray-400 text-sm">No CPU samples yet — run a recognition first.</p>
  }

  const max = Math.max(100, ...samples.map((s) => s.cpu_percent))
  const width = 100
  const height = 40
  const points = samples
    .map((s, i) => {
      const x = samples.length > 1 ? (i / (samples.length - 1)) * width : 0
      const y = height - (s.cpu_percent / max) * height
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')

  const first = samples[0]
  const last = samples[samples.length - 1]
  const latest = last.cpu_percent

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-sm text-gray-400">
          Per-core capacity: {cpuCount * 100}% ({cpuCount} cores)
        </span>
        <span className="text-2xl font-bold">{latest.toFixed(0)}%</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="w-full h-32">
        <polyline fill="none" stroke="currentColor" strokeWidth="0.6" className="text-accent" points={points} />
      </svg>
      <div className="flex justify-between text-[10px] text-gray-500 mt-1">
        <span>{new Date(first.timestamp).toLocaleString()}</span>
        <span>{new Date(last.timestamp).toLocaleString()}</span>
      </div>
    </div>
  )
}

function Bar({ label, count, max }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  return (
    <div className="mb-2">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-300">{label}</span>
        <span className="text-gray-400 font-mono">{count}</span>
      </div>
      <div className="w-full bg-surface-hover rounded h-2">
        <div className="bg-accent h-2 rounded" style={{ width: `${pct}%` }} />
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
        <div className="card p-4 text-center">
          <div className="text-3xl font-bold">{data.total_events}</div>
          <div className="text-gray-400 text-sm">Recognition Events</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-3xl font-bold">{(data.avg_confidence * 100).toFixed(0)}%</div>
          <div className="text-gray-400 text-sm">Avg. Confidence</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-3xl font-bold">{data.persons_trained}</div>
          <div className="text-gray-400 text-sm">Trained Persons</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-3xl font-bold">{data.persons_total}</div>
          <div className="text-gray-400 text-sm">Total Persons</div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <div className="card p-6">
          <h3 className="text-lg font-bold mb-4">By Person</h3>
          {data.by_person.length === 0 && <p className="text-gray-400 text-sm">No events yet.</p>}
          {data.by_person.map((p) => (
            <Bar key={p.person_name} label={p.person_name} count={p.count} max={maxPerson} />
          ))}
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-bold mb-4">By Camera</h3>
          {data.by_camera.length === 0 && <p className="text-gray-400 text-sm">No events yet.</p>}
          {data.by_camera.map((c) => (
            <Bar key={c.camera} label={c.camera} count={c.count} max={maxCamera} />
          ))}
        </div>
      </div>

      <div className="card p-6 mb-8">
        <h3 className="text-lg font-bold mb-4">CPU Usage During Recognition</h3>
        <CpuChart samples={data.cpu_usage || []} cpuCount={data.cpu_count || 1} />
      </div>

      <div className="card p-6">
        <h3 className="text-lg font-bold mb-4">Last 14 Days</h3>
        <div className="flex items-end gap-2 h-32">
          {data.by_day.map((d) => (
            <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full bg-accent rounded-t"
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
