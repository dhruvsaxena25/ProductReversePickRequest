// js/utils.js - Utility Functions

const Utils = {
    storage: {
        get(key) {
            try {
                const item = localStorage.getItem(key);
                if (!item) return null;
                
                // Try to parse as JSON, if it fails, return as string
                try {
                    return JSON.parse(item);
                } catch {
                    // If not valid JSON (like JWT tokens), return as string
                    return item;
                }
            } catch (error) {
                console.error('Storage get error:', error);
                return null;
            }
        },
        
        set(key, value) {
            try {
                // If value is string (like JWT token), store directly
                // If value is object, stringify it
                const stored = typeof value === 'string' ? value : JSON.stringify(value);
                localStorage.setItem(key, stored);
            } catch (error) {
                console.error('Storage set error:', error);
            }
        },
        
        remove(key) {
            try {
                localStorage.removeItem(key);
            } catch (error) {
                console.error('Storage remove error:', error);
            }
        }
    },

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    formatRelativeTime(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (seconds < 60) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        return this.formatDate(dateString);
    },

    formatNumber(num) {
        if (typeof num !== 'number') return '0';
        return num.toLocaleString('en-US');
    },

    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    },

    capitalize(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1);
    },

    formatStatus(status) {
        if (!status) return 'N/A';
        return status.split('_').map(word => this.capitalize(word)).join(' ');
    },

    formatPriority(priority) {
        if (!priority) return 'Normal';
        return this.capitalize(priority);
    },

    getStatusBadgeClass(status) {
        const classes = {
            'pending': 'status-pending',
            'in_progress': 'status-in-progress',
            'completed': 'status-completed',
            'paused': 'status-paused',
            'cancelled': 'status-cancelled',
            'partially_completed': 'status-partially-completed'
        };
        return classes[status] || 'badge-secondary';
    },

    getPriorityBadgeClass(priority) {
        const classes = {
            'low': 'badge-info',
            'normal': 'badge-secondary',
            'high': 'badge-warning',
            'urgent': 'badge-danger'
        };
        return classes[priority] || 'badge-secondary';
    },

    validateRequestName(name) {
        if (!name || name.trim().length === 0) {
            return { valid: false, error: 'Request name is required' };
        }

        const trimmed = name.trim();
        
        if (trimmed.length < 3) {
            return { valid: false, error: 'Request name must be at least 3 characters' };
        }

        if (trimmed.length > 50) {
            return { valid: false, error: 'Request name must be less than 50 characters' };
        }

        const validChars = /^[a-zA-Z0-9\s-]+$/;
        if (!validChars.test(trimmed)) {
            return { valid: false, error: 'Request name can only contain letters, numbers, spaces, and hyphens' };
        }

        return { valid: true, name: trimmed };
    },

    async copyToClipboard(text) {
        try {
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(text);
                return true;
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                return true;
            }
        } catch (error) {
            console.error('Copy to clipboard failed:', error);
            return false;
        }
    },

    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
};
