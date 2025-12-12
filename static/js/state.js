/**
 * Simple state management for Scrapefruit
 */
const State = {
    // Current state
    data: {
        jobs: [],
        selectedJobId: null,
        currentView: 'jobs',
        settings: {},
    },

    // Subscribers
    subscribers: [],

    // Get state value
    get(key) {
        return this.data[key];
    },

    // Set state value and notify subscribers
    set(key, value) {
        this.data[key] = value;
        this.notify(key, value);
    },

    // Subscribe to state changes
    subscribe(callback) {
        this.subscribers.push(callback);
        return () => {
            this.subscribers = this.subscribers.filter(cb => cb !== callback);
        };
    },

    // Notify subscribers
    notify(key, value) {
        this.subscribers.forEach(cb => cb(key, value));
    },

    // Get selected job
    getSelectedJob() {
        const jobId = this.data.selectedJobId;
        if (!jobId) return null;
        return this.data.jobs.find(j => j.id === jobId);
    },

    // Update a job in the list
    updateJob(jobId, updates) {
        const jobs = this.data.jobs.map(job => {
            if (job.id === jobId) {
                return { ...job, ...updates };
            }
            return job;
        });
        this.set('jobs', jobs);
    },

    // Add a job to the list
    addJob(job) {
        const jobs = [job, ...this.data.jobs];
        this.set('jobs', jobs);
    },

    // Remove a job from the list
    removeJob(jobId) {
        const jobs = this.data.jobs.filter(j => j.id !== jobId);
        this.set('jobs', jobs);
        if (this.data.selectedJobId === jobId) {
            this.set('selectedJobId', null);
        }
    },
};

// Export for use
window.State = State;
