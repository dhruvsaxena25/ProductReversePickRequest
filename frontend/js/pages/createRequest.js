// js/pages/createRequest.js - Create Request Page (FIXED)

const CreateRequestPage = {
    ws: null,

    async render() {
        const content = document.getElementById('main-content');

        content.innerHTML = `
            <div class="container-fluid">
                <h1 class="mb-6">
                    <i class="fas fa-plus-circle"></i> Create Pick Request
                </h1>

                <div class="grid grid-cols-3 gap-6">
                    <div style="grid-column: span 2;">
                        <div class="card">
                            <div class="card-header">
                                <h3 class="card-title">
                                    <i class="fas fa-camera"></i> Scan Products
                                </h3>
                                <div class="camera-status" id="camera-status"></div>
                            </div>
                            <div class="card-body">
                                <div class="camera-container">
                                    <video id="create-camera" class="camera-view" autoplay playsinline></video>
                                </div>
                                <div class="flex gap-2" style="margin-top: 1rem;">
                                    <button class="btn btn-primary" id="start-scan-btn" onclick="CreateRequestPage.startScanning()">
                                        <i class="fas fa-camera"></i> Start Scanner
                                    </button>
                                    <button class="btn btn-danger hidden" id="stop-scan-btn" onclick="CreateRequestPage.stopScanning()">
                                        <i class="fas fa-stop"></i> Stop Scanner
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Manual UPC Entry Card -->
                        <div class="card" style="margin-top: 1.5rem;">
                            <div class="card-header">
                                <h3 class="card-title">
                                    <i class="fas fa-keyboard"></i> Manual Entry
                                </h3>
                            </div>
                            <div class="card-body">
                                <form id="manual-upc-form" class="flex gap-2" onsubmit="CreateRequestPage.addManualUPC(event)">
                                    <div class="form-group" style="flex: 1; margin: 0;">
                                        <input 
                                            type="text" 
                                            class="form-input" 
                                            id="manual-upc-input" 
                                            placeholder="Enter UPC/EAN code..."
                                            pattern="[0-9]*"
                                            inputmode="numeric"
                                        >
                                    </div>
                                    <button type="submit" class="btn btn-primary">
                                        <i class="fas fa-plus"></i> Add to Cart
                                    </button>
                                </form>
                                <p class="form-help" style="margin-top: 0.5rem; margin-bottom: 0;">
                                    Enter UPC/EAN code (8-14 digits) and press Enter or click Add
                                </p>
                            </div>
                        </div>
                    </div>

                    <div class="cart-summary">
                        <div class="cart-header">
                            <div class="cart-title">
                                <i class="fas fa-shopping-cart"></i>
                                Cart
                                <span class="cart-count" id="cart-count">0</span>
                            </div>
                            <button class="btn btn-sm btn-ghost" onclick="CreateRequestPage.clearCart()" title="Clear Cart">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>

                        <ul class="cart-items" id="cart-items">
                            <div class="empty-state">
                                <i class="fas fa-shopping-cart"></i>
                                <p>Scan or enter products to add to cart</p>
                            </div>
                        </ul>

                        <div class="cart-footer">
                            <div class="cart-total">
                                <span class="cart-total-label">Total Items:</span>
                                <span class="cart-total-value" id="total-items">0</span>
                            </div>
                            <button class="btn btn-primary btn-block" onclick="CreateRequestPage.submitRequest()" id="submit-btn" disabled>
                                <i class="fas fa-check"></i> Submit Request
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        await this.initialize();
    },

    async initialize() {
        try {
            this.ws = new RequesterWebSocket();
            await this.ws.connect();

            this.ws.onInit = (data) => {
                Notification.success('Scanner ready!');
            };

            this.ws.onDetection = (data) => {
                // Camera scan detection
                if (data.found) {
                    this.ws.addItem(data.product.upc, 1);
                    this.showScanSuccess(data.product.name);
                } else {
                    Notification.error('Product not found in catalog');
                }
            };

            this.ws.onCartUpdate = (data) => {
                this.renderCart(data.items);
            };

            this.ws.onSubmitted = (data) => {
                Notification.success(`Request "${data.request_name}" created!`);
                setTimeout(() => {
                    App.navigate(`pick-request/${encodeURIComponent(data.request_name)}`);
                }, 1000);
            };
        } catch (error) {
            console.error('Failed to initialize:', error);
            Notification.error('Failed to connect to scanner');
        }
    },

    async startScanning() {
        try {
            await this.ws.startCamera('create-camera');
            document.getElementById('start-scan-btn').classList.add('hidden');
            document.getElementById('stop-scan-btn').classList.remove('hidden');
            document.getElementById('camera-status').innerHTML = `
                <div class="camera-status-badge">
                    <div class="status-indicator"></div>
                    Scanning
                </div>
            `;
        } catch (error) {
            console.error('Camera error:', error);
            Notification.error('Failed to start camera');
        }
    },

    stopScanning() {
        if (this.ws) {
            this.ws.stop();
        }
        document.getElementById('start-scan-btn').classList.remove('hidden');
        document.getElementById('stop-scan-btn').classList.add('hidden');
        document.getElementById('camera-status').innerHTML = '';
    },

    // FIXED: Manual UPC Entry - Uses backend's lookup_upc handler
    async addManualUPC(event) {
        event.preventDefault();

        const input = document.getElementById('manual-upc-input');
        const upc = input.value.trim();

        // Validate input
        if (!upc) {
            Notification.error('Please enter a UPC code');
            return;
        }

        // Validate UPC format (8-14 digits)
        if (!/^\d{8,14}$/.test(upc)) {
            Notification.error('Invalid UPC format. Must be 8-14 digits');
            input.focus();
            return;
        }

        // Check WebSocket connection
        if (!this.ws || !this.ws.ws || this.ws.ws.readyState !== WebSocket.OPEN) {
            Notification.error('Scanner not connected. Please refresh the page.');
            return;
        }

        // FIXED: Use lookup_upc (backend's manual UPC handler)
        this.ws.lookupUPC(upc);

        // Clear input and refocus for next entry
        input.value = '';
        input.focus();
    },

    // Show visual feedback for successful scan
    showScanSuccess(productName) {
        const statusDiv = document.getElementById('camera-status');
        if (!statusDiv) return;

        const originalContent = statusDiv.innerHTML;

        statusDiv.innerHTML = `
            <div class="camera-status-badge" style="background-color: #10b981; color: white;">
                <i class="fas fa-check-circle"></i>
                Scanned: ${Utils.escapeHtml(productName)}
            </div>
        `;

        setTimeout(() => {
            statusDiv.innerHTML = originalContent;
        }, 2000);
    },

    renderCart(items) {
        const cartItems = document.getElementById('cart-items');
        const cartCount = document.getElementById('cart-count');
        const totalItems = document.getElementById('total-items');
        const submitBtn = document.getElementById('submit-btn');

        if (!items || items.length === 0) {
            cartItems.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-shopping-cart"></i>
                    <p>Scan or enter products to add to cart</p>
                </div>
            `;
            cartCount.textContent = '0';
            totalItems.textContent = '0';
            submitBtn.disabled = true;
            return;
        }

        cartCount.textContent = items.length;
        totalItems.textContent = items.reduce((sum, item) => sum + item.quantity, 0);
        submitBtn.disabled = false;

        cartItems.innerHTML = items.map(item => `
            <li class="cart-item">
                <div class="cart-item-info">
                    <div class="cart-item-name">${Utils.escapeHtml(item.product_name)}</div>
                    <div class="cart-item-meta">UPC: ${item.upc}</div>
                </div>
                <div class="cart-item-quantity">
                    <button class="btn btn-sm btn-ghost" onclick="CreateRequestPage.decrementItem('${item.upc}')">
                        <i class="fas fa-minus"></i>
                    </button>
                    <span class="quantity-display">${item.quantity}</span>
                    <button class="btn btn-sm btn-ghost" onclick="CreateRequestPage.incrementItem('${item.upc}')">
                        <i class="fas fa-plus"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="CreateRequestPage.removeItem('${item.upc}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </li>
        `).join('');
    },

    incrementItem(upc) {
        const item = this.ws.cart.find(i => i.upc === upc);
        if (item) {
            this.ws.updateQuantity(upc, item.quantity + 1);
        }
    },

    decrementItem(upc) {
        const item = this.ws.cart.find(i => i.upc === upc);
        if (item && item.quantity > 1) {
            this.ws.updateQuantity(upc, item.quantity - 1);
        }
    },

    removeItem(upc) {
        this.ws.removeItem(upc);
    },

    clearCart() {
        Modal.confirm({
            title: 'Clear Cart',
            message: 'Are you sure you want to clear all items from the cart?',
            variant: 'danger',
            onConfirm: () => {
                this.ws.clearCart();
            }
        });
    },

    submitRequest() {
        const modal = Modal.create({
            title: 'Submit Request',
            content: `
                <form id="submit-request-form">
                    <div class="form-group">
                        <label class="form-label required">Request Name</label>
                        <input type="text" class="form-input" id="request-name" required>
                        <p class="form-help">Unique name for this pick request</p>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Priority</label>
                        <select class="form-select" id="request-priority">
                            <option value="low">Low</option>
                            <option value="normal" selected>Normal</option>
                            <option value="high">High</option>
                            <option value="urgent">Urgent</option>
                        </select>
                    </div>
                </form>
            `,
            actions: [
                { label: 'Cancel', variant: 'ghost', action: (m) => m.close() },
                { 
                    label: 'Submit', 
                    variant: 'primary',
                    action: () => {
                        const name = document.getElementById('request-name').value.trim();
                        const priority = document.getElementById('request-priority').value;

                        const validation = Utils.validateRequestName(name);
                        if (!validation.valid) {
                            Notification.error(validation.error);
                            return;
                        }

                        this.ws.submit(validation.name, priority);
                        modal.close();
                    }
                }
            ]
        });
    },

    cleanup() {
        if (this.ws) {
            this.ws.stop();
            this.ws = null;
        }
    }
};
