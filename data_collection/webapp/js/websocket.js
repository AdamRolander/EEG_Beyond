// ─── WebSocket → LSL Bridge Client ──────────────────────────
class LSLWebSocket {
  constructor() {
    this.socket = null;
    this.connected = false;
    this.markerCount = 0;
    this.onStatusChange = null;
    this.messageQueue = [];
  }

  connect(url) {
    return new Promise((resolve, reject) => {
      try {
        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
          console.log('[WS] Connected to LSL bridge');
          this.connected = true;
          this.flushQueue();
          if (this.onStatusChange) this.onStatusChange(true);
          resolve(true);
        };

        this.socket.onclose = () => {
          console.log('[WS] Disconnected');
          this.connected = false;
          if (this.onStatusChange) this.onStatusChange(false);
        };

        this.socket.onerror = (error) => {
          console.error('[WS] Error:', error);
          this.connected = false;
          if (this.onStatusChange) this.onStatusChange(false);
          reject(new Error('WebSocket connection failed'));
        };

        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.markerCount !== undefined) {
              this.markerCount = data.markerCount;
            }
          } catch (e) { /* ignore non-JSON */ }
        };

        setTimeout(() => {
          if (!this.connected) {
            reject(new Error('Connection timeout (5s)'));
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

  /**
   * Send a marker to the LSL bridge.
   * @param {number} code       - Marker code
   * @param {object} metadata   - Extra data (logged, not all sent to LSL)
   */
  sendMarker(code, metadata = {}) {
    const message = {
      type: 'marker',
      code: code,
      timestamp: performance.now(),
      trialNumber: metadata.trialNumber || 0,
      ...metadata
    };

    if (this.connected && this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
      this.markerCount++;
    } else {
      this.messageQueue.push(message);
      console.warn(`[WS] Queued marker ${code} (not connected)`);
    }

    console.log(`[Marker] code=${code}`, metadata);
  }

  flushQueue() {
    while (this.messageQueue.length > 0 && this.connected) {
      const msg = this.messageQueue.shift();
      this.socket.send(JSON.stringify(msg));
      this.markerCount++;
    }
  }
}

// Global instance
const lslBridge = new LSLWebSocket();