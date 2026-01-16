/**
 * Welcome Overlay Component
 * Shows tips and instructions on first visit, can be recalled from sidebar
 */

const WelcomeOverlay = {
    STORAGE_KEY: 'scrapefruit_welcome_dismissed',

    init() {
        this.overlay = document.getElementById('welcome-overlay');
        this.bindEvents();

        // Show on first visit
        if (!this.hasBeenDismissed()) {
            this.show();
        }
    },

    bindEvents() {
        // Close buttons
        const closeBtn = this.overlay.querySelector('.welcome-close');
        const dismissBtn = document.getElementById('btn-dismiss-welcome');
        const helpBtn = document.getElementById('btn-show-help');

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hide());
        }
        if (dismissBtn) {
            dismissBtn.addEventListener('click', () => this.hide());
        }
        if (helpBtn) {
            helpBtn.addEventListener('click', () => this.show());
        }

        // Click outside to close
        this.overlay.querySelector('.welcome-backdrop').addEventListener('click', () => this.hide());

        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay.classList.contains('active')) {
                this.hide();
            }
        });

        // ? key to show help (when not in an input field)
        document.addEventListener('keydown', (e) => {
            if (e.key === '?' && !this.isInputFocused()) {
                e.preventDefault();
                this.show();
            }
        });
    },

    isInputFocused() {
        const active = document.activeElement;
        return active && (
            active.tagName === 'INPUT' ||
            active.tagName === 'TEXTAREA' ||
            active.tagName === 'SELECT' ||
            active.isContentEditable
        );
    },

    show() {
        this.overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    },

    hide() {
        this.overlay.classList.remove('active');
        document.body.style.overflow = '';
        localStorage.setItem(this.STORAGE_KEY, 'true');
    },

    hasBeenDismissed() {
        return localStorage.getItem(this.STORAGE_KEY) === 'true';
    },

    reset() {
        localStorage.removeItem(this.STORAGE_KEY);
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    WelcomeOverlay.init();
});
