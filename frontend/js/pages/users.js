// js/pages/users.js - User Management Page (COLORED ROLES)


const UsersPage = {
    allUsers: [],  // Store users array for reference


    async render() {
        const content = document.getElementById('main-content');


        content.innerHTML = `
            <div class="container">
                <div class="flex justify-between items-center mb-6">
                    <h1><i class="fas fa-users"></i> User Management</h1>
                    <button class="btn btn-primary" onclick="UsersPage.createUser()">
                        <i class="fas fa-user-plus"></i> Add User
                    </button>
                </div>


                <div class="card">
                    <div class="card-body">
                        <div id="users-container">
                            <div class="loader-container">
                                <div class="loader"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;


        await this.loadUsers();
    },


    getRoleBadgeClass(role) {
        // Color-coded badges for different roles
        const roleColors = {
            'admin': 'badge-danger',      // Red for Admin (highest privilege)
            'requester': 'badge-primary',  // Blue for Requester
            'picker': 'badge-success'      // Green for Picker
        };
        return roleColors[role] || 'badge-secondary';
    },


    getRoleIcon(role) {
        // Icons for different roles
        const roleIcons = {
            'admin': 'fa-crown',           // Crown for Admin
            'requester': 'fa-clipboard-list', // Clipboard for Requester
            'picker': 'fa-boxes'           // Boxes for Picker
        };
        return roleIcons[role] || 'fa-user';
    },


    async loadUsers() {
        try {
            const response = await API.users.list();
            console.log('Users API response:', response);

            // Extract users array from response
            const users = response.users || response;
            this.allUsers = users;  // Store for reference

            if (!users || users.length === 0) {
                document.getElementById('users-container').innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-users"></i>
                        <h3>No Users Found</h3>
                    </div>
                `;
                return;
            }


            const tableHtml = `
                <div class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Username</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Created</th>
                                <th style="width: 150px;">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${users.map((user, index) => `
                                <tr>
                                    <td><strong>${Utils.escapeHtml(user.username)}</strong></td>
                                    <td>
                                        <span class="badge ${this.getRoleBadgeClass(user.role)}">
                                            <i class="fas ${this.getRoleIcon(user.role)}"></i>
                                            ${Utils.capitalize(user.role)}
                                        </span>
                                    </td>
                                    <td>
                                        <span class="badge ${user.is_active ? 'badge-success' : 'badge-danger'}">
                                            ${user.is_active ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    <td>${Utils.formatDate(user.created_at)}</td>
                                    <td>
                                        <button 
                                            class="btn btn-sm btn-ghost" 
                                            onclick="UsersPage.editUser('${user.id}')"
                                            title="Edit user"
                                        >
                                            <i class="fas fa-edit"></i>
                                        </button>
                                        ${user.is_active ? `
                                            <button 
                                                class="btn btn-sm btn-danger" 
                                                onclick="UsersPage.deactivateUser('${user.id}')"
                                                title="Deactivate user"
                                            >
                                                <i class="fas fa-ban"></i>
                                            </button>
                                        ` : `
                                            <button 
                                                class="btn btn-sm btn-success" 
                                                onclick="UsersPage.activateUser('${user.id}')"
                                                title="Activate user"
                                            >
                                                <i class="fas fa-check"></i>
                                            </button>
                                        `}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;


            document.getElementById('users-container').innerHTML = tableHtml;
        } catch (error) {
            console.error('Failed to load users:', error);
            Notification.error('Failed to load users');

            document.getElementById('users-container').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Error Loading Users</h3>
                    <p>${error.message || 'Please try again later'}</p>
                </div>
            `;
        }
    },


    createUser() {
        const modal = Modal.create({
            title: '<i class="fas fa-user-plus"></i> Create User',
            content: `
                <form id="create-user-form">
                    <div class="form-group">
                        <label class="form-label required">Username</label>
                        <input type="text" class="form-input" id="new-username" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label required">Password</label>
                        <input type="password" class="form-input" id="new-password" required minlength="6">
                        <p class="form-help">Minimum 6 characters</p>
                    </div>
                    <div class="form-group">
                        <label class="form-label required">Role</label>
                        <select class="form-select" id="new-role" required>
                            <option value="">Select Role</option>
                            <option value="admin">👑 Admin - Full System Access</option>
                            <option value="requester">📋 Requester - Create Pick Requests</option>
                            <option value="picker">📦 Picker - Fulfill Requests</option>
                        </select>
                    </div>
                </form>
            `,
            actions: [
                { label: 'Cancel', variant: 'ghost', action: (m) => m.close() },
                { 
                    label: 'Create', 
                    variant: 'primary',
                    action: async () => {
                        const username = document.getElementById('new-username').value.trim();
                        const password = document.getElementById('new-password').value;
                        const role = document.getElementById('new-role').value;


                        if (!username || !password || !role) {
                            Notification.error('All fields are required');
                            return;
                        }


                        if (password.length < 6) {
                            Notification.error('Password must be at least 6 characters');
                            return;
                        }


                        try {
                            await API.users.create({ username, password, role });
                            Notification.success('User created successfully');
                            modal.close();
                            await UsersPage.loadUsers();
                        } catch (error) {
                            console.error('Create user error:', error);
                            Notification.error(error.message || 'Failed to create user');
                        }
                    }
                }
            ]
        });
    },


    async editUser(userId) {
        try {
            console.log('Editing user:', userId);
            const response = await API.users.get(userId);
            console.log('Get user response:', response);

            // Extract user from response
            const user = response.user || response;


            const modal = Modal.create({
                title: '<i class="fas fa-edit"></i> Edit User',
                content: `
                    <form id="edit-user-form">
                        <div class="form-group">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-input" value="${Utils.escapeHtml(user.username)}" disabled>
                        </div>
                        <div class="form-group">
                            <label class="form-label required">Role</label>
                            <select class="form-select" id="edit-role" required>
                                <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>👑 Admin</option>
                                <option value="requester" ${user.role === 'requester' ? 'selected' : ''}>📋 Requester</option>
                                <option value="picker" ${user.role === 'picker' ? 'selected' : ''}>📦 Picker</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">New Password (leave blank to keep current)</label>
                            <input type="password" class="form-input" id="edit-password" minlength="6">
                            <p class="form-help">Only fill this if you want to change the password</p>
                        </div>
                    </form>
                `,
                actions: [
                    { label: 'Cancel', variant: 'ghost', action: (m) => m.close() },
                    { 
                        label: 'Update', 
                        variant: 'primary',
                        action: async () => {
                            const role = document.getElementById('edit-role').value;
                            const password = document.getElementById('edit-password').value;


                            if (password && password.length < 6) {
                                Notification.error('Password must be at least 6 characters');
                                return;
                            }


                            const updateData = { role };
                            if (password) {
                                updateData.password = password;
                            }


                            try {
                                await API.users.update(userId, updateData);
                                Notification.success('User updated successfully');
                                modal.close();
                                await UsersPage.loadUsers();
                            } catch (error) {
                                console.error('Update user error:', error);
                                Notification.error(error.message || 'Failed to update user');
                            }
                        }
                    }
                ]
            });
        } catch (error) {
            console.error('Failed to load user:', error);
            Notification.error('Failed to load user details');
        }
    },


    async deactivateUser(userId) {
        console.log('Deactivating user:', userId);

        Modal.confirm({
            title: 'Deactivate User',
            message: 'Are you sure you want to deactivate this user? They will not be able to log in.',
            variant: 'danger',
            confirmLabel: 'Deactivate',
            onConfirm: async () => {
                try {
                    console.log('Calling deactivate API for:', userId);
                    await API.users.deactivate(userId);
                    Notification.success('User deactivated successfully');
                    await UsersPage.loadUsers();
                } catch (error) {
                    console.error('Deactivate user error:', error);
                    Notification.error(error.message || 'Failed to deactivate user');
                }
            }
        });
    },


    async activateUser(userId) {
        console.log('Activating user:', userId);

        try {
            await API.users.activate(userId);
            Notification.success('User activated successfully');
            await UsersPage.loadUsers();
        } catch (error) {
            console.error('Activate user error:', error);
            Notification.error(error.message || 'Failed to activate user');
        }
    },


    cleanup() {
        this.allUsers = [];
    }
};
