/**
 * Sample Analyzer Component
 * Upload HTML samples to auto-detect extraction rules
 */
const SampleAnalyzer = {
    files: [],
    suggestions: [],
    isAnalyzing: false,

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
        if (btn) {
            btn.disabled = this.files.length === 0 || this.isAnalyzing;
            btn.textContent = this.isAnalyzing
                ? 'Analyzing...'
                : `Analyze ${this.files.length} sample${this.files.length !== 1 ? 's' : ''}`;
        }
    },

    /**
     * Send files to backend for analysis
     */
    async analyzeSamples() {
        if (this.files.length === 0 || this.isAnalyzing) return;

        this.isAnalyzing = true;
        this.updateAnalyzeButton();

        try {
            const formData = new FormData();
            this.files.forEach(f => formData.append('samples', f));

            const response = await fetch('/api/scraping/analyze-html', {
                method: 'POST',
                body: formData,
            });

            // Check if response is OK
            if (!response.ok) {
                const text = await response.text();
                console.error('Server error:', response.status, text.substring(0, 500));
                throw new Error(`Server error ${response.status}: ${text.substring(0, 100)}`);
            }

            // Check content type
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Non-JSON response:', contentType, text.substring(0, 500));
                throw new Error('Server returned invalid response. Check console for details.');
            }

            const result = await response.json();

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
     * Clear uploaded files
     */
    clearFiles() {
        this.files = [];
        this.suggestions = [];
        const fileInput = document.getElementById('sample-files');
        if (fileInput) fileInput.value = '';
        this.renderFileList();
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
