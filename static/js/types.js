/**
 * Type definitions for Scrapefruit frontend.
 *
 * Uses JSDoc for type safety without requiring TypeScript compilation.
 * These types are used for IDE autocompletion and documentation.
 *
 * @fileoverview Type definitions for state, API responses, and domain objects.
 */

// =============================================================================
// Job Types
// =============================================================================

/**
 * Job status values.
 * @typedef {'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled' | 'archived'} JobStatus
 */

/**
 * Job mode values.
 * @typedef {'single' | 'list' | 'crawl'} JobMode
 */

/**
 * A scraping job.
 * @typedef {Object} Job
 * @property {string} id - Unique job identifier (UUID)
 * @property {string} name - Human-readable job name
 * @property {JobStatus} status - Current job status
 * @property {JobMode} mode - Scraping mode
 * @property {string|null} template_id - Optional template ID
 * @property {Object} settings - Job-specific settings
 * @property {number} progress_current - Number of URLs processed
 * @property {number} progress_total - Total URLs to process
 * @property {number} success_count - Successfully scraped URLs
 * @property {number} failure_count - Failed URLs
 * @property {string|null} error_message - Last error message if any
 * @property {string|null} started_at - ISO timestamp when job started
 * @property {string|null} completed_at - ISO timestamp when job completed
 * @property {string} created_at - ISO timestamp when job was created
 * @property {string} updated_at - ISO timestamp of last update
 */

/**
 * Job progress information.
 * @typedef {Object} JobProgress
 * @property {JobStatus} status - Current job status
 * @property {number} current - URLs processed
 * @property {number} total - Total URLs
 * @property {number} success - Successful scrapes
 * @property {number} failure - Failed scrapes
 * @property {number} percent - Progress percentage (0-100)
 */

// =============================================================================
// URL Types
// =============================================================================

/**
 * URL status values.
 * @typedef {'pending' | 'processing' | 'completed' | 'failed' | 'skipped'} UrlStatus
 */

/**
 * A URL entry for a job.
 * @typedef {Object} Url
 * @property {string} id - Unique URL identifier
 * @property {string} job_id - Parent job ID
 * @property {string} url - The actual URL string
 * @property {UrlStatus} status - Processing status
 * @property {number} attempt_count - Number of scraping attempts
 * @property {string|null} error_message - Last error if failed
 * @property {string} created_at - ISO timestamp
 * @property {string|null} processed_at - When processing completed
 */

/**
 * Paginated URL list response.
 * @typedef {Object} UrlListResponse
 * @property {Url[]} urls - List of URLs
 * @property {number} total - Total count
 * @property {number} limit - Page size
 * @property {number} offset - Current offset
 * @property {boolean} has_more - Whether more pages exist
 */

// =============================================================================
// Rule Types
// =============================================================================

/**
 * Selector type values.
 * @typedef {'css' | 'xpath'} SelectorType
 */

/**
 * An extraction rule.
 * @typedef {Object} Rule
 * @property {string} id - Unique rule identifier
 * @property {string} job_id - Parent job ID
 * @property {string} name - Field name for extracted data
 * @property {SelectorType} selector_type - Type of selector
 * @property {string} selector_value - CSS selector or XPath expression
 * @property {string|null} attribute - HTML attribute to extract (null = text content)
 * @property {boolean} is_required - Whether field is required
 * @property {boolean} is_list - Whether to extract multiple values
 * @property {number} order - Sort order
 * @property {string} created_at - ISO timestamp
 */

// =============================================================================
// Result Types
// =============================================================================

/**
 * A scraping result.
 * @typedef {Object} Result
 * @property {string} id - Unique result identifier
 * @property {string} job_id - Parent job ID
 * @property {string} url_id - Source URL ID
 * @property {string} url - The scraped URL
 * @property {Object.<string, any>} data - Extracted data (field name -> value)
 * @property {Object|null} metadata - Additional metadata
 * @property {string} created_at - ISO timestamp
 */

// =============================================================================
// Log Types
// =============================================================================

