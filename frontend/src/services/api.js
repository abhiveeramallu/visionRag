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
export const retrySource = (sourceId) => api.post(`/sources/${sourceId}/retry`)
export const getSources = (params = {}) => api.get('/sources', { params })
export const getSource = (sourceId) => api.get(`/source/${sourceId}`)
export const getSourceMediaUrl = (sourceId) => `/api/source/${sourceId}/media`
export const deleteSource = (sourceId) => api.delete(`/source/${sourceId}`)
export const getKnowledge = (sourceId) => api.get(`/knowledge/${sourceId}`)
export const getKnowledgeUnitHistory = (kuId) => api.get(`/knowledge/unit/${kuId}/history`)
export const getKnowledgeUnitEvidence = (kuId) => api.get(`/knowledge/unit/${kuId}/evidence`)
export const getSourceConflicts = (sourceId) => api.get(`/source/${sourceId}/conflicts`)
export const getSourceEvolution = (sourceId) => api.get(`/source/${sourceId}/evolution`)
export const getKnowledgeGraph = (sourceId = null) =>
  api.get('/knowledge-graph', { params: sourceId ? { source_id: sourceId } : {} })

export const querySource = (
  sourceId,
  query,
  topK = 5,
  includeEvidence = true,
  includeConflicts = true,
  conversationId = null,
  strategy = null,
  modality = null,
  timestampFilter = null,
) =>
  api.post('/query', {
    source_id: sourceId,
    query,
    top_k: topK,
    include_evidence: includeEvidence,
    include_conflicts: includeConflicts,
    conversation_id: conversationId,
    strategy: strategy || undefined,
    modality: modality || undefined,
    timestamp_filter: timestampFilter !== null ? timestampFilter : undefined,
  })

export const getSourceConversation = (sourceId, conversationId = null) =>
  api.get(`/chat/sources/${sourceId}/conversation`, {
    params: conversationId ? { conversation_id: conversationId } : {},
  })

export const newSourceConversation = (sourceId) =>
  api.post(`/chat/sources/${sourceId}/conversation/new`)

export const getSuggestedQuestions = (sourceId) =>
  api.get(`/chat/sources/${sourceId}/suggested-questions`)

export const getSourceConversations = (sourceId) =>
  api.get(`/chat/sources/${sourceId}/conversations`)

export const deleteConversation = (conversationId) =>
  api.delete(`/chat/conversations/${conversationId}`)

export const getKnowledgeUnits = (params = {}) =>
  api.get('/knowledge-units', { params })

export const getKnowledgeUnitDetail = (kuId) =>
  api.get(`/knowledge-units/${kuId}`)

export const getEvaluationArtifacts = () =>
  api.get('/evaluation/artifacts')

export const runEvaluation = (type = 'synthetic') =>
  api.post('/evaluation/run', { type })

export default api
