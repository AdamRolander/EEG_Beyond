#!/usr/bin/env python3
"""
LSL WebSocket Bridge for EEG Stimulus Platform

This bridge receives events from the web-based stimulus platform
and pushes them as markers to a Lab Streaming Layer (LSL) outlet.

Requirements:
    pip install pylsl websockets asyncio

Usage:
    python lsl_bridge.py

Then in the browser console:
    EventLogger.connectLSL('ws://localhost:8765')
"""

import asyncio
import json
import logging
from datetime import datetime

try:
    import pylsl
except ImportError:
    print("ERROR: pylsl not installed. Run: pip install pylsl")
    exit(1)

try:
    import websockets
except ImportError:
    print("ERROR: websockets not installed. Run: pip install websockets")
    exit(1)

# Configuration
HOST = 'localhost'
PORT = 8765
STREAM_NAME = 'EEGStimulusMarkers'
STREAM_TYPE = 'Markers'

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class LSLBridge:
    def __init__(self):
        # Create LSL stream info
        self.info = pylsl.StreamInfo(
            name=STREAM_NAME,
            type=STREAM_TYPE,
            channel_count=2,  # [event_code, timestamp]
            nominal_srate=0,  # Irregular rate (event-driven)
            channel_format=pylsl.cf_double64,
            source_id='eeg_stimulus_platform'
        )
        
        # Add metadata
        desc = self.info.desc()
        channels = desc.append_child('channels')
        
        ch1 = channels.append_child('channel')
        ch1.append_child_value('label', 'EventCode')
        ch1.append_child_value('type', 'Marker')
        
        ch2 = channels.append_child('channel')
        ch2.append_child_value('label', 'BrowserTimestamp')
        ch2.append_child_value('type', 'Timestamp')
        
        # Create outlet
        self.outlet = pylsl.StreamOutlet(self.info)
        logger.info(f"LSL outlet created: {STREAM_NAME}")
    
    def push_marker(self, event_code: int, browser_timestamp: float):
        """Push a marker to the LSL stream."""
        sample = [float(event_code), browser_timestamp]
        self.outlet.push_sample(sample)
        logger.debug(f"Pushed marker: code={event_code}, time={browser_timestamp:.3f}")
    
    async def handle_websocket(self, websocket, path):
        """Handle incoming WebSocket connections."""
        client_addr = websocket.remote_address
        logger.info(f"Client connected: {client_addr}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get('type') == 'marker':
                        # Expected format: { type: 'marker', data: [code, timestamp] }
                        marker_data = data.get('data', [])
                        if len(marker_data) >= 2:
                            event_code = int(marker_data[0])
                            timestamp = float(marker_data[1])
                            self.push_marker(event_code, timestamp)
                    else:
                        # Generic event - extract code from data
                        event_code = data.get('numericCode', 0)
                        timestamp = data.get('absoluteTime', 0)
                        self.push_marker(event_code, timestamp)
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {message}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_addr}")
    
    async def start_server(self):
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket server on ws://{HOST}:{PORT}")
        
        async with websockets.serve(self.handle_websocket, HOST, PORT):
            logger.info("Server running. Press Ctrl+C to stop.")
            await asyncio.Future()  # Run forever


def main():
    print("""
╔═══════════════════════════════════════════════════════╗
║         LSL Bridge for EEG Stimulus Platform          ║
╠═══════════════════════════════════════════════════════╣
║  LSL Stream: {:<40} ║
║  WebSocket:  ws://{}:{:<27} ║
╚═══════════════════════════════════════════════════════╝
    """.format(STREAM_NAME, HOST, PORT))
    
    bridge = LSLBridge()
    
    try:
        asyncio.run(bridge.start_server())
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == '__main__':
    main()