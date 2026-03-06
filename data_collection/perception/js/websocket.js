// WebSocket client for LSL bridge communication
class LSLWebSocket {
  constructor() {
    this.socket = null;
    this.ed = false;
    this.markerCount = 0;
    this.onStatusChange = null;
    this.messageQueue = [];
  }

  connect(url) {

    return new Promise((resolve, reject) => {
      try {
        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
          console.log('[WebSocket] Connected to LSL bridge');
          this.connected = true;
          this.flushQueue();
          if (this.onStatusChange) this.onStatusChange(true);
          resolve(true);
        };

        this.socket.onclose = () => {
          console.log('[WebSocket] Disconnected');
          this.connected = false;
          if (this.onStatusChange) this.onStatusChange(false);
        };

        this.socket.onerror = (error) => {
          console.error('[WebSocket] Error:', error);
          this.connected = false;
          if (this.onStatusChange) this.onStatusChange(false);
          reject(error);
        };

        this.socket.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.markerCount !== undefined) {
            this.markerCount = data.markerCount;
          }
        };

        // Timeout after 5 seconds
        setTimeout(() => {
          if (!this.connected) {
            reject(new Error('Connection timeout'));
          }
        }, 5000);

      } catch (e) {
        reject(e);
      }
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.connected = false;
  }

  sendMarker(code, data = {}) {
    const message = {
      type: 'marker',
      code: code,
      timestamp: performance.now(),
      ...data
    };

    if (this.connected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
      this.markerCount++;
    } else {
      this.messageQueue.push(message);
    }

    console.log(`[Marker] ${code}`, data);
  }

  flushQueue() {
    while (this.messageQueue.length > 0 && this.connected) {
      const msg = this.messageQueue.shift();
      this.socket.send(JSON.stringify(msg));
    }
  }
}

// Global instance
const lslBridge = new LSLWebSocket();
