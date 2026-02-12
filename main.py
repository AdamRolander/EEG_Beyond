#!/usr/bin/env python3
"""
Minimal experimental protocol with LSL
Two classes: banana and strawberry
"""

import time
import random
from pylsl import StreamInfo, StreamOutlet
import pygame
import os

# ============================================================================
# CONFIGURATION - Adjust these parameters
# ============================================================================

# Classes
CLASSES = ['banana', 'strawberry']

# Timing (in seconds)
VISUALIZATION_TIME = 4      # Duration of visualization after stimulus
PAUSE_TIME = 5              # Total pause duration

# Trials
N_TRIALS = 10               # Number of trials per class
BREAK_EVERY = 20            # Break every N trials (set to 0 to disable)

# Audio files
SOUND_BANANA = "banana.mp3"
SOUND_STRAWBERRY = "strawberry.mp3"
SOUND_OK = "ok.mp3"          # End-of-trial beep
SOUND_BREAK = "press.mp3"

# Volume control (0.0 to 1.0)
VOLUME_OTHER = 1.0          # All sounds volume (100%)

# LSL Stream
LSL_STREAM_NAME = 'ExperimentMarkers'
LSL_STREAM_TYPE = 'Markers'
LSL_SOURCE_ID = 'experiment123'

# ============================================================================

def initialize_lsl():
    """Initialize LSL stream for markers"""
    info = StreamInfo(
        name=LSL_STREAM_NAME,
        type=LSL_STREAM_TYPE,
        channel_count=1,
        nominal_srate=0,
        channel_format='string',
        source_id=LSL_SOURCE_ID
    )
    return StreamOutlet(info)

def play_sound_and_mark(sound_file, marker, outlet, volume=1.0):
    """Play sound and send LSL marker"""
    if os.path.exists(sound_file):
        sound = pygame.mixer.Sound(sound_file)
        sound.set_volume(volume)
        sound.play()
        outlet.push_sample([marker])
        print(f"Marker sent: {marker}")
    else:
        print(f"Warning: {sound_file} not found")
        outlet.push_sample([marker])
        print(f"Marker sent: {marker} (no sound)")

def run_trial(class_name, outlet):
    """Execute one trial for given class"""
    print(f"\n=== TRIAL: {class_name.upper()} ===")
    
    # 1. Fruit sound at beginning (0-1s)
    if class_name == 'banana':
        sound_file = SOUND_BANANA
    elif class_name == 'strawberry':
        sound_file = SOUND_STRAWBERRY
    else:
        sound_file = f"{class_name}.mp3"
    
    play_sound_and_mark(sound_file, class_name, outlet, VOLUME_OTHER)
    time.sleep(1.0)
    
    # 2. Pure visualization (1s-5s = 4s)
    print(f"Visualization ({VISUALIZATION_TIME}s)...")
    time.sleep(VISUALIZATION_TIME)
    
    # 3. End-of-trial beep (5s-5.5s)
    play_sound_and_mark(SOUND_OK, "ok", outlet, VOLUME_OTHER)
    time.sleep(0.5)
    
    # 4. Pause period (5.5s-9.5s = 4s)
    time.sleep(PAUSE_TIME - 1.0)

def main():
    print("=" * 50)
    print("EXPERIMENTAL PROTOCOL - LSL")
    print("=" * 50)
    print("\nPress ENTER to start experiment...")
    input()
    
    # Initialization
    print("\nInitializing...")
    pygame.mixer.init()
    outlet = initialize_lsl()
    print("LSL stream initialized: 'ExperimentMarkers'")
    
    # Create randomized sequence
    sequence = CLASSES * N_TRIALS
    random.shuffle(sequence)
    print(f"\nTotal trials: {len(sequence)}")
    print("Randomized sequence generated\n")
    
    time.sleep(2)
    print("EXPERIMENT START\n")
    
    # Start marker
    outlet.push_sample(['experiment_start'])
    
    # Execute all trials
    for i, class_name in enumerate(sequence, 1):
        print(f"\n[Trial {i}/{len(sequence)}]")
        run_trial(class_name, outlet)
        
        # Break every N trials
        if BREAK_EVERY > 0 and i % BREAK_EVERY == 0 and i < len(sequence):
            print("\n" + "=" * 50)
            play_sound_and_mark(SOUND_BREAK, "break", outlet, VOLUME_OTHER)
            print("Press ENTER to continue...")
            input()
            print("=" * 50)
    
    # End marker
    outlet.push_sample(['experiment_end'])
    print("\n" + "=" * 50)
    print("EXPERIMENT COMPLETE")
    print("=" * 50)
    
    pygame.mixer.quit()

if __name__ == "__main__":
    main()