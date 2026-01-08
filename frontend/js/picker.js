// js/picker.js - Picker WebSocket Handler with Bounding Box Support

class PickerWebSocket {
    constructor(requestName) {
        this.ws = null;
        this.requestName = requestName;
        this.videoElement = null;
        this.canvasElement = null;
        this.overlayCanvas = null;
        this.isScanning = false;
        this.frameInterval = null;
        this.onInit = null;
        this.onDetection = null;
        this.onUpdate = null;
        this.onStatus = null;
        this.lastDetections = [];
    }

    async connect() {
        const token = Auth.getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        return new Promise((resolve, reject) => {
            this.ws = API.websocket.pickRequest(this.requestName, token);

            this.ws.onopen = () => {
                console.log('Picker WebSocket connected');
                resolve();
            };

            this.ws.onerror = (error) => {
                console.error('Picker WebSocket error:', error);
                reject(error);
            };

            this.ws.onclose = () => {
                console.log('Picker WebSocket closed');
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
                console.log('Picker initialized:', data);
                if (this.onInit) {
                    this.onInit(data);
                }
                break;

            case 'detection':
                console.log('Barcode detected:', data);
                // Store detections for bounding box drawing
                if (data.detections) {
                    this.lastDetections = data.detections;
                    this.drawBoundingBoxes();
                }
                
                if (data.in_request) {
                    Notification.success(`Scanned: ${data.product_name}`, 'Item Updated');
                } else {
                    Notification.warning('Item not in this request', 'Invalid Scan');
                }
                
                if (this.onDetection) {
                    this.onDetection(data);
                }
                break;

            case 'manual_scan':
                console.log('Manual scan result:', data);
                if (data.in_request) {
                    Notification.success(`Updated: ${data.product_name}`, 'Manual Entry');
                } else {
                    Notification.warning('UPC not in this request', 'Invalid UPC');
                }
                if (this.onDetection) {
                    this.onDetection(data);
                }
                break;

            case 'update':
                console.log('Item updated:', data);
                if (this.onUpdate) {
                    this.onUpdate(data);
                }
                break;

            case 'status':
                console.log('Status update:', data);
                if (this.onStatus) {
                    this.onStatus(data);
                }
                break;

            case 'error':
                console.error('Picker error:', data);
                Notification.error(data.message, 'Error');
                break;
        }
    }

    drawBoundingBoxes() {
        if (!this.overlayCanvas || !this.videoElement) return;

        const ctx = this.overlayCanvas.getContext('2d');
        const video = this.videoElement;

        // Clear previous drawings
        ctx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);

        // Skip if video not ready
        if (!video.videoWidth || !video.videoHeight) return;

        // Calculate scaling factors
        const scaleX = this.overlayCanvas.width / video.videoWidth;
        const scaleY = this.overlayCanvas.height / video.videoHeight;

        // Draw each detection
        this.lastDetections.forEach(detection => {
            if (!detection.rect) return;

            const { x, y, width, height } = detection.rect;
            
            // Scale coordinates to canvas size
            const scaledX = x * scaleX;
            const scaledY = y * scaleY;
            const scaledWidth = width * scaleX;
            const scaledHeight = height * scaleY;

            // Determine color based on whether item is in request
            const color = detection.in_request ? '#10b981' : '#ef4444'; // Green if in request, red if not

            // Draw rectangle
            ctx.strokeStyle = color;
            ctx.lineWidth = 3;
            ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

            // Draw label background
            const label = detection.product_name || detection.upc;
            ctx.font = '14px sans-serif';
            const textMetrics = ctx.measureText(label);
            const labelHeight = 20;
            const labelWidth = textMetrics.width + 10;

            ctx.fillStyle = color;
            ctx.fillRect(scaledX, scaledY - labelHeight, labelWidth, labelHeight);

            // Draw label text
            ctx.fillStyle = '#ffffff';
            ctx.fillText(label, scaledX + 5, scaledY - 5);
        });
    }

    async startCamera(videoElementId) {
        this.videoElement = document.getElementById(videoElementId);
        
        // Create or get overlay canvas
        const videoContainer = this.videoElement.parentElement;
        let existingOverlay = videoContainer.querySelector('.barcode-overlay');
        
        if (existingOverlay) {
            this.overlayCanvas = existingOverlay;
        } else {
            this.overlayCanvas = document.createElement('canvas');
            this.overlayCanvas.className = 'barcode-overlay';
            this.overlayCanvas.style.position = 'absolute';
            this.overlayCanvas.style.top = '0';
            this.overlayCanvas.style.left = '0';
            this.overlayCanvas.style.width = '100%';
            this.overlayCanvas.style.height = '100%';
            this.overlayCanvas.style.pointerEvents = 'none';
            videoContainer.style.position = 'relative';
            videoContainer.appendChild(this.overlayCanvas);
        }
        
        this.canvasElement = document.createElement('canvas');

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });
            this.videoElement.srcObject = stream;
            await this.videoElement.play();

            // Set overlay canvas size to match video element
            const resizeOverlay = () => {
                this.overlayCanvas.width = this.videoElement.offsetWidth;
                this.overlayCanvas.height = this.videoElement.offsetHeight;
            };
            
            this.videoElement.addEventListener('loadedmetadata', resizeOverlay);
            resizeOverlay();

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
                    type: 'frame',
                    frame: imageData
                }));
            }
        }, 500);
    }

    manualUpdate(upc, quantity) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'manual_update',
                upc: upc,
                quantity: parseInt(quantity)
            }));
        }
    }

    getStatus() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'get_status'
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

        // Clear overlay
        if (this.overlayCanvas) {
            const ctx = this.overlayCanvas.getContext('2d');
            ctx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);
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
