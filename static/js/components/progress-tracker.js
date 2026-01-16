/**
 * Progress Tracker Component
 * Tracks job progress with ETA calculations and detailed status
 */
const ProgressTracker = {
    // Track timing data per job
    jobTimings: new Map(),

    // Configuration
    WINDOW_SIZE: 10, // Number of recent timings to average for ETA

    /**
     * Initialize tracking for a job
     */
    initJob(jobId, totalUrls) {
        this.jobTimings.set(jobId, {
            startTime: Date.now(),
            totalUrls,
            processedUrls: 0,
            successCount: 0,
            failureCount: 0,
            recentTimings: [], // Sliding window of recent URL processing times
            lastUpdateTime: Date.now(),
            currentUrl: null,
            currentUrlStartTime: null,
            averageTimeMs: 0,
        });
    },

    /**
     * Record when a URL starts processing
     */
    urlStarted(jobId, url) {
        const timing = this.jobTimings.get(jobId);
        if (!timing) return;

        timing.currentUrl = url;
        timing.currentUrlStartTime = Date.now();
    },

    /**
     * Record URL completion and update timing stats
     */
    urlCompleted(jobId, success, processingTimeMs = null) {
        const timing = this.jobTimings.get(jobId);
        if (!timing) return;

        timing.processedUrls++;
        if (success) {
            timing.successCount++;
        } else {
            timing.failureCount++;
        }

        // Calculate processing time if not provided
        const elapsed = processingTimeMs || (timing.currentUrlStartTime
            ? Date.now() - timing.currentUrlStartTime
            : 2000);

        // Update sliding window
        timing.recentTimings.push(elapsed);
        if (timing.recentTimings.length > this.WINDOW_SIZE) {
            timing.recentTimings.shift();
        }

        // Calculate new average
        timing.averageTimeMs = timing.recentTimings.reduce((a, b) => a + b, 0) / timing.recentTimings.length;

        timing.lastUpdateTime = Date.now();
        timing.currentUrl = null;
        timing.currentUrlStartTime = null;
    },

    /**
     * Get progress data for a job
     */
    getProgress(jobId) {
        const timing = this.jobTimings.get(jobId);
        if (!timing) {
            return null;
        }

        const remaining = timing.totalUrls - timing.processedUrls;
        const etaMs = remaining * timing.averageTimeMs;
        const elapsedMs = Date.now() - timing.startTime;
        const percent = timing.totalUrls > 0
            ? Math.round((timing.processedUrls / timing.totalUrls) * 100)
            : 0;

        // Calculate speed (URLs per minute)
        const speedPerMin = elapsedMs > 0
            ? Math.round((timing.processedUrls / elapsedMs) * 60000 * 10) / 10
            : 0;

        return {
            current: timing.processedUrls,
            total: timing.totalUrls,
            remaining,
            percent,
            success: timing.successCount,
            failure: timing.failureCount,
            eta: this.formatDuration(etaMs),
            etaMs,
            elapsed: this.formatDuration(elapsedMs),
            elapsedMs,
            averageTimeMs: Math.round(timing.averageTimeMs),
            speedPerMin,
            currentUrl: timing.currentUrl,
            currentUrlElapsed: timing.currentUrlStartTime
                ? Date.now() - timing.currentUrlStartTime
                : 0,
        };
    },

    /**
     * Update progress from API response
     */
    updateFromApi(jobId, apiProgress) {
        let timing = this.jobTimings.get(jobId);

        if (!timing) {
            // Initialize if not exists
            this.initJob(jobId, apiProgress.total || 0);
            timing = this.jobTimings.get(jobId);
        }

        // Calculate implicit timing based on progress change
        const newProcessed = apiProgress.current || 0;
        const urlsProcessedSinceLastUpdate = newProcessed - timing.processedUrls;

        if (urlsProcessedSinceLastUpdate > 0) {
            const timeSinceLastUpdate = Date.now() - timing.lastUpdateTime;
            const avgTimePerUrl = timeSinceLastUpdate / urlsProcessedSinceLastUpdate;

            // Add to sliding window
            for (let i = 0; i < urlsProcessedSinceLastUpdate; i++) {
                timing.recentTimings.push(avgTimePerUrl);
                if (timing.recentTimings.length > this.WINDOW_SIZE) {
                    timing.recentTimings.shift();
                }
            }

            timing.averageTimeMs = timing.recentTimings.reduce((a, b) => a + b, 0) / timing.recentTimings.length;
        }

        timing.processedUrls = newProcessed;
        timing.totalUrls = apiProgress.total || timing.totalUrls;
        timing.successCount = apiProgress.success || 0;
        timing.failureCount = apiProgress.failure || 0;
        timing.lastUpdateTime = Date.now();

        return this.getProgress(jobId);
    },

    /**
     * Clear tracking for a job
     */
    clearJob(jobId) {
        this.jobTimings.delete(jobId);
    },

    /**
     * Format milliseconds to human-readable duration
     */
    formatDuration(ms) {
        if (!ms || ms < 0) return '--:--';

        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            const h = hours;
            const m = minutes % 60;
            const s = seconds % 60;
            return `${h}h ${m}m ${s}s`;
        } else if (minutes > 0) {
            const m = minutes;
            const s = seconds % 60;
            return `${m}m ${s}s`;
        } else {
            return `${seconds}s`;
        }
    },

    /**
     * Render progress detail panel
     */
    renderProgressDetail(jobId, container) {
        const progress = this.getProgress(jobId);

        if (!progress) {
            container.innerHTML = '';
            return;
        }

        const currentUrlDisplay = progress.currentUrl
            ? `<div class="progress-current-url">
                   <div class="spinner"></div>
                   <span class="url-text" title="${this.escapeHtml(progress.currentUrl)}">${this.escapeHtml(this.truncateUrl(progress.currentUrl, 60))}</span>
                   <span class="current-elapsed">${this.formatDuration(progress.currentUrlElapsed)}</span>
               </div>`
            : '';

        container.innerHTML = `
            <div class="job-progress-detail">
                ${currentUrlDisplay}
                <div class="progress-eta">
                    <div class="eta-label">
                        <span>⏱ ETA:</span>
                        <span class="eta-value">${progress.eta}</span>
                    </div>
                    <div class="progress-speed">
                        ${progress.speedPerMin} URLs/min
                    </div>
                </div>
                <div class="progress-stats-row">
                    <span class="stat-mini">
                        <span class="stat-label">Elapsed:</span>
                        <span class="stat-value">${progress.elapsed}</span>
                    </span>
                    <span class="stat-mini">
                        <span class="stat-label">Avg:</span>
                        <span class="stat-value">${this.formatDuration(progress.averageTimeMs)}/URL</span>
                    </span>
                    <span class="stat-mini">
                        <span class="stat-label">Remaining:</span>
                        <span class="stat-value">${progress.remaining} URLs</span>
                    </span>
                </div>
            </div>
        `;
    },

    /**
     * Truncate URL for display
     */
    truncateUrl(url, maxLength) {
        if (url.length <= maxLength) return url;

        // Try to keep the domain and end of path visible
        try {
            const urlObj = new URL(url);
            const domain = urlObj.hostname;
            const path = urlObj.pathname + urlObj.search;

            if (domain.length >= maxLength - 3) {
                return domain.substring(0, maxLength - 3) + '...';
            }

            const remainingLength = maxLength - domain.length - 6; // 6 for "..." and "/"
            if (path.length > remainingLength) {
                return domain + '/...' + path.slice(-remainingLength);
            }

            return url.substring(0, maxLength - 3) + '...';
        } catch {
            return url.substring(0, maxLength - 3) + '...';
        }
    },

    /**
     * Escape HTML characters
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};

// Export
window.ProgressTracker = ProgressTracker;
