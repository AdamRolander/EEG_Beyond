# EEG Imagery Experiment Platform

A modular, Python-based platform for conducting EEG imagery experiments with LSL integration.

## Overview

This platform supports mental imagery experiments where participants visualize categories (colors, shapes, complex objects) while EEG data is recorded. The system provides:

- **Web-based GUI** for experiment configuration and control
- **LSL marker streaming** for EEG synchronization
- **Dynamic category loading** from audio files
- **Configurable trial structure** with breaks and Likert scales
- **Comprehensive logging** in JSON format

## Architecture

```
imagery/
├── app.py                    # Flask server + WebSocket handling
├── config.py                 # Configuration, marker codes, paths
├── experiment_engine.py      # Core state machine + trial logic
├── lsl_bridge.py            # LSL streaming abstraction
├── audio_manager.py         # Audio playback with pygame
├── generate_audio.py        # Utility to create placeholder audio
├── requirements.txt         # Python dependencies
├── templates/
│   └── index.html           # Main UI template
├── static/
│   ├── css/style.css        # Styling
│   └── js/experiment.js     # Frontend logic
├── audio/
│   ├── colors/              # Color category audio
│   ├── primitives/          # Primitive shapes audio
│   ├── complex/             # Complex objects audio
│   └── administrative/      # Beep and other sounds
└── logs/                    # Session logs (JSON)
```

## Installation

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Generate placeholder audio (for testing)
python generate_audio.py
```

## Usage

### Starting the Server

```bash
python app.py
```

Then open http://localhost:8080 in your browser.

### Adding Categories

Categories are loaded dynamically from audio files. To add a new category:

1. Record an audio file saying the category name (e.g., "triangle.mp3")
2. Place it in the appropriate folder:
   - `audio/colors/` for color visualization
   - `audio/primitives/` for primitive shapes
   - `audio/complex/` for complex objects
3. The category will appear automatically in the UI

### Experiment Flow

```
[Audio Cue] → [Pre-Recording Buffer] → [RECORDING] → [Recording End] → [End Beep] → [Gap] → [Next Trial]
                                            ↑                               ↑
                                       REC_START marker              REC_END marker
```

At configured intervals, breaks occur with optional Likert scale rating.

### Keyboard Controls

- **Space**: Pause/Resume during experiment, Continue after break

## Configuration Options

| Parameter              | Description                           | Default |
| ---------------------- | ------------------------------------- | ------- |
| Visualization Duration | How long to record EEG during imagery | 3000ms  |
| Pre-Recording Buffer   | Delay between cue and recording start | 500ms   |
| Inter-Trial Gap        | Time between trials                   | 1000ms  |
| Trials per Category    | Number of trials for each category    | 10      |
| Trials until Break     | Trials before a break occurs          | 15      |
| Randomize Order        | Shuffle trial order                   | Yes     |
| End Beep               | Play beep when visualization ends     | Yes     |
| Likert Scale           | Enable quality rating at breaks       | Yes     |

## LSL Markers

### Marker Codes

| Event            | Numeric Code | String Marker        |
| ---------------- | ------------ | -------------------- |
| Experiment Start | 90           | EXP_START            |
| Experiment End   | 91           | EXP_END              |
| Trial Start      | 1            | TRIAL_START          |
| Buffer Start     | 10           | BUFFER_START         |
| Recording Start  | 20           | REC_START            |
| Recording End    | 21           | REC_END              |
| End Beep         | 30           | END_BEEP             |
| Break Start      | 40           | BREAK_START          |
| Break End        | 41           | BREAK_END            |
| Pause            | 60           | PAUSE                |
| Resume           | 61           | RESUME               |
| Likert 1-5       | 51-55        | LIKERT_1 to LIKERT_5 |

### Category Cue Markers

- **Colors**: 100 + index (e.g., CUE_RED = 100, CUE_GREEN = 101)
- **Primitives**: 200 + index (e.g., CUE_SPHERE = 200)
- **Complex**: 300 + index (e.g., CUE_FACE = 300)

## Session Logs

Each session generates a JSON log in the `logs/` folder:

```json
{
  "session_id": "20240115_143022",
  "start_time": "2024-01-15T14:30:22.123456",
  "end_time": "2024-01-15T14:45:33.789012",
  "config": { ... },
  "categories": ["red", "green", "blue"],
  "trials": [
    {
      "trial_number": 1,
      "category": "red",
      "cue_onset": 1234.567,
      "recording_start": 1235.123,
      "recording_end": 1238.123,
      "markers": [ ... ]
    }
  ],
  "likert_responses": [
    {"timestamp": 1500.123, "rating": 4, "after_trial": 15}
  ],
  "events": [ ... ]
}
```

## Extending the Platform

### Adding New Experiment Types

1. Add entry to `EXPERIMENT_TYPES` in `config.py`:

   ```python
   "new_type": {
       "display_name": "New Experiment",
       "audio_folder": "new_type",
       "marker_base": 400,  # Unique base code
   }
   ```

2. Create the audio folder and add files:

   ```
   audio/new_type/
   ├── category1.mp3
   ├── category2.mp3
   └── ...
   ```

3. Add a tab button in `index.html`:
   ```html
   <button class="tab-btn" data-tab="new_type">New Experiment</button>
   ```

### Custom Timing Precision

The experiment engine uses `time.perf_counter()` with busy-wait for the final 2ms of any timing interval, achieving sub-millisecond precision. For even higher precision, consider:

- Running with elevated priority
- Using a real-time OS kernel
- Hardware triggers via parallel port or Arduino

## Troubleshooting

### No audio playing

- Check that audio files exist in the correct folders
- Ensure pygame is installed correctly
- On Linux, you may need `pulseaudio` or `pipewire`

### LSL not connecting

- Install `pylsl`: `pip install pylsl`
- Ensure no firewall is blocking UDP
- Check that your EEG software is listening for the stream

### Categories not loading

- Verify audio files have `.mp3`, `.wav`, or `.ogg` extension
- Check file permissions
- Look for errors in the terminal

## License

Research use - XRLab, UCSD
