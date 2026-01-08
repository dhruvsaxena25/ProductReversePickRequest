// js/pages/pickRequests.js - Pick Requests List Page (FIXED)


const PickRequestsPage = {
    filters: {},


    async render() {
        const content = document.getElementById('main-content');


        content.innerHTML = `
            <div class="container">
                <div class="flex justify-between items-center mb-6">
                    <h1><i class="fas fa-clipboard-list"></i> Pick Requests</h1>
                    ${Auth.canRequest() ? `
                        <a href="#create-request" class="btn btn-primary">
                            <i class="fas fa-plus"></i> New Request
                        </a>
                    ` : ''}
                </div>


                <div class="card mb-6">
                    <div class="card-body">
                        <div class="grid grid-cols-4 gap-4">
                            <select class="form-select" id="status-filter">
                                <option value="">All Statuses</option>
                                <option value="pending">Pending</option>
                                <option value="in_progress">In Progress</option>
                                <option value="completed">Completed</option>
                                <option value="partially_completed">Partially Completed</option>
                                <option value="cancelled">Cancelled</option>
                            </select>
                            <select class="form-select" id="priority-filter">
                                <option value="">All Priorities</option>
                                <option value="low">Low</option>
                                <option value="normal">Normal</option>
                                <option value="high">High</option>
                                <option value="urgent">Urgent</option>
                            </select>
                            <div class="form-check">
                                <input type="checkbox" id="mine-only">
                                <label for="mine-only">My Requests Only</label>
                            </div>
                            <button class="btn btn-secondary" onclick="PickRequestsPage.applyFilters()">
                                <i class="fas fa-filter"></i> Apply Filters
                            </button>
                        </div>
                    </div>
                </div>


                <div class="card">
                    <div class="card-body">
                        <div id="requests-container">
                            <div class="loader-container">
                                <div class="loader"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;


        await this.loadRequests();
    },


    async loadRequests() {
        try {
            console.log('Loading pick requests with filters:', this.filters);
            const response = await API.pickRequests.list(this.filters);
            console.log('Pick Requests API response:', response);

            // FIXED: Extract requests array from response
            // Backend returns: { requests: [...], total: 10 } or just [...]
            const requests = response.requests || response;

            if (!requests || requests.length === 0) {
                document.getElementById('requests-container').innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-clipboard"></i>
                        <h3>No Requests Found</h3>
                        <p>Try adjusting your filters or create a new request</p>
                        ${Auth.canRequest() ? `
                            <a href="#create-request" class="btn btn-primary" style="margin-top: 1rem;">
                                <i class="fas fa-plus"></i> Create Request
                            </a>
                        ` : ''}
                    </div>
                `;
                return;
            }


            const tableHtml = `
                <div class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Status</th>
                                <th>Priority</th>
                                <th>Items</th>
                                <th>Progress</th>
                                <th>Created</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${requests.map(request => {
                                const totalItems = request.total_items || 0;
                                const pickedItems = request.picked_items || 0;
                                const progress = totalItems > 0 
                                    ? Math.round((pickedItems / totalItems) * 100) 
                                    : 0;


                                return `
                                    <tr>
                                        <td>
                                            <a href="#pick-request/${encodeURIComponent(request.name)}">
                                                <strong>${Utils.escapeHtml(request.name)}</strong>
                                            </a>
                                        </td>
                                        <td>
                                            <span class="badge ${Utils.getStatusBadgeClass(request.status)}">
                                                ${Utils.formatStatus(request.status)}
                                            </span>
                                        </td>
                                        <td>
                                            <span class="badge ${Utils.getPriorityBadgeClass(request.priority)}">
                                                ${Utils.formatPriority(request.priority)}
                                            </span>
                                        </td>
                                        <td>${pickedItems} / ${totalItems}</td>
                                        <td>
                                            <div class="progress-bar-container">
                                                <div class="progress-bar" style="width: ${progress}%"></div>
                                            </div>
                                            <small style="color: var(--text-secondary);">${progress}%</small>
                                        </td>
                                        <td>${Utils.formatRelativeTime(request.created_at)}</td>
                                        <td>
                                            <a href="#pick-request/${encodeURIComponent(request.name)}" class="btn btn-sm btn-primary">
                                                <i class="fas fa-eye"></i> View
                                            </a>
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            `;


            document.getElementById('requests-container').innerHTML = tableHtml;
        } catch (error) {
            console.error('Failed to load requests:', error);
            Notification.error('Failed to load requests');

            document.getElementById('requests-container').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Error Loading Requests</h3>
                    <p>${error.message || 'Please try again later'}</p>
                </div>
            `;
        }
    },


    applyFilters() {
        const status = document.getElementById('status-filter').value;
        const priority = document.getElementById('priority-filter').value;
        const mineOnly = document.getElementById('mine-only').checked;


        this.filters = {};
        if (status) this.filters.status = status;
        if (priority) this.filters.priority = priority;
        if (mineOnly) this.filters.mine = true;


        this.loadRequests();
    },


    cleanup() {
        this.filters = {};
    }
};
