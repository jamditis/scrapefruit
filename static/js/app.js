/**
 * Scrapefruit Main Application
 */
const App = {
    // Polling interval for job progress
    pollInterval: null,
    POLL_RATE: 2000, // 2 seconds

    init() {
        this.setupNavigation();
        this.initComponents();
        this.loadSettings();
        this.startPolling();
    },

    setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        const views = document.querySelectorAll('.view');

        navItems.forEach(item => {
            item.addEventListener('click', () => {
                const viewName = item.dataset.view;

                // Update nav active state
                navItems.forEach(n => n.classList.remove('active'));
                item.classList.add('active');

                // Update view visibility
                views.forEach(v => v.classList.remove('active'));
                document.getElementById(`view-${viewName}`).classList.add('active');

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
        this.initSettings();
    },

    initSettings() {
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
        const jobs = State.get('jobs');
        const runningJobs = jobs.filter(j => j.status === 'running');

        if (runningJobs.length === 0) {
            this.updateStatusIndicator(false);
            return;
        }

        this.updateStatusIndicator(true);

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
            } catch (error) {
                console.error(`Failed to poll job ${job.id}:`, error);
            }
        }
    },

    updateStatusIndicator(isRunning) {
        const indicator = document.getElementById('status-indicator');
        const text = indicator.querySelector('.status-text');

        if (isRunning) {
            indicator.classList.add('running');
            text.textContent = 'Scraping...';
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
