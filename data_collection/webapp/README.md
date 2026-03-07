# Perception–Imagery EEG Stimulus Platform

WebXR-based visual stimulus presentation for EEG perception and mental imagery research.

## Protocol

Each trial follows this sequence:

```
Fixation (3s) → Perception (4s) → Mask (2s) → [Audio Cue] → Imagery (4s) → Rest (4s) → Repeat
```

All durations are configurable. Stimuli are randomly distributed across trials (sampling without replacement, equal counts per class).

### Default Classes

| Stimulus   | Marker Code | GLB File       |
| ---------- | ----------- | -------------- |
| Banana     | 100         | banana.glb     |
| Strawberry | 101         | strawberry.glb |
| Cube       | 102         | cube.glb       |

### Marker Codes (LSL)

| Event            | Code |
| ---------------- | ---- |
| Exp Start        | 90   |
| Exp End          | 91   |
| Trial Start      | 1    |
| Trial End        | 2    |
| Fixation Onset   | 10   |
| Perception Onset | 11   |
| Mask Onset       | 12   |
| Imagery Cue      | 13   |
| Imagery Onset    | 14   |
| Imagery Offset   | 15   |
| Rest Onset       | 16   |
| Break Start      | 40   |
| Break End        | 41   |
| Likert (base)    | 50   |
| Pause            | 60   |
| Resume           | 61   |
| Banana           | 100  |
| Strawberry       | 101  |
| Cube             | 102  |

Stimulus identity markers (100–102) are sent at both Perception Onset and Imagery Onset, with the `phase` field distinguishing them.

## File Structure

```
perception/
├── index.html
├── css/
│   └── style.css
├── js/
│   ├── config.js       # Stimulus & marker definitions
│   ├── audio.js        # Audio cue system (beep / TTS)
│   ├── websocket.js    # LSL bridge WebSocket client
│   ├── stimuli.js      # GLB loader + fallback geometry + mask
│   ├── renderer.js     # Three.js / WebXR renderer
│   ├── experiment.js   # Trial state machine
│   └── main.js         # UI controller
├── assets/
│   ├── banana.glb      # 3D models (you provide these)
│   ├── strawberry.glb
│   ├── cube.glb
│   └── audio/          # Optional TTS cues
│       ├── banana.mp3
│       ├── strawberry.mp3
│       └── cube.mp3
├── lsl_bridge.py       # Python WebSocket → LSL bridge (ws + wss)
├── app.py              # Local dev server
├── requirements.txt
└── vercel.json
```

## Setup

### 1. LSL Bridge (Lab Computer)

```bash
pip install -r requirements.txt
```

**Plain WebSocket (local network, HTTP app):**

```bash
python lsl_bridge.py --port 8765
```

**Secure WebSocket (for HTTPS/Vercel deployment):**

```bash
# Generate self-signed cert
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes

# Run with SSL (auto-detects cert.pem/key.pem in same directory)
python lsl_bridge.py --port 8765
# Or explicitly:
python lsl_bridge.py --port 8765 --ssl-cert cert.pem --ssl-key key.pem
```

**Important for wss:// with self-signed certs:** Visit `https://<IP>:8765` in your browser and accept the certificate warning before connecting from the web app.

### 2. Web App

**Local development:**

```bash
python app.py
# Open http://localhost:3000
```

**Deploy to Vercel:**

```bash
npx vercel --prod
```

### 3. Assets

Place your `.glb` 3D model files in the `assets/` folder. The app will auto-detect them based on the filenames in `config.js`. If a GLB is missing, the app uses procedural fallback geometry (colored shapes).

For TTS audio cues, place `.mp3` files in `assets/audio/` named after each stimulus (lowercase). If missing, the app falls back to a beep tone.

## Running an Experiment

1. Start `lsl_bridge.py` on the lab computer
2. Open LabRecorder → add **PerceptionMarkers** stream
3. Open the web app → enter the bridge URL shown in the terminal
4. Click **Connect to LSL Bridge**
5. Configure timing, trials, and options
6. Select display mode: **Browser** (2D fullscreen) or **VR** (WebXR)
7. Click **Start Experiment**
8. Press **F** to toggle fullscreen in browser mode

## Display Modes

- **Browser (2D):** Fullscreen canvas with Three.js rendering. Works on any device with a modern browser. Press F for fullscreen.
- **VR (WebXR):** Immersive VR session via WebXR. Requires a VR headset and WebXR-compatible browser.

## Keyboard Shortcuts

| Key   | Action                    |
| ----- | ------------------------- |
| Space | Pause / Resume / Continue |
| Esc   | Stop experiment           |
| F     | Toggle fullscreen         |

## Adding New Stimulus Classes

Edit `js/config.js` → `CONFIG.stimuli`:

```js
stimuli: {
  BANANA:     { name: 'Banana',     file: 'banana.glb',     code: 100 },
  STRAWBERRY: { name: 'Strawberry', file: 'strawberry.glb', code: 101 },
  CUBE:       { name: 'Cube',       file: 'cube.glb',       code: 102 },
  // Add more:
  APPLE:      { name: 'Apple',      file: 'apple.glb',      code: 103 },
}
```

Then add the corresponding `.glb` file to `assets/`.
