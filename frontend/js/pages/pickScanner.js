// js/pages/pickScanner.js - Pick Scanner Page (WITH MANUAL UPC ENTRY)


const PickScannerPage = {
    ws: null,
    requestName: null,


    async render(params) {
        if (!params || params.length === 0) {
            App.navigate('pick-requests');
            return;
        }


        this.requestName = decodeURIComponent(params[0]);


        const content = document.getElementById('main-content');
        content.innerHTML = `
            <div class="container-fluid">
                <div class="mb-4">
                    <button class="btn btn-ghost" onclick="PickScannerPage.goBack()">
                        <i class="fas fa-arrow-left"></i> Back
                    </button>
                </div>


                <h1 class="mb-6">
                    <i class="fas fa-camera"></i> Picking: ${Utils.escapeHtml(this.requestName)}
                </h1>


                <div class="grid grid-cols-3 gap-6">
                    <div style="grid-column: span 2;">
                        <!-- Camera Scanner Card -->
                        <div class="card mb-6">
                            <div class="card-header">
                                <h3 class="card-title">Camera Scanner</h3>
                                <div class="camera-status" id="camera-status"></div>
                            </div>
                            <div class="card-body">
                                <div class="camera-container">
                                    <video id="pick-camera" class="camera-view" autoplay playsinline></video>
                                </div>
                                <div class="flex gap-2" style="margin-top: 1rem;">
                                    <button class="btn btn-primary" id="start-pick-btn" onclick="PickScannerPage.startScanning()">
                                        <i class="fas fa-camera"></i> Start Scanner
                                    </button>
                                    <button class="btn btn-danger hidden" id="stop-pick-btn" onclick="PickScannerPage.stopScanning()">
                                        <i class="fas fa-stop"></i> Stop Scanner
                                    </button>
                                    <button class="btn btn-warning" onclick="PickScannerPage.pauseRequest()">
                                        <i class="fas fa-pause"></i> Pause
                                    </button>
                                    <button class="btn btn-success" onclick="PickScannerPage.submitRequest()">
                                        <i class="fas fa-check"></i> Submit
                                    </button>
                                </div>
                            </div>
                        </div>


                        <!-- Manual UPC Entry Card -->
                        <div class="card mb-6">
                            <div class="card-header">
                                <h3 class="card-title">
                                    <i class="fas fa-keyboard"></i> Manual Entry
                                </h3>
                            </div>
                            <div class="card-body">
                                <div class="flex gap-2">
                                    <div class="form-group" style="flex: 1; margin: 0;">
                                        <input 
                                            type="text" 
                                            class="form-input" 
                                            id="manual-upc-input"
                                            placeholder="Enter UPC or barcode..."
                                            onkeypress="if(event.key === 'Enter') PickScannerPage.scanManualUPC()"
                                        >
                                    </div>
                                    <button class="btn btn-primary" onclick="PickScannerPage.scanManualUPC()">
                                        <i class="fas fa-barcode"></i> Scan
                                    </button>
                                </div>
                                <p class="form-help" style="margin-top: 0.5rem;">
                                    Type or paste a barcode and press Enter or click Scan
                                </p>
                            </div>
                        </div>


                        <!-- Items List Card -->
                        <div class="card">
                            <div class="card-header">
                                <h3 class="card-title">Items to Pick</h3>
                            </div>
                            <div class="card-body">
                                <ul class="pick-items-list" id="pick-items-list">
                                    <div class="loader-container">
                                        <div class="loader"></div>
                                    </div>
                                </ul>
                            </div>
                        </div>
                    </div>


                    <!-- Progress Sidebar -->
                    <div>
                        <div class="pick-progress">
                            <div class="progress-header">
                                <h4>Progress</h4>
                                <div class="progress-percentage" id="progress-percentage">0%</div>
                            </div>
                            <div class="progress-bar-container" style="margin-bottom: 1rem;">
                                <div class="progress-bar" id="progress-bar" style="width: 0%"></div>
                            </div>
                            <div class="progress-stats">
                                <span id="picked-count">0</span> / <span id="total-count">0</span> Items
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;


        await this.initialize();
    },


    async initialize() {
        try {
            this.ws = new PickerWebSocket(this.requestName);
            await this.ws.connect();


            this.ws.onInit = (data) => {
                this.renderItems(data.items);
                this.updateProgress(data.items);
                Notification.success('Ready to pick!');
            };


            this.ws.onDetection = (data) => {
                if (data.in_request) {
                    this.updateItemQuantity(data.upc, data.picked_quantity);
                    // Auto-clear manual input after successful scan
                    const input = document.getElementById('manual-upc-input');
                    if (input) input.value = '';
                }
            };


            this.ws.onUpdate = (data) => {
                this.updateItemQuantity(data.upc, data.picked_quantity);
            };


            this.ws.onStatus = (data) => {
                this.renderItems(data.items);
                this.updateProgress(data.items);
            };


        } catch (error) {
            console.error('Failed to initialize:', error);
            Notification.error('Failed to connect to picker');
        }
    },


    async startScanning() {
        try {
            await this.ws.startCamera('pick-camera');
            document.getElementById('start-pick-btn').classList.add('hidden');
            document.getElementById('stop-pick-btn').classList.remove('hidden');
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
        document.getElementById('start-pick-btn').classList.remove('hidden');
        document.getElementById('stop-pick-btn').classList.add('hidden');
        document.getElementById('camera-status').innerHTML = '';
    },


    // NEW: Manual UPC scan function
    scanManualUPC() {
        const input = document.getElementById('manual-upc-input');
        const upc = input.value.trim();

        if (!upc) {
            Notification.warning('Please enter a UPC');
            return;
        }

        console.log('Manual UPC scan:', upc);

        // Send manual scan through websocket
        if (this.ws && this.ws.ws && this.ws.ws.readyState === WebSocket.OPEN) {
            this.ws.ws.send(JSON.stringify({
                type: 'manual_scan',
                upc: upc
            }));

            // Visual feedback
            input.style.borderColor = 'var(--primary-color)';
            setTimeout(() => {
                input.style.borderColor = '';
            }, 500);
        } else {
            Notification.error('Scanner not connected');
        }
    },


    renderItems(items) {
        const listEl = document.getElementById('pick-items-list');


        if (!items || items.length === 0) {
            listEl.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-clipboard-check"></i>
                    <p>No items to pick</p>
                </div>
            `;
            return;
        }


        listEl.innerHTML = items.map(item => {
            const isComplete = item.picked_quantity >= item.requested_quantity;
            return `
                <li class="pick-item ${isComplete ? 'complete' : ''}" id="item-${item.upc}">
                    <div class="pick-item-header">
                        <div class="pick-item-name">${Utils.escapeHtml(item.product_name)}</div>
                        ${isComplete ? '<i class="fas fa-check-circle" style="color: var(--secondary-color);"></i>' : ''}
                    </div>
                    <div class="pick-item-body">
                        <div class="pick-item-upc">UPC: ${item.upc}</div>
                        <div class="pick-item-quantity">
                            <span id="qty-${item.upc}">${item.picked_quantity}</span> / ${item.requested_quantity}
                        </div>
                    </div>
                    <div class="quantity-controls">
                        <button class="btn btn-sm btn-ghost" onclick="PickScannerPage.decrementItem('${item.upc}')">
                            <i class="fas fa-minus"></i>
                        </button>
                        <input 
                            type="number" 
                            class="quantity-input" 
                            id="input-${item.upc}" 
                            value="${item.picked_quantity}"
                            min="0"
                            max="${item.requested_quantity}"
                        >
                        <button class="btn btn-sm btn-ghost" onclick="PickScannerPage.incrementItem('${item.upc}')">
                            <i class="fas fa-plus"></i>
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="PickScannerPage.updateItem('${item.upc}')">
                            Update
                        </button>
                    </div>
                </li>
            `;
        }).join('');


        this.updateProgress(items);
    },


    updateItemQuantity(upc, quantity) {
        const qtyEl = document.getElementById(`qty-${upc}`);
        const inputEl = document.getElementById(`input-${upc}`);
        const itemEl = document.getElementById(`item-${upc}`);


        if (qtyEl) qtyEl.textContent = quantity;
        if (inputEl) inputEl.value = quantity;


        if (itemEl) {
            const requestedQty = parseInt(itemEl.querySelector('.pick-item-quantity').textContent.split('/')[1].trim());
            if (quantity >= requestedQty) {
                itemEl.classList.add('complete');
            } else {
                itemEl.classList.remove('complete');
            }
        }


        this.ws.getStatus();
    },


    updateProgress(items) {
        if (!items || items.length === 0) return;


        const picked = items.filter(i => i.picked_quantity >= i.requested_quantity).length;
        const total = items.length;
        const percentage = Math.round((picked / total) * 100);


        document.getElementById('picked-count').textContent = picked;
        document.getElementById('total-count').textContent = total;
        document.getElementById('progress-percentage').textContent = `${percentage}%`;
        document.getElementById('progress-bar').style.width = `${percentage}%`;
    },


    incrementItem(upc) {
        const inputEl = document.getElementById(`input-${upc}`);
        if (inputEl) {
            inputEl.value = parseInt(inputEl.value) + 1;
            this.updateItem(upc);
        }
    },


    decrementItem(upc) {
        const inputEl = document.getElementById(`input-${upc}`);
        if (inputEl && parseInt(inputEl.value) > 0) {
            inputEl.value = parseInt(inputEl.value) - 1;
            this.updateItem(upc);
        }
    },


    updateItem(upc) {
        const inputEl = document.getElementById(`input-${upc}`);
        if (inputEl) {
            const quantity = parseInt(inputEl.value);
            this.ws.manualUpdate(upc, quantity);
        }
    },


    async pauseRequest() {
        Modal.confirm({
            title: 'Pause Picking',
            message: 'Do you want to pause picking? You can resume later.',
            onConfirm: async () => {
                try {
                    await API.pickRequests.pause(this.requestName);
                    Notification.info('Request paused');
                    App.navigate('pick-requests');
                } catch (error) {
                    Notification.error(error.message);
                }
            }
        });
    },


    async submitRequest() {
        Modal.confirm({
            title: 'Submit Pick Request',
            message: 'Are you sure you want to submit this pick request?',
            variant: 'success',
            onConfirm: async () => {
                try {
                    await API.pickRequests.submit(this.requestName);
                    Notification.success('Pick request submitted successfully!');
                    App.navigate(`pick-request/${encodeURIComponent(this.requestName)}`);
                } catch (error) {
                    Notification.error(error.message);
                }
            }
        });
    },


    goBack() {
        Modal.confirm({
            title: 'Leave Picking',
            message: 'Your progress will be saved. You can resume later.',
            onConfirm: () => {
                App.navigate(`pick-request/${encodeURIComponent(this.requestName)}`);
            }
        });
    },


    cleanup() {
        if (this.ws) {
            this.ws.stop();
            this.ws = null;
        }
        this.requestName = null;
    }
};
