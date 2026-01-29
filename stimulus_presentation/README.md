## Three.js App with LSL Integration for VR/Web-based Stimulus Presentation

### TODO

- Make requirements.txt file, think about conda env or python virtual env setup with automation
- Proper documentation (pictures/debugging/troubleshooting) esp. for VR integration
- Create + assign feature TODOs/Issues
- Integrate with Yann's branch

### Setup

- Install dependencies:
  `pip insall pylsl websockets`
- Launch server in terminal from `stimulus_presentation` directory
  `python eeg_server_with_lsl.py`
- Launch app in new terminal from `stimulus_presentation` directory
  `python -m http.server 8000`
- Navigate to `http://localhost:8000` in browser

For VR deployment:

- Install ngrok, launch it
- `ngrok http 8080`
- Navigate to port-forwarded URL in VR browser
- Enter VR mode

### Marker Code Events

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
