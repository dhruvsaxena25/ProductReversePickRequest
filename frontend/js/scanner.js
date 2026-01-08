// js/scanner.js - General Scanner WebSocket Handler with Bounding Box Support

class ScannerWebSocket {
    constructor() {
        this.ws = null;
        this.videoElement = null;
        this.canvasElement = null;
        this.overlayCanvas = null;
        this.isScanning = false;
        this.frameInterval = null;
        this.onDetection = null;
        this.lastDetections = [];
    }

    async connect() {
        const token = Auth.getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        return new Promise((resolve, reject) => {
            this.ws = API.websocket.scanner(token);

            this.ws.onopen = () => {
                console.log('Scanner WebSocket connected');
                resolve();
            };

            this.ws.onerror = (error) => {
                console.error('Scanner WebSocket error:', error);
                reject(error);
            };

            this.ws.onclose = () => {
                console.log('Scanner WebSocket closed');
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
                console.log('Scanner initialized:', data);
                Notification.success(`Scanner ready. Found ${data.matched_products || 0} products.`);
                break;

            case 'detection':
                console.log('Barcode detected:', data);
                this.lastDetections = data.detections || [];
                this.drawBoundingBoxes();
                if (this.onDetection) {
                    this.onDetection(data.detections);
                }
                break;

            case 'error':
                console.error('Scanner error:', data);
                Notification.error(data.message, 'Scanner Error');
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

            // Determine color based on detection color
            let color;
            switch (detection.color) {
                case 'green':
                    color = '#10b981'; // Success green
                    break;
                case 'red':
                    color = '#ef4444'; // Error red
                    break;
                case 'yellow':
                    color = '#eab308'; // Warning yellow
                    break;
                case 'orange':
                    color = '#f97316'; // Orange
                    break;
                default:
                    color = '#10b981'; // Default to green
            }

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

    async initialize(queries = [], mode = 'catalog', mainCategory = null, subcategory = null) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('WebSocket not connected');
        }

        this.ws.send(JSON.stringify({
            type: 'init',
            queries: queries,
            mode: mode,
            main_category: mainCategory,
            subcategory: subcategory
        }));
    }

    async startCamera(videoElementId, canvasElementId = null) {
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

        if (canvasElementId) {
            this.canvasElement = document.getElementById(canvasElementId);
        }

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
        if (!this.canvasElement) {
            this.canvasElement = document.createElement('canvas');
        }

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
