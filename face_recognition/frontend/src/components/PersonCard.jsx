import { useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, CircleSlash, ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react'
import { personsAPI } from '../api'

export default function PersonCard({
  person,
  expanded,
  onToggle,
  onDelete,
  onImageCountChange,
}) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef(null)

  const { data: images = [] } = useQuery({
    queryKey: ['person_images', person.id],
    queryFn: () => personsAPI.listImages(person.id).then((r) => r.data),
    enabled: expanded,
  })

  const uploadMutation = useMutation({
    mutationFn: (file) => personsAPI.uploadImage(person.id, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['person_images', person.id] })
      queryClient.invalidateQueries({ queryKey: ['persons'] })
      onImageCountChange()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (imageId) => personsAPI.deleteImage(person.id, imageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['person_images', person.id] })
      queryClient.invalidateQueries({ queryKey: ['persons'] })
      onImageCountChange()
    },
  })

  const handleFileChange = async (e) => {
    const files = e.target.files
    if (files) {
      for (const file of files) {
        uploadMutation.mutate(file)
      }
    }
  }

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="p-4 bg-surface-hover cursor-pointer hover:bg-border transition" onClick={onToggle}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold text-lg">{person.name}</h3>
            <p className="text-sm text-gray-400 flex items-center gap-2 mt-1">
              {person.image_count} image{person.image_count !== 1 ? 's' : ''}
              {person.has_embedding ? (
                <span className="chip-success"><Check size={12} /> Trained</span>
              ) : (
                <span className="chip-warning"><CircleSlash size={12} /> Not trained</span>
              )}
            </p>
          </div>
          {expanded ? <ChevronDown size={20} className="text-gray-400" /> : <ChevronRight size={20} className="text-gray-400" />}
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4 border-t border-border">
          {/* Upload Section */}
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">Upload Training Images</label>
            <div className="border-2 border-dashed border-border rounded-lg p-4 text-center cursor-pointer hover:border-accent hover:bg-accent/5 transition">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadMutation.isPending}
                className="text-accent hover:text-accent-hover font-medium disabled:opacity-50"
              >
                {uploadMutation.isPending ? 'Uploading...' : 'Click to upload or drag files'}
              </button>
            </div>
          </div>

          {/* Images Grid */}
          {images.length > 0 && (
            <div className="mb-4">
              <h4 className="font-medium mb-2">Training Images ({images.length})</h4>
              <div className="grid grid-cols-2 gap-2">
                {images.map((image) => (
                  <div key={image.id} className="relative group">
                    <div className="aspect-square bg-surface-hover rounded overflow-hidden">
                      <div className="w-full h-full flex items-center justify-center text-gray-500">
                        <span className="text-xs">{image.filename.split('_')[2]?.substring(0, 8)}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => deleteMutation.mutate(image.id)}
                      disabled={deleteMutation.isPending}
                      className="absolute top-1 right-1 bg-danger/80 hover:bg-danger text-white rounded w-6 h-6 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition disabled:opacity-50"
                    >
                      ×
                    </button>
                    {image.face_detected && (
                      <div className="absolute bottom-1 left-1 chip-success">
                        <Check size={12} /> Face
                      </div>
                    )}
                    {image.quality_warning && (
                      <div
                        className="absolute bottom-1 right-1 chip-warning"
                        title={`Quality: ${image.quality_warning}`}
                      >
                        <AlertTriangle size={12} /> {image.quality_warning}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-4 border-t border-border">
            <button
              onClick={() => onDelete(person.id)}
              className="btn-danger flex-1"
            >
              Delete Person
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