/**
 * Log level values.
 * @typedef {'debug' | 'info' | 'success' | 'warning' | 'error'} LogLevel
 */

/**
 * A log entry.
 * @typedef {Object} LogEntry
 * @property {number} index - Log sequence number
 * @property {LogLevel} level - Log level
 * @property {string} message - Log message
 * @property {string} timestamp - ISO timestamp
 * @property {Object|null} data - Optional structured data
 */

/**
 * Log list response.
 * @typedef {Object} LogResponse
 * @property {LogEntry[]} logs - List of log entries
 * @property {number} total_count - Total logs
 * @property {number} current_index - Latest log index
 * @property {JobStatus} job_status - Current job status
 */

// =============================================================================
// Settings Types
// =============================================================================

/**
 * Application settings.
 * @typedef {Object} Settings
 * @property {number} default_timeout - Request timeout in ms
 * @property {number} default_retry_count - Number of retries
 * @property {number} delay_min - Minimum delay between requests (ms)
 * @property {number} delay_max - Maximum delay between requests (ms)
 * @property {boolean} cascade_enabled - Whether cascade scraping is enabled
 * @property {string[]} cascade_order - Order of fetcher methods
 * @property {string} user_agent - Custom user agent (empty = rotate)
 * @property {boolean} respect_robots - Whether to respect robots.txt
 * @property {Object} google_sheets - Google Sheets export settings
 */

// =============================================================================
// State Types
// =============================================================================

/**
 * Application state data.
 * @typedef {Object} StateData
 * @property {Job[]} jobs - List of jobs
 * @property {string|null} selectedJobId - Currently selected job ID
 * @property {string} currentView - Current view name
 * @property {Settings} settings - Application settings
 */

/**
 * State change event keys.
 * @typedef {'jobs' | 'selectedJobId' | 'currentView' | 'settings'} StateKey
 */

/**
 * State change callback.
 * @callback StateSubscriber
 * @param {StateKey} key - The key that changed
 * @param {any} value - The new value
 * @returns {void}
 */

// =============================================================================
// API Response Types
// =============================================================================

/**
 * Job list response.
 * @typedef {Object} JobListResponse
 * @property {Job[]} jobs - List of jobs
 * @property {number} total - Total count
 */

/**
 * Job detail response.
 * @typedef {Object} JobDetailResponse
 * @property {Job} job - The job
 * @property {Rule[]} rules - Job's extraction rules
 */

/**
 * Single job response.
 * @typedef {Object} JobResponse
 * @property {Job} job - The job
 */

/**
 * Rule response.
 * @typedef {Object} RuleResponse
 * @property {Rule} rule - The rule
 */

/**
 * Result list response.
 * @typedef {Object} ResultListResponse
 * @property {Result[]} results - List of results
 */

/**
 * API error response.
 * @typedef {Object} APIError
 * @property {Object} error - Error details
 * @property {string} error.code - Error code
 * @property {string} error.message - Error message
 * @property {Object} [error.details] - Optional additional details
 */

// =============================================================================
// Validation Schemas
// =============================================================================

/**
 * Valid job statuses.
 * @type {readonly JobStatus[]}
 */
const JOB_STATUSES = Object.freeze([
    'pending', 'running', 'paused', 'completed', 'failed', 'cancelled', 'archived'
]);

/**
 * Valid job modes.
 * @type {readonly JobMode[]}
 */
const JOB_MODES = Object.freeze(['single', 'list', 'crawl']);

/**
 * Valid URL statuses.
 * @type {readonly UrlStatus[]}
 */
const URL_STATUSES = Object.freeze([
    'pending', 'processing', 'completed', 'failed', 'skipped'
]);

/**
 * Valid selector types.
 * @type {readonly SelectorType[]}
 */
const SELECTOR_TYPES = Object.freeze(['css', 'xpath']);

/**
 * Valid log levels.
 * @type {readonly LogLevel[]}
 */
const LOG_LEVELS = Object.freeze(['debug', 'info', 'success', 'warning', 'error']);

