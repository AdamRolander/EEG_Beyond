#!/usr/bin/env python3
"""
Simulated EEG Stream - ActiChamp 64 Channels (OPTIMIZED)
Pushes data in chunks instead of sample-by-sample for better performance
"""

import time
import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock

# ============================================================================
# CONFIGURATION - ActiChamp 64 Channels
# ============================================================================

CHANNELS = 64
SAMPLING_RATE = 500  # Hz

# Standard 10-20 system 64 channel names
CHANNEL_NAMES = [
    'Fp1', 'Fp2', 'F7', 'F3', 'Fz', 'F4', 'F8', 'FC5', 'FC1', 'FC2', 'FC6',
    'T7', 'C3', 'Cz', 'C4', 'T8', 'TP9', 'CP5', 'CP1', 'CP2', 'CP6', 'TP10',
    'P7', 'P3', 'Pz', 'P4', 'P8', 'PO9', 'O1', 'Oz', 'O2', 'PO10',
    'AF7', 'AF3', 'AF4', 'AF8', 'F5', 'F1', 'F2', 'F6', 'FC3', 'FCz', 'FC4',
    'C5', 'C1', 'C2', 'C6', 'CP3', 'CPz', 'CP4', 'P5', 'P1', 'P2', 'P6',
    'PO7', 'PO3', 'POz', 'PO4', 'PO8', 'FT9', 'FT10', 'TP7', 'TP8', 'Iz'
]

# Signal Parameters
BASELINE_AMPLITUDE = 50
ALPHA_FREQ = 10
BETA_FREQ = 20
THETA_FREQ = 6
NOISE_LEVEL = 5

# LSL Stream
STREAM_NAME = 'BrainVision RDA'
STREAM_TYPE = 'EEG'
STREAM_ID = 'actichamp_simulator_64ch'

# PERFORMANCE: Push data in chunks
CHUNK_SIZE = 50  # Push 50 samples at a time (100ms chunks @ 500Hz)

# ============================================================================

def generate_realistic_eeg(t, channel_idx):
    """Generate realistic EEG signal"""
    alpha = BASELINE_AMPLITUDE * 0.6 * np.sin(2 * np.pi * (ALPHA_FREQ + channel_idx * 0.5) * t)
    beta = BASELINE_AMPLITUDE * 0.3 * np.sin(2 * np.pi * (BETA_FREQ + channel_idx * 0.3) * t)
    theta = BASELINE_AMPLITUDE * 0.4 * np.sin(2 * np.pi * (THETA_FREQ + channel_idx * 0.2) * t)
    noise = np.random.randn() * NOISE_LEVEL
    
    return alpha + beta + theta + noise

def main():
    print("=" * 70)
    print("OPTIMIZED EEG SIMULATOR - ActiChamp 64 Channels")
    print("=" * 70)
    
    # Create LSL stream
    info = StreamInfo(
        name=STREAM_NAME,
        type=STREAM_TYPE,
        channel_count=CHANNELS,
        nominal_srate=SAMPLING_RATE,
        channel_format='float32',
        source_id=STREAM_ID
    )
    
    # Add channel metadata
    chns = info.desc().append_child("channels")
    for i, name in enumerate(CHANNEL_NAMES):
        ch = chns.append_child("channel")
        ch.append_child_value("label", name)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")
    
    # Create outlet with larger buffer
    outlet = StreamOutlet(info, chunk_size=CHUNK_SIZE, max_buffered=360)
    
    print(f"\nStream Name: '{STREAM_NAME}'")
    print(f"Stream Type: '{STREAM_TYPE}'")
    print(f"Channels: {CHANNELS}")
    print(f"Sampling Rate: {SAMPLING_RATE} Hz")
    print(f"Chunk Size: {CHUNK_SIZE} samples ({CHUNK_SIZE/SAMPLING_RATE*1000:.0f}ms)")
    print(f"\nStreaming... (Press Ctrl+C to stop)")
    print("=" * 70)
    
    # Streaming loop
    start_time = local_clock()
    sample_count = 0
    
    try:
        while True:
            # Generate chunk of samples
            chunk_start_time = local_clock()
            chunk = []
            
            for i in range(CHUNK_SIZE):
                current_time = chunk_start_time - start_time + (i / SAMPLING_RATE)
                sample = [generate_realistic_eeg(current_time, ch) for ch in range(CHANNELS)]
                chunk.append(sample)
            
            # Push entire chunk at once
            outlet.push_chunk(chunk)
            sample_count += CHUNK_SIZE
            
            # Progress indicator
            if sample_count % SAMPLING_RATE == 0:
                print(f"Streaming... {sample_count} samples ({sample_count/SAMPLING_RATE:.1f}s)")
            
            # Wait for next chunk
            chunk_duration = CHUNK_SIZE / SAMPLING_RATE
            elapsed = local_clock() - chunk_start_time
            sleep_time = chunk_duration - elapsed
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                print(f"WARNING: Cannot keep up! Behind by {-sleep_time*1000:.1f}ms")
            
    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        print("Stream stopped")
        print(f"Total samples sent: {sample_count}")
        print(f"Duration: {sample_count/SAMPLING_RATE:.2f} seconds")
        print("=" * 70)

if __name__ == "__main__":
    main()