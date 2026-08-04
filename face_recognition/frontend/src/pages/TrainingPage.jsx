import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

  if (isLoading) return <div className="text-center py-8">Loading...</div>

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Training</h2>

      <div className="bg-blue-900 bg-opacity-20 border border-blue-600 p-4 rounded mb-8">
        <p className="text-sm text-blue-200">
          Click "Train" to compute face embeddings from training images.
          You need at least one image per person.
        </p>
      </div>

      <div className="space-y-4">
        {status.map((person) => (
          <div key={person.id} className="bg-gray-800 p-6 rounded-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xl font-bold">{person.name}</h3>
                <p className="text-gray-400">
                  {person.image_count} image{person.image_count !== 1 ? 's' : ''} •{' '}
                  {person.has_embedding ? (
                    <span className="text-green-400">✓ Trained</span>
                  ) : (
                    <span className="text-yellow-400">⊘ Not trained</span>
                  )}
                </p>
              </div>
              <button
                onClick={() => trainMutation.mutate(person.id)}
                disabled={person.image_count === 0 || trainMutation.isPending}
                className="bg-green-600 hover:bg-green-700 px-6 py-2 rounded font-medium disabled:opacity-50 disabled:cursor-not-allowed"
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
              <div className="text-red-400 text-sm mt-2">
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
