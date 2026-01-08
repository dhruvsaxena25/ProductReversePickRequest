// js/pages/pickRequestDetail.js - Pick Request Detail Page (COMPLETE API SUPPORT)


const PickRequestDetailPage = {
    requestName: null,
    request: null,


    async render(params) {
        if (!params || params.length === 0) {
            App.navigate('pick-requests');
            return;
        }


        this.requestName = decodeURIComponent(params[0]);


        const content = document.getElementById('main-content');
        content.innerHTML = `
            <div class="container">
                <div class="loader-container">
                    <div class="loader"></div>
                </div>
            </div>
        `;


        await this.loadRequest();
    },


    async loadRequest() {
        try {
            console.log('Loading request:', this.requestName);
            const response = await API.pickRequests.get(this.requestName);
            console.log('Pick Request API response:', response);

            this.request = response.request || response;

            console.log('Extracted request:', this.request);
            this.renderDetails();
        } catch (error) {
            console.error('Failed to load request:', error);
            const content = document.getElementById('main-content');
            content.innerHTML = `
                <div class="container">
                    <div class="empty-state">
                        <i class="fas fa-exclamation-circle"></i>
                        <h3>Request Not Found</h3>
                        <p>The request "${Utils.escapeHtml(this.requestName)}" could not be found.</p>
                        <button class="btn btn-primary" onclick="App.navigate('pick-requests')">
                            Back to Requests
                        </button>
                    </div>
                </div>
            `;
        }
    },


    renderDetails() {
        const r = this.request;

        const totalItems = r.total_items || 0;
        const pickedItems = r.picked_items || 0;
        const progress = totalItems > 0 ? Math.round((pickedItems / totalItems) * 100) : 0;


        const content = document.getElementById('main-content');
        content.innerHTML = `
            <div class="container">
                <div class="mb-4">
                    <button class="btn btn-ghost" onclick="App.navigate('pick-requests')">
                        <i class="fas fa-arrow-left"></i> Back
                    </button>
                </div>


                <div class="card mb-6">
                    <div class="card-header">
                        <h1 class="card-title">
                            <i class="fas fa-clipboard-list"></i>
                            ${Utils.escapeHtml(r.name || 'Unknown Request')}
                        </h1>
                        <div class="flex gap-2">
                            ${this.renderActions()}
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="grid grid-cols-4 gap-4 mb-6">
                            <div>
                                <p class="text-muted mb-2">Status</p>
                                <span class="badge ${Utils.getStatusBadgeClass(r.status)}">
                                    ${Utils.formatStatus(r.status)}
                                </span>
                            </div>
                            <div>
                                <p class="text-muted mb-2">Priority</p>
                                <span class="badge ${Utils.getPriorityBadgeClass(r.priority)}">
                                    ${Utils.formatPriority(r.priority)}
                                </span>
                            </div>
                            <div>
                                <p class="text-muted mb-2">Progress</p>
                                <div class="progress-bar-container">
                                    <div class="progress-bar" style="width: ${progress}%"></div>
                                </div>
                                <small>${progress}%</small>
                            </div>
                            <div>
                                <p class="text-muted mb-2">Items</p>
                                <strong>${pickedItems} / ${totalItems}</strong>
                            </div>
                        </div>


                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-muted mb-2">Created By</p>
                                <p><strong>${Utils.escapeHtml(r.created_by || 'Unknown')}</strong></p>
                            </div>
                            <div>
                                <p class="text-muted mb-2">Created At</p>
                                <p>${r.created_at ? Utils.formatDate(r.created_at) : 'N/A'}</p>
                            </div>
                            ${r.picked_by ? `
                            <div>
                                <p class="text-muted mb-2">Picked By</p>
                                <p><strong>${Utils.escapeHtml(r.picked_by)}</strong></p>
                            </div>
                            ` : ''}
                            ${r.submitted_at ? `
                            <div>
                                <p class="text-muted mb-2">Submitted At</p>
                                <p>${Utils.formatDate(r.submitted_at)}</p>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                </div>


                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Items</h3>
                    </div>
                    <div class="card-body">
                        ${this.renderItems()}
                    </div>
                </div>
            </div>
        `;
    },


    renderActions() {
        const r = this.request;
        const user = Auth.getCurrentUser();
        let actions = [];

        console.log('Rendering actions for:', {
            status: r.status,
            picked_by: r.picked_by,
            current_user: user.username,
            created_by: r.created_by
        });

        // START PICKING - Pending requests (picker role)
        if (r.status === 'pending' && Auth.canPick()) {
            actions.push(`
                <button class="btn btn-primary" onclick="PickRequestDetailPage.startPicking()">
                    <i class="fas fa-play"></i> Start Picking
                </button>
            `);
        }

        // CONTINUE PICKING - In progress requests
        if (r.status === 'in_progress' && Auth.canPick()) {
            const canContinue = !r.picked_by || r.picked_by === user.username;
            if (canContinue) {
                actions.push(`
                    <a href="#pick-scanner/${encodeURIComponent(r.name)}" class="btn btn-primary">
                        <i class="fas fa-camera"></i> Continue Picking
                    </a>
                `);
            } else {
                actions.push(`
                    <div class="alert alert-info" style="margin: 0; padding: 0.5rem 1rem;">
                        <i class="fas fa-info-circle"></i> Being picked by ${Utils.escapeHtml(r.picked_by)}
                    </div>
                `);
            }
        }

        // RESUME PICKING - Paused requests (picker who paused it)
        if (r.status === 'paused' && Auth.canPick() && r.picked_by === user.username) {
            actions.push(`
                <button class="btn btn-success" onclick="PickRequestDetailPage.resumePicking()">
                    <i class="fas fa-play"></i> Resume Picking
                </button>
            `);
        }

        // PAUSE - In progress (picker or admin)
        if (r.status === 'in_progress' && (Auth.canPick() || Auth.isAdmin())) {
            actions.push(`
                <button class="btn btn-warning" onclick="PickRequestDetailPage.pausePicking()">
                    <i class="fas fa-pause"></i> Pause
                </button>
            `);
        }

        // SUBMIT - In progress (picker or admin)
        if (r.status === 'in_progress' && (Auth.canPick() || Auth.isAdmin())) {
            actions.push(`
                <button class="btn btn-success" onclick="PickRequestDetailPage.submitRequest()">
                    <i class="fas fa-check"></i> Submit
                </button>
            `);
        }

        // APPROVE - Partially completed (admin only)
        if (r.status === 'partially_completed' && Auth.isAdmin()) {
            actions.push(`
                <button class="btn btn-success" onclick="PickRequestDetailPage.approve()">
                    <i class="fas fa-check-double"></i> Approve
                </button>
            `);
        }

        // RELEASE LOCK - In progress/paused (admin only)
        if (['in_progress', 'paused'].includes(r.status) && Auth.isAdmin()) {
            actions.push(`
                <button class="btn btn-secondary" onclick="PickRequestDetailPage.releaseLock()">
                    <i class="fas fa-unlock"></i> Release Lock
                </button>
            `);
        }

        // CANCEL - Pending/In progress (creator or admin)
        if (['pending', 'in_progress'].includes(r.status) && (Auth.isAdmin() || r.created_by === user.username)) {
            actions.push(`
                <button class="btn btn-danger" onclick="PickRequestDetailPage.cancel()">
                    <i class="fas fa-times"></i> Cancel
                </button>
            `);
        }

        // DELETE - Pending only (creator or admin)
        if (r.status === 'pending' && (Auth.isAdmin() || r.created_by === user.username)) {
            actions.push(`
                <button class="btn btn-danger" onclick="PickRequestDetailPage.deleteRequest()">
                    <i class="fas fa-trash"></i> Delete
                </button>
            `);
        }

        return actions.join('');
    },


    renderItems() {
        if (!this.request.items || this.request.items.length === 0) {
            return `
                <div class="empty-state">
                    <i class="fas fa-box-open"></i>
                    <p>No items in this request</p>
                </div>
            `;
        }


        return `
            <div class="table-container">
                <table class="table">
                    <thead>
                        <tr>
                            <th>UPC</th>
                            <th>Product Name</th>
                            <th>Requested</th>
                            <th>Picked</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.request.items.map(item => {
                            const requestedQty = item.requested_quantity || 0;
                            const pickedQty = item.picked_quantity || 0;
                            const isComplete = pickedQty >= requestedQty;
                            return `
                                <tr class="${isComplete ? 'complete' : ''}">
                                    <td><code>${item.upc}</code></td>
                                    <td>${Utils.escapeHtml(item.product_name || 'Unknown Product')}</td>
                                    <td>${requestedQty}</td>
                                    <td><strong>${pickedQty}</strong></td>
                                    <td>
                                        ${isComplete 
                                            ? '<span class="badge badge-success"><i class="fas fa-check"></i> Complete</span>'
                                            : '<span class="badge badge-warning"><i class="fas fa-clock"></i> Pending</span>'
                                        }
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    },


    // === ACTION METHODS ===

    async startPicking() {
        try {
            await API.pickRequests.start(this.requestName);
            Notification.success('Pick request started');
            App.navigate(`pick-scanner/${encodeURIComponent(this.requestName)}`);
        } catch (error) {
            console.error('Start picking error:', error);
            Notification.error(error.message || 'Failed to start picking');
        }
    },


    async resumePicking() {
        Modal.confirm({
            title: 'Resume Picking',
            message: 'Do you want to resume picking this request?',
            variant: 'success',
            confirmLabel: 'Resume',
            onConfirm: async () => {
                try {
                    await API.pickRequests.resume(this.requestName);
                    Notification.success('Picking resumed');
                    App.navigate(`pick-scanner/${encodeURIComponent(this.requestName)}`);
                } catch (error) {
                    console.error('Resume error:', error);
                    Notification.error(error.message || 'Failed to resume picking');
                }
            }
        });
    },


    async pausePicking() {
        Modal.confirm({
            title: 'Pause Picking',
            message: 'Do you want to pause this pick request? You can resume later.',
            variant: 'warning',
            confirmLabel: 'Pause',
            onConfirm: async () => {
                try {
                    await API.pickRequests.pause(this.requestName);
                    Notification.info('Request paused');
                    await this.loadRequest();
                } catch (error) {
                    console.error('Pause error:', error);
                    Notification.error(error.message || 'Failed to pause request');
                }
            }
        });
    },


    async submitRequest() {
        Modal.confirm({
            title: 'Submit Pick Request',
            message: 'Are you sure you want to submit this pick request?',
            variant: 'success',
            confirmLabel: 'Submit',
            onConfirm: async () => {
                try {
                    await API.pickRequests.submit(this.requestName);
                    Notification.success('Pick request submitted successfully!');
                    await this.loadRequest();
                } catch (error) {
                    console.error('Submit error:', error);
                    Notification.error(error.message || 'Failed to submit request');
                }
            }
        });
    },


    async approve() {
        Modal.confirm({
            title: 'Approve Request',
            message: 'Are you sure you want to approve this partially completed request?',
            variant: 'success',
            confirmLabel: 'Approve',
            onConfirm: async () => {
                try {
                    await API.pickRequests.approve(this.requestName);
                    Notification.success('Request approved');
                    await this.loadRequest();
                } catch (error) {
                    console.error('Approve error:', error);
                    Notification.error(error.message || 'Failed to approve request');
                }
            }
        });
    },


    async releaseLock() {
        Modal.confirm({
            title: 'Release Lock',
            message: 'Are you sure you want to release the lock on this request? The current picker will lose access.',
            variant: 'warning',
            confirmLabel: 'Release',
            onConfirm: async () => {
                try {
                    await API.pickRequests.releaseLock(this.requestName);
                    Notification.success('Lock released');
                    await this.loadRequest();
                } catch (error) {
                    console.error('Release lock error:', error);
                    Notification.error(error.message || 'Failed to release lock');
                }
            }
        });
    },


    async cancel() {
        Modal.confirm({
            title: 'Cancel Request',
            message: 'Are you sure you want to cancel this request?',
            variant: 'danger',
            confirmLabel: 'Cancel Request',
            onConfirm: async () => {
                try {
                    await API.pickRequests.cancel(this.requestName);
                    Notification.success('Request cancelled');
                    App.navigate('pick-requests');
                } catch (error) {
                    console.error('Cancel error:', error);
                    Notification.error(error.message || 'Failed to cancel request');
                }
            }
        });
    },


    async deleteRequest() {
        Modal.confirm({
            title: 'Delete Request',
            message: 'Are you sure you want to delete this request? This cannot be undone.',
            variant: 'danger',
            confirmLabel: 'Delete',
            onConfirm: async () => {
                try {
                    await API.pickRequests.delete(this.requestName);
                    Notification.success('Request deleted');
                    App.navigate('pick-requests');
                } catch (error) {
                    console.error('Delete error:', error);
                    Notification.error(error.message || 'Failed to delete request');
                }
            }
        });
    },


    cleanup() {
        this.requestName = null;
        this.request = null;
    }
};
