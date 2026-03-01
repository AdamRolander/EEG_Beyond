# Generate a test XDF file

Pyxdf cannot **write** XDF files directly. You need to **record** LSL streams with **LabRecorder** to get a .xdf file.

## Method 1: LSL script (recommended)

1. Install LabRecorder (or use an existing installation).
2. Start **LabRecorder**.
3. Start recording and **add the 3 streams** when they appear:
   - **OpenBCI-CytonDaisy** (or **EEG**) — 16 channels, 250 Hz (OpenBCI Cyton Daisy config)
   - **ImageryMarkers**
   - **ImageryTrialRatings**
4. In a terminal:
   ```bash
   cd data_collection/neurofeedback/scripts
   python3 stream_test_lsl.py
   ```
5. Wait for the script to finish (~15 s), then **stop** recording in LabRecorder and **save** the .xdf file.

The resulting file contains fake 16-channel EEG (OpenBCI Cyton Daisy layout), markers (REC_START, REC_END, etc.), and 3 trial ratings (4, 5, 3). You can import it in the neurofeedback app to test the Streams / Channels / Markers / Ratings box.

## Method 2: Real recording

Run a real **Imagery** session (Fruits, Phase 1) and record with LabRecorder: you get an XDF with the actual ImageryMarkers and ImageryTrialRatings streams (and your EEG stream if the amplifier is connected).
