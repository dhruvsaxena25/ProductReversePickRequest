// js/pages/dashboard.js - Dashboard Page (COMPLETE FIX)


const DashboardPage = {
    async render() {
        const content = document.getElementById('main-content');
        const user = Auth.getCurrentUser();


        content.innerHTML = `
            <div class="container">
                <div class="dashboard-header">
                    <h1 class="dashboard-title">
                        Welcome back, ${Utils.escapeHtml(user.username)}!
                    </h1>
                    <p class="dashboard-subtitle">
                        ${this.getGreeting()} Here's your overview for today.
                    </p>
                </div>


                <div id="dashboard-stats" class="stats-grid">
                    <div class="loader-container">
                        <div class="loader"></div>
                    </div>
                </div>


                ${Auth.canRequest() ? `
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">
                            <i class="fas fa-bolt"></i>
                            Quick Actions
                        </h3>
                    </div>
                    <div class="card-body">
                        <div class="quick-actions">
                            <a href="#create-request" class="quick-action-card">
                                <div class="quick-action-icon">
                                    <i class="fas fa-plus"></i>
                                </div>
                                <div class="quick-action-title">Create Request</div>
                            </a>
                            <a href="#products" class="quick-action-card">
                                <div class="quick-action-icon">
                                    <i class="fas fa-barcode"></i>
                                </div>
                                <div class="quick-action-title">Browse Products</div>
                            </a>
                            ${Auth.canPick() ? `
                            <a href="#pick-requests" class="quick-action-card">
                                <div class="quick-action-icon">
                                    <i class="fas fa-camera"></i>
                                </div>
                                <div class="quick-action-title">Start Picking</div>
                            </a>
                            ` : ''}
                        </div>
                    </div>
                </div>
                ` : ''}


                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">
                            <i class="fas fa-history"></i>
                            Recent Activity
                        </h3>
                    </div>
                    <div class="card-body">
                        <ul class="activity-list" id="activity-list">
                            <div class="loader-container">
                                <div class="loader"></div>
                            </div>
                        </ul>
                    </div>
                </div>
            </div>
        `;


        await this.loadStats();
        await this.loadActivity();
    },


    async loadStats() {
        try {
            console.log('[Dashboard] Loading stats...');

            // FIXED: Direct API call to /pick-requests
            const response = await API.pickRequests.list({ limit: 1000 });
            console.log('[Dashboard] API response:', response);

            // FIXED: Handle both response formats
            const requests = Array.isArray(response) ? response : (response.requests || []);
            console.log('[Dashboard] Extracted requests:', requests.length);


            // Calculate stats
            const stats = {
                total: requests.length,
                pending: requests.filter(r => r.status === 'pending').length,
                in_progress: requests.filter(r => r.status === 'in_progress').length,
                completed: requests.filter(r => r.status === 'completed').length
            };


            console.log('[Dashboard] Stats:', stats);


            const statsHtml = `
                <div class="stat-card primary">
                    <div class="stat-header">
                        <div class="stat-icon">
                            <i class="fas fa-clipboard-list"></i>
                        </div>
                    </div>
                    <div class="stat-value">${stats.total}</div>
                    <div class="stat-label">Total Requests</div>
                </div>
                <div class="stat-card warning">
                    <div class="stat-header">
                        <div class="stat-icon">
                            <i class="fas fa-clock"></i>
                        </div>
                    </div>
                    <div class="stat-value">${stats.pending}</div>
                    <div class="stat-label">Pending</div>
                </div>
                <div class="stat-card info">
                    <div class="stat-header">
                        <div class="stat-icon">
                            <i class="fas fa-tasks"></i>
                        </div>
                    </div>
                    <div class="stat-value">${stats.in_progress}</div>
                    <div class="stat-label">In Progress</div>
                </div>
                <div class="stat-card success">
                    <div class="stat-header">
                        <div class="stat-icon">
                            <i class="fas fa-check-circle"></i>
                        </div>
                    </div>
                    <div class="stat-value">${stats.completed}</div>
                    <div class="stat-label">Completed</div>
                </div>
            `;


            document.getElementById('dashboard-stats').innerHTML = statsHtml;
            console.log('[Dashboard] Stats loaded successfully');
        } catch (error) {
            console.error('[Dashboard] Failed to load stats:', error);

            // FIXED: Better error display
            const errorMessage = error.message || 'Unknown error';
            document.getElementById('dashboard-stats').innerHTML = `
                <div class="alert alert-danger" style="grid-column: 1 / -1;">
                    <i class="fas fa-exclamation-circle"></i>
                    Failed to load statistics: ${Utils.escapeHtml(errorMessage)}
                    ${errorMessage.includes('Session expired') ? '<br><a href="#login">Click here to login again</a>' : ''}
                </div>
            `;
        }
    },


    async loadActivity() {
        try {
            console.log('[Dashboard] Loading activity...');

            // FIXED: Direct API call to /pick-requests
            const response = await API.pickRequests.list({ limit: 10 });
            console.log('[Dashboard] Activity API response:', response);

            // FIXED: Handle both response formats
            const requests = Array.isArray(response) ? response : (response.requests || []);
            console.log('[Dashboard] Extracted activity requests:', requests.length);


            if (requests.length === 0) {
                document.getElementById('activity-list').innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-inbox"></i>
                        <p>No recent activity</p>
                    </div>
                `;
                return;
            }


            const activityHtml = requests.map(request => {
                const iconClass = this.getActivityIcon(request.status);
                return `
                    <li class="activity-item">
                        <div class="activity-icon ${iconClass.type}">
                            <i class="${iconClass.icon}"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">
                                <a href="#pick-request/${encodeURIComponent(request.name)}">
                                    ${Utils.escapeHtml(request.name)}
                                </a>
                            </div>
                            <div class="activity-meta">
                                <span class="badge ${Utils.getStatusBadgeClass(request.status)}">
                                    ${Utils.formatStatus(request.status)}
                                </span>
                                <span>${Utils.formatRelativeTime(request.created_at)}</span>
                            </div>
                        </div>
                    </li>
                `;
            }).join('');


            document.getElementById('activity-list').innerHTML = activityHtml;
            console.log('[Dashboard] Activity loaded successfully');
        } catch (error) {
            console.error('[Dashboard] Failed to load activity:', error);

            // FIXED: Better error display
            const errorMessage = error.message || 'Unknown error';
            document.getElementById('activity-list').innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle"></i>
                    Failed to load recent activity: ${Utils.escapeHtml(errorMessage)}
                    ${errorMessage.includes('Session expired') ? '<br><a href="#login">Click here to login again</a>' : ''}
                </div>
            `;
        }
    },


    getGreeting() {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning!';
        if (hour < 18) return 'Good afternoon!';
        return 'Good evening!';
    },


    getActivityIcon(status) {
        const icons = {
            'pending': { icon: 'fas fa-clock', type: 'warning' },
            'in_progress': { icon: 'fas fa-spinner', type: 'info' },
            'paused': { icon: 'fas fa-pause', type: 'warning' },
            'completed': { icon: 'fas fa-check', type: 'success' },
            'partially_completed': { icon: 'fas fa-check-circle', type: 'info' },
            'cancelled': { icon: 'fas fa-times', type: 'danger' }
        };
        return icons[status] || icons.pending;
    },


    cleanup() {
        // Nothing to clean up
    }
};
