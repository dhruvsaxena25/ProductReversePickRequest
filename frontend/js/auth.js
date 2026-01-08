// js/auth.js - Authentication Manager

const Auth = {
    TOKEN_KEY: 'access_token',
    REFRESH_TOKEN_KEY: 'refresh_token',
    USER_KEY: 'current_user',

    getAccessToken() {
        // Get token as string (not parsed as JSON)
        return localStorage.getItem(this.TOKEN_KEY);
    },

    getRefreshToken() {
        // Get token as string (not parsed as JSON)
        return localStorage.getItem(this.REFRESH_TOKEN_KEY);
    },

    getCurrentUser() {
        // User should be stored as JSON object
        return Utils.storage.get(this.USER_KEY);
    },

    saveAuth(accessToken, refreshToken, user) {
        // Store tokens as plain strings
        localStorage.setItem(this.TOKEN_KEY, accessToken);
        localStorage.setItem(this.REFRESH_TOKEN_KEY, refreshToken);
        // Store user as JSON
        Utils.storage.set(this.USER_KEY, user);
    },

    isAuthenticated() {
        return !!this.getAccessToken();
    },

    hasRole(role) {
        const user = this.getCurrentUser();
        if (!user) return false;
        return user.role === role || user.role === 'admin';
    },

    canPick() {
        const user = this.getCurrentUser();
        if (!user) return false;
        return user.role === 'picker' || user.role === 'admin';
    },

    canRequest() {
        const user = this.getCurrentUser();
        if (!user) return false;
        return user.role === 'requester' || user.role === 'admin';
    },

    isAdmin() {
        return this.hasRole('admin');
    },

    async login(username, password) {
        try {
            const response = await API.auth.login(username, password);
            this.saveAuth(
                response.access_token,
                response.refresh_token,
                response.user
            );
            return { success: true, user: response.user };
        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    async refreshToken() {
        try {
            const refreshToken = this.getRefreshToken();
            if (!refreshToken) return false;

            const response = await API.auth.refresh(refreshToken);
            this.saveAuth(
                response.access_token,
                response.refresh_token,
                response.user
            );
            return true;
        } catch (error) {
            console.error('Token refresh failed:', error);
            return false;
        }
    },

    logout() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.REFRESH_TOKEN_KEY);
        Utils.storage.remove(this.USER_KEY);
    },

    async initialize() {
        if (!this.isAuthenticated()) {
            return false;
        }

        try {
            const user = await API.auth.getCurrentUser();
            Utils.storage.set(this.USER_KEY, user.user);
            return true;
        } catch (error) {
            const refreshed = await this.refreshToken();
            if (!refreshed) {
                this.logout();
                return false;
            }
            return true;
        }
    }
};
