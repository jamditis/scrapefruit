/**
 * Activity Log Component
 * Real-time log display for job execution
 */
const ActivityLog = {
    currentJobId: null,
    logIndex: 0,
    pollInterval: null,
    POLL_RATE: 1000, // Poll every second for new logs
    activeFilter: 'all',
    isFetching: false, // Guard against concurrent fetches

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
                        Activity Log
                        <span class="log-count" id="log-count">0</span>
                    </h4>
                    <div class="activity-controls">
                        <div class="activity-filters">
                            <button class="activity-filter active" data-level="all">All</button>
                            <button class="activity-filter" data-level="success">Success</button>
                            <button class="activity-filter" data-level="error">Errors</button>
                        </div>
                        <div class="activity-actions">
                            <button class="btn btn-ghost btn-xs" id="btn-copy-logs" title="Copy to clipboard">📋 Copy</button>
                            <button class="btn btn-ghost btn-xs" id="btn-save-logs" title="Save as .txt file">💾 Save</button>
                        </div>
                    </div>
                </div>
                <div class="activity-body" id="activity-body">
                    <div class="log-empty">No activity yet. Start a job to see logs.</div>
                </div>
            </div>
        `;

        this.bindFilterEvents();
        this.bindExportEvents();
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
        });

        // Only auto-scroll if user was already at bottom
        if (wasAtBottom) {
            body.scrollTop = body.scrollHeight;
        }
    },

    /**
     * Create a single log entry element
     */
    createLogEntry(log) {
        const entry = document.createElement('div');
        entry.className = 'log-entry new';

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

        entry.innerHTML = `
            <span class="log-time">${timeStr}</span>
            <span class="log-level ${log.level}"></span>
            <span class="log-message">${message}</span>
        `;

        // Remove 'new' class after animation
        setTimeout(() => entry.classList.remove('new'), 200);

        return entry;
    },

    /**
     * Clear all logs
     */
    clearLogs() {
        const body = document.getElementById('activity-body');
        if (body) {
            body.innerHTML = '<div class="log-empty">Waiting for activity...</div>';
        }
        document.getElementById('log-count').textContent = '0';
        this.logIndex = 0;
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
