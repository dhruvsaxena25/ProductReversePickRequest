// js/scanner.js - General Scanner WebSocket Handler

class ScannerWebSocket {
    constructor() {
        this.ws = null;
        this.videoElement = null;
        this.canvasElement = null;
        this.isScanning = false;
        this.frameInterval = null;
        this.onDetection = null;
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
        if (canvasElementId) {
            this.canvasElement = document.getElementById(canvasElementId);
        }

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

        if (this.ws) {
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'stop' }));
            }
            this.ws.close();
            this.ws = null;
        }
    }
}
