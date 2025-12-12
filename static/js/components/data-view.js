/**
 * Data View Component
 * Browse database tables and execute SQL queries
 */
const DataView = {
    els: {},
    currentTable: null,
    currentPage: 0,
    pageSize: 50,
    totalRows: 0,

    init() {
        this.cacheElements();
        this.bindEvents();
    },

    cacheElements() {
        this.els = {
            tableSelect: document.getElementById('data-table-select'),
            rowCount: document.getElementById('data-row-count'),
            schemaColumns: document.getElementById('schema-columns'),
            tableHead: document.getElementById('data-table-head'),
            tableBody: document.getElementById('data-table-body'),
            paginationInfo: document.getElementById('pagination-info'),
            btnPrev: document.getElementById('btn-prev-page'),
            btnNext: document.getElementById('btn-next-page'),
            btnRefresh: document.getElementById('btn-refresh-data'),
            sqlInput: document.getElementById('sql-input'),
            btnExecute: document.getElementById('btn-execute-sql'),
            sqlStatus: document.getElementById('sql-status'),
            sqlResults: document.getElementById('sql-results'),
        };
    },

    bindEvents() {
        // Table selector
        this.els.tableSelect?.addEventListener('change', () => {
            this.currentPage = 0;
            this.loadTableData();
        });

        // Pagination
        this.els.btnPrev?.addEventListener('click', () => {
            if (this.currentPage > 0) {
                this.currentPage--;
                this.loadTableRows();
            }
        });

        this.els.btnNext?.addEventListener('click', () => {
            const maxPage = Math.ceil(this.totalRows / this.pageSize) - 1;
            if (this.currentPage < maxPage) {
                this.currentPage++;
                this.loadTableRows();
            }
        });

        // Refresh
        this.els.btnRefresh?.addEventListener('click', () => {
            this.loadTables();
        });

        // SQL execute
        this.els.btnExecute?.addEventListener('click', () => {
            this.executeQuery();
        });

        // Ctrl+Enter to execute SQL
        this.els.sqlInput?.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                this.executeQuery();
            }
        });

        // Load tables when Data view becomes active
        State.subscribe((key, value) => {
            if (key === 'currentView' && value === 'data') {
                this.loadTables();
            }
        });
    },

    async loadTables() {
        try {
            const result = await API.listTables();
            const tables = result.tables || [];

            this.els.tableSelect.innerHTML = tables.map(t =>
                `<option value="${t.name}">${t.name} (${t.row_count} rows)</option>`
            ).join('');

            if (tables.length > 0) {
                this.currentTable = tables[0].name;
                this.loadTableData();
            }
        } catch (error) {
            console.error('Failed to load tables:', error);
            this.els.tableSelect.innerHTML = '<option value="">Error loading tables</option>';
        }
    },

    async loadTableData() {
        this.currentTable = this.els.tableSelect.value;
        if (!this.currentTable) return;

        // Load schema and rows in parallel
        await Promise.all([
            this.loadTableSchema(),
            this.loadTableRows(),
        ]);
    },

    async loadTableSchema() {
        try {
            const result = await API.getTableSchema(this.currentTable);
            const columns = result.columns || [];

            this.els.schemaColumns.innerHTML = columns.map(col => {
                const type = col.type.replace(/\(\d+\)/, '');
                return `<span class="schema-col" title="${col.type}${col.nullable ? '' : ' NOT NULL'}">${col.name}</span>`;
            }).join('');
        } catch (error) {
            console.error('Failed to load schema:', error);
            this.els.schemaColumns.textContent = 'Error loading schema';
        }
    },

    async loadTableRows() {
        try {
            const offset = this.currentPage * this.pageSize;
            const result = await API.getTableRows(this.currentTable, this.pageSize, offset);

            this.totalRows = result.total || 0;
            const rows = result.rows || [];

            // Update row count
            this.els.rowCount.textContent = `${this.totalRows} total rows`;

            // Build table header
            if (rows.length > 0) {
                const columns = Object.keys(rows[0]);
                this.els.tableHead.innerHTML = `<tr>${columns.map(c =>
                    `<th>${this.escapeHtml(c)}</th>`
                ).join('')}</tr>`;

                // Build table body
                this.els.tableBody.innerHTML = rows.map(row =>
                    `<tr>${columns.map(c =>
                        `<td>${this.formatCell(row[c])}</td>`
                    ).join('')}</tr>`
                ).join('');
            } else {
                this.els.tableHead.innerHTML = '<tr><th>No data</th></tr>';
                this.els.tableBody.innerHTML = '<tr><td>This table is empty</td></tr>';
            }

            // Update pagination
            this.updatePagination();
        } catch (error) {
            console.error('Failed to load rows:', error);
            this.els.tableBody.innerHTML = '<tr><td>Error loading data</td></tr>';
        }
    },

    updatePagination() {
        const totalPages = Math.ceil(this.totalRows / this.pageSize);
        const currentPageDisplay = totalPages > 0 ? this.currentPage + 1 : 0;

        this.els.paginationInfo.textContent = `Page ${currentPageDisplay} of ${totalPages}`;
        this.els.btnPrev.disabled = this.currentPage <= 0;
        this.els.btnNext.disabled = this.currentPage >= totalPages - 1;
    },

    async executeQuery() {
        const sql = this.els.sqlInput.value.trim();
        if (!sql) {
            this.els.sqlStatus.textContent = 'Enter a query first';
            return;
        }

        this.els.btnExecute.disabled = true;
        this.els.sqlStatus.textContent = 'Running...';

        try {
            const result = await API.executeQuery(sql);

            if (result.success) {
                const rows = result.rows || [];
                const columns = result.columns || [];

                this.els.sqlStatus.textContent = `${result.row_count} row${result.row_count !== 1 ? 's' : ''} returned`;

                if (rows.length > 0) {
                    this.els.sqlResults.innerHTML = `
                        <div class="sql-results-table-wrapper">
                            <table class="data-table">
                                <thead>
                                    <tr>${columns.map(c => `<th>${this.escapeHtml(c)}</th>`).join('')}</tr>
                                </thead>
                                <tbody>
                                    ${rows.map(row => `<tr>${columns.map(c =>
                                        `<td>${this.formatCell(row[c])}</td>`
                                    ).join('')}</tr>`).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                } else {
                    this.els.sqlResults.innerHTML = '<div class="sql-results-empty">Query returned no results</div>';
                }
            } else {
                this.els.sqlStatus.textContent = 'Error';
                this.els.sqlResults.innerHTML = `<div class="sql-error">${this.escapeHtml(result.error)}</div>`;
            }
        } catch (error) {
            this.els.sqlStatus.textContent = 'Error';
            this.els.sqlResults.innerHTML = `<div class="sql-error">${this.escapeHtml(error.message)}</div>`;
        } finally {
            this.els.btnExecute.disabled = false;
        }
    },

    formatCell(value) {
        if (value === null || value === undefined) {
            return '<span class="null-value">NULL</span>';
        }
        if (typeof value === 'object') {
            return `<span class="json-value">${this.escapeHtml(JSON.stringify(value))}</span>`;
        }
        const str = String(value);
        // Truncate long values
        if (str.length > 100) {
            return `<span title="${this.escapeHtml(str)}">${this.escapeHtml(str.substring(0, 100))}...</span>`;
        }
        return this.escapeHtml(str);
    },

    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    },
};

// Export
window.DataView = DataView;
