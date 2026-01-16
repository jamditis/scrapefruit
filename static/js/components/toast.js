/**
 * Toast Notification System
 * Provides non-intrusive feedback for job events and errors
 */
const Toast = {
    container: null,
    queue: [],
    maxVisible: 5,
    defaultDuration: 4000,

    // Duration by type (ms)
    durations: {
        success: 3000,
        error: 6000,
        warning: 5000,
        info: 4000,
    },

    /**
     * Initialize the toast container
     */
    init() {
        if (this.container) return;

        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.setAttribute('aria-live', 'polite');
        this.container.setAttribute('aria-label', 'Notifications');
        document.body.appendChild(this.container);
    },

    /**
     * Show a toast notification
     * @param {string} message - The message to display
     * @param {string} type - Type: success, error, warning, info
     * @param {object} options - Optional settings
     */
    show(message, type = 'info', options = {}) {
        this.init();

        const {
            duration = this.durations[type] || this.defaultDuration,
            title = null,
            action = null, // { label: 'Retry', onClick: () => {} }
            dismissible = true,
            progress = null, // { current: 5, total: 10 }
            url = null, // URL being processed
        } = options;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'alert');

        // Build toast content
        let html = `
            <div class="toast-icon">${this.getIcon(type)}</div>
            <div class="toast-content">
        `;

        if (title) {
            html += `<div class="toast-title">${this.escapeHtml(title)}</div>`;
        }

        html += `<div class="toast-message">${this.escapeHtml(message)}</div>`;

        if (url) {
            const shortUrl = url.length > 50 ? url.substring(0, 47) + '...' : url;
            html += `<div class="toast-url" title="${this.escapeHtml(url)}">${this.escapeHtml(shortUrl)}</div>`;
        }

        if (progress) {
            const percent = Math.round((progress.current / progress.total) * 100);
            html += `
                <div class="toast-progress-info">
                    <span>${progress.current}/${progress.total}</span>
                    <span>${percent}%</span>
                </div>
                <div class="toast-progress-bar">
                    <div class="toast-progress-fill" style="width: ${percent}%"></div>
                </div>
            `;
        }

        html += `</div>`;

        if (action) {
            html += `<button class="toast-action">${this.escapeHtml(action.label)}</button>`;
        }

        if (dismissible) {
            html += `<button class="toast-dismiss" aria-label="Dismiss">×</button>`;
        }

        toast.innerHTML = html;

        // Bind events
        if (dismissible) {
            toast.querySelector('.toast-dismiss').addEventListener('click', () => {
                this.dismiss(toast);
            });
        }

        if (action && action.onClick) {
            toast.querySelector('.toast-action').addEventListener('click', () => {
                action.onClick();
                this.dismiss(toast);
            });
        }

        // Add to container
        this.container.appendChild(toast);

        // Enforce max visible
        this.enforceMaxVisible();

        // Trigger entrance animation
        requestAnimationFrame(() => {
            toast.classList.add('toast-visible');
        });

        // Auto-dismiss
        if (duration > 0) {
            toast.timeoutId = setTimeout(() => {
                this.dismiss(toast);
            }, duration);
        }

        return toast;
    },

    /**
     * Dismiss a toast
     */
    dismiss(toast) {
        if (!toast || toast.classList.contains('toast-dismissing')) return;

        if (toast.timeoutId) {
            clearTimeout(toast.timeoutId);
        }

        toast.classList.add('toast-dismissing');
        toast.classList.remove('toast-visible');

        // Remove after animation
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    },

    /**
     * Dismiss all toasts
     */
    dismissAll() {
        if (!this.container) return;
        const toasts = this.container.querySelectorAll('.toast');
        toasts.forEach(toast => this.dismiss(toast));
    },

    /**
     * Enforce maximum visible toasts
     */
    enforceMaxVisible() {
        if (!this.container) return;
        const toasts = this.container.querySelectorAll('.toast:not(.toast-dismissing)');
        const excess = toasts.length - this.maxVisible;

        if (excess > 0) {
            for (let i = 0; i < excess; i++) {
                this.dismiss(toasts[i]);
            }
        }
    },

    /**
     * Get icon for toast type
     */
    getIcon(type) {
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ',
        };
        return icons[type] || icons.info;
    },

    /**
     * Escape HTML characters
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // Convenience methods
    success(message, options = {}) {
        return this.show(message, 'success', options);
    },

    error(message, options = {}) {
        return this.show(message, 'error', options);
    },

    warning(message, options = {}) {
        return this.show(message, 'warning', options);
    },

    info(message, options = {}) {
        return this.show(message, 'info', options);
    },

    /**
     * Show a job-related notification
     */
    jobEvent(event, data = {}) {
        const events = {
            'job_started': {
                type: 'info',
                title: 'Job started',
                message: `Processing ${data.total || 0} URLs`,
            },
            'job_completed': {
                type: 'success',
                title: 'Job completed',
                message: `${data.success || 0} successful, ${data.failed || 0} failed`,
            },
            'job_failed': {
                type: 'error',
                title: 'Job failed',
                message: data.error || 'Unknown error',
            },
            'job_paused': {
                type: 'warning',
                title: 'Job paused',
                message: `${data.current || 0}/${data.total || 0} URLs processed`,
            },
            'url_success': {
                type: 'success',
                message: `Scraped successfully via ${data.method || 'http'}`,
                url: data.url,
            },
            'url_failed': {
                type: 'error',
                message: data.error || 'Scrape failed',
                url: data.url,
            },
        };

        const config = events[event];
        if (!config) return;

        return this.show(config.message, config.type, {
            title: config.title,
            url: config.url,
            progress: data.progress,
        });
    },
};

// Export
window.Toast = Toast;
