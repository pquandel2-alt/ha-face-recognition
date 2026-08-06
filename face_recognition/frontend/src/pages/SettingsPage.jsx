import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Loader2, RefreshCw } from 'lucide-react'
import { settingsAPI } from '../api'

const SECTIONS = [
  {
    title: 'Erkennung',
    description: 'Ab wann ein Gesicht als bekannt, unsicher oder unbekannt gilt.',
    fields: [
      'similarity_threshold_known',
      'similarity_threshold_unknown',
      'similarity_margin_min',
      'knn_k',
    ],
  },
  {
    title: 'Bildqualität',
    description: 'Schwellenwerte, ab denen ein Trainingsbild als unscharf/kontrastarm markiert wird.',
    fields: ['quality_blur_threshold', 'quality_contrast_threshold'],
  },
  {
    title: 'Ausreißer-Erkennung',
    description: 'Erkennt Trainingsbilder, die nicht zu den übrigen Bildern einer Person passen.',
    fields: ['outlier_similarity_threshold', 'outlier_min_images'],
  },
  {
    title: 'Frigate-Import-Gruppierung',
    description: 'Ab welcher Ähnlichkeit zwei Frigate-Schnappschüsse beim Import als dieselbe Person gruppiert werden.',
    fields: ['cluster_similarity_threshold'],
  },
  {
    title: 'Konsens (Mehrfach-Erkennung)',
    description: 'Wie viele Frigate-Bildausschnitte übereinstimmen müssen, bevor eine Erkennung gemeldet wird.',
    fields: ['consensus_min_crops', 'consensus_fallback_margin_min'],
  },
  {
    title: 'Aufbewahrung',
    description: 'Wie lange Events und Snapshots gespeichert bleiben, bevor sie automatisch gelöscht werden.',
    fields: ['event_retention_days', 'frigate_snapshot_retention_hours'],
  },
  {
    title: 'Frigate',
    description: 'Verbindung zur Frigate-API und Abfrage-Häufigkeit.',
    fields: ['frigate_api_url', 'frigate_update_check_interval_seconds'],
  },
  {
    title: 'Erkennungsmodell',
    description: 'Größeres Modell = genauer, aber langsamer. Ein Wechsel lädt das Modell im Hintergrund neu.',
    fields: ['insightface_model'],
  },
  {
    title: 'MQTT',
    description: 'Verbindung zum MQTT-Broker. Änderungen bauen die Verbindung automatisch neu auf.',
    fields: ['mqtt_host', 'mqtt_port', 'mqtt_username', 'mqtt_password'],
  },
]

const FIELD_LABELS = {
  similarity_threshold_known: 'Schwelle „bekannt“',
  similarity_threshold_unknown: 'Schwelle „unsicher“',
  similarity_margin_min: 'Mindestabstand zwischen Personen',
  knn_k: 'Anzahl k-NN-Nachbarn',
  quality_blur_threshold: 'Unschärfe-Schwelle',
  quality_contrast_threshold: 'Kontrast-Schwelle',
  outlier_similarity_threshold: 'Ausreißer-Ähnlichkeitsschwelle',
  outlier_min_images: 'Mindestbilder für Ausreißer-Check',
  cluster_similarity_threshold: 'Cluster-Ähnlichkeitsschwelle',
  consensus_min_crops: 'Mindestanzahl übereinstimmender Ausschnitte',
  consensus_fallback_margin_min: 'Mindestabstand bei Einzelbild-Erkennung',
  frigate_update_check_interval_seconds: 'Abfrage-Intervall (Sekunden)',
  frigate_snapshot_retention_hours: 'Snapshot-Aufbewahrung (Stunden)',
  event_retention_days: 'Event-Aufbewahrung (Tage)',
  insightface_model: 'Modell',
  frigate_api_url: 'Frigate-API-URL',
  mqtt_host: 'Broker-Host',
  mqtt_port: 'Broker-Port',
  mqtt_username: 'Benutzername',
  mqtt_password: 'Passwort',
}

const STATUS_LABELS = {
  applied: 'Übernommen',
  reloading: 'Modell wird neu geladen…',
  reconnecting: 'Verbindung wird neu aufgebaut…',
}

