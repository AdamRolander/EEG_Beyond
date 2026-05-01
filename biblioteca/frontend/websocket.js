import { WS_URL } from './config.js';

// Thin wrapper over native WebSocket: type-routed dispatch + queued sends.
// Usage:
//   const ws = new WS();
//   ws.on('session_ready', m => console.log(m));
//   await ws.connect();
//   ws.send('start_phase', { phase: 'ICA_CAL' });
export class WS {
  constructor() {
    this.ws = null;
    this.handlers = new Map();
    this.connected = false;
    this.queue = [];
    this.onCloseCb = null;
  }

  connect(url = WS_URL) {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(url);
      this.ws.onopen = () => {
        this.connected = true;
        while (this.queue.length) this.ws.send(this.queue.shift());
        resolve();
      };
      this.ws.onmessage = (event) => {
        let msg;
        try { msg = JSON.parse(event.data); }
        catch (e) { console.error('[WS] bad JSON:', event.data); return; }
        const handler = this.handlers.get(msg.type);
        if (handler) handler(msg);
        else console.warn('[WS] no handler for type:', msg.type, msg);
      };
      this.ws.onerror = (e) => { console.error('[WS] error', e); reject(e); };
      this.ws.onclose = () => {
        this.connected = false;
        if (this.onCloseCb) this.onCloseCb();
      };
    });
  }

  send(type, payload = {}) {
    const msg = JSON.stringify({ type, ...payload });
    if (this.connected && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(msg);
    } else {
      this.queue.push(msg);
    }
  }

  on(type, handler) {
    this.handlers.set(type, handler);
  }

  onClose(cb) { this.onCloseCb = cb; }
}