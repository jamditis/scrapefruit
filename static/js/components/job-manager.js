/**
 * Job Manager Component
 */
const JobManager = {
    // Elements
    els: {},

    // Initialize
    init() {
        this.cacheElements();
        this.bindEvents();
        this.loadJobs();

        // Initialize cascade settings component
        if (typeof CascadeSettings !== 'undefined') {
            CascadeSettings.init();
        }
    },

    cacheElements() {
        this.els = {
            jobsList: document.getElementById('jobs-list'),
            jobsEmpty: document.getElementById('jobs-empty'),
            jobDetail: document.getElementById('job-detail'),
            btnNewJob: document.getElementById('btn-new-job'),
            btnRefreshJobs: document.getElementById('btn-refresh-jobs'),
            modalNewJob: document.getElementById('modal-new-job'),
            modalAddRule: document.getElementById('modal-add-rule'),
        };
    },

    bindEvents() {
        // New job button
        this.els.btnNewJob.addEventListener('click', () => this.showNewJobModal());

        // Refresh button
        if (this.els.btnRefreshJobs) {
            this.els.btnRefreshJobs.addEventListener('click', () => this.loadJobs());
        }

        // Modal close buttons
        document.querySelectorAll('.modal-close, .modal-cancel').forEach(btn => {
            btn.addEventListener('click', () => this.closeModals());
        });

        // Modal backdrop click
        document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
            backdrop.addEventListener('click', () => this.closeModals());
        });

        // Create job button
        document.getElementById('btn-create-job').addEventListener('click', () => this.createJob());

        // Add rule button
        document.getElementById('btn-save-rule').addEventListener('click', () => this.saveRule());

        // Subscribe to state changes
        State.subscribe((key, value) => {
            if (key === 'jobs') this.renderJobsList();
            if (key === 'selectedJobId') this.renderJobDetail();
        });
    },

    async loadJobs() {
        try {
            const result = await API.listJobs();
            State.set('jobs', result.jobs || []);
        } catch (error) {
            console.error('Failed to load jobs:', error);
        }
    },

    renderJobsList() {
        const jobs = State.get('jobs');
        const selectedId = State.get('selectedJobId');

        if (jobs.length === 0) {
            this.els.jobsEmpty.style.display = 'flex';
            return;
        }

        this.els.jobsEmpty.style.display = 'none';

        const html = jobs.map(job => {
            const percent = job.progress_total > 0
                ? Math.round((job.progress_current / job.progress_total) * 100)
                : 0;

            return `
                <div class="job-card ${job.id === selectedId ? 'selected' : ''}" data-job-id="${job.id}">
                    <div class="job-card-header">
                        <span class="job-card-title">${this.escapeHtml(job.name)}</span>
                        <span class="job-status ${job.status}">${job.status}</span>
                    </div>
                    ${job.progress_total > 0 ? `
                        <div class="job-card-progress">
                            <div class="progress-bar">
                                <div class="progress-bar-fill" style="width: ${percent}%"></div>
                            </div>
                        </div>
                    ` : ''}
                    <div class="job-card-meta">
                        <span>${job.progress_current}/${job.progress_total} URLs</span>
                        <span>${job.success_count} success, ${job.failure_count} failed</span>
                    </div>
                </div>
            `;
        }).join('');

        // Keep empty state but hide it, render jobs before it
        const emptyState = this.els.jobsEmpty.outerHTML;
        this.els.jobsList.innerHTML = html + emptyState;
        this.els.jobsEmpty = document.getElementById('jobs-empty');

        // Add click listeners
        this.els.jobsList.querySelectorAll('.job-card').forEach(card => {
            card.addEventListener('click', () => {
                State.set('selectedJobId', card.dataset.jobId);
            });
        });
    },

    async renderJobDetail() {
        const jobId = State.get('selectedJobId');

        if (!jobId) {
            this.els.jobDetail.innerHTML = `
                <div class="detail-placeholder">
                    <p>Select a job to view details</p>
                </div>
            `;
            return;
        }

        try {
            const result = await API.getJob(jobId);
            const job = result.job;
            const rules = result.rules || [];

            // Store pagination state for URLs
            this._urlPagination = { offset: 0, limit: 50, total: job.progress_total, loaded: [] };

            const percent = job.progress_total > 0
                ? Math.round((job.progress_current / job.progress_total) * 100)
                : 0;

            this.els.jobDetail.innerHTML = `
                <div class="detail-header">
                    <h2 class="detail-title">${this.escapeHtml(job.name)}</h2>
                    <div class="detail-actions">
                        ${this.renderJobActions(job)}
                    </div>
                </div>

                <div class="detail-section">
                    <h3>Progress</h3>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">${percent}%</div>
                            <div class="stat-label">Complete</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${job.progress_total}</div>
                            <div class="stat-label">Total URLs</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" style="color: var(--color-success)">${job.success_count}</div>
                            <div class="stat-label">Successful</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" style="color: var(--color-error)">${job.failure_count}</div>
                            <div class="stat-label">Failed</div>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-md);">
                        <h3 style="margin: 0;">Extraction rules</h3>
                        <button class="btn btn-secondary btn-sm" id="btn-add-rule">+ Add rule</button>
                    </div>
                    <div class="rules-list" id="rules-list">
                        ${rules.length > 0 ? rules.map(rule => `
                            <div class="rule-item" data-rule-id="${rule.id}">
                                <span class="rule-name">${this.escapeHtml(rule.name)}</span>
                                <span class="rule-selector">${this.escapeHtml(rule.selector_value)}</span>
                                <div class="rule-badges">
                                    <span class="rule-badge">${rule.selector_type}</span>
                                    ${rule.is_required ? '<span class="rule-badge">required</span>' : ''}
                                    ${rule.is_list ? '<span class="rule-badge">list</span>' : ''}
                                </div>
                                <button class="rule-delete" data-rule-id="${rule.id}">×</button>
                            </div>
                        `).join('') : '<p style="color: var(--color-text-muted)">No extraction rules defined. Add rules to specify what data to scrape.</p>'}
                    </div>
                </div>

                <div class="detail-section sample-analyzer-section">
                    <h3>Quick setup from samples</h3>
                    <p style="color: var(--color-text-muted); margin-bottom: var(--spacing-md);">
                        Upload 1-10 HTML sample files to auto-detect extraction patterns
                    </p>
                    <div class="sample-upload-zone" id="sample-upload-zone">
                        <input type="file" id="sample-files" multiple accept=".html,.htm" hidden>
                        <div class="upload-prompt">
                            <span class="upload-icon">📄</span>
                            <span>Drop HTML files here or click to browse</span>
                        </div>
                        <div class="upload-files" id="upload-files-list"></div>
                    </div>
                    <button class="btn btn-secondary" id="btn-analyze-samples" disabled style="margin-top: var(--spacing-md);">
                        Analyze samples
                    </button>
                </div>

                <div class="detail-section">
                    <h3>URLs (${job.progress_total})</h3>
                    <div class="urls-preview" id="urls-preview">
                        <div class="urls-loading" style="padding: var(--spacing-md); color: var(--muted);">Loading URLs...</div>
                    </div>
                    ${job.progress_total > 50 ? `
                        <div class="urls-pagination" style="margin-top: var(--spacing-sm); display: flex; gap: var(--spacing-sm); align-items: center;">
                            <button class="btn btn-sm btn-ghost" id="btn-urls-prev" disabled>← Prev</button>
                            <span class="urls-page-info" id="urls-page-info" style="font-size: 12px; color: var(--muted);">1-50 of ${job.progress_total}</span>
                            <button class="btn btn-sm btn-ghost" id="btn-urls-next" ${job.progress_total <= 50 ? 'disabled' : ''}>Next →</button>
                        </div>
                    ` : ''}
                </div>

                <div class="detail-section">
                    <h3>Activity log</h3>
                    <div id="activity-log-container"></div>
                </div>

                <div class="detail-section raw-data-section">
                    <div class="raw-data-header" id="raw-data-toggle">
                        <h3>Raw data</h3>
                        <span class="raw-data-toggle-icon">+</span>
                    </div>
                    <div class="raw-data-content" id="raw-data-content" style="display: none;">
                        <div class="raw-data-tabs">
                            <button class="raw-data-tab active" data-tab="job">Job</button>
                            <button class="raw-data-tab" data-tab="urls">URLs (${job.progress_total})</button>
                            <button class="raw-data-tab" data-tab="results">Results</button>
                        </div>
                        <div class="raw-data-panel" id="raw-data-panel">
                            <pre class="raw-data-json">${JSON.stringify(job, null, 2)}</pre>
                        </div>
                    </div>
                </div>
            `;

            // Store data for raw data inspector
            this._rawData = { job, rules };

            // Bind action buttons
            this.bindDetailActions(job);

            // Load first page of URLs (non-blocking)
            this.loadUrls(job.id, 0);

            // Initialize sample analyzer
            if (typeof SampleAnalyzer !== 'undefined') {
                SampleAnalyzer.bindEvents();
            }

            // Initialize activity log
            if (typeof ActivityLog !== 'undefined') {
                ActivityLog.render('activity-log-container');
                // Start polling if job is running
                if (job.status === 'running') {
                    ActivityLog.startPolling(job.id);
                }
            }

        } catch (error) {
            console.error('Failed to load job details:', error);
            this.els.jobDetail.innerHTML = `
                <div class="detail-placeholder">
                    <p>Failed to load job details</p>
                </div>
            `;
        }
    },

    /**
     * Update just the progress stats without re-rendering everything.
     * This prevents scroll position reset during polling.
     */
    updateProgressStats(job) {
        const percent = job.progress_total > 0
            ? Math.round((job.progress_current / job.progress_total) * 100)
            : 0;

        // Update stat cards if they exist
        const statCards = this.els.jobDetail.querySelectorAll('.stat-card');
        if (statCards.length >= 4) {
            statCards[0].querySelector('.stat-value').textContent = `${percent}%`;
            statCards[1].querySelector('.stat-value').textContent = job.progress_total;
            statCards[2].querySelector('.stat-value').textContent = job.success_count;
            statCards[3].querySelector('.stat-value').textContent = job.failure_count;
        }

        // Update job card in list
        const card = this.els.jobsList.querySelector(`[data-job-id="${job.id}"]`);
        if (card) {
            const progressFill = card.querySelector('.progress-bar-fill');
            if (progressFill) {
                progressFill.style.width = `${percent}%`;
            }
            const meta = card.querySelector('.job-card-meta');
            if (meta) {
                meta.innerHTML = `
                    <span>${job.progress_current}/${job.progress_total} URLs</span>
                    <span>${job.success_count} success, ${job.failure_count} failed</span>
                `;
            }
            const status = card.querySelector('.job-status');
            if (status && status.textContent !== job.status) {
                status.className = `job-status ${job.status}`;
                status.textContent = job.status;
            }
        }
    },

    renderJobActions(job) {
        const buttons = [];

        if (job.status === 'pending' || job.status === 'paused') {
            buttons.push(`<button class="btn btn-primary" data-action="start">▶ Start</button>`);
        }

        if (job.status === 'running') {
            buttons.push(`<button class="btn btn-secondary" data-action="pause">⏸ Pause</button>`);
            buttons.push(`<button class="btn btn-danger" data-action="stop">⏹ Stop</button>`);
        }

        if (job.status === 'completed' || job.status === 'failed') {
            buttons.push(`<button class="btn btn-secondary" data-action="restart">↻ Restart</button>`);
        }

        buttons.push(`<button class="btn btn-ghost" data-action="delete">Delete</button>`);

        return buttons.join('');
    },

    bindDetailActions(job) {
        const detail = this.els.jobDetail;

        // Job action buttons
        detail.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const action = btn.dataset.action;
                await this.handleJobAction(job.id, action);
            });
        });

        // Add rule button
        const btnAddRule = detail.querySelector('#btn-add-rule');
        if (btnAddRule) {
            btnAddRule.addEventListener('click', () => this.showAddRuleModal());
        }

        // Delete rule buttons
        detail.querySelectorAll('.rule-delete').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await this.deleteRule(job.id, btn.dataset.ruleId);
            });
        });

        // URL pagination buttons
        const btnUrlsPrev = detail.querySelector('#btn-urls-prev');
        const btnUrlsNext = detail.querySelector('#btn-urls-next');

        if (btnUrlsPrev) {
            btnUrlsPrev.addEventListener('click', () => {
                const newOffset = Math.max(0, (this._urlPagination?.offset || 0) - 50);
                this.loadUrls(job.id, newOffset);
            });
        }
        if (btnUrlsNext) {
            btnUrlsNext.addEventListener('click', () => {
                const newOffset = (this._urlPagination?.offset || 0) + 50;
                this.loadUrls(job.id, newOffset);
            });
        }

        // Raw data toggle
        const rawDataToggle = detail.querySelector('#raw-data-toggle');
        const rawDataContent = detail.querySelector('#raw-data-content');
        const toggleIcon = detail.querySelector('.raw-data-toggle-icon');

        if (rawDataToggle && rawDataContent) {
            rawDataToggle.addEventListener('click', () => {
                const isHidden = rawDataContent.style.display === 'none';
                rawDataContent.style.display = isHidden ? 'block' : 'none';
                toggleIcon.textContent = isHidden ? '−' : '+';
            });
        }

        // Raw data tabs
        detail.querySelectorAll('.raw-data-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                detail.querySelectorAll('.raw-data-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.showRawDataTab(tab.dataset.tab, job.id);
            });
        });
    },

    async loadUrls(jobId, offset = 0) {
        const preview = document.getElementById('urls-preview');
        if (!preview) return;

        try {
            const result = await API.listUrls(jobId, { limit: 50, offset });
            const urls = result.urls || [];
            const total = result.total || 0;

            // Update pagination state
            this._urlPagination = { offset, limit: 50, total, loaded: urls };

            // Render URLs
            if (urls.length === 0) {
                preview.innerHTML = `<div style="padding: var(--spacing-md); color: var(--muted);">No URLs added yet</div>`;
            } else {
                preview.innerHTML = urls.map(url => `
                    <div class="url-item ${url.status}">
                        <span class="url-status-dot ${url.status}"></span>
                        <span class="url-text">${this.escapeHtml(url.url)}</span>
                    </div>
                `).join('');
            }

            // Update pagination info
            const pageInfo = document.getElementById('urls-page-info');
            const btnPrev = document.getElementById('btn-urls-prev');
            const btnNext = document.getElementById('btn-urls-next');

            if (pageInfo) {
                const start = offset + 1;
                const end = Math.min(offset + urls.length, total);
                pageInfo.textContent = `${start}-${end} of ${total}`;
            }
            if (btnPrev) {
                btnPrev.disabled = offset === 0;
            }
            if (btnNext) {
                btnNext.disabled = offset + 50 >= total;
            }
        } catch (error) {
            console.error('Failed to load URLs:', error);
            preview.innerHTML = `<div style="padding: var(--spacing-md); color: var(--signal);">Failed to load URLs</div>`;
        }
    },

    async showRawDataTab(tabName, jobId) {
        const panel = document.getElementById('raw-data-panel');
        if (!panel) return;

        panel.innerHTML = '<div class="raw-data-loading">Loading...</div>';

        try {
            let data;
            switch (tabName) {
                case 'job':
                    data = this._rawData?.job || {};
                    break;
                case 'urls':
                    // Fetch first 100 URLs for raw data view
                    const urlResult = await API.listUrls(jobId, { limit: 100, offset: 0 });
                    data = {
                        urls: urlResult.urls || [],
                        total: urlResult.total,
                        showing: `First ${Math.min(100, urlResult.total)} of ${urlResult.total}`,
                    };
                    break;
                case 'results':
                    const results = await API.listResults(jobId, 100, 0);
                    data = results.results || [];
                    break;
                default:
                    data = {};
            }

            panel.innerHTML = `<pre class="raw-data-json">${JSON.stringify(data, null, 2)}</pre>`;
        } catch (error) {
            panel.innerHTML = `<div class="raw-data-error">Error loading data: ${error.message}</div>`;
        }
    },

    async handleJobAction(jobId, action) {
        try {
            let result;
            switch (action) {
                case 'start':
                    result = await API.startJob(jobId);
                    // Start activity log polling
                    if (typeof ActivityLog !== 'undefined') {
                        ActivityLog.startPolling(jobId);
                    }
                    break;
                case 'pause':
                    result = await API.pauseJob(jobId);
                    // Stop activity log polling
                    if (typeof ActivityLog !== 'undefined') {
                        ActivityLog.stopPolling();
                    }
                    break;
                case 'stop':
                    result = await API.stopJob(jobId);
                    // Stop activity log polling
                    if (typeof ActivityLog !== 'undefined') {
                        ActivityLog.stopPolling();
                    }
                    break;
                case 'restart':
                    // Reset and start
                    result = await API.startJob(jobId);
                    // Start activity log polling
                    if (typeof ActivityLog !== 'undefined') {
                        ActivityLog.startPolling(jobId);
                    }
                    break;
                case 'delete':
                    if (confirm('Delete this job and all its data?')) {
                        await API.deleteJob(jobId);
                        State.removeJob(jobId);
                        // Stop activity log polling
                        if (typeof ActivityLog !== 'undefined') {
                            ActivityLog.stopPolling();
                        }
                        return;
                    }
                    return;
            }

            if (result && result.job) {
                State.updateJob(jobId, result.job);
                this.renderJobDetail();
            }
        } catch (error) {
            console.error(`Failed to ${action} job:`, error);
            alert(`Failed to ${action} job: ${error.message}`);
        }
    },

    showNewJobModal() {
        document.getElementById('job-name').value = '';
        document.getElementById('job-mode').value = 'list';
        document.getElementById('job-urls').value = '';

        // Reset cascade settings
        if (typeof CascadeSettings !== 'undefined') {
            CascadeSettings.reset();
        }

        this.els.modalNewJob.classList.add('active');
    },

    showAddRuleModal() {
        document.getElementById('rule-name').value = '';
        document.getElementById('rule-type').value = 'css';
        document.getElementById('rule-selector').value = '';
        document.getElementById('rule-attribute').value = '';
        document.getElementById('rule-required').checked = false;
        document.getElementById('rule-list').checked = false;
        this.els.modalAddRule.classList.add('active');
    },

    closeModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
    },

    async createJob() {
        const name = document.getElementById('job-name').value.trim() || 'Untitled Job';
        const mode = document.getElementById('job-mode').value;
        const urlsText = document.getElementById('job-urls').value.trim();

        // Get cascade configuration
        let cascadeConfig = null;
        if (typeof CascadeSettings !== 'undefined') {
            cascadeConfig = CascadeSettings.getConfig();
        }

        try {
            // Create job with cascade settings
            const jobData = { name, mode };
            if (cascadeConfig) {
                jobData.settings = { cascade: cascadeConfig };
            }
            const result = await API.createJob(jobData);
            const job = result.job;

            // Add URLs if provided
            if (urlsText) {
                const urls = urlsText.split('\n').map(u => u.trim()).filter(u => u);
                if (urls.length > 0) {
                    await API.addUrls(job.id, urls);
                }
            }

            // Reload jobs
            await this.loadJobs();
            State.set('selectedJobId', job.id);

            this.closeModals();
        } catch (error) {
            console.error('Failed to create job:', error);
            alert(`Failed to create job: ${error.message}`);
        }
    },

    async saveRule() {
        const jobId = State.get('selectedJobId');
        if (!jobId) return;

        const rule = {
            name: document.getElementById('rule-name').value.trim(),
            selector_type: document.getElementById('rule-type').value,
            selector_value: document.getElementById('rule-selector').value.trim(),
            attribute: document.getElementById('rule-attribute').value.trim() || null,
            is_required: document.getElementById('rule-required').checked,
            is_list: document.getElementById('rule-list').checked,
        };

        if (!rule.name || !rule.selector_value) {
            alert('Please provide a field name and selector');
            return;
        }

        try {
            await API.addRule(jobId, rule);
            this.closeModals();
            this.renderJobDetail();
        } catch (error) {
            console.error('Failed to add rule:', error);
            alert(`Failed to add rule: ${error.message}`);
        }
    },

    async deleteRule(jobId, ruleId) {
        if (!confirm('Delete this rule?')) return;

        try {
            await API.deleteRule(jobId, ruleId);
            this.renderJobDetail();
        } catch (error) {
            console.error('Failed to delete rule:', error);
            alert(`Failed to delete rule: ${error.message}`);
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};

// Export
window.JobManager = JobManager;
