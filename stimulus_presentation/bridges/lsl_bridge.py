#!/usr/bin/env python3
"""
LSL Bridge for EEG Stimulus Platform
=====================================

This bridge receives stimulus events from the browser via WebSocket
and pushes them as markers to a Lab Streaming Layer (LSL) outlet.

The LSL markers can then be recorded alongside your EEG data in
software like LabRecorder, OpenViBE, BrainVision Recorder, etc.

INSTALLATION
------------
    pip install pylsl websockets

    Note: pylsl requires liblsl. On most systems pip handles this,
    but if you get errors, see: https://github.com/labstreaminglayer/pylsl

USAGE
-----
    1. Start this bridge BEFORE running the experiment:
       
       python lsl_bridge.py
    
    2. Start your EEG recording software and add the "EEGStimulusMarkers" stream
    
    3. In the browser experiment, the connection happens automatically when
       you check "Enable LSL Markers" before starting

    4. Run your experiment - markers will be sent in real-time

MARKER FORMAT
-------------
    The LSL stream sends markers with 3 channels:
    - Channel 1: Event code (integer)
    - Channel 2: Trial number
    - Channel 3: Browser timestamp (ms since experiment start)

    Event codes:
        1   = STIM_ONSET
        2   = STIM_OFFSET
        10  = RED
        11  = GREEN
        12  = BLUE
        13  = BLACK
        14  = WHITE
        20  = SPHERE
        21  = CUBE
        22  = PYRAMID
        23  = ICOSAHEDRON
        50  = PAUSE
        51  = RESUME
        99  = ABORT
        100 = EXPERIMENT_START
        101 = EXPERIMENT_END

TIMING NOTES
------------
    - Markers are timestamped by LSL when they ARRIVE at this bridge
    - WebSocket latency is typically 1-5ms on localhost
    - For sub-millisecond precision, use a parallel port instead
    - LSL's clock sync protocol handles drift between machines

TESTING
-------
    You can test the connection by running:
    
        python lsl_bridge.py --test
    
    This will send test markers every second.

"""

import asyncio
import json
import argparse
import sys
from datetime import datetime

# Check dependencies
try:
    import pylsl
except ImportError:
    print("ERROR: pylsl not installed")
    print("Run: pip install pylsl")
    print("\nIf that fails, see: https://github.com/labstreaminglayer/pylsl")
    sys.exit(1)

try:
    import websockets
except ImportError:
    print("ERROR: websockets not installed")
    print("Run: pip install websockets")
    sys.exit(1)


# =============================================================================
# Configuration
# =============================================================================

HOST = '0.0.0.0'      # Listen on all interfaces (use 'localhost' for local only)
PORT = 8765           # WebSocket port
STREAM_NAME = 'EEGStimulusMarkers'
STREAM_TYPE = 'Markers'

# Event code mapping (matches Config.eventCodes in JavaScript)
EVENT_CODES = {
    'EXPERIMENT_START': 100,
    'EXPERIMENT_END': 101,
    'STIM_ONSET': 1,
    'STIM_OFFSET': 2,
    'PAUSE': 50,
    'RESUME': 51,
    'ABORT': 99,
    'SKIP': 98,
    # Colors
    'COL_R': 10,
    'COL_G': 11,
    'COL_B': 12,
    'COL_K': 13,
    'COL_W': 14,
    # Shapes
    'SHP_SPH': 20,
    'SHP_CUB': 21,
    'SHP_PYR': 22,
    'SHP_ICO': 23,
}


# =============================================================================
# LSL Bridge Class
# =============================================================================

