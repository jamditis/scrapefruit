/**
 * Rules Editor Component
 */
const RulesEditor = {
    // Preview state
    previewUrl: null,
    previewHtml: null,

    init() {
        // Rules editor functionality is integrated into JobManager
        // This module can be expanded for visual selector in Phase 2
    },

    // Test a selector against a URL
    async testSelector(url, selectorType, selectorValue, attribute = null) {
        try {
            const result = await API.testSelector(url, selectorType, selectorValue, attribute);
            return result;
        } catch (error) {
            console.error('Selector test failed:', error);
            return { success: false, error: error.message, matches: [], count: 0 };
        }
    },

    // Preview scrape a URL with rules
    async previewScrape(url, rules) {
        try {
            const result = await API.previewScrape(url, rules);
            return result;
        } catch (error) {
            console.error('Preview scrape failed:', error);
            return { success: false, error: error.message };
        }
    },
};

// Export
window.RulesEditor = RulesEditor;
