#!/usr/bin/env python3
"""
Combined HTTP + WebSocket Server for EEG Stimulus Platform
===========================================================

This server handles BOTH:
- HTTP: Serves the experiment HTML/JS files
- WebSocket: Receives markers and pushes to LSL

With this single server, you only need ONE ngrok tunnel.

USAGE
-----
    python bridges/combined_server.py

    Then use ngrok:
    ngrok http 8080

    Open the ngrok URL in the Quest browser.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Check dependencies
try:
    import pylsl
except ImportError:
    print("ERROR: pylsl not installed")
    print("Run: pip install pylsl")
    sys.exit(1)

try:
    from aiohttp import web
except ImportError:
    print("ERROR: aiohttp not installed")
    print("Run: pip install aiohttp")
    sys.exit(1)


# =============================================================================
# Configuration
# =============================================================================

PORT = 8080
STREAM_NAME = 'EEGStimulusMarkers'
STREAM_TYPE = 'Markers'

# Event code mapping
EVENT_CODES = {
    'EXPERIMENT_START': 100,
    'EXPERIMENT_END': 101,
    'STIM_ONSET': 1,
    'STIM_OFFSET': 2,
    'PAUSE': 50,
    'RESUME': 51,
    'ABORT': 99,
    'SKIP': 98,
    'COL_R': 10,
    'COL_G': 11,
    'COL_B': 12,
    'COL_K': 13,
    'COL_W': 14,
    'SHP_SPH': 20,
    'SHP_CUB': 21,
    'SHP_PYR': 22,
    'SHP_ICO': 23,
}


# =============================================================================
# LSL Bridge
# =============================================================================

class LSLBridge:
    def __init__(self):
        self.outlet = None
        self.marker_count = 0
        self._create_outlet()
    
    def _create_outlet(self):
        info = pylsl.StreamInfo(
            name=STREAM_NAME,
            type=STREAM_TYPE,
            channel_count=3,
            nominal_srate=0,
            channel_format=pylsl.cf_double64,
            source_id='eeg_stimulus_platform_v1'
        )
        self.outlet = pylsl.StreamOutlet(info)
        print(f"[LSL] Created outlet: {STREAM_NAME}")
    
    def push_marker(self, event_code, trial_number=0, browser_time=0):
        sample = [float(event_code), float(trial_number), float(browser_time)]
        self.outlet.push_sample(sample)
        self.marker_count += 1
        return pylsl.local_clock()
    
    def parse_event(self, data):
        event_type = data.get('eventType', '')
        stim_code = data.get('stimulusCode', '')
        trial_num = data.get('trialNumber', 0)
        browser_time = data.get('relativeTime', 0)
        
        if stim_code and stim_code in EVENT_CODES:
            event_code = EVENT_CODES[stim_code]
        elif event_type in EVENT_CODES:
            event_code = EVENT_CODES[event_type]
        else:
            event_code = 0
        
        return event_code, trial_num, browser_time


# =============================================================================
# Web Server
# =============================================================================

bridge = LSLBridge()

async def websocket_handler(request):
    """Handle WebSocket connections for LSL markers."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    client_ip = request.remote
    print(f"[WS] Client connected: {client_ip}")
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    event_code, trial_num, browser_time = bridge.parse_event(data)
                    lsl_time = bridge.push_marker(event_code, trial_num, browser_time)
                    
                    event_type = data.get('eventType', 'UNKNOWN')
                    stim_code = data.get('stimulusCode', '')
                    print(f"[MARKER] {event_type:20s} code={event_code:3d} trial={trial_num:3d} {stim_code}")
                    
                    await ws.send_json({
                        'status': 'ok',
                        'lsl_timestamp': lsl_time,
                        'marker_count': bridge.marker_count
                    })
                except Exception as e:
                    print(f"[WS] Error: {e}")
            elif msg.type == web.WSMsgType.ERROR:
                print(f"[WS] Error: {ws.exception()}")
    finally:
        print(f"[WS] Client disconnected: {client_ip}")
    
    return ws


async def index_handler(request):
    """Serve index.html with modified WebSocket URL."""
    # Find the project root (parent of bridges/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    index_path = project_root / 'index.html'
    
    if not index_path.exists():
        return web.Response(text="index.html not found", status=404)
    
    content = index_path.read_text(encoding='utf-8')
    
    # Replace the default WebSocket URL to use relative path
    # This makes it work through ngrok automatically
    content = content.replace(
        'value="ws://localhost:8765"',
        'value="AUTO"'
    )
    
    # Inject script to auto-detect WebSocket URL
    inject_script = '''
<script>
// Auto-detect WebSocket URL based on current page location
(function() {
    window.addEventListener('DOMContentLoaded', function() {
        var lslUrlInput = document.getElementById('lsl-url');
        if (lslUrlInput && lslUrlInput.value === 'AUTO') {
            var wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            var wsUrl = wsProtocol + '//' + window.location.host + '/ws';
            lslUrlInput.value = wsUrl;
            console.log('[AUTO] WebSocket URL set to:', wsUrl);
        }
    });
})();
</script>
</head>'''
    
    content = content.replace('</head>', inject_script)
    
    return web.Response(text=content, content_type='text/html')


def create_app():
    """Create the web application."""
    app = web.Application()
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Routes
    app.router.add_get('/', index_handler)
    app.router.add_get('/index.html', index_handler)
    app.router.add_get('/ws', websocket_handler)
    
    # Static files (JS, CSS, etc.)
    app.router.add_static('/js/', project_root / 'js')
    app.router.add_static('/bridges/', project_root / 'bridges')
    
    return app


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       Combined HTTP + WebSocket Server for EEG Platform          ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Server: http://0.0.0.0:8080                                     ║
║  LSL Stream: EEGStimulusMarkers                                  ║
║                                                                  ║
║  USAGE:                                                          ║
║  1. Run: ngrok http 8080                                         ║
║  2. Open the ngrok URL in Quest browser                          ║
║  3. LSL markers will be sent automatically                       ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=PORT, print=lambda x: print(f"[HTTP] {x}"))


if __name__ == '__main__':
    main()
