/**
 * Sample Analyzer Component
 * Upload HTML samples to auto-detect extraction rules
 */
const SampleAnalyzer = {
    files: [],
    suggestions: [],
    htmlSamples: [], // HTML content fetched from URLs
    isAnalyzing: false,
    isFetching: false,

    init() {
        // Bind modal close handlers once
        const suggestionsModal = document.getElementById('modal-suggestions');
        if (suggestionsModal) {
            suggestionsModal.querySelector('.modal-close')?.addEventListener('click', () => this.closeModal());
            suggestionsModal.querySelector('.modal-cancel')?.addEventListener('click', () => this.closeModal());
            suggestionsModal.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeModal());
        }

        // Bind add selected rules button once
        const addSelectedBtn = document.getElementById('btn-add-selected-rules');
        if (addSelectedBtn) {
            addSelectedBtn.addEventListener('click', () => this.addSelectedRules());
        }
    },

    /**
     * Bind events for the upload zone (called from JobManager after render)
     */
    bindEvents() {
        const uploadZone = document.getElementById('sample-upload-zone');
        const fileInput = document.getElementById('sample-files');
        const analyzeBtn = document.getElementById('btn-analyze-samples');

        if (!uploadZone || !fileInput) return;

        // Click to browse
        uploadZone.addEventListener('click', () => fileInput.click());

        // File input change
        fileInput.addEventListener('change', (e) => {
            this.handleFiles(e.target.files);
        });

        // Drag and drop
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            this.handleFiles(e.dataTransfer.files);
        });

        // Analyze button
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => this.analyzeSamples());
        }

        // Fetch from URLs button
        const fetchBtn = document.getElementById('btn-fetch-samples');
        if (fetchBtn) {
            fetchBtn.addEventListener('click', () => this.fetchSamplesFromJobUrls());
        }
    },

    /**
     * Handle dropped/selected files
     */
    handleFiles(fileList) {
        const htmlFiles = Array.from(fileList).filter(f =>
            f.name.endsWith('.html') || f.name.endsWith('.htm')
        );

        if (htmlFiles.length === 0) {
            alert('Please select HTML files (.html or .htm)');
            return;
        }

        if (htmlFiles.length > 10) {
            alert('Maximum 10 files allowed');
            return;
        }

        this.files = htmlFiles;
        this.renderFileList();
        this.updateAnalyzeButton();
    },

    /**
     * Render the list of uploaded files
     */
    renderFileList() {
        const listEl = document.getElementById('upload-files-list');
        if (!listEl) return;

        if (this.files.length === 0) {
            listEl.innerHTML = '';
            return;
        }

        listEl.innerHTML = this.files.map((f, i) => `
            <div class="upload-file-item">
                <span class="file-name">${this.escapeHtml(f.name)}</span>
                <span class="file-size">${this.formatSize(f.size)}</span>
                <button class="file-remove" data-index="${i}">×</button>
            </div>
        `).join('');

        // Bind remove buttons
        listEl.querySelectorAll('.file-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const index = parseInt(btn.dataset.index);
                this.files.splice(index, 1);
                this.renderFileList();
                this.updateAnalyzeButton();
            });
        });
    },

    /**
     * Update analyze button state
     */
    updateAnalyzeButton() {
        const btn = document.getElementById('btn-analyze-samples');
        const totalSamples = this.files.length + this.htmlSamples.length;
        if (btn) {
            btn.disabled = totalSamples === 0 || this.isAnalyzing || this.isFetching;
            btn.textContent = this.isAnalyzing
                ? 'Analyzing...'
                : `Analyze ${totalSamples} sample${totalSamples !== 1 ? 's' : ''}`;
        }
    },

    /**
     * Update fetch button state
     */
    updateFetchButton() {
        const btn = document.getElementById('btn-fetch-samples');
        if (btn) {
            btn.disabled = this.isFetching || this.isAnalyzing;
            btn.textContent = this.isFetching ? 'Fetching...' : 'Fetch from URLs';
        }
    },

    /**
     * Fetch HTML samples from job URLs
     */
    async fetchSamplesFromJobUrls() {
        const jobId = State.get('selectedJobId');
        if (!jobId) {
            alert('No job selected');
            return;
        }

        this.isFetching = true;
        this.updateFetchButton();
        this.updateAnalyzeButton();

        try {
            // Get first 10 URLs from the job
            const urlResult = await API.listUrls(jobId, { limit: 10, offset: 0 });
            const urls = (urlResult.urls || []).map(u => u.url);

            if (urls.length === 0) {
                alert('No URLs in this job. Add some URLs first.');
                return;
            }

            // Fetch HTML from the URLs
            const result = await API.fetchSamplesFromUrls(urls);

            if (result.samples && result.samples.length > 0) {
                this.htmlSamples = result.samples;
                this.renderFetchedSamples();

                if (result.errors && result.errors.length > 0) {
                    console.warn('Some URLs failed to fetch:', result.errors);
                }
            } else {
                alert('Failed to fetch any HTML samples. Check console for errors.');
            }

        } catch (error) {
            console.error('Failed to fetch samples:', error);
            alert(`Failed to fetch samples: ${error.message}`);
        } finally {
            this.isFetching = false;
            this.updateFetchButton();
            this.updateAnalyzeButton();
        }
    },

    /**
     * Render fetched samples in the file list
     */
    renderFetchedSamples() {
        const listEl = document.getElementById('upload-files-list');
        if (!listEl) return;

        // Combine file items and fetched sample items
        let html = '';

        // File items
        this.files.forEach((f, i) => {
            html += `
                <div class="upload-file-item">
                    <span class="file-name">${this.escapeHtml(f.name)}</span>
                    <span class="file-size">${this.formatSize(f.size)}</span>
                    <button class="file-remove" data-type="file" data-index="${i}">×</button>
                </div>
            `;
        });

        // Fetched HTML samples
        this.htmlSamples.forEach((sample, i) => {
            const urlShort = sample.url.length > 40 ? sample.url.substring(0, 37) + '...' : sample.url;
            html += `
                <div class="upload-file-item fetched">
                    <span class="file-name" title="${this.escapeHtml(sample.url)}">🌐 ${this.escapeHtml(urlShort)}</span>
                    <span class="file-size">${this.formatSize(sample.size)}</span>
                    <button class="file-remove" data-type="fetched" data-index="${i}">×</button>
                </div>
            `;
        });

        listEl.innerHTML = html;

        // Bind remove buttons
        listEl.querySelectorAll('.file-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const type = btn.dataset.type;
                const index = parseInt(btn.dataset.index);

                if (type === 'file') {
                    this.files.splice(index, 1);
                } else {
                    this.htmlSamples.splice(index, 1);
                }

                this.renderFetchedSamples();
                this.updateAnalyzeButton();
            });
        });
    },

    /**
     * Send files to backend for analysis
     */
    async analyzeSamples() {
        const totalSamples = this.files.length + this.htmlSamples.length;
        if (totalSamples === 0 || this.isAnalyzing) return;

        this.isAnalyzing = true;
        this.updateAnalyzeButton();

        try {
            let result;

            // If we have fetched HTML samples, send them as JSON
            if (this.htmlSamples.length > 0) {
                // Read file contents and combine with fetched HTML
                const fileContents = await Promise.all(
                    this.files.map(f => f.text())
                );

                const allHtml = [
                    ...fileContents,
                    ...this.htmlSamples.map(s => s.html)
                ];

                const response = await fetch('/api/scraping/analyze-html', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ html_samples: allHtml }),
                });

                if (!response.ok) {
                    const text = await response.text();
                    console.error('Server error:', response.status, text.substring(0, 500));
                    throw new Error(`Server error ${response.status}: ${text.substring(0, 100)}`);
                }

                result = await response.json();
            } else {
                // Only files - use FormData
                const formData = new FormData();
                this.files.forEach(f => formData.append('samples', f));

                const response = await fetch('/api/scraping/analyze-html', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    const text = await response.text();
                    console.error('Server error:', response.status, text.substring(0, 500));
                    throw new Error(`Server error ${response.status}: ${text.substring(0, 100)}`);
                }

                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Non-JSON response:', contentType, text.substring(0, 500));
                    throw new Error('Server returned invalid response. Check console for details.');
                }

                result = await response.json();
            }

            if (!result.success) {
                throw new Error(result.error || 'Analysis failed');
            }

            this.suggestions = result.suggestions || [];

            if (this.suggestions.length === 0) {
                alert('No extraction patterns detected in the samples. Try different HTML files or add rules manually.');
            } else {
                this.showSuggestionsModal();
            }

        } catch (error) {
            console.error('Analysis failed:', error);
            alert(`Analysis failed: ${error.message}`);
        } finally {
            this.isAnalyzing = false;
            this.updateAnalyzeButton();
        }
    },

    /**
     * Show the suggestions modal
     */
    showSuggestionsModal() {
        const modal = document.getElementById('modal-suggestions');
        const listEl = document.getElementById('suggestions-list');

        if (!modal || !listEl) return;

        // Build index map for lookups
        this.suggestionMap = {};
        this.suggestions.forEach((s, idx) => {
            this.suggestionMap[idx] = s;
        });

        // Group suggestions by category
        const byCategory = {};
        this.suggestions.forEach((s, idx) => {
            const cat = s.category || 'general';
            if (!byCategory[cat]) byCategory[cat] = [];
            byCategory[cat].push({ suggestion: s, index: idx });
        });

        // Render suggestions grouped by category
        let html = '';
        const categoryLabels = {
            title: 'Titles',
            content: 'Content',
            attribution: 'Author & date',
            meta: 'Meta tags',
            media: 'Media',
            ecommerce: 'E-commerce',
            list: 'Lists',
            data: 'Data attributes',
            navigation: 'Navigation',
            general: 'General',
        };

        for (const [cat, items] of Object.entries(byCategory)) {
            html += `<div class="suggestion-category">
                <h4>${categoryLabels[cat] || cat}</h4>
                ${items.map(item => this.renderSuggestionItem(item.suggestion, item.index)).join('')}
            </div>`;
        }

        listEl.innerHTML = html;

        // Show modal
        modal.classList.add('active');
    },

    /**
     * Render a single suggestion item
     */
    renderSuggestionItem(suggestion, index) {
        const confidenceClass = suggestion.confidence >= 0.9 ? 'high'
            : suggestion.confidence >= 0.75 ? 'medium' : 'low';

        const preview = suggestion.preview
            ? this.escapeHtml(suggestion.preview.substring(0, 60)) + (suggestion.preview.length > 60 ? '...' : '')
            : '';

        return `
            <label class="suggestion-item" data-suggestion-index="${index}">
                <input type="checkbox" checked data-index="${index}">
                <div class="suggestion-info">
                    <div class="suggestion-header">
                        <span class="suggestion-name">${this.escapeHtml(suggestion.name)}</span>
                        <span class="suggestion-confidence ${confidenceClass}">${Math.round(suggestion.confidence * 100)}%</span>
                    </div>
                    <div class="suggestion-selector">${this.escapeHtml(suggestion.selector_value)}</div>
                    ${preview ? `<div class="suggestion-preview">"${preview}"</div>` : ''}
                    <div class="suggestion-badges">
                        ${suggestion.attribute ? `<span class="badge">@${suggestion.attribute}</span>` : ''}
                        ${suggestion.is_list ? '<span class="badge">list</span>' : ''}
                        ${suggestion.found_in_samples > 1 ? `<span class="badge">${suggestion.found_in_samples} samples</span>` : ''}
                    </div>
                </div>
            </label>
        `;
    },

    /**
     * Get selected suggestions from modal
     */
    getSelectedSuggestions() {
        const checkboxes = document.querySelectorAll('#suggestions-list input[type="checkbox"]:checked');
        return Array.from(checkboxes).map(cb => this.suggestionMap[cb.dataset.index]);
    },

    /**
     * Add selected rules to the current job
     */
    async addSelectedRules() {
        const selected = this.getSelectedSuggestions();

        if (selected.length === 0) {
            alert('Please select at least one rule to add');
            return;
        }

        const jobId = State.get('selectedJobId');
        if (!jobId) {
            alert('No job selected');
            return;
        }

        try {
            // Add each selected rule
            for (const suggestion of selected) {
                await API.addRule(jobId, {
                    name: suggestion.name,
                    selector_type: suggestion.selector_type,
                    selector_value: suggestion.selector_value,
                    attribute: suggestion.attribute || null,
                    is_required: false,
                    is_list: suggestion.is_list || false,
                });
            }

            // Close modal and refresh
            this.closeModal();
            this.clearFiles();
            JobManager.renderJobDetail();

        } catch (error) {
            console.error('Failed to add rules:', error);
            alert(`Failed to add rules: ${error.message}`);
        }
    },

    /**
     * Close the suggestions modal
     */
    closeModal() {
        const modal = document.getElementById('modal-suggestions');
        if (modal) {
            modal.classList.remove('active');
        }
    },

    /**
     * Clear uploaded files and fetched samples
     */
    clearFiles() {
        this.files = [];
        this.htmlSamples = [];
        this.suggestions = [];
        const fileInput = document.getElementById('sample-files');
        if (fileInput) fileInput.value = '';
        this.renderFetchedSamples();
        this.updateAnalyzeButton();
    },

    /**
     * Format file size
     */
    formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};

// Export
window.SampleAnalyzer = SampleAnalyzer;
