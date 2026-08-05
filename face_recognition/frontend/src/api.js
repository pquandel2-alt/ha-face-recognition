import axios from 'axios'

// Relative (no leading slash) so requests resolve against the current
// document URL — required behind HA Ingress, which serves the app under a
// dynamic path prefix (/api/hassio_ingress/<token>/) rather than at "/".
const API_BASE = 'api'

const api = axios.create({
  baseURL: API_BASE,
})

// Persons API
export const personsAPI = {
  list: () => api.get('/persons'),
  create: (name) => api.post('/persons', null, { params: { name } }),
  get: (id) => api.get(`/persons/${id}`),
  delete: (id) => api.delete(`/persons/${id}`),
  uploadImage: (personId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/persons/${personId}/images`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listImages: (personId) => api.get(`/persons/${personId}/images`),
  deleteImage: (personId, imageId) => api.delete(`/persons/${personId}/images/${imageId}`),
}

// Training API
export const trainingAPI = {
  train: (personId) => api.post(`/training/${personId}`),
  getStatus: () => api.get('/training/status'),
  getPersonStatus: (personId) => api.get(`/training/${personId}/status`),
}

// Recognition API
export const recognitionAPI = {
  analyze: (file, camera = 'manual') => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/recognition/analyze', formData, {
      params: { camera },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getEvents: (limit = 50) => api.get('/recognition/events', { params: { limit } }),
}

// Frigate API
export const frigateAPI = {
  health: () => api.get('/frigate/health'),
  listSnapshots: (limit = 50) => api.get('/frigate/snapshots', { params: { limit } }),
  importSnapshot: (eventId, personId) =>
    api.post(`/frigate/import/${eventId}`, { person_id: personId }),
  listTrainedFaces: () => api.get('/frigate/faces'),
  importTrainedFaces: (name, filenames, personId) =>
    api.post('/frigate/faces/import', { name, filenames, person_id: personId }),
}

// Health
export const healthAPI = {
  check: () => api.get('/health'),
}

export default api
