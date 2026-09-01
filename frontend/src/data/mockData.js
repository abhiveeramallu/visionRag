/**
 * Realistic sample data for VisionRAG-X, shaped to match the real backend
 * Pydantic/ORM response schemas (SourceResponse, KnowledgeUnitResponse,
 * EvidenceItem, ConflictInfo — see backend/app/schemas/responses.py and
 * backend/app/knowledge/models.py) so it is a drop-in swap once the
 * corresponding endpoints exist.
 *
 * Anything imported from this file is DEMO DATA, not a live API response.
 * Pair it with <DemoDataBadge /> wherever it's rendered.
 */

export const mockSources = [
  {
    id: 'demo-ml-lecture-04',
    title: 'Machine Learning — Lecture 04',
    source_type: 'youtube',
    status: 'completed',
    url: 'https://www.youtube.com/watch?v=demo-ml04',
    duration: 5040, // 1h 24m
    num_pages: null,
    channel: 'Prof. Aditi Rao',
    knowledge_units: 184,
    confidence: 0.94,
    thumbnail_color: 'from-blue-500 to-blue-600',
    created_at: '2026-08-27T09:15:00Z',
  },
  {
    id: 'demo-dbms-unit-03',
    title: 'Database Management — Unit 3',
    source_type: 'pdf',
    status: 'completed',
    url: null,
    duration: null,
    num_pages: 86,
    channel: null,
    knowledge_units: 132,
    confidence: 0.96,
    thumbnail_color: 'from-rose-500 to-rose-600',
    created_at: '2026-08-25T14:02:00Z',
  },
  {
    id: 'demo-cnn-class',
    title: 'Convolutional Neural Networks — Class 07',
    source_type: 'video',
    status: 'completed',
    url: null,
    duration: 3120,
    num_pages: null,
    channel: null,
    knowledge_units: 97,
    confidence: 0.91,
    thumbnail_color: 'from-purple-500 to-purple-600',
    created_at: '2026-08-22T11:40:00Z',
  },
  {
    id: 'demo-numerical-methods',
    title: 'Numerical Methods — Newton-Raphson',
    source_type: 'ppt',
    status: 'completed',
    url: null,
    duration: null,
    num_pages: 24,
    channel: null,
    knowledge_units: 41,
    confidence: 0.89,
    thumbnail_color: 'from-orange-500 to-orange-600',
    created_at: '2026-08-19T08:00:00Z',
  },
]

export const mockNotifications = [
  {
    id: 'n1',
    title: 'Knowledge correction detected',
    detail: '"Gradient Descent" was corrected in ML Lecture 04 at 14:32.',
    time: '2h ago',
    unread: true,
  },
  {
    id: 'n2',
    title: 'Processing complete',
    detail: 'Database Management — Unit 3 finished indexing (132 knowledge units).',
    time: '1d ago',
    unread: true,
  },
  {
    id: 'n3',
    title: 'Weekly revision reminder',
    detail: 'You have 3 sources with unreviewed flashcard decks.',
    time: '2d ago',
    unread: false,
  },
]

// Version-chain evolution for a single concept, shaped like KnowledgeUnitResponse.
export const mockGradientDescentEvolution = {
  concept: 'Gradient Descent',
  source_id: 'demo-ml-lecture-04',
  source_title: 'Machine Learning — Lecture 04',
  versions: [
    {
      id: 'ku-gd-v1',
      version: 1,
      content: 'θ = θ − αJ(θ)',
      modality: 'asr',
      status: 'superseded',
      timestamp_start: 868, // 14:28
      confidence: 0.71,
      correction_reason: null,
    },
    {
      id: 'ku-gd-v2',
      version: 2,
      content: 'θ = θ − α∇J(θ)',
      modality: 'ocr',
      status: 'verified',
      timestamp_start: 872, // 14:32
      confidence: 0.96,
      correction_reason: 'Whiteboard OCR clarified the gradient operator omitted in the spoken transcript.',
      previous_version_id: 'ku-gd-v1',
    },
  ],
  correction_detected_at: 871, // 14:31
  evidence_comparison: {
    speech: { modality: 'asr', text: '"...update theta using the gradient of J..."', confidence: 0.71 },
    whiteboard: { modality: 'ocr', text: '∇J(θ) written on whiteboard, boxed', confidence: 0.98 },
    visual_consistency: 'High',
    final_confidence: 0.96,
  },
}

