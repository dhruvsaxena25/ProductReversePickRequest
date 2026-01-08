// js/picker.js - Picker WebSocket Handler (FIXED)


class PickerWebSocket {
    constructor(requestName) {
        this.requestName = requestName;
        this.ws = null;
        this.videoElement = null;
        this.canvasElement = null;
        this.isScanning = false;
        this.frameInterval = null;
        this.onInit = null;
        this.onDetection = null;
        this.onUpdate = null;
        this.onWarning = null;
        this.onStatus = null;
    }


    async connect() {
        const token = Auth.getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        return new Promise((resolve, reject) => {
            // FIXED: Use correct API method
            this.ws = API.websocket.picker(this.requestName, token);

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
        console.log('WebSocket message:', data);

        switch (data.type) {
            case 'init':
                console.log('Picker initialized:', data);
                if (this.onInit) {
                    this.onInit(data);
                }
                break;

            case 'detection':
                console.log('Item scanned:', data);
                if (this.onDetection) {
                    this.onDetection(data);
                }
                if (data.in_request) {
                    Notification.success(`Scanned: ${data.product_name}`, 'Item Found');
                }
                break;

            case 'warning':
                console.warn('Invalid scan:', data);
                if (this.onWarning) {
                    this.onWarning(data);
                }
                Notification.warning(data.message, 'Not in Request');
                break;

            case 'update':
                console.log('Quantity updated:', data);
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
                if (data.code === 'AUTH_REQUIRED' || data.code === 'LOCKED') {
                    this.stop();
                }
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

            console.log('Camera started successfully');
        } catch (error) {
            console.error('Camera error:', error);

            // Better error messages
            if (error.name === 'NotAllowedError') {
                throw new Error('Camera permission denied. Please allow camera access.');
            } else if (error.name === 'NotFoundError') {
                throw new Error('No camera found on this device.');
            } else {
                throw new Error('Failed to start camera: ' + error.message);
            }
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
        }, 300);
    }


    manualUpdate(upc, quantity) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'manual_update',
                upc: upc,
                quantity: quantity
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

        if (this.ws) {
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'stop' }));
            }
            this.ws.close();
            this.ws = null;
        }
    }
}
