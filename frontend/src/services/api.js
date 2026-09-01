import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 180000, // 3 min for heavy operations
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg =
      err.response?.data?.detail ||
      err.response?.data?.error ||
      err.message ||
      'Unknown error'
    return Promise.reject(new Error(msg))
  }
)

export const healthCheck = () => api.get('/health')

export const ingestYouTube = (url, title = null) =>
  api.post('/youtube', { url, title })

export const uploadFile = (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total)
        onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
}

export const getStatus = (sourceId) => api.get(`/status/${sourceId}`)
export const getSources = () => api.get('/sources')
export const getSource = (sourceId) => api.get(`/source/${sourceId}`)
export const deleteSource = (sourceId) => api.delete(`/source/${sourceId}`)
export const getKnowledge = (sourceId) => api.get(`/knowledge/${sourceId}`)
export const getKnowledgeUnitHistory = (kuId) => api.get(`/knowledge/unit/${kuId}/history`)
export const getKnowledgeUnitEvidence = (kuId) => api.get(`/knowledge/unit/${kuId}/evidence`)
export const getSourceConflicts = (sourceId) => api.get(`/source/${sourceId}/conflicts`)
export const getSourceEvolution = (sourceId) => api.get(`/source/${sourceId}/evolution`)

export const querySource = (sourceId, query, topK = 5, includeEvidence = true, includeConflicts = true) =>
  api.post('/query', {
    source_id: sourceId, query, top_k: topK,
    include_evidence: includeEvidence, include_conflicts: includeConflicts,
  })

export const getSummary = (sourceId, summaryType = 'overall', topic = null) =>
  api.post('/summary', { source_id: sourceId, summary_type: summaryType, topic })

export const generateQuiz = (sourceId, quizType = 'mcq', difficulty = 'medium', numQuestions = 5, topic = null) =>
  api.post('/quiz', { source_id: sourceId, quiz_type: quizType, difficulty, num_questions: numQuestions, topic })

export const generateFlashcards = (sourceId, numCards = 10, topic = null) =>
  api.post('/flashcards', { source_id: sourceId, num_cards: numCards, topic })

export const generateNotes = (sourceId, notesType = 'concise', topic = null) =>
  api.post('/notes', { source_id: sourceId, notes_type: notesType, topic })

export default api
