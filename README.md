# EEG Stimulus Platform

A research-grade visual stimulus generator for EEG/neuroscience studies built with Three.js.

## Overview

This platform provides precise, time-locked visual stimuli suitable for event-related potential (ERP) studies, steady-state visual evoked potential (SSVEP) research, and other EEG paradigms requiring deterministic stimulus presentation.

### Key Features

- **Precise timing** via `performance.now()` with sub-millisecond resolution
- **Deterministic behavior** - no random elements unless explicitly seeded
- **Full-screen color stimuli** using pure sRGB primaries
- **3D primitive solids** with constant angular velocity rotation
- **WebXR/VR support** with head-locked stimulus positioning
- **Modular architecture** for easy extension
- **EEG integration hooks** for LSL, WebSocket, and parallel port triggers

## Files

```
eeg-stimulus-platform/
├── index.html              # Single-file version (all-in-one)
├── index-modular.html      # ES6 modules version
├── js/
│   ├── config.js           # Configuration parameters
│   ├── event-logger.js     # Timing and EEG integration
│   ├── experiment-controller.js
│   └── stimuli/
│       └── stimulus-factory.js
└── README.md
```

## Quick Start

1. Serve the files via a local HTTP server:

   ```bash
   python -m http.server 8000
   # or
   npx serve .
   ```

2. Open `http://localhost:8000/index.html` in a browser

3. Configure experiment parameters and click "START EXPERIMENT"

## Timing Architecture

### How Timing Works

```
┌─────────────────────────────────────────────────────────────┐
│  Experiment Timeline                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ISI → [STIM_ONSET] → Stimulus Display → [STIM_OFFSET] → ISI
│   │                        │                    │           │
│   │    performance.now()   │   setTimeout()     │           │
│   │         ▼              │        ▼           │           │
│   │    logged to           │   deterministic    │           │
│   │    EventLogger         │   duration         │           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key timing mechanisms:**

1. **`performance.now()`** - Used for all event timestamps
   - Provides high-resolution timestamps (microsecond precision in most browsers)
   - Monotonic clock (never goes backwards)
   - Relative to page load (more stable than `Date.now()`)

2. **`setTimeout()`** - Used for stimulus duration control
   - Schedules offset events
   - Note: JavaScript timers have ~4ms minimum delay in background tabs

3. **`requestAnimationFrame()` via `setAnimationLoop()`** - Used for rendering
   - Syncs with display refresh rate (typically 60Hz = 16.67ms)
   - VSync-locked for tear-free rendering

### Event Logging Format

Each event is logged with:

```javascript
{
  eventType: 'STIM_ONSET',      // Event type identifier
  absoluteTime: 12345.678,      // performance.now() timestamp
  relativeTime: 3456.789,       // Time since experiment start
  stimulusType: 'color',        // 'color' or 'shape'
  stimulusCode: 'COL_R',        // Stimulus identifier
  trialNumber: 5                // 1-indexed trial number
}
```

### Console Output

All events are logged to the console in a parseable format:

```
[EEG_EVENT] STIM_ONSET { absoluteMs: "12345.678", relativeMs: "3456.789", stimulusType: "color", stimulusCode: "COL_R", trialNumber: 5 }
```

## Stimulus Specifications

### Color Stimuli

| Name  | Hex     | sRGB            | Code  |
| ----- | ------- | --------------- | ----- |
| RED   | #FF0000 | (255, 0, 0)     | COL_R |
| GREEN | #00FF00 | (0, 255, 0)     | COL_G |
| BLUE  | #0000FF | (0, 0, 255)     | COL_B |
| BLACK | #000000 | (0, 0, 0)       | COL_K |
| WHITE | #FFFFFF | (255, 255, 255) | COL_W |

**Note:** Three.js color management is disabled (`THREE.ColorManagement.enabled = false`) to ensure accurate sRGB color reproduction.

### 3D Shape Stimuli

| Shape       | Geometry            | Code    |
| ----------- | ------------------- | ------- |
| Sphere      | SphereGeometry      | SHP_SPH |
| Cube        | BoxGeometry         | SHP_CUB |
| Pyramid     | TetrahedronGeometry | SHP_PYR |
| Icosahedron | IcosahedronGeometry | SHP_ICO |

**Rendering properties:**

- Material: MeshStandardMaterial (light gray, roughness=0.7)
- Lighting: Ambient (0.4) + Directional (0.6)
- Rotation: Y-axis only, constant angular velocity
- Background: Neutral gray (#808080)

## WebXR / VR Support

### Enabling VR

1. Check "Enable WebXR (VR Mode)" before starting
2. After experiment starts, click "ENTER VR" button
3. Put on headset

### VR Behavior

- **Head-locked stimuli**: Shapes remain fixed relative to gaze direction
- **No locomotion**: User position is fixed
- **Implementation**: Shapes are parented to camera in VR mode

```javascript
// VR positioning code
if (this.vrEnabled && this.renderer.xr.isPresenting) {
  shape.position.set(0, 0, -3); // 3m in front of user
  this.camera.add(shape); // Parent to camera
}
```

### Supported Platforms

- Quest 2/3/Pro (via browser)
- PC VR (SteamVR, Oculus)
- Any WebXR-compatible browser

## Extending the Platform

### Adding New Colors

```javascript
// Via Config
Config.colors.PURPLE = { hex: 0xff00ff, name: "PURPLE", code: "COL_P" };

// Via API
window.EEGStimulus.addCustomColor("PURPLE", 0xff00ff, "COL_P");
```

### Adding New Shapes

```javascript
// Simple registration
Config.shapes.TORUS = { name: "TORUS", code: "SHP_TOR" };

