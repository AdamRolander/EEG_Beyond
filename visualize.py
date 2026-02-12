#!/usr/bin/env python3
"""
EEG Stream Receiver - Compatible with all pylsl versions
"""

import time

# Try different import methods for compatibility
try:
    from pylsl import StreamInlet, resolve_byprop
    resolve_function = lambda name: resolve_byprop('name', name, timeout=5.0)
except ImportError:
    try:
        from pylsl import StreamInlet, resolve_stream
        resolve_function = lambda name: resolve_stream('name', name)
    except ImportError:
        from pylsl import StreamInlet, resolve_streams
        resolve_function = lambda name: [s for s in resolve_streams(5.0) if s.name() == name]

# ============================================================================
# CONFIGURATION
# ============================================================================

STREAM_NAME = 'SimulatedEEG'    # Name of stream to connect to
DISPLAY_INTERVAL = 1.0          # Show stats every N seconds

# ============================================================================

def main():
    print("=" * 60)
    print("EEG STREAM RECEIVER")
    print("=" * 60)
    print(f"\nSearching for stream: '{STREAM_NAME}'...")
    
    # Resolve stream
    streams = resolve_function(STREAM_NAME)
    
    if not streams:
        print(f"ERROR: No stream named '{STREAM_NAME}' found!")
        print("Make sure the simulated_eeg_stream.py is running.")
        return
    
    # Create inlet
    inlet = StreamInlet(streams[0])
    
    # Get stream info
    info = inlet.info()
    print(f"\n✓ Connected to stream!")
    print(f"Stream Name: {info.name()}")
    print(f"Stream Type: {info.type()}")
    print(f"Channels: {info.channel_count()}")
    print(f"Sampling Rate: {info.nominal_srate()} Hz")
    
    # Get channel names
    ch = info.desc().child("channels").child("channel")
    channel_names = []
    for _ in range(info.channel_count()):
        channel_names.append(ch.child_value("label"))
        ch = ch.next_sibling()
    
    print(f"Channel Names: {', '.join(channel_names)}")
    print(f"\nReceiving data... (Press Ctrl+C to stop)")
    print("=" * 60)
    
    # Receiving loop
    sample_count = 0
    last_display = time.time()
    samples_buffer = []
    
    try:
        while True:
            # Pull sample
            sample, timestamp = inlet.pull_sample(timeout=1.0)
            
            if sample:
                sample_count += 1
                samples_buffer.append(sample)
                
                # Display stats periodically
                if time.time() - last_display >= DISPLAY_INTERVAL:
                    if samples_buffer:
                        import numpy as np
                        samples_array = np.array(samples_buffer)
                        
                        print(f"\n[{sample_count} samples received]")
                        print(f"Timestamp: {timestamp:.3f}s")
                        print("Channel statistics (last {:.1f}s):".format(DISPLAY_INTERVAL))
                        
                        for i, name in enumerate(channel_names):
                            mean_val = np.mean(samples_array[:, i])
                            std_val = np.std(samples_array[:, i])
                            min_val = np.min(samples_array[:, i])
                            max_val = np.max(samples_array[:, i])
                            print(f"  {name:4s}: μ={mean_val:6.2f} σ={std_val:5.2f} "
                                  f"[{min_val:6.2f}, {max_val:6.2f}] μV")
                        
                        samples_buffer = []
                        last_display = time.time()
            
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("Receiver stopped")
        print(f"Total samples received: {sample_count}")
        print("=" * 60)

if __name__ == "__main__":
    main()