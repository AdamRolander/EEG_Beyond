#!/usr/bin/env python3
"""
Calibration Protocol - CONTINUOUS DATA COLLECTION VERSION
Collects EEG continuously in background thread - solves buffer clearing problem
"""

import time
import random
import numpy as np
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_byprop, local_clock
import pygame
import os
from collections import defaultdict
import sys
import threading

def get_single_keypress():
    """Get a single keypress without waiting for ENTER (cross-platform)"""
    if sys.platform == 'win32':
        import msvcrt
        return msvcrt.getch().decode('utf-8')
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def get_rating():
    """Get rating from user with single keypress (no ENTER needed)"""
    while True:
        try:
            key = get_single_keypress()
            if key in ['1', '2', '3']:
                return key
            else:
                print(f"\r{RATING_PROMPT}", end='', flush=True)
        except (KeyboardInterrupt, EOFError):
            print("\nInterrupted")
            raise
        except Exception:
            # Fallback silencieux, continue à attendre une touche valide
            pass

# ============================================================================
# CONFIGURATION
# ============================================================================

CLASSES = ['banana', 'strawberry']
VISUALIZATION_TIME = 4
PAUSE_TIME = 5
MIN_GOOD_TRIALS = 25
RATING_PROMPT = "Rate visualization quality (1=bad, 2=ok, 3=good): "

SOUND_BANANA = "banana.mp3"
SOUND_STRAWBERRY = "strawberry.mp3"
SOUND_OK = "ok.mp3"
VOLUME_OTHER = 1.0

LSL_MARKER_NAME = 'CalibrationMarkers'
LSL_EEG_SEARCH_TYPE = 'EEG'

EPOCH_START = 0.0
EPOCH_END = 4.0

BANDPASS_LOW = 8
BANDPASS_HIGH = 30
CSP_COMPONENTS = 4
CV_FOLDS = 5

MODEL_FILE = "bci_model.pkl"
DATA_X_FILE = "X_raw.npy"
DATA_Y_FILE = "y.npy"

# ============================================================================
# CONTINUOUS DATA COLLECTOR
# ============================================================================

