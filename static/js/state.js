/**
 * Enhanced state management for Scrapefruit.
 *
 * Features:
 * - Typed state with JSDoc annotations
 * - Schema validation on mutations
 * - Fine-grained event subscriptions
 * - Selectors for derived state
 * - Immutable updates
 *
 * @fileoverview Central state management with type safety.
 */

// =============================================================================
// State Manager
// =============================================================================

/**
 * @typedef {import('./types.js').Job} Job
 * @typedef {import('./types.js').StateData} StateData
 * @typedef {import('./types.js').StateKey} StateKey
 * @typedef {import('./types.js').JobStatus} JobStatus
 */

const State = {
    /**
     * Current application state.
     * @type {StateData}
     */
    data: {
        /** @type {Job[]} */
        jobs: [],
        /** @type {string|null} */
        selectedJobId: null,
        /** @type {string} */
        currentView: 'jobs',
        /** @type {Object} */
        settings: {},
    },

    /**
     * Event subscribers by key.
     * @type {Map<string, Set<Function>>}
     * @private
     */
    _subscribers: new Map(),

    /**
     * Global subscribers (receive all changes).
     * @type {Set<Function>}
     * @private
     */
    _globalSubscribers: new Set(),

    /**
     * Whether to validate state mutations.
     * @type {boolean}
     */
    validateOnMutation: true,

    // =========================================================================
    // Core State Methods
    // =========================================================================

    /**
     * Get a state value by key.
     * @template T
     * @param {StateKey} key - State key to retrieve
     * @returns {T} The state value
     */
    get(key) {
        return this.data[key];
    },

    /**
     * Set a state value and notify subscribers.
     * @param {StateKey} key - State key to update
     * @param {any} value - New value
     * @param {Object} [options] - Options
     * @param {boolean} [options.silent=false] - Skip notifications
     * @param {boolean} [options.validate=true] - Validate the value
     */
    set(key, value, options = {}) {
        const { silent = false, validate = this.validateOnMutation } = options;

        // Validate if enabled
        if (validate && key === 'jobs') {
            this._validateJobs(value);
        }

        // Create immutable copy for arrays/objects
        const newValue = Array.isArray(value)
            ? [...value]
            : (value && typeof value === 'object')
                ? { ...value }
                : value;

        this.data[key] = newValue;

        if (!silent) {
            this._notify(key, newValue);
        }
    },

    /**
     * Batch multiple state updates.
     * Only notifies once after all updates.
     * @param {Object.<StateKey, any>} updates - Key-value pairs to update
     */
    batch(updates) {
        const changedKeys = [];

        for (const [key, value] of Object.entries(updates)) {
            if (this.data[key] !== value) {
                this.data[key] = value;
                changedKeys.push(key);
            }
        }

        // Notify for each changed key
        for (const key of changedKeys) {
            this._notify(key, this.data[key]);
        }
    },

    // =========================================================================
    // Subscription Methods
    // =========================================================================

    /**
     * Subscribe to state changes.
     * @param {StateKey|StateKey[]|Function} keyOrCallback - Key(s) to watch, or callback for all
     * @param {Function} [callback] - Callback function (if key provided)
     * @returns {Function} Unsubscribe function
     */
    subscribe(keyOrCallback, callback) {
        // Global subscription (no key specified)
        if (typeof keyOrCallback === 'function') {
            this._globalSubscribers.add(keyOrCallback);
            return () => this._globalSubscribers.delete(keyOrCallback);
        }

        // Key-specific subscription
        const keys = Array.isArray(keyOrCallback) ? keyOrCallback : [keyOrCallback];
        const cb = callback;

        for (const key of keys) {
            if (!this._subscribers.has(key)) {
                this._subscribers.set(key, new Set());
            }
            this._subscribers.get(key).add(cb);
        }

        // Return unsubscribe function
        return () => {
            for (const key of keys) {
                const subs = this._subscribers.get(key);
                if (subs) {
                    subs.delete(cb);
                }
            }
        };
    },

    /**
     * Subscribe to a specific key (alias for subscribe with key).
     * @param {StateKey} key - State key to watch
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    on(key, callback) {
        return this.subscribe(key, callback);
    },

    /**
     * Notify subscribers of a state change.
     * @param {StateKey} key - Changed key
     * @param {any} value - New value
     * @private
     */
    _notify(key, value) {
        // Notify key-specific subscribers
        const keySubscribers = this._subscribers.get(key);
        if (keySubscribers) {
            for (const cb of keySubscribers) {
                try {
                    cb(value, key);
                } catch (err) {
                    console.error(`State subscriber error for '${key}':`, err);
                }
            }
        }

        // Notify global subscribers
        for (const cb of this._globalSubscribers) {
            try {
                cb(key, value);
            } catch (err) {
                console.error('Global state subscriber error:', err);
            }
        }
    },

    // =========================================================================
    // Job Selectors
    // =========================================================================

    /**
     * Get the currently selected job.
     * @returns {Job|null}
     */
    getSelectedJob() {
        const jobId = this.data.selectedJobId;
        if (!jobId) return null;
        return this.data.jobs.find(j => j.id === jobId) || null;
    },

    /**
     * Get a job by ID.
     * @param {string} jobId - Job ID to find
     * @returns {Job|null}
     */
    getJobById(jobId) {
        return this.data.jobs.find(j => j.id === jobId) || null;
    },

    /**
     * Get jobs filtered by status.
     * @param {JobStatus} status - Status to filter by
     * @returns {Job[]}
     */
    getJobsByStatus(status) {
        return this.data.jobs.filter(j => j.status === status);
    },

    /**
     * Get running jobs.
     * @returns {Job[]}
     */
    getRunningJobs() {
        return this.getJobsByStatus('running');
    },

    /**
     * Get pending jobs.
     * @returns {Job[]}
     */
    getPendingJobs() {
        return this.getJobsByStatus('pending');
    },

    /**
     * Check if any job is currently running.
     * @returns {boolean}
     */
    hasRunningJobs() {
        return this.data.jobs.some(j => j.status === 'running');
    },

    // =========================================================================
    // Job Mutations
    // =========================================================================

    /**
     * Update a job in the list.
     * @param {string} jobId - Job ID to update
     * @param {Partial<Job>} updates - Fields to update
     * @returns {Job|null} Updated job or null if not found
     */
    updateJob(jobId, updates) {
        let updatedJob = null;

        const jobs = this.data.jobs.map(job => {
            if (job.id === jobId) {
                updatedJob = { ...job, ...updates };
                return updatedJob;
            }
            return job;
        });

        if (updatedJob) {
            this.set('jobs', jobs);
        }

        return updatedJob;
    },

    /**
     * Add a job to the list.
     * @param {Job} job - Job to add
     */
    addJob(job) {
        if (this.validateOnMutation) {
            const validation = window.Types?.validateJob(job);
            if (validation && !validation.valid) {
                console.warn('Adding job with validation errors:', validation.errors);
            }
        }

        const jobs = [job, ...this.data.jobs];
        this.set('jobs', jobs);
    },

    /**
     * Remove a job from the list.
     * @param {string} jobId - Job ID to remove
     */
    removeJob(jobId) {
        const jobs = this.data.jobs.filter(j => j.id !== jobId);
        this.set('jobs', jobs);

        // Clear selection if removed job was selected
        if (this.data.selectedJobId === jobId) {
            this.set('selectedJobId', null);
        }
    },

    /**
     * Select a job by ID.
     * @param {string|null} jobId - Job ID to select, or null to clear
     */
    selectJob(jobId) {
        if (jobId !== null && !this.getJobById(jobId)) {
            console.warn(`Cannot select non-existent job: ${jobId}`);
            return;
        }
        this.set('selectedJobId', jobId);
    },

    // =========================================================================
    // Validation
    // =========================================================================

    /**
     * Validate jobs array.
     * @param {any[]} jobs - Jobs to validate
     * @private
     */
    _validateJobs(jobs) {
        if (!Array.isArray(jobs)) {
            console.error('State.jobs must be an array');
            return;
        }

        if (!window.Types?.validateJob) {
            return; // Types not loaded yet
        }

        for (let i = 0; i < jobs.length; i++) {
            const validation = window.Types.validateJob(jobs[i]);
            if (!validation.valid) {
                console.warn(`Job at index ${i} has validation errors:`, validation.errors);
            }
        }
    },

    // =========================================================================
    // Utility Methods
    // =========================================================================

    /**
     * Reset state to initial values.
     */
    reset() {
        this.data = {
            jobs: [],
            selectedJobId: null,
            currentView: 'jobs',
            settings: {},
        };
        this._notify('jobs', []);
        this._notify('selectedJobId', null);
        this._notify('currentView', 'jobs');
        this._notify('settings', {});
    },

    /**
     * Get a snapshot of current state (for debugging).
     * @returns {StateData}
     */
    getSnapshot() {
        return JSON.parse(JSON.stringify(this.data));
    },

    /**
     * Get subscriber counts (for debugging).
     * @returns {Object.<string, number>}
     */
    getSubscriberCounts() {
        const counts = { global: this._globalSubscribers.size };
        for (const [key, subs] of this._subscribers) {
            counts[key] = subs.size;
        }
        return counts;
    },
};

// =============================================================================
// Legacy Compatibility
// =============================================================================

// Keep old subscribe API working (receives key, value instead of value, key)
const originalSubscribe = State.subscribe.bind(State);
State.subscribe = function(keyOrCallback, callback) {
    // If called with just a function (legacy API), wrap it
    if (typeof keyOrCallback === 'function' && !callback) {
        const legacyCallback = keyOrCallback;
        return originalSubscribe((key, value) => legacyCallback(key, value));
    }
    return originalSubscribe(keyOrCallback, callback);
};

// Add legacy 'subscribers' array for any code checking it
Object.defineProperty(State, 'subscribers', {
    get() {
        // Return array of global subscribers for compatibility
        return Array.from(this._globalSubscribers);
    },
    set(value) {
        // Convert array to Set
        this._globalSubscribers = new Set(value);
    }
});

// =============================================================================
// Export
// =============================================================================

window.State = State;