class LSLBridge:
    def __init__(self):
        self.outlet = None
        self.connected_clients = set()
        self.marker_count = 0
        self._create_outlet()
    
    def _create_outlet(self):
        """Create the LSL outlet for markers."""
        # Stream info: 3 channels (event_code, trial_number, browser_timestamp)
        info = pylsl.StreamInfo(
            name=STREAM_NAME,
            type=STREAM_TYPE,
            channel_count=3,
            nominal_srate=0,  # Irregular rate (event-driven)
            channel_format=pylsl.cf_double64,
            source_id='eeg_stimulus_platform_v1'
        )
        
        # Add metadata
        desc = info.desc()
        
        # Channel descriptions
        channels = desc.append_child('channels')
        
        ch1 = channels.append_child('channel')
        ch1.append_child_value('label', 'EventCode')
        ch1.append_child_value('type', 'Marker')
        ch1.append_child_value('unit', 'integer')
        
        ch2 = channels.append_child('channel')
        ch2.append_child_value('label', 'TrialNumber')
        ch2.append_child_value('type', 'Marker')
        ch2.append_child_value('unit', 'integer')
        
        ch3 = channels.append_child('channel')
        ch3.append_child_value('label', 'BrowserTime')
        ch3.append_child_value('type', 'Timestamp')
        ch3.append_child_value('unit', 'milliseconds')
        
        # Acquisition info
        acq = desc.append_child('acquisition')
        acq.append_child_value('manufacturer', 'EEG Stimulus Platform')
        acq.append_child_value('version', '1.0')
        
        # Create outlet
        self.outlet = pylsl.StreamOutlet(info)
        print(f"[LSL] Created outlet: {STREAM_NAME}")
        print(f"[LSL] Stream ID: eeg_stimulus_platform_v1")
    
    def push_marker(self, event_code: int, trial_number: int = 0, browser_time: float = 0):
        """
        Push a marker to the LSL stream.
        
        The marker is timestamped by LSL at the moment of this call,
        which provides the most accurate timing relative to EEG data.
        """
        sample = [float(event_code), float(trial_number), float(browser_time)]
        
        # Push with LSL's current timestamp
        self.outlet.push_sample(sample)
        self.marker_count += 1
        
        return pylsl.local_clock()
    
    def parse_event(self, data: dict) -> tuple:
        """Parse a browser event into (event_code, trial_number, browser_time)."""
        event_type = data.get('eventType', '')
        stim_code = data.get('stimulusCode', '')
        trial_num = data.get('trialNumber', 0)
        browser_time = data.get('relativeTime', 0)
        
        # Determine event code
        # Priority: stimulus code > event type
        if stim_code and stim_code in EVENT_CODES:
            event_code = EVENT_CODES[stim_code]
        elif event_type in EVENT_CODES:
            event_code = EVENT_CODES[event_type]
        else:
            event_code = 0  # Unknown event
        
        return event_code, trial_num, browser_time
    
    async def handle_client(self, websocket, path=None):
        """Handle a WebSocket client connection."""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.connected_clients.add(websocket)
        print(f"[WS] Client connected: {client_id}")
        print(f"[WS] Active connections: {len(self.connected_clients)}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    # Parse and push marker
                    event_code, trial_num, browser_time = self.parse_event(data)
                    lsl_time = self.push_marker(event_code, trial_num, browser_time)
                    
                    # Log
                    event_type = data.get('eventType', 'UNKNOWN')
                    stim_code = data.get('stimulusCode', '')
                    
                    print(f"[MARKER] {event_type:20s} code={event_code:3d} "
                          f"trial={trial_num:3d} lsl_t={lsl_time:.3f} "
                          f"{stim_code}")
                    
                    # Send acknowledgment
                    await websocket.send(json.dumps({
                        'status': 'ok',
                        'lsl_timestamp': lsl_time,
                        'marker_count': self.marker_count
                    }))
                    
                except json.JSONDecodeError:
                    print(f"[WS] Invalid JSON received: {message[:100]}")
                except Exception as e:
                    print(f"[WS] Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[WS] Client disconnected: {client_id} ({e.code})")
        finally:
            self.connected_clients.discard(websocket)
            print(f"[WS] Active connections: {len(self.connected_clients)}")
    
    async def run_server(self):
        """Start the WebSocket server."""
        print(f"[WS] Starting server on ws://{HOST}:{PORT}")
        
        # Use the newer API for websockets 10.0+
        try:
            async with websockets.serve(self.handle_client, HOST, PORT):
                print("[WS] Server running. Press Ctrl+C to stop.\n")
                await asyncio.Future()  # Run forever
        except Exception as e:
            print(f"[WS] Server error: {e}")
            raise


# =============================================================================
# Test Mode
# =============================================================================

async def test_mode(duration=30):
    """Send test markers for specified duration to verify LSL is working."""
    print("\n" + "="*60)
    print(f"TEST MODE - {duration} second simulated experiment")
    print("Open LabRecorder or another LSL client to verify reception")
    print("="*60 + "\n")
    
    bridge = LSLBridge()
    
    # Timing parameters (matching default experiment settings)
    STIM_DURATION = 2.0      # seconds
    ISI_DURATION = 1.0       # seconds
    TOTAL_DURATION = float(duration)
    
    # Stimuli to cycle through
    stimuli = [
        (10, 'RED'),
        (11, 'GREEN'),
        (12, 'BLUE'),
        (20, 'SPHERE'),
        (21, 'CUBE'),
        (22, 'PYRAMID'),
    ]
    
    print(f"Stimulus duration: {STIM_DURATION}s")
    print(f"Inter-stimulus interval: {ISI_DURATION}s")
    print(f"Total duration: {TOTAL_DURATION}s")
    print("-" * 60)
    
    # Send experiment start
    start_time = asyncio.get_event_loop().time()
    lsl_time = bridge.push_marker(100, 0, 0)
    print(f"[{0:5.1f}s] EXPERIMENT_START      code=100  lsl_t={lsl_time:.3f}")
    
    trial = 0
    stim_index = 0
    elapsed = 0
    
    while elapsed < TOTAL_DURATION:
        trial += 1
        stim_code, stim_name = stimuli[stim_index % len(stimuli)]
        stim_index += 1
        
        # ISI
        await asyncio.sleep(ISI_DURATION)
        elapsed = asyncio.get_event_loop().time() - start_time
        
        if elapsed >= TOTAL_DURATION:
            break
        
        # Stimulus onset
        browser_time = elapsed * 1000  # Convert to ms
        lsl_time = bridge.push_marker(1, trial, browser_time)  # STIM_ONSET
        bridge.push_marker(stim_code, trial, browser_time)      # Stimulus type
        print(f"[{elapsed:5.1f}s] STIM_ONSET  trial={trial:2d}  {stim_name:10s}  code={stim_code:3d}  lsl_t={lsl_time:.3f}")
        
        # Stimulus duration
        await asyncio.sleep(STIM_DURATION)
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Stimulus offset
        browser_time = elapsed * 1000
        lsl_time = bridge.push_marker(2, trial, browser_time)  # STIM_OFFSET
        print(f"[{elapsed:5.1f}s] STIM_OFFSET trial={trial:2d}  {stim_name:10s}  code=  2  lsl_t={lsl_time:.3f}")
    
    # Send experiment end
    elapsed = asyncio.get_event_loop().time() - start_time
    lsl_time = bridge.push_marker(101, 0, elapsed * 1000)
    print(f"[{elapsed:5.1f}s] EXPERIMENT_END        code=101  lsl_t={lsl_time:.3f}")
    
    print("-" * 60)
    print(f"\n[TEST] Complete!")
    print(f"[TEST] Total markers sent: {bridge.marker_count}")
    print(f"[TEST] Total trials: {trial}")
    print(f"[TEST] Actual duration: {elapsed:.1f}s")


# =============================================================================
# Main
# =============================================================================

def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           LSL Bridge for EEG Stimulus Platform                   ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  WebSocket:  ws://localhost:{port:<5}                              ║
║  LSL Stream: {name:<40}       ║
║                                                                  ║
║  Waiting for browser connection...                               ║
║                                                                  ║
║  Instructions:                                                   ║
║  1. Open your EEG recording software                             ║
║  2. Add the "{name}" stream                     ║
║  3. Start recording                                              ║
║  4. Run the browser experiment with "Enable LSL" checked         ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """.format(port=PORT, name=STREAM_NAME))


def main():
    global PORT
    
    parser = argparse.ArgumentParser(
        description='LSL Bridge for EEG Stimulus Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--test', action='store_true',
                        help='Run in test mode (send test markers)')
    parser.add_argument('--duration', type=int, default=30,
                        help='Test mode duration in seconds (default: 30)')
    parser.add_argument('--port', type=int, default=PORT,
                        help=f'WebSocket port (default: {PORT})')
    args = parser.parse_args()
    
    PORT = args.port
    
    if args.test:
        asyncio.run(test_mode(args.duration))
    else:
        print_banner()
        bridge = LSLBridge()
        try:
            asyncio.run(bridge.run_server())
        except KeyboardInterrupt:
            print("\n[LSL] Shutting down...")
            print(f"[LSL] Total markers sent: {bridge.marker_count}")


if __name__ == '__main__':
    main()