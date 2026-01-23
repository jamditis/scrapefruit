/**
 * Scrapefruit Main Application
 */
const App = {
    // Polling interval for job progress
    pollInterval: null,
    POLL_RATE: 2000, // 2 seconds
    isPolling: false, // Guard against concurrent polling

    init() {
        this.loadTheme();
        this.setupNavigation();
        this.initComponents();
        this.loadSettings();
        this.startPolling();
    },

    // Theme management
    loadTheme() {
        const savedTheme = localStorage.getItem('scrapefruit-theme') || 'rose';
        this.applyTheme(savedTheme);
    },

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        // Sync both theme selectors
        ['setting-theme', 'sidebar-theme'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = theme;
        });
    },

    initThemeSelector() {
        // Initialize both sidebar and settings theme selectors
        const themeSelects = document.querySelectorAll('#setting-theme, #sidebar-theme');
        const savedTheme = localStorage.getItem('scrapefruit-theme') || 'rose';

        themeSelects.forEach(themeSelect => {
            if (themeSelect) {
                themeSelect.value = savedTheme;

                // Listen for changes
                themeSelect.addEventListener('change', (e) => {
                    const theme = e.target.value;
                    this.applyTheme(theme);
                    localStorage.setItem('scrapefruit-theme', theme);
                    // Sync both selectors
                    themeSelects.forEach(s => { if (s) s.value = theme; });
                });
            }
        });
    },

    setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item[data-view]');
        const views = document.querySelectorAll('.view');

        navItems.forEach(item => {
            item.addEventListener('click', () => {
                const viewName = item.dataset.view;
                const viewElement = document.getElementById(`view-${viewName}`);

                // Skip if view doesn't exist
                if (!viewElement) {
                    console.warn(`View not found: view-${viewName}`);
                    return;
                }

                // Update nav active state
                navItems.forEach(n => n.classList.remove('active'));
                item.classList.add('active');

                // Update view visibility
                views.forEach(v => v.classList.remove('active'));
                viewElement.classList.add('active');

                State.set('currentView', viewName);

                // Load view data
                if (viewName === 'results') {
                    ResultsView.updateJobSelect();
                }
            });
        });
    },

    initComponents() {
        JobManager.init();
        RulesEditor.init();
        ResultsView.init();
        SampleAnalyzer.init();
        DataView.init();
        this.initSettings();
    },

    initSettings() {
        // Theme selector
        this.initThemeSelector();

        // Save settings button
        document.getElementById('btn-save-settings').addEventListener('click', async () => {
            await this.saveSettings();
        });

        // Reset settings button
        document.getElementById('btn-reset-settings').addEventListener('click', async () => {
            if (confirm('Reset all settings to defaults?')) {
                await this.resetSettings();
            }
        });
    },

    async loadSettings() {
        try {
            const result = await API.getSettings();
            const settings = result.settings || {};

            // Populate form fields
            document.getElementById('setting-timeout').value = settings['scraping.timeout'] || '30000';
            document.getElementById('setting-retries').value = settings['scraping.retry_count'] || '3';
            document.getElementById('setting-delay-min').value = settings['scraping.delay_min'] || '1000';
            document.getElementById('setting-delay-max').value = settings['scraping.delay_max'] || '3000';
            document.getElementById('setting-stealth').checked = settings['scraping.use_stealth'] === 'true';
            document.getElementById('setting-rotate-ua').checked = settings['scraping.rotate_user_agent'] === 'true';

            State.set('settings', settings);
        } catch (error) {
            console.error('Failed to load settings:', error);
        }
    },

    async saveSettings() {
        const settings = {
            'scraping.timeout': document.getElementById('setting-timeout').value,
            'scraping.retry_count': document.getElementById('setting-retries').value,
            'scraping.delay_min': document.getElementById('setting-delay-min').value,
            'scraping.delay_max': document.getElementById('setting-delay-max').value,
            'scraping.use_stealth': document.getElementById('setting-stealth').checked ? 'true' : 'false',
            'scraping.rotate_user_agent': document.getElementById('setting-rotate-ua').checked ? 'true' : 'false',
        };

        try {
            await API.updateSettings(settings);
            State.set('settings', settings);
            alert('Settings saved');
        } catch (error) {
            console.error('Failed to save settings:', error);
            alert(`Failed to save settings: ${error.message}`);
        }
    },

    async resetSettings() {
        try {
            await API.resetSettings();
            await this.loadSettings();
            alert('Settings reset to defaults');
        } catch (error) {
            console.error('Failed to reset settings:', error);
            alert(`Failed to reset settings: ${error.message}`);
        }
    },

    // Poll for job progress updates
    startPolling() {
        this.pollInterval = setInterval(() => this.pollJobs(), this.POLL_RATE);
    },

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },

    async pollJobs() {
        // Guard against concurrent polling
        if (this.isPolling) return;
        this.isPolling = true;

        try {
            const jobs = State.get('jobs');
            const runningJobs = jobs.filter(j => j.status === 'running');

            if (runningJobs.length === 0) {
                this.updateStatusIndicator(false, null);
                return;
            }

            // Update each running job
            for (const job of runningJobs) {
                try {
                    const progress = await API.getJobProgress(job.id);
                    const wasRunning = job.status === 'running';
                    const isNowDone = progress.status !== 'running';

                    State.updateJob(job.id, {
                        status: progress.status,
                        progress_current: progress.current,
                        progress_total: progress.total,
                        success_count: progress.success,
                        failure_count: progress.failure,
                    });

                    // Update status indicator with progress
                    this.updateStatusIndicator(true, {
                        current: progress.current,
                        total: progress.total,
                        jobName: job.name,
                    });

                    // Update stats in place (doesn't reset scroll)
                    const selectedId = State.get('selectedJobId');
                    if (selectedId === job.id) {
                        const updatedJob = State.get('jobs').find(j => j.id === job.id);
                        if (updatedJob) {
                            JobManager.updateProgressStats(updatedJob);
                        }

                        // Only do full re-render if job just completed
                        if (wasRunning && isNowDone) {
                            JobManager.renderJobDetail();
                        }
                    }

                    // Show toast notification when job completes
                    if (wasRunning && isNowDone && typeof Toast !== 'undefined') {
                        if (progress.status === 'completed') {
                            Toast.jobEvent('job_completed', {
                                success: progress.success,
                                failed: progress.failure,
                            });
                        } else if (progress.status === 'failed') {
                            Toast.jobEvent('job_failed', {
                                error: 'Job failed to complete',
                            });
                        }

                        // Clean up progress tracker
                        if (typeof ProgressTracker !== 'undefined') {
                            ProgressTracker.clearJob(job.id);
                        }
                    }
                } catch (error) {
                    // Errors handled by API layer with backoff, just skip this poll
                }
            }
        } finally {
            this.isPolling = false;
        }
    },

    updateStatusIndicator(isRunning, progress = null) {
        const indicator = document.getElementById('status-indicator');
        const text = indicator.querySelector('.status-text');

        if (isRunning) {
            indicator.classList.add('running');
            if (progress && progress.total > 0) {
                const percent = Math.round((progress.current / progress.total) * 100);
                text.textContent = `${progress.current}/${progress.total} (${percent}%)`;
            } else {
                text.textContent = 'Scraping...';
            }
        } else {
            indicator.classList.remove('running');
            text.textContent = 'Ready';
        }
    },
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Export
window.App = App;