// =============================================================================
// Validation Functions
// =============================================================================

/**
 * Validate a job object.
 * @param {any} obj - Object to validate
 * @returns {{valid: boolean, errors: string[]}} Validation result
 */
function validateJob(obj) {
    const errors = [];

    if (!obj || typeof obj !== 'object') {
        return { valid: false, errors: ['Job must be an object'] };
    }

    if (typeof obj.id !== 'string' || !obj.id) {
        errors.push('Job must have a string id');
    }

    if (typeof obj.name !== 'string') {
        errors.push('Job must have a string name');
    }

    if (!JOB_STATUSES.includes(obj.status)) {
        errors.push(`Invalid job status: ${obj.status}`);
    }

    if (obj.mode && !JOB_MODES.includes(obj.mode)) {
        errors.push(`Invalid job mode: ${obj.mode}`);
    }

    if (typeof obj.progress_current !== 'number' || obj.progress_current < 0) {
        errors.push('progress_current must be a non-negative number');
    }

    if (typeof obj.progress_total !== 'number' || obj.progress_total < 0) {
        errors.push('progress_total must be a non-negative number');
    }

    return { valid: errors.length === 0, errors };
}

/**
 * Validate a rule object.
 * @param {any} obj - Object to validate
 * @returns {{valid: boolean, errors: string[]}} Validation result
 */
function validateRule(obj) {
    const errors = [];

    if (!obj || typeof obj !== 'object') {
        return { valid: false, errors: ['Rule must be an object'] };
    }

    if (typeof obj.name !== 'string' || !obj.name.trim()) {
        errors.push('Rule must have a non-empty name');
    }

    if (!SELECTOR_TYPES.includes(obj.selector_type)) {
        errors.push(`Invalid selector type: ${obj.selector_type}`);
    }

    if (typeof obj.selector_value !== 'string' || !obj.selector_value.trim()) {
        errors.push('Rule must have a non-empty selector_value');
    }

    return { valid: errors.length === 0, errors };
}

/**
 * Validate a URL object.
 * @param {any} obj - Object to validate
 * @returns {{valid: boolean, errors: string[]}} Validation result
 */
function validateUrl(obj) {
    const errors = [];

    if (!obj || typeof obj !== 'object') {
        return { valid: false, errors: ['URL must be an object'] };
    }

    if (typeof obj.url !== 'string' || !obj.url.trim()) {
        errors.push('URL must have a non-empty url string');
    }

    if (obj.status && !URL_STATUSES.includes(obj.status)) {
        errors.push(`Invalid URL status: ${obj.status}`);
    }

    return { valid: errors.length === 0, errors };
}

// =============================================================================
// Type Guards (for runtime checking)
// =============================================================================

/**
 * Check if value is a valid JobStatus.
 * @param {any} value - Value to check
 * @returns {value is JobStatus}
 */
function isJobStatus(value) {
    return JOB_STATUSES.includes(value);
}

/**
 * Check if value is a valid JobMode.
 * @param {any} value - Value to check
 * @returns {value is JobMode}
 */
function isJobMode(value) {
    return JOB_MODES.includes(value);
}

/**
 * Check if value is a valid SelectorType.
 * @param {any} value - Value to check
 * @returns {value is SelectorType}
 */
function isSelectorType(value) {
    return SELECTOR_TYPES.includes(value);
}

/**
 * Check if value is a valid LogLevel.
 * @param {any} value - Value to check
 * @returns {value is LogLevel}
 */
function isLogLevel(value) {
    return LOG_LEVELS.includes(value);
}

// =============================================================================
// Exports
// =============================================================================

window.Types = {
    // Constants
    JOB_STATUSES,
    JOB_MODES,
    URL_STATUSES,
    SELECTOR_TYPES,
    LOG_LEVELS,

    // Validators
    validateJob,
    validateRule,
    validateUrl,

    // Type guards
    isJobStatus,
    isJobMode,
    isSelectorType,
    isLogLevel,
};
