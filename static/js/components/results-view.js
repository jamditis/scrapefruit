/**
 * Results View Component
 */
const ResultsView = {
    els: {},
    currentJobId: null,
    results: [],
    expandedRows: new Set(),

    init() {
        this.cacheElements();
        this.bindEvents();
    },

    cacheElements() {
        this.els = {
            jobSelect: document.getElementById('results-job-select'),
            jobSelectMain: document.getElementById('results-job-select-main'),
            resultsContainer: document.getElementById('results-container'),
            emptyState: document.getElementById('results-empty-state'),
            btnExportJson: document.getElementById('btn-export-json'),
            btnExportCsv: document.getElementById('btn-export-csv'),
            btnRefresh: document.getElementById('btn-refresh-results'),
        };
    },

    bindEvents() {
        // Job selection - header dropdown
        this.els.jobSelect.addEventListener('change', (e) => {
            this.currentJobId = e.target.value;
            this.syncJobSelects();
            this.expandedRows.clear();
            this.loadResults();
        });

        // Job selection - main centered dropdown
        if (this.els.jobSelectMain) {
            this.els.jobSelectMain.addEventListener('change', (e) => {
                this.currentJobId = e.target.value;
                this.syncJobSelects();
                this.expandedRows.clear();
                this.loadResults();
            });
        }

        // Export buttons
        this.els.btnExportJson.addEventListener('click', () => this.exportJson());
        this.els.btnExportCsv.addEventListener('click', () => this.exportCsv());

        // Refresh button
        if (this.els.btnRefresh) {
            this.els.btnRefresh.addEventListener('click', () => this.loadResults());
        }

        // Subscribe to job changes
        State.subscribe((key, value) => {
            if (key === 'jobs') this.updateJobSelect();
        });
    },

    updateJobSelect() {
        const jobs = State.get('jobs');
        const options = jobs.map(job =>
            `<option value="${job.id}">${this.escapeHtml(job.name)} (${job.success_count} results)</option>`
        ).join('');

        const optionsHtml = `<option value="">Select a job...</option>${options}`;

        // Update both dropdowns
        this.els.jobSelect.innerHTML = optionsHtml;
        if (this.els.jobSelectMain) {
            this.els.jobSelectMain.innerHTML = optionsHtml;
        }

        // Restore selection if valid
        this.syncJobSelects();
    },

    syncJobSelects() {
        // Keep both selects in sync
        if (this.els.jobSelect) {
            this.els.jobSelect.value = this.currentJobId || '';
        }
        if (this.els.jobSelectMain) {
            this.els.jobSelectMain.value = this.currentJobId || '';
        }
    },

    async loadResults() {
        if (!this.currentJobId) {
            this.showEmptyState();
            return;
        }

        // Hide empty state, show loading
        this.hideEmptyState();
        this.els.resultsContainer.innerHTML = `
            <div class="results-loading">
                <span>Loading results...</span>
            </div>
        `;

        try {
            const result = await API.listResults(this.currentJobId, 500);
            this.results = result.results || [];

            if (this.results.length === 0) {
                this.renderNoResults();
                return;
            }

            this.renderResults();

        } catch (error) {
            console.error('Failed to load results:', error);
            this.renderError(`Failed to load results: ${error.message}`);
        }
    },

    showEmptyState() {
        // Show the centered empty state with job selector
        if (this.els.emptyState) {
            this.els.emptyState.style.display = 'flex';
        }
        // Clear any results
        const existingResults = this.els.resultsContainer.querySelector('.results-stats, .results-table-wrapper, .results-loading');
        if (existingResults) {
            this.els.resultsContainer.innerHTML = '';
            this.els.resultsContainer.appendChild(this.els.emptyState);
        }
    },

    hideEmptyState() {
        if (this.els.emptyState) {
            this.els.emptyState.style.display = 'none';
        }
    },

    renderNoResults() {
        this.hideEmptyState();
        this.els.resultsContainer.innerHTML = `
            <div class="results-empty">
                <div class="empty-state-centered">
                    <div class="empty-icon">📭</div>
                    <h3>No results yet</h3>
                    <p>Run the job to see scraped data here</p>
                </div>
            </div>
        `;
    },

    renderError(message) {
        this.hideEmptyState();
        this.els.resultsContainer.innerHTML = `
            <div class="results-empty" style="color: var(--color-error)">
                <div class="empty-state-centered">
                    <div class="empty-icon">⚠️</div>
                    <h3>Error loading results</h3>
                    <p>${message}</p>
                </div>
            </div>
        `;
    },

    renderResults() {
        this.hideEmptyState();

        // Extract all unique field names from results
        const allFields = new Set();
        this.results.forEach(r => {
            if (r.data && typeof r.data === 'object') {
                Object.keys(r.data).forEach(k => allFields.add(k));
            }
        });
        const fields = Array.from(allFields);

        // Build table
        const html = `
            <div class="results-stats">
                <span class="results-count">${this.results.length} results</span>
                <span class="results-fields">${fields.length} fields: ${fields.join(', ')}</span>
            </div>
            <div class="results-table-wrapper">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th class="col-expand"></th>
                            <th class="col-url">URL</th>
                            ${fields.map(f => `<th class="col-field">${this.escapeHtml(f)}</th>`).join('')}
                            <th class="col-time">Scraped</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.results.map((r, idx) => this.renderResultRow(r, idx, fields)).join('')}
                    </tbody>
                </table>
            </div>
        `;

        this.els.resultsContainer.innerHTML = html;

        // Bind expand/collapse events
        this.els.resultsContainer.querySelectorAll('.row-expand-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(btn.dataset.idx);
                this.toggleRowExpand(idx);
            });
        });
    },

    renderResultRow(result, idx, fields) {
        const isExpanded = this.expandedRows.has(idx);
        const data = result.data || {};

        // Main row
        let mainRow = `
            <tr class="result-row ${isExpanded ? 'expanded' : ''}" data-idx="${idx}">
                <td class="col-expand">
                    <button class="row-expand-btn" data-idx="${idx}">${isExpanded ? '▼' : '▶'}</button>
                </td>
                <td class="col-url result-url" title="${this.escapeHtml(result.url)}">
                    ${this.escapeHtml(this.truncateUrl(result.url))}
                </td>
                ${fields.map(f => `
                    <td class="col-field result-field" title="${this.escapeHtml(this.formatValue(data[f]))}">
                        ${this.escapeHtml(this.truncateValue(data[f]))}
                    </td>
                `).join('')}
                <td class="col-time">${result.scraped_at ? this.formatTime(result.scraped_at) : ''}</td>
            </tr>
        `;

        // Expanded detail row
        if (isExpanded) {
            mainRow += `
                <tr class="result-detail-row">
                    <td colspan="${fields.length + 3}">
                        <div class="result-detail">
                            <div class="result-detail-url">
                                <strong>URL:</strong>
                                <a href="${this.escapeHtml(result.url)}" target="_blank">${this.escapeHtml(result.url)}</a>
                            </div>
                            <div class="result-detail-data">
                                ${Object.entries(data).map(([key, value]) => `
                                    <div class="result-detail-field">
                                        <span class="field-label">${this.escapeHtml(key)}:</span>
                                        <span class="field-value">${this.escapeHtml(this.formatValue(value))}</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        }

        return mainRow;
    },

    toggleRowExpand(idx) {
        if (this.expandedRows.has(idx)) {
            this.expandedRows.delete(idx);
        } else {
            this.expandedRows.add(idx);
        }
        this.renderResults();
    },

    truncateUrl(url) {
        if (!url) return '';
        if (url.length <= 50) return url;
        return url.substring(0, 47) + '...';
    },

    truncateValue(value) {
        const str = this.formatValue(value);
        if (str.length <= 40) return str;
        return str.substring(0, 37) + '...';
    },

    formatValue(value) {
        if (value === null || value === undefined) return '';
        if (Array.isArray(value)) {
            return value.length === 1 ? String(value[0]) : `[${value.length} items] ${value.join(', ')}`;
        }
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value);
    },

    formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    },

    async exportJson() {
        if (!this.currentJobId) {
            alert('Please select a job first');
            return;
        }

        try {
            const blob = await API.exportJson(this.currentJobId);
            this.downloadBlob(blob, `scrapefruit_${this.currentJobId.slice(0, 8)}.json`);
        } catch (error) {
            console.error('Export failed:', error);
            alert(`Export failed: ${error.message}`);
        }
    },

    async exportCsv() {
        if (!this.currentJobId) {
            alert('Please select a job first');
            return;
        }

        try {
            const blob = await API.exportCsv(this.currentJobId);
            this.downloadBlob(blob, `scrapefruit_${this.currentJobId.slice(0, 8)}.csv`);
        } catch (error) {
            console.error('Export failed:', error);
            alert(`Export failed: ${error.message}`);
        }
    },

    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    escapeHtml(text) {
        if (typeof text !== 'string') text = String(text);
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};

// Export
window.ResultsView = ResultsView;
