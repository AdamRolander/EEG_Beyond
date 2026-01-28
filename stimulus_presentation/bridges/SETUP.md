# LSL Integration Guide

This guide explains how to synchronize stimulus markers with your EEG recording using Lab Streaming Layer (LSL).

## Overview

```
┌─────────────────┐    WebSocket    ┌─────────────────┐    LSL    ┌─────────────────┐
│  Browser        │ ──────────────► │  Python Bridge  │ ────────► │  EEG Recording  │
│  (Stimulus)     │  ws://localhost │  (lsl_bridge)   │  Markers  │  (LabRecorder)  │
└─────────────────┘     :8765       └─────────────────┘           └─────────────────┘
```

The browser sends events to a Python bridge via WebSocket. The bridge then pushes these as LSL markers, which your EEG recording software can receive.

## Step 1: Install Dependencies

```bash
# Install Python packages
pip install pylsl websockets

# Verify installation
python -c "import pylsl; print('pylsl version:', pylsl.__version__)"
```

### Troubleshooting pylsl Installation

If `pip install pylsl` fails:

**macOS:**

```bash
brew install labstreaminglayer/tap/lsl
pip install pylsl
```

**Linux (Ubuntu/Debian):**

```bash
# Download liblsl from GitHub releases
wget https://github.com/sccn/liblsl/releases/download/v1.16.2/liblsl-1.16.2-jammy_amd64.deb
sudo dpkg -i liblsl-1.16.2-jammy_amd64.deb
pip install pylsl
```

