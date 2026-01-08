// js/components/notifications.js - Toast Notification Component

const Notification = {
    container: null,

    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'notification-container';
            document.body.appendChild(this.container);
        }
    },

    show(message, title = '', type = 'info', duration = 5000) {
        this.init();

        const id = `notification-${Utils.generateId()}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        const notificationHtml = `
            <div class="notification ${type}" id="${id}">
                <div class="notification-icon">
                    <i class="fas ${icons[type]}"></i>
                </div>
                <div class="notification-content">
                    ${title ? `<div class="notification-title">${Utils.escapeHtml(title)}</div>` : ''}
                    <div class="notification-message">${Utils.escapeHtml(message)}</div>
                </div>
                <button class="notification-close" onclick="Notification.close('${id}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        this.container.insertAdjacentHTML('beforeend', notificationHtml);

        if (duration > 0) {
            setTimeout(() => this.close(id), duration);
        }
    },

    success(message, title = 'Success') {
        this.show(message, title, 'success');
    },

    error(message, title = 'Error') {
        this.show(message, title, 'error');
    },

    warning(message, title = 'Warning') {
        this.show(message, title, 'warning');
    },

    info(message, title = 'Info') {
        this.show(message, title, 'info');
    },

    close(id) {
        const notification = document.getElementById(id);
        if (notification) {
            notification.classList.add('hiding');
            setTimeout(() => notification.remove(), 300);
        }
    }
};
