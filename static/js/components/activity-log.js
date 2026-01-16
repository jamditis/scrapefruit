/**
 * Activity Log Component
 * Real-time log display for job execution with enhanced details
 */
const ActivityLog = {
    currentJobId: null,
    logIndex: 0,
    pollInterval: null,
    POLL_RATE: 1000, // Poll every second for new logs
    activeFilter: 'all',
    isFetching: false, // Guard against concurrent fetches
    errorCounts: { total: 0, byType: {} }, // Track error categories
    successCount: 0,
    lastLogTimestamp: null,

    // Error type descriptions for better UX
    errorDescriptions: {
        'poison_pill': 'Anti-bot protection detected',
        'cloudflare': 'Cloudflare challenge blocked',
        'captcha': 'CAPTCHA verification required',
        'paywall': 'Paywall or subscription required',
        'rate_limit': 'Rate limit exceeded',
        'timeout': 'Request timed out',
        'extraction_failed': 'No data could be extracted',
        'exception': 'Unexpected error occurred',
        'network': 'Network connection failed',
        '403': 'Access forbidden (403)',
        '404': 'Page not found (404)',
        '429': 'Too many requests (429)',
        '500': 'Server error (500)',
        '503': 'Service unavailable (503)',
    },

    /**
     * Render the activity log panel
     */
    render(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="activity-log">
                <div class="activity-header">
                    <h4>
                        Activity log
                        <span class="log-count" id="log-count">0</span>
                    </h4>
                    <div class="activity-controls">
                        <div class="activity-filters">
                            <button class="activity-filter active" data-level="all">All</button>
                            <button class="activity-filter" data-level="success">
                                Success <span class="filter-count" id="success-count">0</span>
                            </button>
                            <button class="activity-filter" data-level="error">
                                Errors <span class="filter-count" id="error-count">0</span>
                            </button>
                        </div>
                        <div class="activity-actions">
                            <button class="btn btn-ghost btn-xs" id="btn-copy-logs" title="Copy to clipboard">📋 Copy</button>
                            <button class="btn btn-ghost btn-xs" id="btn-save-logs" title="Save as .txt file">💾 Save</button>
                        </div>
                    </div>
                </div>
                <div class="activity-summary" id="activity-summary" style="display: none;">
                    <div class="error-breakdown" id="error-breakdown"></div>
                </div>
                <div class="activity-body" id="activity-body">
                    <div class="log-empty">No activity yet. Start a job to see logs.</div>
                </div>
            </div>
        `;

        this.bindFilterEvents();
        this.bindExportEvents();
        this.resetCounts();
    },

    /**
     * Reset error/success counts
     */
    resetCounts() {
        this.errorCounts = { total: 0, byType: {} };
        this.successCount = 0;
        this.lastLogTimestamp = null;
    },

    /**
     * Bind filter button events
     */
    bindFilterEvents() {
        const filters = document.querySelectorAll('.activity-filter');
        filters.forEach(btn => {
            btn.addEventListener('click', () => {
                filters.forEach(f => f.classList.remove('active'));
                btn.classList.add('active');
                this.activeFilter = btn.dataset.level;
                this.refreshDisplay();
            });
        });
    },

    /**
     * Start polling for logs for a specific job
     */
    startPolling(jobId) {
        this.stopPolling();
        this.currentJobId = jobId;
        this.logIndex = 0;
        this.clearLogs();
        this.resetCounts();

        // Initialize progress tracker
        if (typeof ProgressTracker !== 'undefined') {
            ProgressTracker.initJob(jobId, 0);
        }

        this.pollInterval = setInterval(() => this.fetchLogs(), this.POLL_RATE);
        this.fetchLogs(); // Immediate first fetch
    },

    /**
     * Stop polling for logs
     */
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },

    /**
     * Fetch new logs from API
     */
    async fetchLogs() {
        if (!this.currentJobId) return;

        // Guard against concurrent fetches
        if (this.isFetching) return;
        this.isFetching = true;

        try {
            const levelFilter = this.activeFilter !== 'all' ? this.activeFilter : null;
            const result = await API.getJobLogs(this.currentJobId, this.logIndex, levelFilter);

            if (result.logs && result.logs.length > 0) {
                this.appendLogs(result.logs);
            }

            // Update index for next poll
            this.logIndex = result.current_index;

            // Update count display
            const logCountEl = document.getElementById('log-count');
            if (logCountEl) {
                logCountEl.textContent = result.total_count;
            }

            // Stop polling if job is complete
            if (result.job_status === 'completed' || result.job_status === 'failed' || result.job_status === 'cancelled') {
                this.stopPolling();
            }

        } catch (error) {
            // Errors handled by API layer with backoff
        } finally {
            this.isFetching = false;
        }
    },

    /**
     * Check if user is scrolled near the bottom
     */
    isNearBottom(element) {
        const threshold = 50; // pixels from bottom
        return element.scrollHeight - element.scrollTop - element.clientHeight < threshold;
    },

    /**
     * Append new log entries to the display
     */
    appendLogs(logs) {
        const body = document.getElementById('activity-body');
        if (!body) return;

        // Check if user is at bottom BEFORE adding new content
        const wasAtBottom = this.isNearBottom(body);

        // Remove empty state if present
        const emptyState = body.querySelector('.log-empty');
        if (emptyState) {
            emptyState.remove();
        }

        logs.forEach(log => {
            const entry = this.createLogEntry(log);
            body.appendChild(entry);

            // Track counts and emit events
            this.trackLogEntry(log);
        });

        // Update filter counts
        this.updateFilterCounts();

        // Update error breakdown if there are errors
        this.updateErrorBreakdown();

        // Only auto-scroll if user was already at bottom
        if (wasAtBottom) {
            body.scrollTop = body.scrollHeight;
        }
    },

    /**
     * Track log entry for counts and toast notifications
     */
    trackLogEntry(log) {
        if (log.level === 'success') {
            this.successCount++;

            // Update progress tracker with success
            if (typeof ProgressTracker !== 'undefined' && this.currentJobId) {
                const timeMs = log.data?.time_ms || null;
                ProgressTracker.urlCompleted(this.currentJobId, true, timeMs);
            }

        } else if (log.level === 'error') {
            this.errorCounts.total++;

            // Categorize the error
            const errorType = this.categorizeError(log);
            this.errorCounts.byType[errorType] = (this.errorCounts.byType[errorType] || 0) + 1;

            // Update progress tracker with failure
            if (typeof ProgressTracker !== 'undefined' && this.currentJobId) {
                const timeMs = log.data?.time_ms || null;
                ProgressTracker.urlCompleted(this.currentJobId, false, timeMs);
            }

            // Show toast for errors (but not too frequently)
            if (typeof Toast !== 'undefined' && this.errorCounts.total <= 5) {
                const url = log.data?.url || null;
                const errorMsg = log.message || 'Unknown error';
                Toast.error(errorMsg, {
                    url,
                    duration: 4000,
                });
            }
        } else if (log.level === 'info' && log.message.includes('Starting job')) {
            // Extract total URLs from job start message
            const match = log.message.match(/(\d+) URLs/);
            if (match && typeof ProgressTracker !== 'undefined' && this.currentJobId) {
                const total = parseInt(match[1], 10);
                ProgressTracker.initJob(this.currentJobId, total);
            }

            // Show job started toast
            if (typeof Toast !== 'undefined') {
                const total = log.data?.total_urls || 0;
                Toast.jobEvent('job_started', { total });
            }
        } else if (log.level === 'info' && log.message.includes('Job complete')) {
            // Show job completed toast
            if (typeof Toast !== 'undefined') {
                Toast.jobEvent('job_completed', {
                    success: this.successCount,
                    failed: this.errorCounts.total,
                });
            }
        } else if (log.level === 'info' && log.message.includes('Fetching:')) {
            // Track current URL being processed
            const urlMatch = log.message.match(/Fetching: (.+?)\.{3}$/);
            if (urlMatch && typeof ProgressTracker !== 'undefined' && this.currentJobId) {
                ProgressTracker.urlStarted(this.currentJobId, urlMatch[1]);
            }
        }

        this.lastLogTimestamp = log.timestamp;
    },

    /**
     * Categorize error for grouping
     */
    categorizeError(log) {
        const errorType = log.data?.error_type || '';
        const message = (log.message || '').toLowerCase();

        // Check for specific error types
        if (errorType.includes('poison') || message.includes('poison')) return 'poison_pill';
        if (message.includes('cloudflare')) return 'cloudflare';
        if (message.includes('captcha')) return 'captcha';
        if (message.includes('paywall') || message.includes('subscribe')) return 'paywall';
        if (message.includes('rate limit') || message.includes('429')) return 'rate_limit';
        if (message.includes('timeout')) return 'timeout';
        if (message.includes('403')) return '403';
        if (message.includes('404')) return '404';
        if (message.includes('500')) return '500';
        if (message.includes('503')) return '503';
        if (errorType === 'extraction_failed') return 'extraction_failed';
        if (errorType === 'exception') return 'exception';

        return 'other';
    },

    /**
     * Update filter button counts
     */
    updateFilterCounts() {
        const successCountEl = document.getElementById('success-count');
        const errorCountEl = document.getElementById('error-count');

        if (successCountEl) {
            successCountEl.textContent = this.successCount;
            successCountEl.classList.toggle('has-count', this.successCount > 0);
        }
        if (errorCountEl) {
            errorCountEl.textContent = this.errorCounts.total;
            errorCountEl.classList.toggle('has-count', this.errorCounts.total > 0);
            errorCountEl.classList.toggle('has-errors', this.errorCounts.total > 0);
        }
    },

    /**
     * Update error breakdown summary
     */
    updateErrorBreakdown() {
        const summary = document.getElementById('activity-summary');
        const breakdown = document.getElementById('error-breakdown');

        if (!summary || !breakdown) return;

        if (this.errorCounts.total === 0) {
            summary.style.display = 'none';
            return;
        }

        summary.style.display = 'block';

        const sortedErrors = Object.entries(this.errorCounts.byType)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5); // Top 5 error types

        breakdown.innerHTML = sortedErrors.map(([type, count]) => {
            const description = this.errorDescriptions[type] || type;
            const percent = Math.round((count / this.errorCounts.total) * 100);
            return `
                <div class="error-type-badge" title="${description}">
                    <span class="error-type-name">${this.formatErrorType(type)}</span>
                    <span class="error-type-count">${count}</span>
                </div>
            `;
        }).join('');
    },

    /**
     * Format error type for display
     */
    formatErrorType(type) {
        const labels = {
            'poison_pill': 'Anti-bot',
            'cloudflare': 'Cloudflare',
            'captcha': 'CAPTCHA',
            'paywall': 'Paywall',
            'rate_limit': 'Rate limit',
            'timeout': 'Timeout',
            'extraction_failed': 'No data',
            'exception': 'Error',
            'network': 'Network',
            '403': '403',
            '404': '404',
            '429': '429',
            '500': '500',
            '503': '503',
            'other': 'Other',
        };
        return labels[type] || type;
    },

    /**
     * Create a single log entry element
     */
    createLogEntry(log) {
        const entry = document.createElement('div');
        entry.className = `log-entry new log-${log.level}`;

        // Parse timestamp
        const time = new Date(log.timestamp);
        const timeStr = time.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        // Format message with highlights
        let message = this.escapeHtml(log.message);

        // Highlight URLs
        message = message.replace(/(https?:\/\/[^\s]+)/g, '<span class="url">$1</span>');

        // Highlight field names in brackets
        message = message.replace(/\[([^\]]+)\]/g, '[<span class="field">$1</span>]');

        // Highlight numbers with units
        message = message.replace(/(\d+(?:ms|s|%|\/\d+))/g, '<span class="value">$1</span>');

        // Build additional details for expandable view
        let details = '';
        if (log.data && Object.keys(log.data).length > 0) {
            details = this.buildLogDetails(log);
        }

        // Get level icon
        const levelIcon = this.getLevelIcon(log.level);

        entry.innerHTML = `
            <span class="log-time">${timeStr}</span>
            <span class="log-level ${log.level}" title="${log.level}">${levelIcon}</span>
            <div class="log-content">
                <span class="log-message">${message}</span>
                ${details}
            </div>
        `;

        // Make expandable if has details
        if (details) {
            entry.classList.add('expandable');
            entry.addEventListener('click', () => {
                entry.classList.toggle('expanded');
            });
        }

        // Remove 'new' class after animation
        setTimeout(() => entry.classList.remove('new'), 200);

        return entry;
    },

    /**
     * Get icon for log level
     */
    getLevelIcon(level) {
        const icons = {
            'success': '✓',
            'error': '✕',
            'warning': '⚠',
            'info': '→',
            'debug': '·',
        };
        return icons[level] || '·';
    },

    /**
     * Build expandable details section
     */
    buildLogDetails(log) {
        const data = log.data;
        if (!data || Object.keys(data).length === 0) return '';

        const items = [];

        // URL
        if (data.url) {
            items.push(`<div class="detail-row"><span class="detail-label">URL:</span><span class="detail-value detail-url">${this.escapeHtml(data.url)}</span></div>`);
        }

        // Method used
        if (data.method) {
            items.push(`<div class="detail-row"><span class="detail-label">Method:</span><span class="detail-value">${data.method}</span></div>`);
        }

        // Processing time
        if (data.time_ms) {
            items.push(`<div class="detail-row"><span class="detail-label">Time:</span><span class="detail-value">${data.time_ms}ms</span></div>`);
        }

        // Error type
        if (data.error_type) {
            const description = this.errorDescriptions[data.error_type] || data.error_type;
            items.push(`<div class="detail-row"><span class="detail-label">Error type:</span><span class="detail-value detail-error">${description}</span></div>`);
        }

        // Cascade attempts
        if (data.cascade_attempts && data.cascade_attempts > 1) {
            items.push(`<div class="detail-row"><span class="detail-label">Cascade attempts:</span><span class="detail-value">${data.cascade_attempts}</span></div>`);
        }

        // Fields extracted
        if (data.fields && Object.keys(data.fields).length > 0) {
            const fieldsList = Object.entries(data.fields)
                .map(([k, v]) => `${k}: ${v}`)
                .join(', ');
            items.push(`<div class="detail-row"><span class="detail-label">Fields:</span><span class="detail-value">${this.escapeHtml(fieldsList)}</span></div>`);
        }

        // Data preview (for successful extractions)
        if (data.data_preview && Object.keys(data.data_preview).length > 0) {
            const previewItems = Object.entries(data.data_preview).slice(0, 3);
            const preview = previewItems.map(([k, v]) => {
                const val = typeof v === 'string' ? v.substring(0, 100) : JSON.stringify(v).substring(0, 100);
                return `<div class="preview-item"><strong>${k}:</strong> ${this.escapeHtml(val)}${val.length >= 100 ? '...' : ''}</div>`;
            }).join('');
            items.push(`<div class="detail-row detail-preview">${preview}</div>`);
        }

        if (items.length === 0) return '';

        return `<div class="log-details">${items.join('')}</div>`;
    },

    /**
     * Clear all logs
     */
    clearLogs() {
        const body = document.getElementById('activity-body');
        if (body) {
            body.innerHTML = '<div class="log-empty">Waiting for activity...</div>';
        }
        const logCount = document.getElementById('log-count');
        if (logCount) logCount.textContent = '0';
        this.logIndex = 0;
        this.resetCounts();
        this.updateFilterCounts();

        // Hide error breakdown
        const summary = document.getElementById('activity-summary');
        if (summary) summary.style.display = 'none';
    },

    /**
     * Refresh the display with current filter
     */
    async refreshDisplay() {
        this.logIndex = 0;
        this.clearLogs();
        await this.fetchLogs();
    },

    /**
     * Bind export button events
     */
    bindExportEvents() {
        const btnCopy = document.getElementById('btn-copy-logs');
        const btnSave = document.getElementById('btn-save-logs');

        if (btnCopy) {
            btnCopy.addEventListener('click', () => this.copyLogsToClipboard());
        }
        if (btnSave) {
            btnSave.addEventListener('click', () => this.saveLogsToFile());
        }
    },

    /**
     * Get all logs as plain text
     */
    getLogsAsText() {
        const body = document.getElementById('activity-body');
        if (!body) return '';

        const entries = body.querySelectorAll('.log-entry');
        const lines = [];

        entries.forEach(entry => {
            const time = entry.querySelector('.log-time')?.textContent || '';
            const level = entry.querySelector('.log-level')?.classList.contains('error') ? 'ERROR' :
                          entry.querySelector('.log-level')?.classList.contains('success') ? 'SUCCESS' : 'INFO';
            const message = entry.querySelector('.log-message')?.textContent || '';
            lines.push(`[${time}] [${level}] ${message}`);
        });

        return lines.join('\n');
    },

    /**
     * Copy logs to clipboard
     */
    async copyLogsToClipboard() {
        const text = this.getLogsAsText();
        if (!text) {
            alert('No logs to copy');
            return;
        }

        try {
            await navigator.clipboard.writeText(text);
            // Show feedback
            const btn = document.getElementById('btn-copy-logs');
            if (btn) {
                const originalText = btn.textContent;
                btn.textContent = '✓ Copied!';
                setTimeout(() => btn.textContent = originalText, 2000);
            }
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
            alert('Failed to copy to clipboard');
        }
    },

    /**
     * Save logs to .txt file
     */
    saveLogsToFile() {
        const text = this.getLogsAsText();
        if (!text) {
            alert('No logs to save');
            return;
        }

        const jobId = this.currentJobId || 'unknown';
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `scrapefruit-logs-${jobId.slice(0, 8)}-${timestamp}.txt`;

        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    /**
     * Escape HTML characters
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Export
window.ActivityLog = ActivityLog;
