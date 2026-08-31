/**
 * @typedef {Object} Source
 * @property {string} id
 * @property {string} title
 * @property {string} source_type - youtube | video | audio | pdf | ppt | image
 * @property {string} status - pending | processing | completed | failed
 * @property {string|null} url
 * @property {number|null} duration
 * @property {number|null} num_pages
 */

/**
 * @typedef {Object} JobStatus
 * @property {string} job_id
 * @property {string} source_id
 * @property {string} status - pending | processing | completed | failed
 * @property {number} progress - 0 to 1
 * @property {string|null} current_step
 * @property {string|null} error
 */

/**
 * @typedef {Object} EvidenceItem
 * @property {string} text
 * @property {string} source_id
 * @property {string} modality - asr | ocr | vision | formula | code
 * @property {number|null} timestamp_start
 * @property {number|null} timestamp_end
 * @property {number|null} page
 * @property {number|null} slide
 * @property {number} confidence
 * @property {string|null} status - active | superseded | disputed | verified
 */

/**
 * @typedef {Object} ConflictInfo
 * @property {string} conflict_id
 * @property {string} conflict_type
 * @property {string[]} sources
 * @property {string[]} claims
 * @property {number|null} timestamp
 * @property {string} severity - low | medium | high
 * @property {number} confidence
 */

/**
 * @typedef {Object} QueryResponse
 * @property {string} answer
 * @property {string} query
 * @property {EvidenceItem[]} evidence
 * @property {ConflictInfo[]} conflicts
 * @property {number} confidence
 * @property {number} latency_ms
 * @property {string} retrieval_strategy_used
 */

export {}