// Interactive knowledge graph tree.
export const mockKnowledgeGraph = {
  id: 'root-ml',
  label: 'Machine Learning',
  definition: 'The study of algorithms that improve automatically through experience and data.',
  confidence: 0.95,
  evidence_count: 184,
  children: [
    {
      id: 'supervised',
      label: 'Supervised Learning',
      definition: 'Learning a mapping from labeled input-output pairs.',
      confidence: 0.93,
      evidence_count: 58,
      source: 'ML Lecture 04',
      timestamp_start: 120,
      children: [
        {
          id: 'classification',
          label: 'Classification',
          definition: 'Predicting a discrete category label for an input.',
          confidence: 0.92,
          evidence_count: 22,
          source: 'ML Lecture 04',
          timestamp_start: 210,
          children: [],
        },
        {
          id: 'regression',
          label: 'Regression',
          definition: 'Predicting a continuous numeric value for an input.',
          confidence: 0.9,
          evidence_count: 19,
          source: 'ML Lecture 04',
          timestamp_start: 340,
          children: [],
        },
      ],
    },
    {
      id: 'unsupervised',
      label: 'Unsupervised Learning',
      definition: 'Finding structure in data without labeled outcomes.',
      confidence: 0.88,
      evidence_count: 31,
      source: 'ML Lecture 04',
      timestamp_start: 560,
      children: [
        {
          id: 'clustering',
          label: 'Clustering',
          definition: 'Grouping similar data points together (e.g. k-means).',
          confidence: 0.87,
          evidence_count: 14,
          source: 'ML Lecture 04',
          timestamp_start: 610,
          children: [],
        },
        {
          id: 'dim-reduction',
          label: 'Dimensionality Reduction',
          definition: 'Reducing the number of features while preserving structure (e.g. PCA).',
          confidence: 0.85,
          evidence_count: 9,
          source: 'ML Lecture 04',
          timestamp_start: 700,
          children: [],
        },
      ],
    },
    {
      id: 'optimization',
      label: 'Optimization',
      definition: 'Algorithms that iteratively minimize a loss function.',
      confidence: 0.94,
      evidence_count: 46,
      source: 'ML Lecture 04',
      timestamp_start: 850,
      children: [
        {
          id: 'gradient-descent',
          label: 'Gradient Descent',
          definition: 'An optimization algorithm used to minimize a loss function by iteratively updating model parameters.',
          confidence: 0.96,
          evidence_count: 12,
          source: 'ML Lecture 04',
          timestamp_start: 872,
          hasCorrectionHistory: true,
          children: [],
        },
        {
          id: 'backpropagation',
          label: 'Backpropagation',
          definition: 'An algorithm that computes gradients of the loss with respect to network weights via the chain rule.',
          confidence: 0.93,
          evidence_count: 17,
          source: 'ML Lecture 06',
          timestamp_start: 1934,
          children: [],
        },
      ],
    },
  ],
}

export const mockChatExchange = {
  question: 'What is gradient descent?',
  answer:
    'Gradient descent is an optimization algorithm used to minimize a loss function by iteratively updating model parameters.',
  evidence: [
    {
      text: '"...we update theta using the gradient of J, taking small steps in the direction that reduces error..."',
      modality: 'asr',
      source_id: 'demo-ml-lecture-04',
      timestamp_start: 872,
      confidence: 0.93,
      status: 'verified',
    },
    {
      text: 'Whiteboard: θ = θ − α∇J(θ), boxed and underlined',
      modality: 'ocr',
      source_id: 'demo-ml-lecture-04',
      timestamp_start: 872,
      confidence: 0.98,
      status: 'verified',
    },
  ],
  confidence: 0.96,
  retrieval_strategy_used: 'semantic+graph',
}

export const mockSearchResults = [
  {
    source_title: 'Machine Learning — Lecture 05',
    source_type: 'youtube',
    modality: 'asr',
    timestamp_start: 872,
    snippet: '"...Newton-Raphson converges faster than bisection when the derivative is well-behaved..."',
    confidence: 0.92,
  },
  {
    source_title: 'Machine Learning — Lecture 07',
    source_type: 'youtube',
    modality: 'ocr',
    timestamp_start: 1338,
    snippet: 'Whiteboard: x_{n+1} = x_n − f(x_n)/f\'(x_n)',
    confidence: 0.95,
  },
  {
    source_title: 'Numerical Methods PDF',
    source_type: 'pdf',
    modality: 'text',
    page: 42,
    snippet: '"The Newton-Raphson method is an iterative root-finding technique..."',
    confidence: 0.97,
  },
]

export function formatTimestamp(seconds) {
  if (seconds === null || seconds === undefined) return null
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function formatDuration(seconds) {
  if (!seconds) return null
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
