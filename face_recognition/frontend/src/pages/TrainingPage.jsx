import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, CircleSlash } from 'lucide-react'
import { trainingAPI, personsAPI } from '../api'

export default function TrainingPage() {
  const queryClient = useQueryClient()

  const { data: status = [], isLoading } = useQuery({
    queryKey: ['training_status'],
    queryFn: () => trainingAPI.getStatus().then((r) => r.data),
    refetchInterval: 5000,
  })

  const trainMutation = useMutation({
    mutationFn: (personId) => trainingAPI.train(personId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training_status'] })
      queryClient.invalidateQueries({ queryKey: ['persons'] })
    },
  })

  const trainBatchMutation = useMutation({
    mutationFn: () => trainingAPI.trainBatch(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training_status'] })
      queryClient.invalidateQueries({ queryKey: ['persons'] })
    },
  })

  if (isLoading) return <div className="text-center py-8">Loading...</div>

  const trainableCount = status.filter((p) => p.image_count > 0).length

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold">Training</h2>
        <button
          onClick={() => trainBatchMutation.mutate()}
          disabled={trainableCount === 0 || trainBatchMutation.isPending}
          className="btn-success"
        >
          {trainBatchMutation.isPending ? 'Training all...' : `Train All (${trainableCount})`}
        </button>
      </div>

      <div className="bg-info-bg border border-info-border rounded-lg p-4 mb-8">
        <p className="text-sm text-info">
          Click "Train" to compute face embeddings from training images.
          You need at least one image per person.
        </p>
      </div>

      {trainBatchMutation.data && (
        <div className="card border-success/40 p-4 mb-8 text-sm">
          Trained {trainBatchMutation.data.data.trained} of{' '}
          {trainBatchMutation.data.data.trained + trainBatchMutation.data.data.failed} persons.
        </div>
      )}

      {trainBatchMutation.error && (
        <div className="text-danger text-sm mb-8">
          {trainBatchMutation.error.response?.data?.detail || 'Batch training failed'}
        </div>
      )}

      <div className="space-y-4">
        {status.map((person) => (
          <div key={person.id} className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xl font-bold">{person.name}</h3>
                <p className="text-gray-400 flex items-center gap-2 mt-1">
                  {person.image_count} image{person.image_count !== 1 ? 's' : ''}
                  {person.has_embedding ? (
                    <span className="chip-success"><Check size={12} /> Trained</span>
                  ) : (
                    <span className="chip-warning"><CircleSlash size={12} /> Not trained</span>
                  )}
                </p>
              </div>
              <button
                onClick={() => trainMutation.mutate(person.id)}
                disabled={person.image_count === 0 || trainMutation.isPending}
                className="btn-success"
              >
                {trainMutation.isPending ? 'Training...' : 'Train'}
              </button>
            </div>

            {person.has_embedding && (
              <div className="grid grid-cols-2 gap-4 text-sm text-gray-300">
                <div>
                  <span className="text-gray-400">Faces detected:</span>
                  <span className="ml-2 font-mono">{person.faces_in_images}</span>
                </div>
                <div>
                  <span className="text-gray-400">Trained at:</span>
                  <span className="ml-2 font-mono">{new Date(person.trained_at).toLocaleString()}</span>
                </div>
              </div>
            )}

            {trainMutation.error && (
              <div className="text-danger text-sm mt-2">
                {trainMutation.error.response?.data?.detail || 'Training failed'}
              </div>
            )}
          </div>
        ))}
      </div>

      {status.length === 0 && (
        <div className="text-center text-gray-400 py-12">
          No persons yet. Create one first!
        </div>
      )}
    </div>
  )
}
