# EEG Perception Stimulus Platform

WebXR-based visual stimulus presentation platform for EEG research.

## File Structure

```
perception/
├── index.html          # Main web app
├── css/
│   └── style.css       # Dark minimal theme
├── js/
│   ├── config.js       # Stimulus & marker definitions
│   ├── websocket.js    # LSL bridge connection
│   ├── stimuli.js      # 3D shape factory
│   ├── renderer.js     # Three.js / WebXR renderer
│   ├── experiment.js   # Trial state machine
│   └── main.js         # UI controller
├── lsl_bridge.py       # Python WebSocket → LSL bridge
├── requirements.txt    # Python dependencies
├── app.py              # Local dev server
└── vercel.json         # Vercel deployment config
```

## Setup

### 1. Python Bridge (Lab Computer)

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the bridge:
```bash
python lsl_bridge.py
# Optional: custom port
python lsl_bridge.py --port 8765
```

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

## Running an Experiment

1. Start `lsl_bridge.py` on the lab computer
2. Open LabRecorder → add **PerceptionMarkers** stream
3. Open the web app → enter the bridge URL (shown in terminal)
4. Click **Connect to LSL Bridge**
5. Configure stimuli, timing, and trial structure
6. Click **Start Experiment** → **Enter VR**

## Marker Codes

| Event         | Code |
|---------------|------|
| Exp Start     | 90   |
| Exp End       | 91   |
| Trial Start   | 1    |
| Stim Onset    | 10   |
| Stim Offset   | 11   |
| Break Start   | 40   |
| Break End     | 41   |
| Pause         | 60   |
| Resume        | 61   |
| Red           | 100  |
| Green         | 101  |
| Blue          | 102  |
| Black         | 103  |
| White         | 104  |
| Sphere        | 200  |
| Cube          | 201  |
| Pyramid       | 202  |
| Icosahedron   | 203  |
| Face          | 300  |
| Building      | 301  |
| Landscape     | 302  |

## Keyboard Shortcuts

- `Space` — Pause / Resume
- `Esc` — Stop experiment