function FieldInput({ name, spec, value, onChange }) {
  if (spec.type === 'enum') {
    return (
      <select
        className="bg-surface-hover border border-border rounded px-3 py-2 w-full"
        value={value}
        onChange={(e) => onChange(name, e.target.value)}
      >
        {spec.options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    )
  }

  if (spec.secret) {
    return (
      <input
        type="password"
        className="bg-surface-hover border border-border rounded px-3 py-2 w-full"
        placeholder={value || '(nicht gesetzt)'}
        onChange={(e) => onChange(name, e.target.value)}
      />
    )
  }

  if (spec.type === 'str') {
    return (
      <input
        type="text"
        className="bg-surface-hover border border-border rounded px-3 py-2 w-full"
        value={value ?? ''}
        onChange={(e) => onChange(name, e.target.value)}
      />
    )
  }

  return (
    <div>
      <input
        type="number"
        step={spec.type === 'float' ? 0.01 : 1}
        min={spec.min}
        max={spec.max}
        className="bg-surface-hover border border-border rounded px-3 py-2 w-full"
        value={value ?? ''}
        onChange={(e) =>
          onChange(name, spec.type === 'float' ? parseFloat(e.target.value) : parseInt(e.target.value, 10))
        }
      />
      <p className="text-xs text-gray-500 mt-1">
        Bereich: {spec.min} – {spec.max} (Standard: {spec.default})
      </p>
    </div>
  )
}

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [values, setValues] = useState({})
  const [statusByField, setStatusByField] = useState({})

  const { data: fields, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsAPI.get().then((r) => r.data),
  })

  useEffect(() => {
    if (!fields) return
    setValues((prev) => {
      const next = { ...prev }
      for (const [name, spec] of Object.entries(fields)) {
        if (!(name in next)) next[name] = spec.secret ? '' : spec.value
      }
      return next
    })
  }, [fields])

  const updateMutation = useMutation({
    mutationFn: (changes) => settingsAPI.update(changes).then((r) => r.data),
    onSuccess: (data) => {
      setStatusByField(data.updated || {})
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })

  if (isLoading || !fields) {
    return <div className="text-center py-8">Loading...</div>
  }

  const handleChange = (name, value) => {
    setValues((prev) => ({ ...prev, [name]: value }))
  }

  const changedFields = Object.keys(values).filter((name) => {
    const spec = fields[name]
    if (!spec) return false
    if (spec.secret) return values[name] !== ''
    return values[name] !== spec.value
  })

  const handleSave = () => {
    const changes = {}
    for (const name of changedFields) {
      changes[name] = values[name]
    }
    updateMutation.mutate(changes)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold">Einstellungen</h2>
        <button
          className="btn-primary flex items-center gap-2"
          disabled={changedFields.length === 0 || updateMutation.isPending}
          onClick={handleSave}
        >
          {updateMutation.isPending ? (
            <>
              <Loader2 size={16} className="animate-spin" /> Speichern...
            </>
          ) : (
            `Speichern${changedFields.length > 0 ? ` (${changedFields.length})` : ''}`
          )}
        </button>
      </div>

      {updateMutation.error && (
        <div className="text-danger text-sm mb-6">
          {updateMutation.error.response?.data?.detail || 'Speichern fehlgeschlagen'}
        </div>
      )}

      <div className="space-y-6">
        {SECTIONS.map((section) => (
          <div key={section.title} className="card p-6">
            <h3 className="text-lg font-bold">{section.title}</h3>
            <p className="text-sm text-gray-400 mb-4">{section.description}</p>
            <div className="grid md:grid-cols-2 gap-4">
              {section.fields.map((name) => {
                const spec = fields[name]
                if (!spec) return null
                const status = statusByField[name]
                return (
                  <div key={name}>
                    <label className="block text-sm font-medium mb-1 flex items-center gap-2">
                      {FIELD_LABELS[name] || name}
                      {status && (
                        <span className="chip-info">
                          {status === 'applied' ? <Check size={12} /> : <RefreshCw size={12} className="animate-spin" />}
                          {STATUS_LABELS[status]}
                        </span>
                      )}
                    </label>
                    <FieldInput name={name} spec={spec} value={values[name]} onChange={handleChange} />
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
