// js/requester.js - Requester WebSocket Handler (FIXED)


class RequesterWebSocket {
    constructor() {
        this.ws = null;
        this.videoElement = null;
        this.canvasElement = null;
        this.isScanning = false;
        this.frameInterval = null;
        this.cart = [];
        this.categories = {};
        this.onInit = null;
        this.onDetection = null;
        this.onCartUpdate = null;
        this.onSubmitted = null;
    }


    async connect() {
        const token = Auth.getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }


        return new Promise((resolve, reject) => {
            this.ws = API.websocket.createRequest(token);


            this.ws.onopen = () => {
                console.log('Requester WebSocket connected');
                resolve();
            };


            this.ws.onerror = (error) => {
                console.error('Requester WebSocket error:', error);
                reject(error);
            };


            this.ws.onclose = () => {
                console.log('Requester WebSocket closed');
                this.stop();
            };


            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
        });
    }


    handleMessage(data) {
        switch (data.type) {
            case 'init':
                console.log('Requester initialized:', data);
                this.categories = data.categories || {};
                this.cart = data.cart || [];
                if (this.onInit) {
                    this.onInit(data);
                }
                break;


            case 'detection':
                console.log('Product detected:', data);
                if (this.onDetection) {
                    this.onDetection(data);
                }
                if (data.found) {
                    Notification.success(`Found: ${data.product.name}`, 'Product Detected');
                } else {
                    Notification.warning('Product not found in catalog', 'Unknown Barcode');
                }
                break;

            // NEW: Handle manual UPC lookup result
            case 'lookup_result':
                console.log('UPC lookup result:', data);
                if (data.found) {
                    // Automatically add to cart
                    this.addItem(data.product.upc, 1);
                    Notification.success(`Added: ${data.product.name}`, 'Product Found');
                } else {
                    Notification.error(`Product not found for UPC: ${data.input_upc}`, 'Not Found');
                }
                break;


            case 'cart_updated':
                console.log('Cart updated:', data);
                this.cart = data.items || [];
                if (this.onCartUpdate) {
                    this.onCartUpdate(data);
                }
                break;


            case 'submitted':
                console.log('Request submitted:', data);
                if (this.onSubmitted) {
                    this.onSubmitted(data);
                }
                Notification.success(`Request "${data.request_name}" created successfully!`, 'Success');
                break;


            case 'error':
                console.error('Requester error:', data);
                Notification.error(data.message, 'Error');
                break;
        }
    }


    async startCamera(videoElementId) {
        this.videoElement = document.getElementById(videoElementId);
        this.canvasElement = document.createElement('canvas');


        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });
            this.videoElement.srcObject = stream;
            await this.videoElement.play();


            this.isScanning = true;
            this.startSending();
        } catch (error) {
            console.error('Camera error:', error);
            throw error;
        }
    }


    startSending() {
        this.frameInterval = setInterval(() => {
            if (!this.isScanning || !this.videoElement || this.videoElement.readyState !== this.videoElement.HAVE_ENOUGH_DATA) {
                return;
            }


            const canvas = this.canvasElement;
            const video = this.videoElement;


            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;


            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);


            const imageData = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];


            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'frame',  // Backend expects "type", not "action"
                    frame: imageData
                }));
            }
        }, 500);
    }

    // NEW: Lookup UPC manually (for manual entry)
    lookupUPC(upc) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'lookup_upc',  // Backend's manual UPC lookup handler
                upc: upc
            }));
        }
    }


    addItem(upc, quantity) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'add_item',  // Backend uses snake_case
                upc: upc,
                quantity: parseInt(quantity)
            }));
        }
    }


    removeItem(upc) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'remove_item',
                upc: upc
            }));
        }
    }


    updateQuantity(upc, quantity) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'update_quantity',
                upc: upc,
                quantity: parseInt(quantity)
            }));
        }
    }


    clearCart() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'clear_cart'
            }));
        }
    }


    submit(name, priority = 'normal') {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'submit',
                name: name,
                priority: priority
            }));
        }
    }


    stop() {
        this.isScanning = false;


        if (this.frameInterval) {
            clearInterval(this.frameInterval);
            this.frameInterval = null;
        }


        if (this.videoElement && this.videoElement.srcObject) {
            this.videoElement.srcObject.getTracks().forEach(track => track.stop());
            this.videoElement.srcObject = null;
        }


        if (this.ws) {
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'stop' }));
            }
            this.ws.close();
            this.ws = null;
        }
    }
}