class ContinuousEEGCollector:
    """Continuously collects EEG data in background thread"""
    
    def __init__(self, inlet, srate):
        self.inlet = inlet
        self.srate = srate
        self.samples = []
        self.timestamps = []
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def start(self):
        """Start continuous collection"""
        self.running = True
        self.thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.thread.start()
        print("  ✓ Continuous EEG collection started")
    
    def stop(self):
        """Stop continuous collection"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("  ✓ Continuous EEG collection stopped")
    
    def _collect_loop(self):
        """Background thread loop"""
        while self.running:
            try:
                # Pull available data with longer timeout
                samples, timestamps = self.inlet.pull_chunk(timeout=1.0, max_samples=10000)
                
                if len(samples) > 0:
                    with self.lock:
                        self.samples.extend(samples)
                        self.timestamps.extend(timestamps)
            except Exception as e:
                # Continue silencieusement en cas d'erreur de lecture
                if self.running:  # Ne log que si on tourne encore
                    pass  # Ou print(f"  [Collector warning]: {e}") pour debug

    
    def get_epoch(self, marker_time):
        """Extract epoch around marker from continuously collected data"""
        with self.lock:
            if len(self.samples) == 0:
                return None, "No data collected"
            
            samples = np.array(self.samples)
            timestamps = np.array(self.timestamps)
            
            # Memory management: keep only last 60 seconds
            max_samples = int(60 * self.srate)
            if len(self.samples) > max_samples:
                samples_to_remove = len(self.samples) - max_samples
                self.samples = self.samples[samples_to_remove:]
                self.timestamps = self.timestamps[samples_to_remove:]
        
        print(f"  Total collected: {len(samples)} samples ({len(samples)/self.srate:.1f}s)")
        print(f"  Time range: {timestamps[0]:.2f} to {timestamps[-1]:.2f}")
        print(f"  Marker at: {marker_time:.2f}")
        
        # Find marker
        time_diffs = np.abs(timestamps - marker_time)
        marker_idx = np.argmin(time_diffs)
        
        if time_diffs[marker_idx] > 0.1:
            return None, f"Marker not found (closest: {time_diffs[marker_idx]*1000:.1f}ms)"
        
        print(f"  ✓ Marker at index {marker_idx}")
        
        # Extract epoch
        start_idx = marker_idx + int(EPOCH_START * self.srate)
        end_idx = marker_idx + int(EPOCH_END * self.srate)
        n_samples_needed = int((EPOCH_END - EPOCH_START) * self.srate)
        
        if start_idx < 0:
            return None, f"Epoch start before data ({start_idx})"
        
        if end_idx > len(timestamps):
            return None, f"Epoch end beyond data (need {n_samples_needed}, have {len(timestamps) - marker_idx})"
        
        # Extract and transpose
        epoch = samples[start_idx:end_idx, :].T
        print(f"  ✓ Epoch extracted: {epoch.shape}")
        
        return epoch, None

# ============================================================================

def initialize_lsl_marker():
    info = StreamInfo(LSL_MARKER_NAME, 'Markers', 1, 0, 'string', 'calibration123')
    return StreamOutlet(info)

def connect_to_eeg():
    print(f"Searching for EEG stream (type='{LSL_EEG_SEARCH_TYPE}')...")
    streams = resolve_byprop('type', LSL_EEG_SEARCH_TYPE, timeout=10.0)
    
    if not streams:
        print(f"WARNING: No EEG stream found!")
        return None, None, None
    
    if len(streams) > 1:
        print(f"\nFound {len(streams)} EEG streams:")
        for i, s in enumerate(streams):
            info = s.info()
            print(f"  {i+1}. {info.name()} ({info.channel_count()} channels, {info.nominal_srate()} Hz)")
        print(f"\nUsing stream: {streams[0].info().name()}")
    
    inlet = StreamInlet(streams[0], max_buflen=360)
    info = inlet.info()
    srate = info.nominal_srate()
    n_channels = info.channel_count()
    stream_name = info.name()
    
    print(f"✓ Connected to EEG stream: '{stream_name}'")
    print(f"  Channels: {n_channels}, Sampling Rate: {srate} Hz")
    
    return inlet, srate, n_channels

def play_sound_and_mark(sound_file, marker, outlet, volume=1.0):
    timestamp = local_clock()
    if os.path.exists(sound_file):
        sound = pygame.mixer.Sound(sound_file)
        sound.set_volume(volume)
        sound.play()
    outlet.push_sample([marker], timestamp)
    return timestamp

def run_trial(class_name, marker_outlet, collector):
    """
    Execute one calibration trial
    Now uses continuous collector - no buffer timing issues!
    """
    print(f"\n{'='*60}")
    print(f"TRIAL: {class_name.upper()}")
    print(f"{'='*60}")
    
    # Sound + marker
    sound_file = SOUND_BANANA if class_name == 'banana' else SOUND_STRAWBERRY
    marker_time = play_sound_and_mark(sound_file, class_name, marker_outlet, VOLUME_OTHER)
    time.sleep(1.0)
    
    # Visualization
    print(f"Visualization ({VISUALIZATION_TIME}s)...")
    time.sleep(VISUALIZATION_TIME)
    
    # End beep
    play_sound_and_mark(SOUND_OK, "ok", marker_outlet, VOLUME_OTHER)
    time.sleep(0.5)
    
    # CRITICAL: Wait for full epoch to be collected
    # We need 4s after marker, we've waited 1+4+0.5=5.5s, wait a bit more
    print("Waiting for complete epoch data...")
    time.sleep(0.5)
    
    # Extract epoch from continuously collected data
    print("Extracting epoch...")
    epoch, error = collector.get_epoch(marker_time)
    
    if epoch is not None:
        print("✓ EEG collected")
    else:
        print(f"✗ EEG failed: {error}")
    
    # Rating - maintenant juste une touche, pas besoin d'ENTRÉE
    print(f"\n{RATING_PROMPT}", end='', flush=True)
    rating = get_rating()
    print(rating)  # Echo le chiffre
    rating = int(rating)
    
    marker_outlet.push_sample([f"rating_{rating}"], local_clock())
    time.sleep(max(0, PAUSE_TIME - 1.0))
    
    return epoch, rating

def train_model(X, y):
    print("\n" + "="*60)
    print("TRAINING MODEL")
    print("="*60)
    
    from mne.decoding import CSP
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_score
    from scipy.signal import butter, filtfilt
    import joblib
    
    X = np.array(X)
    y = np.array(y)
    
    print(f"Data: X={X.shape}, y={y.shape}")
    print(f"Classes: {np.unique(y)} (counts: {np.bincount(y)})")
    
    # Filter
    print(f"\nBandpass {BANDPASS_LOW}-{BANDPASS_HIGH} Hz...")
    n_samples = X.shape[2]
    srate = n_samples / (EPOCH_END - EPOCH_START)
    nyq = srate / 2
    b, a = butter(4, [BANDPASS_LOW / nyq, BANDPASS_HIGH / nyq], btype='band')
    
    X_filtered = np.zeros_like(X)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            X_filtered[i, j, :] = filtfilt(b, a, X[i, j, :])
    
    # Train
    pipeline = Pipeline([
        ('CSP', CSP(n_components=CSP_COMPONENTS, reg=None, log=True, norm_trace=False)),
        ('LDA', LinearDiscriminantAnalysis())
    ])
    
    scores = cross_val_score(pipeline, X_filtered, y, cv=CV_FOLDS, scoring='accuracy')
    print(f"\nCV Accuracy: {scores.mean()*100:.1f}% ± {scores.std()*100:.1f}%")
    
    pipeline.fit(X_filtered, y)
    joblib.dump(pipeline, MODEL_FILE)
    np.save(DATA_X_FILE, X)
    np.save(DATA_Y_FILE, y)
    
    print(f"\n✓ Model saved: {MODEL_FILE}")
    return pipeline, scores.mean()

def main():
    print("="*60)
    print("CALIBRATION - CONTINUOUS COLLECTION VERSION")
    print("="*60)
    print(f"\nCollecting {MIN_GOOD_TRIALS} good trials per class")
    print("Press ENTER to start...")
    input()
    
    pygame.mixer.init()
    marker_outlet = initialize_lsl_marker()
    print("✓ Markers ready")
    
    eeg_inlet, srate, n_channels = connect_to_eeg()
    if eeg_inlet is None:
        print("\nERROR: No EEG stream!")
        return
    
    # Start continuous collection
    collector = ContinuousEEGCollector(eeg_inlet, srate)
    collector.start()
    
    # Wait for initial data - need at least 4s for first epoch
    print("Waiting for initial data accumulation (5 seconds)...")
    time.sleep(5.0)
    
    # Check how much data we have
    with collector.lock:
        n_samples = len(collector.samples)
    print(f"  Accumulated {n_samples} samples ({n_samples/srate:.1f}s) - ready to start")
    
    good_trials = defaultdict(int)
    all_epochs = []
    all_labels = []
    
    marker_outlet.push_sample(['calibration_start'], local_clock())
    
    print("\n" + "="*60)
    print("CALIBRATION STARTED")
    print("="*60)
    
    trial_count = 0
    
    try:
        while min(good_trials.values(), default=0) < MIN_GOOD_TRIALS or len(good_trials) < len(CLASSES):
            class_name = random.choice(CLASSES)
            trial_count += 1
            
            print(f"\nTrial {trial_count} | Good: ", end='')
            display_order = CLASSES.copy()
            random.shuffle(display_order)
            for cls in display_order:
                print(f"{cls}={good_trials[cls]}/{MIN_GOOD_TRIALS} ", end='')
            print()
            
            epoch, rating = run_trial(class_name, marker_outlet, collector)
            
            if epoch is not None and rating == 3:
                all_epochs.append(epoch)
                all_labels.append(CLASSES.index(class_name))
                good_trials[class_name] += 1
                print(f"✓ Saved ({class_name}, rating={rating})")
            elif epoch is not None:
                print(f"○ Collected but not counted (rating={rating})")
            else:
                print(f"✗ Failed")
    
    except KeyboardInterrupt:
        print("\n\nCalibration interrupted by user")
    finally:
        # Stop collector
        collector.stop()
    
    marker_outlet.push_sample(['calibration_end'], local_clock())
    
    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)
    
    if len(all_epochs) >= 10:
        pipeline, accuracy = train_model(all_epochs, all_labels)
        print(f"\nAccuracy: {accuracy*100:.1f}%")
        print("Ready for BCI!")
    else:
        print(f"\nNot enough data to train model (got {len(all_epochs)}, need 10)")
    
    pygame.mixer.quit()

if __name__ == "__main__":
    main()