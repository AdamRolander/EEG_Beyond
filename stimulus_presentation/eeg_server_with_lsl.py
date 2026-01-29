#!/usr/bin/env python3
"""
EEG Experiment Server with Integrated LSL
==========================================

This server:
1. Serves your HTML/JS experiment via HTTP (accessible via ngrok)
2. Receives event notifications from the browser via HTTP POST
3. Pushes markers DIRECTLY to LSL (local, no network issues!)

ARCHITECTURE
------------
    [Meta Quest Browser]
         │
         │ HTTP (via ngrok)
         ├──> GET /  ──────> [Serve HTML experiment]
         │
         └──> POST /event ──> [Python Server on PC]
                                    │
                                    └──> [LSL Local] ──> [LabRecorder]

WHY THIS IS BETTER
------------------
- ✓ Browser only sends simple HTTP requests (works anywhere)
- ✓ LSL stays 100% local (no network issues)
- ✓ Perfect timing (server timestamp, not browser)
- ✓ Simple setup (one script)
- ✓ Works with ngrok effortlessly

INSTALLATION
------------
    pip install flask flask-cors pylsl

USAGE
-----
    1. Put your experiment HTML in a folder (e.g., ./experiment/)
    
    2. Start server:
       python eeg_server_with_lsl.py --dir ./experiment
    
    3. Tunnel with ngrok:
       ngrok http 8080
    
    4. Open ngrok URL on Meta Quest
    
    5. Start LabRecorder and add "EEGStimulusMarkers" stream
    
    6. Run experiment - markers sent automatically!

JAVASCRIPT INTEGRATION
----------------------
In your experiment HTML, replace WebSocket code with:

    // Send event to server (which will handle LSL)
    async function sendEvent(eventType, stimulusCode, trialNumber) {
        await fetch('/event', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                eventType: eventType,
                stimulusCode: stimulusCode,
                trialNumber: trialNumber,
                relativeTime: performance.now()
            })
        });
    }
    
    // Example usage:
    sendEvent('STIM_ONSET', 'COL_R', 1);
    sendEvent('STIM_OFFSET', 'COL_R', 1);

"""

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import pylsl
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# Check dependencies
try:
    import pylsl
except ImportError:
    print("ERROR: pylsl not installed")
    print("Run: pip install pylsl")
    sys.exit(1)

try:
    from flask import Flask
except ImportError:
    print("ERROR: Flask not installed")
    print("Run: pip install flask flask-cors")
    sys.exit(1)


# =============================================================================
# Configuration
# =============================================================================

HOST = '0.0.0.0'
PORT = 8080
STREAM_NAME = 'EEGStimulusMarkers'

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
    'COL_R': 10, 'COL_G': 11, 'COL_B': 12, 'COL_K': 13, 'COL_W': 14,
    # Shapes
    'SHP_SPH': 20, 'SHP_CUB': 21, 'SHP_PYR': 22, 'SHP_ICO': 23,
}


# =============================================================================
# LSL Integration
# =============================================================================

class LSLMarkerStream:
    """Local LSL marker stream."""
    
    def __init__(self):
        self.outlet = None
        self.marker_count = 0
        self.experiment_start_time = None
        self._create_outlet()
    
    def _create_outlet(self):
        """Create LSL outlet."""
        info = pylsl.StreamInfo(
            name=STREAM_NAME,
            type='Markers',
            channel_count=3,
            nominal_srate=0,
            channel_format=pylsl.cf_double64,
            source_id='integrated_server_v1'
        )
        
        desc = info.desc()
        channels = desc.append_child('channels')
        
        for label in ['EventCode', 'TrialNumber', 'BrowserTime']:
            ch = channels.append_child('channel')
            ch.append_child_value('label', label)
            ch.append_child_value('type', 'Marker')
        
        self.outlet = pylsl.StreamOutlet(info)
        print(f"[LSL] ✓ Stream created: {STREAM_NAME}")
    
    def push_marker(self, event_code, trial_number, browser_time):
        """Push marker with server-side LSL timestamp."""
        sample = [float(event_code), float(trial_number), float(browser_time)]
        
        # LSL timestamp is generated HERE on the server
        # This is the most accurate timestamp relative to EEG
        self.outlet.push_sample(sample)
        self.marker_count += 1
        
        return pylsl.local_clock()
    
    def parse_and_push(self, data):
        """Parse event data and push to LSL."""
        event_type = data.get('eventType', '')
        stim_code = data.get('stimulusCode', '')
        trial_num = data.get('trialNumber', 0)
        browser_time = data.get('relativeTime', 0)
        
        # Determine event code
        if stim_code and stim_code in EVENT_CODES:
            event_code = EVENT_CODES[stim_code]
        elif event_type in EVENT_CODES:
            event_code = EVENT_CODES[event_type]
        else:
            event_code = 0
        
        # Push to LSL
        lsl_time = self.push_marker(event_code, trial_num, browser_time)
        
        # Log
        event_name = stim_code or event_type or 'UNKNOWN'
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] "
              f"#{self.marker_count:04d} | {event_name:20s} | "
              f"code={event_code:3d} trial={trial_num:3d} | lsl_t={lsl_time:.3f}")
        
        return lsl_time, event_code


# Create LSL stream
lsl_stream = LSLMarkerStream()


# =============================================================================
# Flask App
# =============================================================================

app = Flask(__name__)
CORS(app)

# Directory to serve files from
SERVE_DIR = None


