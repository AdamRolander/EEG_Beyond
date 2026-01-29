#!/usr/bin/env python3
"""
Parallel Port HTTP Bridge for EEG Stimulus Platform

This bridge receives HTTP POST requests from the web-based stimulus platform
and sends trigger pulses to a parallel port for hardware EEG synchronization.

Requirements (Windows):
    pip install flask inpout32
    
    For inpout32:
    1. Download InpOutBinaries from https://www.highrez.co.uk/downloads/inpout32/
    2. Run InstallDriver.exe as administrator
    3. Copy inpout32.dll and inpoutx64.dll to System32/SysWOW64

Requirements (Linux):
    pip install flask
    sudo modprobe parport
    sudo chmod 666 /dev/parport0

Usage:
    python parallel_port_bridge.py

Then configure in browser:
    EventLogger.configureParallelPort('http://localhost:8888/trigger')
"""

import sys
import time
import logging
from threading import Lock

from flask import Flask, request, jsonify
from flask_cors import CORS

# Configuration
HOST = 'localhost'
PORT = 8888
PARALLEL_PORT_ADDRESS = 0x378  # Standard LPT1 address
TRIGGER_DURATION_MS = 10       # Pulse width in milliseconds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for browser requests

# Thread safety for port access
port_lock = Lock()


class ParallelPortInterface:
    """Interface for parallel port communication."""
    
    def __init__(self, address=PARALLEL_PORT_ADDRESS):
        self.address = address
        self.available = False
        self._init_port()
    
    def _init_port(self):
        """Initialize the parallel port based on OS."""
        if sys.platform == 'win32':
            self._init_windows()
        elif sys.platform.startswith('linux'):
            self._init_linux()
        else:
            logger.warning(f"Unsupported platform: {sys.platform}")
    
    def _init_windows(self):
        """Initialize parallel port on Windows using inpout32."""
        try:
            import ctypes
            
            # Try 64-bit first, then 32-bit
            try:
                self.inpout = ctypes.windll.inpoutx64
            except:
                self.inpout = ctypes.windll.inpout32
            
            # Test port access
            self.inpout.Out32(self.address, 0)
            self.available = True
            logger.info(f"Windows parallel port initialized at 0x{self.address:X}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Windows parallel port: {e}")
            logger.info("Make sure InpOut32 driver is installed")
    
    def _init_linux(self):
        """Initialize parallel port on Linux."""
        try:
            # Check if parport device exists
            import os
            if os.path.exists('/dev/parport0'):
                self.port_file = '/dev/parport0'
                # Test access
                with open(self.port_file, 'wb') as f:
                    f.write(bytes([0]))
                self.available = True
                logger.info(f"Linux parallel port initialized: {self.port_file}")
            else:
                logger.warning("/dev/parport0 not found. Load parport module?")
                
        except PermissionError:
            logger.error("Permission denied. Run: sudo chmod 666 /dev/parport0")
        except Exception as e:
            logger.error(f"Failed to initialize Linux parallel port: {e}")
    
    def write(self, value: int):
        """Write a byte to the parallel port data pins."""
        if not self.available:
            logger.debug(f"[SIMULATED] Port write: {value}")
            return
        
        with port_lock:
            if sys.platform == 'win32':
                self.inpout.Out32(self.address, value)
            else:
                with open(self.port_file, 'wb') as f:
                    f.write(bytes([value & 0xFF]))
    
    def pulse(self, value: int, duration_ms: float = TRIGGER_DURATION_MS):
        """Send a pulse: set value, wait, then reset to 0."""
        self.write(value)
        time.sleep(duration_ms / 1000.0)
        self.write(0)


# Initialize parallel port
parallel_port = ParallelPortInterface()


@app.route('/trigger', methods=['POST'])
def trigger():
    """Handle trigger requests from the stimulus platform."""
    try:
        data = request.get_json()
        
        code = data.get('code', 0)
        duration = data.get('duration', TRIGGER_DURATION_MS)
        
        # Validate code (8-bit value)
        code = int(code) & 0xFF
        
        # Send trigger
        parallel_port.pulse(code, duration)
        
        logger.info(f"Trigger sent: code={code}, duration={duration}ms")
        
        return jsonify({'status': 'ok', 'code': code})
        
    except Exception as e:
        logger.error(f"Trigger error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    """Check bridge status."""
    return jsonify({
        'status': 'running',
        'port_available': parallel_port.available,
        'port_address': hex(parallel_port.address)
    })


@app.route('/test', methods=['POST'])
def test():
    """Test trigger sequence."""
    try:
        # Send test sequence: 1, 2, 4, 8, 16, 32, 64, 128
        for i in range(8):
            code = 1 << i
            parallel_port.pulse(code, 50)
            time.sleep(0.1)
        
        return jsonify({'status': 'ok', 'message': 'Test sequence complete'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def main():
    print("""
╔═══════════════════════════════════════════════════════╗
║     Parallel Port Bridge for EEG Stimulus Platform    ║
╠═══════════════════════════════════════════════════════╣
║  HTTP Endpoint:  http://{}:{}/trigger           ║
║  Port Address:   0x{:04X}                              ║
║  Port Available: {:<36} ║
╚═══════════════════════════════════════════════════════╝
    """.format(HOST, PORT, PARALLEL_PORT_ADDRESS, 
               'Yes' if parallel_port.available else 'No (simulation mode)'))
    
    if not parallel_port.available:
        print("WARNING: Parallel port not available. Running in simulation mode.")
        print("         Triggers will be logged but not sent to hardware.\n")
    
    print("Endpoints:")
    print(f"  POST /trigger  - Send trigger (JSON: {{code: N, duration: M}})")
    print(f"  GET  /status   - Check bridge status")
    print(f"  POST /test     - Run test sequence")
    print()
    
    app.run(host=HOST, port=PORT, threaded=True)


if __name__ == '__main__':
    main()