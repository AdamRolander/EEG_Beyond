#!/usr/bin/env python3
"""
Streams test LSL data (fake EEG, ImageryMarkers, ImageryTrialRatings) for ~15 s.
Record with LabRecorder to get a test XDF file.

Usage:
  1. Start LabRecorder, add streams: OpenBCI-CytonDaisy (or EEG), ImageryMarkers, ImageryTrialRatings
  2. Start recording
  3. Run this script: python3 stream_test_lsl.py
  4. Stop recording after the script finishes
"""

import time
import math

try:
    import pylsl
    import numpy as np
except ImportError:
    print("Install: pip install pylsl numpy")
    raise

# Stream names (must match what the neurofeedback app expects)
EEG_NAME = "OpenBCI-CytonDaisy"  # OpenBCI Cyton Daisy stream name (or "EEG" if renamed)
MARKERS_NAME = "ImageryMarkers"
RATINGS_NAME = "ImageryTrialRatings"

# OpenBCI Cyton Daisy: 16 channels (8 Cyton + 8 Daisy), 250 Hz typical
N_CHANNELS = 16
SRATE = 250
DURATION_S = 15


def main():
    # Fake EEG stream
    info_eeg = pylsl.StreamInfo(
        EEG_NAME,
        "EEG",
        N_CHANNELS,
        SRATE,
        pylsl.cf_float32,
        "test_eeg_001"
    )
    outlet_eeg = pylsl.StreamOutlet(info_eeg)
    print(f"[LSL] {EEG_NAME}: {N_CHANNELS} ch, {SRATE} Hz")

    # Markers stream
    info_m = pylsl.StreamInfo(MARKERS_NAME, "Markers", 1, 0, pylsl.cf_int32, "test_markers_001")
    outlet_m = pylsl.StreamOutlet(info_m)
    print(f"[LSL] {MARKERS_NAME}")

    # Trial ratings stream
    info_r = pylsl.StreamInfo(RATINGS_NAME, "Markers", 2, 0, pylsl.cf_int32, "test_ratings_001")
    outlet_r = pylsl.StreamOutlet(info_r)
    print(f"[LSL] {RATINGS_NAME}")

    t0 = pylsl.local_clock()
    # Markers to send: (approx relative time, code)
    # REC_START=20, REC_END=21; we simulate 3 trials
    markers_to_send = [
        (0.5, 90),   # EXP_START
        (1.0, 1),    # TRIAL_START
        (1.5, 10),   # BUFFER_START
        (2.0, 20),   # REC_START
        (5.0, 21),   # REC_END
        (5.5, 30),   # END_BEEP
        (7.0, 1),    # TRIAL_START
        (7.5, 10),
        (8.0, 20),
        (11.0, 21),
        (11.5, 30),
        (13.0, 1),
        (13.5, 10),
        (14.0, 20),
        (14.5, 21),
    ]
    ratings_to_send = [(1, 4), (2, 5), (3, 3)]  # (trial_number, rating)
    next_marker = 0
    next_rating = 0

    print(f"Streaming for {DURATION_S} s... (record with LabRecorder)")
    n_samples = DURATION_S * SRATE
    for i in range(n_samples):
        t = pylsl.local_clock() - t0
        # Fake EEG (noise + sinusoids)
        sample = np.zeros(N_CHANNELS, dtype=np.float32)
        for c in range(N_CHANNELS):
            sample[c] = 0.1 * math.sin(2 * math.pi * 10 * t + c) + 0.02 * (np.random.rand() - 0.5)
        outlet_eeg.push_sample(sample)

        # Markers
        while next_marker < len(markers_to_send) and markers_to_send[next_marker][0] <= t:
            _, code = markers_to_send[next_marker]
            outlet_m.push_sample([code])
            if code == 21 and next_rating < len(ratings_to_send):
                tn, r = ratings_to_send[next_rating]
                outlet_r.push_sample([tn, r])
                next_rating += 1
            next_marker += 1

        time.sleep(1.0 / SRATE)

    outlet_m.push_sample([91])  # EXP_END
    print("Done. Stop LabRecorder and save the XDF file.")


if __name__ == "__main__":
    main()
