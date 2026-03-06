#!/usr/bin/env python3
"""
WebSocket to LSL Bridge for EEG Perception Experiments

This script:
1. Runs a WebSocket server that receives markers from the web app
2. Pushes markers to a local LSL stream with server-side timestamps
3. Provides accurate timing by timestamping on receipt (not browser time)

Usage:
    python lsl_bridge.py [--port 8765]

The web app connects via: ws://YOUR_PC_IP:8765
"""

import asyncio
import json
import argparse
from datetime import datetime

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
            source_id='perception_bridge_v1'
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
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{timestamp}] #{self.marker_count:04d} | "
                              f"code={code:3d} trial={trial:3d} | "
                              f"lsl_t={lsl_time:.3f}")

                        # Send acknowledgment
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

    async def broadcast(self, message):
        """Broadcast message to all connected clients."""
        if self.clients:
            await asyncio.gather(*[client.send(message) for client in self.clients])


async def main(port):
    bridge = LSLBridge()

    # Get local IP for display
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║         EEG Perception - WebSocket LSL Bridge                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  WebSocket Server: ws://{local_ip}:{port:<34}║
║  LSL Stream:       PerceptionMarkers                         ║
║                                                              ║
║  SETUP:                                                      ║
║  1. Start LabRecorder, add "PerceptionMarkers" stream        ║
║  2. In web app, set bridge URL to: ws://{local_ip}:{port:<14}║
║  3. Click "Connect to LSL Bridge" in the web app             ║
║  4. Enter VR and run experiment                              ║
║                                                              ║
║  Press Ctrl+C to stop                                        ║
╚══════════════════════════════════════════════════════════════╝
""")

    async with websockets.serve(bridge.handle_client, "0.0.0.0", port):
        await asyncio.Future()  # Run forever


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='WebSocket to LSL Bridge')
    parser.add_argument('--port', '-p', type=int, default=8765, help='WebSocket port')
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Bridge stopped")
