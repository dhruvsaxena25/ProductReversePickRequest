// js/api.js - API Client (WEBSOCKET FIXED)


const API = {
    baseURL: 'http://localhost:8000',
    wsURL: 'ws://localhost:8000',


    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;

        const config = {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        const token = Auth?.getAccessToken();
        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, config);

            if (response.status === 401) {
                const refreshed = await Auth?.refreshToken();
                if (refreshed) {
                    config.headers['Authorization'] = `Bearer ${Auth.getAccessToken()}`;
                    return await fetch(url, config);
                } else {
                    Auth?.logout();
                    window.location.hash = 'login';
                    throw new Error('Session expired. Please login again.');
                }
            }

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Request failed' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return response;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },

    // =========================================================================
    // WEBSOCKET CONNECTIONS
    // =========================================================================
    websocket: {
        createRequest: (token) => {
            return new WebSocket(`${API.wsURL}/ws/create-request?token=${token}`);
        },

        pickRequest: (requestName, token) => {
            return new WebSocket(`${API.wsURL}/ws/pick/${encodeURIComponent(requestName)}?token=${token}`);
        },

        // ADDED: Alias for picker
        picker: (requestName, token) => {
            return new WebSocket(`${API.wsURL}/ws/pick/${encodeURIComponent(requestName)}?token=${token}`);
        }
    },

    auth: {
        async login(username, password) {
            const response = await API.request('/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });

            return await response.json();
        },

        async refresh(refreshToken) {
            const response = await API.request('/auth/refresh', {
                method: 'POST',
                body: JSON.stringify({ refresh_token: refreshToken })
            });

            return await response.json();
        },

        async getCurrentUser() {
            const response = await API.request('/auth/me');
            return await response.json();
        }
    },

    users: {
        async list() {
            const response = await API.request('/users');
            return await response.json();
        },

        async get(userId) {
            const response = await API.request(`/users/${userId}`);
            return await response.json();
        },

        async create(userData) {
            const response = await API.request('/users', {
                method: 'POST',
                body: JSON.stringify(userData)
            });
            return await response.json();
        },

        async update(userId, userData) {
            const response = await API.request(`/users/${userId}`, {
                method: 'PUT',
                body: JSON.stringify(userData)
            });
            return await response.json();
        },

        async deactivate(userId) {
            const response = await API.request(`/users/${userId}`, {
                method: 'DELETE'
            });
            return await response.json();
        },

        async activate(userId) {
            const response = await API.request(`/users/${userId}/activate`, {
                method: 'POST'
            });
            return await response.json();
        }
    },

    products: {
        async list(params = {}) {
            const query = new URLSearchParams(params).toString();
            const endpoint = query ? `/products?${query}` : '/products';
            const response = await API.request(endpoint);
            return await response.json();
        },

        async search(query, filters = {}) {
            const params = new URLSearchParams({ q: query, ...filters });
            const response = await API.request(`/products/search?${params}`);
            return await response.json();
        },

        async getCategories() {
            const response = await API.request('/products/categories');
            return await response.json();
        }
    },

    pickRequests: {
        async list(filters = {}) {
            const params = new URLSearchParams(filters).toString();
            const endpoint = params ? `/pick-requests?${params}` : '/pick-requests';
            const response = await API.request(endpoint);
            return await response.json();
        },

        async resume(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}/resume`, {
                method: 'POST'
            });
            return await response.json();
        },

        async releaseLock(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}/release`, {
                method: 'POST'
            });
            return await response.json();
        },

        async get(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}`);
            return await response.json();
        },

        async create(requestData) {
            const response = await API.request('/pick-requests', {
                method: 'POST',
                body: JSON.stringify(requestData)
            });
            return await response.json();
        },

        async start(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}/start`, {
                method: 'POST'
            });
            return await response.json();
        },

        async submit(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}/submit`, {
                method: 'POST'
            });
            return await response.json();
        },

        async approve(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}/approve`, {
                method: 'POST'
            });
            return await response.json();
        },

        async cancel(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}/cancel`, {
                method: 'POST'
            });
            return await response.json();
        },

        async delete(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}`, {
                method: 'DELETE'
            });
            return await response.json();
        },

        async pause(requestName) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}/pause`, {
                method: 'POST'
            });
            return await response.json();
        },

        async pickItem(requestName, barcode) {
            const response = await API.request(`/pick-requests/${encodeURIComponent(requestName)}/pick`, {
                method: 'POST',
                body: JSON.stringify({ barcode: barcode })
            });
            return await response.json();
        }
    }
};
