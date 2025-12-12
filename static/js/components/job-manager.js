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
            const urls = result.urls || [];
            const rules = result.rules || [];

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

                <div class="detail-section">
                    <h3>URLs (${urls.length})</h3>
                    <div class="urls-preview">
                        ${urls.slice(0, 20).map(url => `
                            <div class="url-item">
                                <span class="url-status-dot ${url.status}"></span>
                                <span>${this.escapeHtml(url.url)}</span>
                            </div>
                        `).join('')}
                        ${urls.length > 20 ? `<p style="color: var(--color-text-muted); margin-top: var(--spacing-sm)">... and ${urls.length - 20} more</p>` : ''}
                    </div>
                </div>

                <div class="detail-section">
                    <h3>Activity log</h3>
                    <div id="activity-log-container"></div>
                </div>
            `;

            // Bind action buttons
            this.bindDetailActions(job);

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

        try {
            // Create job
            const result = await API.createJob({ name, mode });
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
