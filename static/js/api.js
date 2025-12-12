/**
 * Scrapefruit API client
 */
const API = {
    baseUrl: '',

    async request(method, endpoint, data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, options);
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Request failed');
            }

            return result;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // Jobs
    async listJobs(status = null) {
        const params = status ? `?status=${status}` : '';
        return this.request('GET', `/api/jobs${params}`);
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
    async listUrls(jobId, status = null) {
        const params = status ? `?status=${status}` : '';
        return this.request('GET', `/api/jobs/${jobId}/urls${params}`);
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