// With custom geometry factory
registerCustomShape(
  "STAR",
  (scale) => {
    const shape = new THREE.Shape();
    // ... define star shape
    return new THREE.ExtrudeGeometry(shape, { depth: 0.5 * scale });
  },
  "SHP_STR",
);
```

### Adding Cue-Based Trials

```javascript
// Example: Add imagined movement cues
const cueTrials = [
    { type: 'cue', config: { text: 'LEFT', code: 'CUE_L' } },
    { type: 'cue', config: { text: 'RIGHT', code: 'CUE_R' } },
];

// Extend showStimulus in ExperimentController
showCueStimulus(cueConfig) {
    // Display text cue using HTML overlay or Three.js text
}
```

### Adding Auditory Cues

```javascript
// Initialize audio context
const audioContext = new AudioContext();

// Create beep function
function playBeep(frequency, duration) {
  const oscillator = audioContext.createOscillator();
  oscillator.frequency.value = frequency;
  oscillator.connect(audioContext.destination);
  oscillator.start();
  setTimeout(() => oscillator.stop(), duration);
}

// Integrate with trial start
controller.onTrialStart = (index, trial) => {
  if (trial.config.playBeep) {
    playBeep(440, 100); // 440Hz, 100ms
  }
};
```

## EEG Integration

### Lab Streaming Layer (LSL)

```javascript
// Connect to LSL bridge
EventLogger.connectLSL("ws://localhost:8765");

// The bridge should forward markers to LSL outlet
// Example Python bridge:
// import pylsl
// outlet = pylsl.StreamOutlet(pylsl.StreamInfo('Markers', 'Markers'))
```

### WebSocket Bridge

```javascript
// Connect to generic WebSocket
EventLogger.connectWebSocket("ws://localhost:9000");

// Events are sent as JSON:
// { type: 'eeg_event', eventType: 'STIM_ONSET', ... }
```

### Parallel Port Triggers

```javascript
// Configure parallel port HTTP bridge
EventLogger.configureParallelPort("http://localhost:8888/trigger");

// Bridge receives POST requests:
// { code: 10, duration: 10 }
//
// Example Python bridge using inpout32:
// from flask import Flask, request
// import ctypes
// inpout32 = ctypes.windll.inpout32
// PORT = 0x378
//
// @app.route('/trigger', methods=['POST'])
// def trigger():
//     code = request.json['code']
//     inpout32.Out32(PORT, code)
//     time.sleep(0.01)
//     inpout32.Out32(PORT, 0)
//     return 'OK'
```

### Event Codes for EEG

| Event            | Code |
| ---------------- | ---- |
| EXPERIMENT_START | 100  |
| EXPERIMENT_END   | 101  |
| STIM_ONSET       | 1    |
| STIM_OFFSET      | 2    |
| PAUSE            | 50   |
| RESUME           | 51   |
| ABORT            | 99   |
| COL_R            | 10   |
| COL_G            | 11   |
| COL_B            | 12   |
| COL_K            | 13   |
| COL_W            | 14   |
| SHP_SPH          | 20   |
| SHP_CUB          | 21   |
| SHP_PYR          | 22   |
| SHP_ICO          | 23   |

## Keyboard Controls

| Key   | Action                  |
| ----- | ----------------------- |
| SPACE | Pause/Resume experiment |
| ESC   | Abort experiment        |
| N     | Skip to next trial      |

## Configuration Parameters

| Parameter        | Default | Range       | Description                   |
| ---------------- | ------- | ----------- | ----------------------------- |
| stimulusDuration | 3000ms  | 500-30000ms | Display time per stimulus     |
| isiDuration      | 1000ms  | 200-10000ms | Inter-stimulus interval       |
| repetitions      | 3       | 1-20        | Repetitions per stimulus type |
| rotationSpeed    | 0.5     | 0-2 rad/s   | Angular velocity of 3D shapes |

## Best Practices for EEG Studies

1. **Use a wired connection** - WiFi introduces latency jitter
2. **Disable browser extensions** - May interfere with timing
3. **Use fullscreen mode** - Prevents OS overlays
4. **Run on dedicated machine** - Avoid background processes
5. **Verify timing** with photodiode on display corner
6. **Test parallel port timing** with oscilloscope
7. **Log browser/system info** with each recording

## Timing Considerations

### Expected Latencies

| Source                | Typical Latency |
| --------------------- | --------------- |
| JavaScript setTimeout | 1-4ms jitter    |
| Display vsync         | 0-16.67ms       |
| LCD response time     | 1-10ms          |
| Parallel port trigger | <1ms            |
| WebSocket round-trip  | 1-50ms          |

### Recommendations

- For ERP studies requiring <1ms precision, use parallel port triggers
- Compensate for display latency in analysis (measure with photodiode)
- Log monitor refresh rate and use it in analysis
- Consider using a CRT or fast gaming monitor for critical timing

## Troubleshooting

### Colors Look Wrong

- Ensure `THREE.ColorManagement.enabled = false`
- Check monitor color profile
- Verify renderer encoding: `renderer.outputEncoding = THREE.LinearEncoding`

### VR Not Working

- Check `navigator.xr` availability
- Ensure HTTPS or localhost
- Update browser and VR runtime

### Timing Inconsistent

- Run in fullscreen
- Disable power saving
- Use wired peripherals
- Check for background processes

## License

MIT License - Free for research use.

## Citation

If you use this platform in your research, please cite:

```
EEG Stimulus Platform
https://github.com/your-repo/eeg-stimulus-platform
```
