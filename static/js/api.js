/**
 * Scrapefruit API client
 */
const API = {
    baseUrl: '',

    // Track consecutive failures for exponential backoff
    consecutiveFailures: 0,
    maxBackoffMs: 30000, // Max 30 second backoff
    baseBackoffMs: 1000, // Start at 1 second

    // Track in-flight requests to prevent duplicates
    pendingRequests: new Map(),

    /**
     * Get current backoff delay based on consecutive failures
     */
    getBackoffDelay() {
        if (this.consecutiveFailures === 0) return 0;
        const delay = Math.min(
            this.baseBackoffMs * Math.pow(2, this.consecutiveFailures - 1),
            this.maxBackoffMs
        );
        return delay;
    },

    /**
     * Wait for backoff period if needed
     */
    async waitForBackoff() {
        const delay = this.getBackoffDelay();
        if (delay > 0) {
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    },

    async request(method, endpoint, data = null, options = {}) {
        const { skipDedup = false } = options;
        const requestKey = `${method}:${endpoint}`;

        // Deduplicate concurrent identical requests (for polling)
        if (!skipDedup && this.pendingRequests.has(requestKey)) {
            return this.pendingRequests.get(requestKey);
        }

        const requestPromise = this._doRequest(method, endpoint, data);

        if (!skipDedup) {
            this.pendingRequests.set(requestKey, requestPromise);
            requestPromise.finally(() => {
                this.pendingRequests.delete(requestKey);
            });
        }

        return requestPromise;
    },

    async _doRequest(method, endpoint, data = null) {
        // Wait for backoff if we've had failures
        await this.waitForBackoff();

        const fetchOptions = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data) {
            fetchOptions.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, fetchOptions);

            // Check for server errors before parsing JSON
            if (response.status >= 500) {
                this.consecutiveFailures++;
                const error = new Error(`Server error: ${response.status} ${response.statusText}`);
                error.status = response.status;
                error.isServerError = true;
                throw error;
            }

            const result = await response.json();

            if (!response.ok) {
                this.consecutiveFailures++;
                throw new Error(result.error || 'Request failed');
            }

            // Success - reset failure counter
            this.consecutiveFailures = 0;
            return result;
        } catch (error) {
            // Only log non-repeated errors to reduce console spam
            if (this.consecutiveFailures <= 1 || this.consecutiveFailures % 5 === 0) {
                console.error(`API Error (failure #${this.consecutiveFailures}):`, error.message);
            }
            throw error;
        }
    },

    // Jobs
    async listJobs(status = null, includeArchived = false) {
        const params = new URLSearchParams();
        if (status) params.set('status', status);
        if (includeArchived) params.set('include_archived', 'true');
        const queryString = params.toString();
        return this.request('GET', `/api/jobs${queryString ? '?' + queryString : ''}`);
    },

    async getJob(jobId) {
        return this.request('GET', `/api/jobs/${jobId}`);
    },

    async createJob(data) {
        return this.request('POST', '/api/jobs', data);
    },

    async updateJob(jobId, data) {
        return this.request('PUT', `/api/jobs/${jobId}`, data);
    },

    async deleteJob(jobId) {
        return this.request('DELETE', `/api/jobs/${jobId}`);
    },

    async startJob(jobId) {
        return this.request('POST', `/api/jobs/${jobId}/start`);
    },

    async pauseJob(jobId) {
        return this.request('POST', `/api/jobs/${jobId}/pause`);
    },

    async resumeJob(jobId) {
        return this.request('POST', `/api/jobs/${jobId}/resume`);
    },

    async stopJob(jobId) {
        return this.request('POST', `/api/jobs/${jobId}/stop`);
    },

    async archiveJob(jobId) {
        return this.request('POST', `/api/jobs/${jobId}/archive`);
    },

    async unarchiveJob(jobId) {
        return this.request('POST', `/api/jobs/${jobId}/unarchive`);
    },

    async getJobProgress(jobId) {
        return this.request('GET', `/api/jobs/${jobId}/progress`);
    },

    // Logs (real-time activity stream)
    async getJobLogs(jobId, sinceIndex = 0, level = null) {
        let params = `?since=${sinceIndex}`;
        if (level) params += `&level=${level}`;
        return this.request('GET', `/api/jobs/${jobId}/logs${params}`);
    },

    async clearJobLogs(jobId) {
        return this.request('DELETE', `/api/jobs/${jobId}/logs`);
    },

    // URLs
    async listUrls(jobId, { status = null, limit = 50, offset = 0 } = {}) {
        const params = new URLSearchParams();
        if (status) params.set('status', status);
        params.set('limit', limit);
        params.set('offset', offset);
        return this.request('GET', `/api/jobs/${jobId}/urls?${params}`);
    },

    async addUrls(jobId, urls) {
        return this.request('POST', `/api/jobs/${jobId}/urls`, { urls });
    },

    async importCsv(jobId, csv, hasHeader = true, column = 0) {
        return this.request('POST', `/api/jobs/${jobId}/urls/import-csv`, {
            csv,
            has_header: hasHeader,
            column,
        });
    },

    async deleteUrl(jobId, urlId) {
        return this.request('DELETE', `/api/jobs/${jobId}/urls/${urlId}`);
    },

    // Rules
    async listRules(jobId) {
        return this.request('GET', `/api/jobs/${jobId}/rules`);
    },

    async addRule(jobId, rule) {
        return this.request('POST', `/api/jobs/${jobId}/rules`, rule);
    },

    async updateRule(jobId, ruleId, data) {
        return this.request('PUT', `/api/jobs/${jobId}/rules/${ruleId}`, data);
    },

    async deleteRule(jobId, ruleId) {
        return this.request('DELETE', `/api/jobs/${jobId}/rules/${ruleId}`);
    },

    // Results
    async listResults(jobId, limit = 100, offset = 0) {
        return this.request('GET', `/api/jobs/${jobId}/results?limit=${limit}&offset=${offset}`);
    },

    // Export
    async exportJson(jobId) {
        const response = await fetch(`${this.baseUrl}/api/export/json`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: jobId }),
        });
        return response.blob();
    },

    async exportCsv(jobId) {
        const response = await fetch(`${this.baseUrl}/api/export/csv`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: jobId }),
        });
        return response.blob();
    },

    // Scraping
    async previewScrape(url, rules) {
        return this.request('POST', '/api/scraping/preview', { url, rules });
    },

    async testSelector(url, selectorType, selectorValue, attribute = null) {
        return this.request('POST', '/api/scraping/test-selector', {
            url,
            selector_type: selectorType,
            selector_value: selectorValue,
            attribute,
        });
    },

    async fetchSamplesFromUrls(urls) {
        return this.request('POST', '/api/scraping/fetch-samples', { urls });
    },

    // Settings
    async getSettings() {
        return this.request('GET', '/api/settings');
    },

    async updateSettings(settings) {
        return this.request('PUT', '/api/settings', settings);
    },

    async resetSettings() {
        return this.request('POST', '/api/settings/defaults');
    },

    // Database
    async listTables() {
        return this.request('GET', '/api/database/tables');
    },

    async getTableSchema(tableName) {
        return this.request('GET', `/api/database/tables/${tableName}/schema`);
    },

    async getTableRows(tableName, limit = 50, offset = 0) {
        return this.request('GET', `/api/database/tables/${tableName}/rows?limit=${limit}&offset=${offset}`);
    },

    async executeQuery(sql) {
        return this.request('POST', '/api/database/query', { sql });
    },
};

// Export for use
window.API = API;
