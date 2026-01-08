// js/components/modal.js - Modal Dialog Component

const Modal = {
    create(options) {
        const modalId = `modal-${Utils.generateId()}`;

        const actionsHtml = options.actions ? options.actions.map(action => {
            const variant = action.variant || 'primary';
            return `<button class="btn btn-${variant}" data-action="${action.label}">${action.label}</button>`;
        }).join('') : '';

        const modalHtml = `
            <div class="modal" id="${modalId}">
                <div class="modal-dialog">
                    <div class="modal-header">
                        <h3 class="modal-title">${options.title}</h3>
                        <button class="modal-close" data-action="close">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        ${options.content}
                    </div>
                    ${actionsHtml ? `<div class="modal-footer">${actionsHtml}</div>` : ''}
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

        const modalEl = document.getElementById(modalId);

        setTimeout(() => modalEl.classList.add('show'), 10);

        const instance = {
            element: modalEl,
            close: () => {
                modalEl.classList.remove('show');
                setTimeout(() => modalEl.remove(), 200);
            }
        };

        modalEl.addEventListener('click', (e) => {
            if (e.target === modalEl) {
                instance.close();
            }
        });

        const closeBtn = modalEl.querySelector('[data-action="close"]');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => instance.close());
        }

        if (options.actions) {
            options.actions.forEach(action => {
                const btn = modalEl.querySelector(`[data-action="${action.label}"]`);
                if (btn && action.action) {
                    btn.addEventListener('click', () => action.action(instance));
                }
            });
        }

        return instance;
    },

    alert(options) {
        return this.create({
            title: options.title || 'Alert',
            content: `<p>${options.message}</p>`,
            actions: [
                { 
                    label: options.buttonText || 'OK', 
                    variant: 'primary',
                    action: (modal) => modal.close()
                }
            ]
        });
    },

    confirm(options) {
        return this.create({
            title: options.title || 'Confirm',
            content: `<p>${options.message}</p>`,
            actions: [
                { 
                    label: options.cancelText || 'Cancel', 
                    variant: 'ghost',
                    action: (modal) => {
                        if (options.onCancel) options.onCancel();
                        modal.close();
                    }
                },
                { 
                    label: options.confirmText || 'Confirm', 
                    variant: options.variant || 'primary',
                    action: (modal) => {
                        if (options.onConfirm) options.onConfirm();
                        modal.close();
                    }
                }
            ]
        });
    }
};
