// js/pages/login.js - Login Page

const LoginPage = {
    render() {
        const content = document.getElementById('main-content');

        content.innerHTML = `
            <div class="auth-container">
                <div class="auth-card">
                    <div class="auth-logo">
                        <div class="auth-logo-icon">
                            <i class="fas fa-box"></i>
                        </div>
                        <h1>Pick Request System</h1>
                        <p>Sign in to your account</p>
                    </div>

                    <div id="auth-error" class="auth-error hidden">
                        <i class="fas fa-exclamation-circle"></i>
                        <span id="error-message"></span>
                    </div>

                    <form class="auth-form" id="login-form">
                        <div class="form-group">
                            <label class="form-label required">Username</label>
                            <input 
                                type="text" 
                                class="form-input" 
                                id="username" 
                                required
                                autocomplete="username"
                            >
                        </div>

                        <div class="form-group">
                            <label class="form-label required">Password</label>
                            <input 
                                type="password" 
                                class="form-input" 
                                id="password" 
                                required
                                autocomplete="current-password"
                            >
                        </div>

                        <div class="auth-remember">
                            <label>
                                <input type="checkbox" id="remember-me">
                                Remember me
                            </label>
                        </div>

                        <button type="submit" class="btn btn-primary btn-block btn-lg" id="login-btn">
                            <i class="fas fa-sign-in-alt"></i>
                            Sign In
                        </button>
                    </form>

                    <div class="auth-footer">
                        &copy; 2026 Pick Request System. All rights reserved.
                    </div>
                </div>
            </div>
        `;

        this.attachEvents();
    },

    attachEvents() {
        const form = document.getElementById('login-form');
        const btn = document.getElementById('login-btn');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;

            if (!username || !password) {
                this.showError('Please enter both username and password');
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';

            const result = await Auth.login(username, password);

            if (result.success) {
                Notification.success(`Welcome back, ${result.user.username}!`);
                App.navigate('dashboard');
            } else {
                this.showError(result.error || 'Invalid username or password');
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Sign In';
            }
        });
    },

    showError(message) {
        const errorDiv = document.getElementById('auth-error');
        const errorMsg = document.getElementById('error-message');
        errorMsg.textContent = message;
        errorDiv.classList.remove('hidden');
    },

    cleanup() {
        // Nothing to clean up
    }
};