@app.route('/')
def index():
    """Serve index.html or directory listing."""
    if SERVE_DIR:
        index_file = Path(SERVE_DIR) / 'index.html'
        if index_file.exists():
            return send_file(index_file)
        else:
            # List available files
            files = list(Path(SERVE_DIR).glob('*.html'))
            if files:
                return f"""
                <html>
                <head><title>EEG Experiment Files</title></head>
                <body style="font-family: sans-serif; padding: 40px;">
                    <h1>Available Experiments</h1>
                    <ul>
                    {''.join(f'<li><a href="/{f.name}">{f.name}</a></li>' for f in files)}
                    </ul>
                </body>
                </html>
                """
    
    # Default info page
    return f"""
    <html>
    <head><title>EEG Server with LSL</title></head>
    <body style="font-family: monospace; padding: 40px; max-width: 800px;">
        <h1>EEG Experiment Server</h1>
        <p style="color: green;"><strong>✓ Server Running</strong></p>
        <p><strong>LSL Stream:</strong> {STREAM_NAME}</p>
        <p><strong>Markers Sent:</strong> {lsl_stream.marker_count}</p>
        
        <h2>Status</h2>
        <ul>
            <li>HTTP Server: Running on port {PORT}</li>
            <li>LSL Stream: Active (local)</li>
            <li>Serve Directory: {SERVE_DIR or 'None (using default page)'}</li>
        </ul>
        
        <h2>Quick Test</h2>
        <button onclick="sendTestEvent()">Send Test Marker</button>
        <div id="result" style="margin-top: 10px;"></div>
        
        <h2>JavaScript Integration</h2>
        <p>Add this to your experiment code:</p>
        <pre style="background: #f0f0f0; padding: 10px; overflow-x: auto;">
async function sendEvent(eventType, stimulusCode, trialNumber) {{
    await fetch('/event', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            eventType: eventType,
            stimulusCode: stimulusCode,
            trialNumber: trialNumber,
            relativeTime: performance.now()
        }})
    }});
}}

// Usage:
sendEvent('EXPERIMENT_START', '', 0);
sendEvent('STIM_ONSET', 'COL_R', 1);
sendEvent('STIM_OFFSET', 'COL_R', 1);
        </pre>
        
        <script>
        async function sendTestEvent() {{
            try {{
                const res = await fetch('/event', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        eventType: 'STIM_ONSET',
                        stimulusCode: 'COL_R',
                        trialNumber: 999,
                        relativeTime: performance.now()
                    }})
                }});
                const data = await res.json();
                document.getElementById('result').innerHTML = 
                    '<span style="color: green;">✓ Marker sent! LSL time: ' + 
                    data.lsl_time.toFixed(3) + '</span>';
            }} catch(e) {{
                document.getElementById('result').innerHTML = 
                    '<span style="color: red;">✗ Error: ' + e + '</span>';
            }}
        }}
        </script>
    </body>
    </html>
    """


@app.route('/<path:path>')
def serve_file(path):
    """Serve static files from experiment directory."""
    if SERVE_DIR:
        return send_from_directory(SERVE_DIR, path)
    return "No serve directory configured", 404


@app.route('/event', methods=['POST', 'OPTIONS'])
def receive_event():
    """Receive event from browser and push to LSL."""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400
        
        # Parse and push to LSL
        lsl_time, event_code = lsl_stream.parse_and_push(data)
        
        return jsonify({
            'status': 'ok',
            'lsl_time': lsl_time,
            'event_code': event_code,
            'marker_count': lsl_stream.marker_count
        })
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    """Server status."""
    return jsonify({
        'status': 'running',
        'marker_count': lsl_stream.marker_count,
        'lsl_stream': STREAM_NAME,
        'port': PORT
    })


# =============================================================================
# Main
# =============================================================================

def print_banner(serve_dir):
    """Print startup banner."""
    import socket
    
    # Get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"
    
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║          EEG Experiment Server with Integrated LSL                ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  ✓ HTTP Server:  http://{ip}:{port:<38} ║
║  ✓ LSL Stream:   {stream:<46} ║
║  ✓ Serve Dir:    {dir:<46} ║
║                                                                   ║
║  SETUP:                                                           ║
║  1. Start ngrok:                                                  ║
║     ngrok http {port}                                             ║
║                                                                   ║
║  2. Open ngrok URL on Meta Quest browser                          ║
║                                                                   ║
║  3. Start LabRecorder and add "{stream}" stream        ║
║                                                                   ║
║  4. Run experiment - markers sent automatically!                  ║
║                                                                   ║
║  BENEFITS:                                                        ║
║  ✓ Browser sends simple HTTP (works through ngrok)                ║
║  ✓ LSL stays local (perfect timing, no network issues)            ║
║  ✓ One script does everything                                     ║
║                                                                   ║
║  LOCAL ACCESS:                                                    ║
║  http://localhost:{port}                                          ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """.format(
        ip=local_ip,
        port=PORT,
        stream=STREAM_NAME,
        dir=serve_dir or 'None (default page)'
    ))


def main():
    global SERVE_DIR, PORT
    
    parser = argparse.ArgumentParser(
        description='EEG Experiment Server with Integrated LSL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--dir', '-d', 
                        help='Directory containing experiment HTML files')
    parser.add_argument('--port', '-p', type=int, default=8080,
                        help=f'HTTP port (default: {PORT})')
    args = parser.parse_args()
    
    PORT = args.port
    
    if args.dir:
        SERVE_DIR = os.path.abspath(args.dir)
        if not os.path.isdir(SERVE_DIR):
            print(f"ERROR: Directory not found: {SERVE_DIR}")
            sys.exit(1)
        print(f"[SERVER] Serving files from: {SERVE_DIR}")
    
    print_banner(SERVE_DIR)
    
    try:
        app.run(host=HOST, port=PORT, threaded=True, debug=False)
    except KeyboardInterrupt:
        print(f"\n[SHUTDOWN] Total markers sent: {lsl_stream.marker_count}")


if __name__ == '__main__':
    main()