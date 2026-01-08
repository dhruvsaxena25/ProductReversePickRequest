// js/components/navbar.js - Navigation Bar Component

const Navbar = {
    render() {
        const user = Auth.getCurrentUser();
        if (!user) return;

        const navbarEl = document.getElementById('navbar');

        const menuItems = this.getMenuItems(user.role);

        navbarEl.innerHTML = `
            <nav class="navbar">
                <div class="navbar-container">
                    <a href="#dashboard" class="navbar-brand">
                        <i class="fas fa-box"></i>
                        Pick System
                    </a>

                    <button class="navbar-toggle" id="navbar-toggle">
                        <i class="fas fa-bars"></i>
                    </button>

                    <ul class="navbar-menu" id="navbar-menu">
                        ${menuItems.map(item => `
                            <li class="navbar-item">
                                <a href="#${item.route}" class="navbar-link" data-route="${item.route}">
                                    <i class="${item.icon}"></i>
                                    <span>${item.label}</span>
                                </a>
                            </li>
                        `).join('')}

                        <li class="navbar-item navbar-user">
                            <div class="navbar-avatar">
                                ${user.username.charAt(0).toUpperCase()}
                            </div>
                            <div class="navbar-user-info">
                                <div class="navbar-username">${Utils.escapeHtml(user.username)}</div>
                                <div class="navbar-role">${Utils.formatStatus(user.role)}</div>
                            </div>
                            <div class="dropdown">
                                <button class="btn btn-ghost btn-sm" id="user-dropdown-btn">
                                    <i class="fas fa-chevron-down"></i>
                                </button>
                                <div class="dropdown-menu" id="user-dropdown">
                                    <button class="dropdown-item" onclick="Navbar.changePassword()">
                                        <i class="fas fa-key"></i>
                                        Change Password
                                    </button>
                                    <div class="dropdown-divider"></div>
                                    <button class="dropdown-item" onclick="Navbar.logout()">
                                        <i class="fas fa-sign-out-alt"></i>
                                        Logout
                                    </button>
                                </div>
                            </div>
                        </li>
                    </ul>
                </div>
            </nav>
        `;

        this.attachEvents();
        this.setActiveLink();

        window.addEventListener('hashchange', () => this.setActiveLink());
    },

    getMenuItems(role) {
        const baseItems = [
            { route: 'dashboard', icon: 'fas fa-home', label: 'Dashboard' },
            { route: 'products', icon: 'fas fa-barcode', label: 'Products' },
            { route: 'pick-requests', icon: 'fas fa-clipboard-list', label: 'Requests' }
        ];

        const roleSpecific = {
            'admin': [
                { route: 'create-request', icon: 'fas fa-plus-circle', label: 'New Request' },
                { route: 'users', icon: 'fas fa-users', label: 'Users' }
            ],
            'requester': [
                { route: 'create-request', icon: 'fas fa-plus-circle', label: 'New Request' }
            ],
            'picker': [
                { route: 'pick-scanner', icon: 'fas fa-camera', label: 'Pick Items' }
            ]
        };

        return [...baseItems, ...(roleSpecific[role] || [])];
    },

    attachEvents() {
        const toggleBtn = document.getElementById('navbar-toggle');
        const menu = document.getElementById('navbar-menu');

        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                menu.classList.toggle('show');
            });
        }

        const dropdownBtn = document.getElementById('user-dropdown-btn');
        const dropdown = document.getElementById('user-dropdown');

        if (dropdownBtn) {
            dropdownBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                dropdown.classList.toggle('show');
            });

            document.addEventListener('click', () => {
                dropdown.classList.remove('show');
            });
        }
    },

    setActiveLink() {
        const hash = window.location.hash.slice(1).split('/')[0];
        const links = document.querySelectorAll('.navbar-link');

        links.forEach(link => {
            const route = link.getAttribute('data-route');
            if (route === hash || (hash === '' && route === 'dashboard')) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    },

    async changePassword() {
        const modal = Modal.create({
            title: 'Change Password',
            content: `
                <form id="change-password-form">
                    <div class="form-group">
                        <label class="form-label required">Current Password</label>
                        <input type="password" class="form-input" id="current-password" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label required">New Password</label>
                        <input type="password" class="form-input" id="new-password" required minlength="6">
                        <p class="form-help">Minimum 6 characters</p>
                    </div>
                    <div class="form-group">
                        <label class="form-label required">Confirm New Password</label>
                        <input type="password" class="form-input" id="confirm-password" required>
                    </div>
                </form>
            `,
            actions: [
                { label: 'Cancel', variant: 'ghost', action: () => modal.close() },
                { 
                    label: 'Change Password', 
                    variant: 'primary',
                    action: async () => {
                        const current = document.getElementById('current-password').value;
                        const newPass = document.getElementById('new-password').value;
                        const confirm = document.getElementById('confirm-password').value;

                        if (newPass !== confirm) {
                            Notification.error('Passwords do not match');
                            return;
                        }

                        if (newPass.length < 6) {
                            Notification.error('Password must be at least 6 characters');
                            return;
                        }

                        try {
                            await API.auth.changePassword(current, newPass);
                            Notification.success('Password changed successfully');
                            modal.close();
                        } catch (error) {
                            Notification.error(error.message);
                        }
                    }
                }
            ]
        });
    },

    logout() {
        Modal.confirm({
            title: 'Logout',
            message: 'Are you sure you want to logout?',
            onConfirm: () => {
                Auth.logout();
                App.navigate('', false);
                Notification.info('You have been logged out');
            }
        });
    }
};
