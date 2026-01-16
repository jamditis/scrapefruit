/**
 * Cascade Settings Component
 * Manages the cascade scraping configuration UI
 */
const CascadeSettings = {
    // Default method order
    defaultOrder: ['http', 'playwright', 'puppeteer', 'agent_browser'],

    // Elements
    els: {},

    // Initialize
    init() {
        this.cacheElements();
        this.bindEvents();
        this.initDragAndDrop();
    },

    cacheElements() {
        this.els = {
            toggle: document.getElementById('cascade-toggle'),
            settings: document.getElementById('cascade-settings'),
            enabled: document.getElementById('cascade-enabled'),
            methods: document.getElementById('cascade-methods'),
        };
    },

    bindEvents() {
        // Toggle expand/collapse
        if (this.els.toggle) {
            this.els.toggle.addEventListener('click', () => {
                const isHidden = this.els.settings.style.display === 'none';
                this.els.settings.style.display = isHidden ? 'block' : 'none';
                this.els.toggle.querySelector('.toggle-icon').textContent = isHidden ? '−' : '+';
            });
        }
    },

    initDragAndDrop() {
        if (!this.els.methods) return;

        const methods = this.els.methods.querySelectorAll('.cascade-method');

        methods.forEach(method => {
            method.draggable = true;

            method.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', method.dataset.method);
                method.classList.add('dragging');
            });

            method.addEventListener('dragend', () => {
                method.classList.remove('dragging');
            });

            method.addEventListener('dragover', (e) => {
                e.preventDefault();
                const dragging = this.els.methods.querySelector('.dragging');
                if (dragging && method !== dragging) {
                    const rect = method.getBoundingClientRect();
                    const midY = rect.top + rect.height / 2;
                    if (e.clientY < midY) {
                        this.els.methods.insertBefore(dragging, method);
                    } else {
                        this.els.methods.insertBefore(dragging, method.nextSibling);
                    }
                }
            });
        });
    },

    /**
     * Get current cascade configuration from UI
     * @returns {Object} Cascade config for job settings
     */
    getConfig() {
        if (!this.els.enabled) return null;

        const enabled = this.els.enabled.checked;

        // Get method order from current DOM order
        const methods = Array.from(this.els.methods.querySelectorAll('.cascade-method'));
        const order = methods
            .filter(m => m.querySelector('input[type="checkbox"]').checked)
            .map(m => m.dataset.method);

        return {
            enabled,
            order,
            fallback_on: {
                status_codes: [403, 429, 503],
                error_patterns: ['blocked', 'captcha', 'cloudflare', 'challenge'],
                poison_pills: ['anti_bot', 'rate_limited'],
                empty_content: true,
                javascript_required: true,
                min_content_length: 500,
            },
        };
    },

    /**
     * Set cascade configuration in UI
     * @param {Object} config - Cascade config from job settings
     */
    setConfig(config) {
        if (!config || !this.els.enabled) return;

        // Set enabled
        this.els.enabled.checked = config.enabled !== false;

        // Set method order and checkboxes
        const order = config.order || this.defaultOrder;
        const methodElements = {};

        // First, uncheck all and store references
        this.els.methods.querySelectorAll('.cascade-method').forEach(m => {
            methodElements[m.dataset.method] = m;
            m.querySelector('input[type="checkbox"]').checked = false;
        });

        // Reorder and check based on config
        order.forEach(method => {
            if (methodElements[method]) {
                methodElements[method].querySelector('input[type="checkbox"]').checked = true;
                this.els.methods.appendChild(methodElements[method]);
            }
        });

        // Append unchecked methods at the end
        this.defaultOrder.forEach(method => {
            if (!order.includes(method) && methodElements[method]) {
                this.els.methods.appendChild(methodElements[method]);
            }
        });
    },

    /**
     * Reset to default configuration
     */
    reset() {
        if (!this.els.enabled) return;

        this.els.enabled.checked = true;

        // Reset order
        this.defaultOrder.forEach(method => {
            const el = this.els.methods.querySelector(`[data-method="${method}"]`);
            if (el) {
                el.querySelector('input[type="checkbox"]').checked = method !== 'agent_browser';
                this.els.methods.appendChild(el);
            }
        });

        // Collapse section
        this.els.settings.style.display = 'none';
        this.els.toggle.querySelector('.toggle-icon').textContent = '+';
    },
};

// Export
window.CascadeSettings = CascadeSettings;
