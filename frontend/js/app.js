// js/app.js - Main Application Controller

const App = {
    currentPage: null,

    async init() {
        console.log('🚀 Initializing application...');

        try {
            // Hide loader initially
            this.hideLoader();

            // Initialize authentication
            console.log('🔐 Checking authentication...');
            const isAuthenticated = await Auth.initialize();
            console.log('Auth status:', isAuthenticated);

            // Setup routing
            this.setupRouting();

            // Handle initial route
            this.handleRoute();

            // Listen for hash changes
            window.addEventListener('hashchange', () => this.handleRoute());

            console.log('✅ Application initialized successfully');
        } catch (error) {
            console.error('❌ Application initialization failed:', error);
            this.showError('Failed to initialize application: ' + error.message);
        }
    },

    setupRouting() {
        // Define all routes
        this.routes = {
            '': 'login',
            'login': 'login',
            'dashboard': 'dashboard',
            'products': 'products',
            'pick-requests': 'pickRequests',
            'pick-request': 'pickRequestDetail',
            'create-request': 'createRequest',
            'pick-scanner': 'pickScanner',
            'users': 'users'
        };

        // Define page objects
        this.pages = {
            login: LoginPage,
            dashboard: DashboardPage,
            products: ProductsPage,
            pickRequests: PickRequestsPage,
            pickRequestDetail: PickRequestDetailPage,
            createRequest: CreateRequestPage,
            pickScanner: PickScannerPage,
            users: UsersPage
        };
    },

    handleRoute() {
        const hash = window.location.hash.slice(1); // Remove #
        const [route, ...params] = hash.split('/');

        console.log('📍 Route:', route || 'root', 'Params:', params);

        // Check if user is authenticated
        const isAuthenticated = Auth.isAuthenticated();

        // Redirect to login if not authenticated
        if (!isAuthenticated && route !== 'login') {
            console.log('🔒 Not authenticated, redirecting to login');
            window.location.hash = 'login';
            return;
        }

        // Redirect to dashboard if authenticated and on login page
        if (isAuthenticated && (route === 'login' || route === '')) {
            console.log('✅ Already authenticated, redirecting to dashboard');
            window.location.hash = 'dashboard';
            return;
        }

        // Get page name
        const pageName = this.routes[route] || 'dashboard';
        const page = this.pages[pageName];

        if (!page) {
            console.error('❌ Page not found:', pageName);
            this.show404();
            return;
        }

        // Render page
        this.renderPage(page, params);
    },

    async renderPage(page, params = []) {
        try {
            console.log('🎨 Rendering page:', page.constructor ? page.constructor.name : 'Unknown');

            // Show loader
            this.showLoader();

            // Cleanup previous page
            if (this.currentPage && this.currentPage.cleanup) {
                console.log('🧹 Cleaning up previous page');
                this.currentPage.cleanup();
            }

            // Render navbar (only if authenticated)
            if (Auth.isAuthenticated()) {
                Navbar.render();
            } else {
                // Hide navbar on login page
                const nav = document.getElementById('navbar');
                if (nav) nav.innerHTML = '';
            }

            // Render new page
            await page.render(params);

            // Store current page
            this.currentPage = page;

            // Hide loader
            this.hideLoader();

            console.log('✅ Page rendered successfully');
        } catch (error) {
            console.error('❌ Page render failed:', error);
            this.hideLoader();
            this.showError('Failed to load page: ' + error.message);
        }
    },

    navigate(route) {
        console.log('🧭 Navigating to:', route);
        window.location.hash = route;
    },

    showLoader() {
        const content = document.getElementById('main-content');
        if (content) {
            content.innerHTML = `
                <div class="loader-container">
                    <div class="loader"></div>
                    <p style="margin-top: 1rem; color: var(--text-secondary);">Loading...</p>
                </div>
            `;
        }
    },

    hideLoader() {
        // Loader will be replaced by page content
    },

    showError(message) {
        const content = document.getElementById('main-content');
        if (content) {
            content.innerHTML = `
                <div class="container">
                    <div class="empty-state">
                        <i class="fas fa-exclamation-circle" style="color: var(--danger-color);"></i>
                        <h3>Error</h3>
                        <p>${Utils.escapeHtml(message)}</p>
                        <button class="btn btn-primary" onclick="location.reload()">
                            <i class="fas fa-redo"></i> Reload
                        </button>
                    </div>
                </div>
            `;
        }
        Notification.error(message);
    },

    show404() {
        const content = document.getElementById('main-content');
        if (content) {
            content.innerHTML = `
                <div class="container">
                    <div class="empty-state">
                        <i class="fas fa-map-marked-alt"></i>
                        <h3>Page Not Found</h3>
                        <p>The page you're looking for doesn't exist.</p>
                        <button class="btn btn-primary" onclick="App.navigate('dashboard')">
                            <i class="fas fa-home"></i> Go to Dashboard
                        </button>
                    </div>
                </div>
            `;
        }
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM Content Loaded');
    console.log('🔧 Starting app initialization...');

    try {
        App.init();
    } catch (error) {
        console.error('💥 Fatal error during initialization:', error);
        document.getElementById('main-content').innerHTML = `
            <div class="container">
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle" style="color: var(--danger-color); font-size: 3rem;"></i>
                    <h3>Application Failed to Start</h3>
                    <p style="color: var(--text-secondary); max-width: 500px; margin: 1rem auto;">
                        ${Utils.escapeHtml(error.message)}
                    </p>
                    <button class="btn btn-primary" onclick="location.reload()">
                        <i class="fas fa-redo"></i> Reload Application
                    </button>
                    <button class="btn btn-ghost" onclick="localStorage.clear(); location.reload()">
                        <i class="fas fa-trash"></i> Clear Data & Reload
                    </button>
                </div>
            </div>
        `;
    }
});

// Global error handler
window.addEventListener('error', (event) => {
    console.error('🔥 Global error:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('🔥 Unhandled promise rejection:', event.reason);
});