**Windows:**
pylsl should install automatically. If not, download liblsl from the [releases page](https://github.com/sccn/liblsl/releases).

## Step 2: Start the LSL Bridge

Open a terminal and run:

```bash
cd eeg-stimulus-platform/bridges
python lsl_bridge.py
```

You should see:

```
╔══════════════════════════════════════════════════════════════════╗
║           LSL Bridge for EEG Stimulus Platform                   ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  WebSocket:  ws://localhost:8765                                 ║
║  LSL Stream: EEGStimulusMarkers                                  ║
║                                                                  ║
║  Waiting for browser connection...                               ║
╚══════════════════════════════════════════════════════════════════╝
```

**Keep this terminal open throughout your experiment.**

## Step 3: Verify LSL Stream (Optional)

Test that the LSL stream is visible:

```bash
python lsl_bridge.py --test
```

Or use LabRecorder / another LSL viewer to see the "EEGStimulusMarkers" stream.

## Step 4: Configure Your EEG Recording Software

### LabRecorder

1. Open LabRecorder
2. Click "Update" to refresh stream list
3. Check "EEGStimulusMarkers" in the list
4. Make sure your EEG stream is also checked
5. Click "Start" to begin recording

### BrainVision Recorder

1. Go to Configuration → LSL Connector
2. Add a new LSL stream source
3. Select "EEGStimulusMarkers"
4. Enable marker channel recording

### OpenViBE

1. Add "LSL Client" acquisition server
2. Connect to "EEGStimulusMarkers" stream
3. Route to your signal processing pipeline

## Step 5: Run the Experiment

1. Open the stimulus platform in your browser (serve via `python -m http.server`)
2. Check **"Enable LSL Markers"** in the EEG Integration section
3. Click **START EXPERIMENT**
4. If connection succeeds, you'll see "LSL: ✓ Connected" in the status bar

## Marker Format

Each marker contains 3 values:

| Channel | Name        | Description                         |
| ------- | ----------- | ----------------------------------- |
| 1       | EventCode   | Numeric code identifying the event  |
| 2       | TrialNumber | Current trial (1-indexed)           |
| 3       | BrowserTime | Milliseconds since experiment start |

### Event Codes

| Code | Event            |
| ---- | ---------------- |
| 100  | EXPERIMENT_START |
| 101  | EXPERIMENT_END   |
| 1    | STIM_ONSET       |
| 2    | STIM_OFFSET      |
| 10   | RED              |
| 11   | GREEN            |
| 12   | BLUE             |
| 13   | BLACK            |
| 14   | WHITE            |
| 20   | SPHERE           |
| 21   | CUBE             |
| 22   | PYRAMID          |
| 23   | ICOSAHEDRON      |
| 50   | PAUSE            |
| 51   | RESUME           |
| 99   | ABORT            |

## Timing Considerations

### Latency Sources

| Source                             | Typical Latency |
| ---------------------------------- | --------------- |
| JavaScript event → WebSocket send  | < 1 ms          |
| WebSocket transmission (localhost) | 1-5 ms          |
| LSL timestamp assignment           | < 0.1 ms        |
| **Total browser → LSL**            | **~2-6 ms**     |

### LSL Clock Synchronization

LSL has built-in clock synchronization. When you record multiple streams (EEG + markers), LSL automatically:

1. Timestamps each sample/marker with its local clock
2. Synchronizes clocks across streams during recording
3. Corrects for clock drift in post-processing

This means the **LSL timestamp** (not the browser timestamp) is what you should use for ERP analysis.

### For Sub-millisecond Precision

If you need <1ms timing precision:

1. Use a **parallel port** trigger instead of WebSocket
2. Add a **photodiode** on screen corner to measure actual display latency
3. Record photodiode signal alongside EEG
4. Use photodiode onsets as ground truth in analysis

## Verifying Synchronization

### Quick Check

While the experiment runs, watch the bridge terminal. You should see markers in real-time:

```
[MARKER] STIM_ONSET           code=  1 trial=  1 lsl_t=1234.567 COL_R
[MARKER] STIM_OFFSET          code=  2 trial=  1 lsl_t=1237.589 COL_R
```

### Post-Recording Verification

After recording, check in your analysis software:

1. Load both EEG and marker streams
2. Verify markers appear at expected times
3. Check that STIM_ONSET and STIM_OFFSET have consistent intervals

## Example: Python Analysis

```python
import pylsl
import numpy as np

# Resolve marker stream
streams = pylsl.resolve_stream('name', 'EEGStimulusMarkers')
inlet = pylsl.StreamInlet(streams[0])

# Pull all available samples
markers = []
while True:
    sample, timestamp = inlet.pull_sample(timeout=0.0)
    if sample is None:
        break
    markers.append({
        'event_code': int(sample[0]),
        'trial': int(sample[1]),
        'browser_time': sample[2],
        'lsl_time': timestamp
    })

# Convert to numpy for analysis
onset_times = [m['lsl_time'] for m in markers if m['event_code'] == 1]
```

## Troubleshooting

### "Could not connect to LSL bridge"

1. Make sure `lsl_bridge.py` is running
2. Check that port 8765 isn't blocked by firewall
3. Try accessing `ws://localhost:8765` in browser console

### Markers not appearing in LabRecorder

1. Click "Update" to refresh stream list
2. Make sure "EEGStimulusMarkers" is checked
3. Verify the bridge shows "Client connected" message

### High latency / jitter

1. Close unnecessary browser tabs
2. Disable browser extensions
3. Use a wired network connection
4. Run bridge and browser on the same machine

### "pylsl.lib not found"

Install liblsl separately:

- macOS: `brew install labstreaminglayer/tap/lsl`
- Linux: Download .deb/.rpm from GitHub releases
- Windows: Download from GitHub releases, add to PATH

## Running on Separate Machines

If you need to run the stimulus display on a different machine than the EEG recording:

1. On the bridge machine, edit `lsl_bridge.py`:

   ```python
   HOST = '0.0.0.0'  # Already set to listen on all interfaces
   ```

2. On the stimulus machine, modify the WebSocket URL in browser console before starting:

   ```javascript
   // Replace with bridge machine IP
   EventLogger.connectLSL("ws://192.168.1.100:8765");
   ```

3. Ensure both machines are on the same network and port 8765 is open.

## Questions?

- LSL documentation: https://labstreaminglayer.readthedocs.io/
- pylsl issues: https://github.com/labstreaminglayer/pylsl/issues
