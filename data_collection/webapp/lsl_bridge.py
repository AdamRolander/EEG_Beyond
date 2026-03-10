#!/usr/bin/env python3
"""
WebSocket (ws:// or wss://) → LSL Bridge for EEG Perception–Imagery Experiments

Supports both plain WebSocket and secure WebSocket (TLS).
For wss://, generate a self-signed cert:
    openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes

Usage:
    python lsl_bridge.py [--port 8765]
    python lsl_bridge.py --port 8765 --ssl-cert cert.pem --ssl-key key.pem
"""

import asyncio
import json
import argparse
import ssl as _ssl
from datetime import datetime
from pathlib import Path

try:
    import websockets
except ImportError:
    print("ERROR: websockets not installed")
    print("Run: pip install websockets")
    exit(1)

try:
    import pylsl
except ImportError:
    print("ERROR: pylsl not installed")
    print("Run: pip install pylsl")
    exit(1)


class LSLBridge:
    def __init__(self):
        self.outlet = None
        self.marker_count = 0
        self.clients = set()
        self._create_outlet()

    def _create_outlet(self):
        """Create LSL outlet for markers."""
        info = pylsl.StreamInfo(
            name='PerceptionMarkers',
            type='Markers',
            channel_count=2,
            nominal_srate=0,
            channel_format=pylsl.cf_int32,
            source_id='perception_imagery_bridge_v2'
        )

        desc = info.desc()
        channels = desc.append_child('channels')

        ch1 = channels.append_child('channel')
        ch1.append_child_value('label', 'MarkerCode')
        ch1.append_child_value('type', 'Marker')

        ch2 = channels.append_child('channel')
        ch2.append_child_value('label', 'TrialNumber')
        ch2.append_child_value('type', 'Marker')

        self.outlet = pylsl.StreamOutlet(info)
        print(f"[LSL] Stream created: PerceptionMarkers")

    def push_marker(self, code, trial_number=0):
        """Push marker with LSL timestamp."""
        sample = [int(code), int(trial_number)]
        self.outlet.push_sample(sample)
        self.marker_count += 1
        lsl_time = pylsl.local_clock()
        return lsl_time

    async def handle_client(self, websocket):
        """Handle WebSocket client connection."""
        self.clients.add(websocket)
        client_addr = websocket.remote_address
        print(f"[WS] Client connected: {client_addr}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)

                    if data.get('type') == 'marker':
                        code  = data.get('code', 0)
                        trial = data.get('trialNumber', 0)

                        # Push to LSL with server timestamp
                        lsl_time = self.push_marker(code, trial)

                        # Log
                        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{ts}] #{self.marker_count:04d} | "
                              f"code={code:3d} trial={trial:3d} | "
                              f"lsl_t={lsl_time:.3f}")

                        # Acknowledge
                        await websocket.send(json.dumps({
                            'status': 'ok',
                            'markerCount': self.marker_count,
                            'lslTime': lsl_time
                        }))

                except json.JSONDecodeError:
                    print(f"[WS] Invalid JSON: {message}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"[WS] Client disconnected: {client_addr}")


async def main(port, ssl_cert=None, ssl_key=None):
    bridge = LSLBridge()

    # SSL context for wss://
    ssl_ctx = None
    protocol = "ws"
    if ssl_cert and ssl_key:
        ssl_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(ssl_cert, ssl_key)
        protocol = "wss"
        print(f"[SSL] Loaded cert={ssl_cert}, key={ssl_key}")

    # Get local IP
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    url = f"{protocol}://{local_ip}:{port}"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║       Perception–Imagery  ·  WebSocket → LSL Bridge          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Server:     {url:<47}║
║  Protocol:   {protocol.upper():<47}║
║  LSL Stream: PerceptionMarkers                               ║
║                                                              ║
║  SETUP:                                                      ║
║  1. Start LabRecorder → add "PerceptionMarkers"              ║
║  2. In the web app, set Bridge URL to:                       ║
║     {url:<55}║
║  3. Click "Connect to LSL Bridge"                            ║
║  4. Configure & run experiment                               ║
║                                                              ║""")

    if ssl_ctx:
        print(f"""║  NOTE: Self-signed cert — visit https://{local_ip}:{port}         ║
║  in your browser first and accept the certificate.           ║
║                                                              ║""")

    print(f"""║  Press Ctrl+C to stop                                        ║
╚══════════════════════════════════════════════════════════════╝
""")

    async with websockets.serve(bridge.handle_client, "0.0.0.0", port, ssl=ssl_ctx):
        await asyncio.Future()  # Run forever


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='WebSocket → LSL Bridge (supports ws:// and wss://)'
    )
    parser.add_argument('--port', '-p', type=int, default=8765,
                        help='WebSocket port (default: 8765)')
    parser.add_argument('--ssl-cert', type=str, default=None,
                        help='Path to SSL certificate (PEM) for wss://')
    parser.add_argument('--ssl-key', type=str, default=None,
                        help='Path to SSL private key (PEM) for wss://')
    args = parser.parse_args()

    # Auto-detect cert files in current directory
    if args.ssl_cert is None and Path('cert.pem').exists() and Path('key.pem').exists():
        print("[SSL] Auto-detected cert.pem and key.pem in current directory")
        args.ssl_cert = 'cert.pem'
        args.ssl_key = 'key.pem'

    try:
        asyncio.run(main(args.port, args.ssl_cert, args.ssl_key))
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Bridge stopped")