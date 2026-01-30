"""
Experiment Engine for EEG Imagery Experiments
Core state machine handling trial logic, timing, and experiment flow.
"""

import time
import random
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from threading import Thread, Event

from config import (
    ExperimentConfig, 
    MarkerCode, 
    EXPERIMENT_TYPES, 
    AUDIO_DIR, 
    LOGS_DIR,
    get_administrative_audio_path
)
from lsl_bridge import LSLBridge, get_lsl_bridge
from audio_manager import AudioManager, get_audio_manager


class ExperimentState(Enum):
    """States for the experiment state machine."""
    IDLE = auto()           # Waiting to start
    RUNNING = auto()        # Experiment in progress
    PAUSED = auto()         # User paused
    BREAK = auto()          # Break between trial blocks
    LIKERT = auto()         # Waiting for Likert response
    COMPLETED = auto()      # Experiment finished


@dataclass
class TrialData:
    """Data for a single trial."""
    trial_number: int
    category: str
    category_index: int
    experiment_type: str
    
    # Timestamps (LSL clock)
    cue_onset: float = 0
    buffer_start: float = 0
    recording_start: float = 0
    recording_end: float = 0
    end_beep: float = 0
    
    # Markers sent
    markers: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "trial_number": self.trial_number,
            "category": self.category,
            "category_index": self.category_index,
            "experiment_type": self.experiment_type,
            "cue_onset": self.cue_onset,
            "buffer_start": self.buffer_start,
            "recording_start": self.recording_start,
            "recording_end": self.recording_end,
            "end_beep": self.end_beep,
            "markers": self.markers
        }


@dataclass
class SessionLog:
    """Complete log for an experiment session."""
    session_id: str
    start_time: str
    config: dict
    categories: List[str]
    trials: List[TrialData] = field(default_factory=list)
    likert_responses: List[Dict] = field(default_factory=list)
    events: List[Dict] = field(default_factory=list)
    end_time: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "config": self.config,
            "categories": self.categories,
            "trials": [t.to_dict() for t in self.trials],
            "likert_responses": self.likert_responses,
            "events": self.events
        }
    
    def save(self, logs_dir: str = LOGS_DIR):
        """Save session log to JSON file."""
        os.makedirs(logs_dir, exist_ok=True)
        filename = f"session_{self.session_id}.json"
        path = os.path.join(logs_dir, filename)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Session log saved: {path}")
        return path


class ExperimentEngine:
    """
    Core experiment engine managing trial flow and state.
    
    Emits events via callbacks for UI updates.
    """
    
    def __init__(self):
        self.config: Optional[ExperimentConfig] = None
        self.state = ExperimentState.IDLE
        self.lsl: Optional[LSLBridge] = None
        self.audio: Optional[AudioManager] = None
        
        # Trial management
        self.trial_queue: List[str] = []  # Categories in order
        self.current_trial_index: int = 0
        self.trials_since_break: int = 0
        self.current_trial: Optional[TrialData] = None
        
        # Category mapping
        self.categories: List[str] = []
        self.category_to_index: Dict[str, int] = {}
        
        # Session logging
        self.session_log: Optional[SessionLog] = None
        
        # Threading
        self._stop_event = Event()
        self._pause_event = Event()
        self._trial_thread: Optional[Thread] = None
        
        # Callbacks for UI updates
        self.on_state_change: Optional[Callable[[ExperimentState], None]] = None
        self.on_trial_start: Optional[Callable[[TrialData], None]] = None
        self.on_phase_change: Optional[Callable[[str, str], None]] = None  # (phase, category)
        self.on_trial_complete: Optional[Callable[[TrialData], None]] = None
        self.on_break_start: Optional[Callable[[int, int], None]] = None  # (completed, total)
        self.on_experiment_complete: Optional[Callable[[SessionLog], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    def initialize(self, config: ExperimentConfig) -> bool:
        """
        Initialize the experiment with given configuration.
        
        Args:
            config: Experiment configuration
            
        Returns:
            True if initialization successful
        """
        self.config = config
        
        # Initialize LSL
        self.lsl = get_lsl_bridge(config.lsl_stream_name)
        if not self.lsl.connect():
            print("Warning: LSL not connected, markers will only be logged")
        
        # Initialize audio
        self.audio = get_audio_manager()
        
        # Load audio for experiment type
        exp_info = EXPERIMENT_TYPES.get(config.experiment_type)
        if not exp_info:
            self._emit_error(f"Unknown experiment type: {config.experiment_type}")
            return False
        
        audio_folder = os.path.join(AUDIO_DIR, exp_info["audio_folder"])
        
        # Scan and filter categories
        available_categories = self.audio.scan_audio_folder(audio_folder)
        
        if config.enabled_categories:
            self.categories = [c for c in config.enabled_categories if c in available_categories]
        else:
            self.categories = available_categories
        
        if not self.categories:
            self._emit_error(f"No valid categories found in {audio_folder}")
            return False
        
        # Preload audio
        self.audio.preload_folder(audio_folder)
        
        # Load beep if enabled
        if config.enable_end_beep:
            beep_path = get_administrative_audio_path("beep")
            if not self.audio.load_beep(beep_path):
                print(f"Warning: Could not load beep from {beep_path}")
        
        # Build category index mapping
        self.category_to_index = {cat: idx for idx, cat in enumerate(self.categories)}
        
        # Build trial queue
        self._build_trial_queue()
        
        # Initialize session log
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log = SessionLog(
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            config=config.to_dict(),
            categories=self.categories
        )
        
        self.current_trial_index = 0
        self.trials_since_break = 0
        self.state = ExperimentState.IDLE
        
        print(f"Experiment initialized: {len(self.trial_queue)} trials across {len(self.categories)} categories")
        return True
    
    def _build_trial_queue(self):
        """Build the queue of trials (categories in order)."""
        self.trial_queue = []
        
        # Create trials_per_category instances of each category
        for _ in range(self.config.trials_per_category):
            for category in self.categories:
                self.trial_queue.append(category)
        
        # Randomize if configured
        if self.config.randomize_order:
            random.shuffle(self.trial_queue)
        
        print(f"Trial queue built: {len(self.trial_queue)} trials")
    
    def start(self):
        """Start the experiment."""
        if self.state != ExperimentState.IDLE:
            print("Experiment not in IDLE state")
            return
        
        self._stop_event.clear()
        self._pause_event.clear()
        
        # Send experiment start marker
        self._log_marker(*self.lsl.send_marker(MarkerCode.EXP_START))
        
        self.state = ExperimentState.RUNNING
        self._emit_state_change()
        
        # Start trial loop in background thread
        self._trial_thread = Thread(target=self._run_trial_loop, daemon=True)
        self._trial_thread.start()
    
    def pause(self):
        """Pause the experiment."""
        if self.state == ExperimentState.RUNNING:
            self._pause_event.set()
            self._log_marker(*self.lsl.send_marker(MarkerCode.PAUSE))
            self.state = ExperimentState.PAUSED
            self._emit_state_change()
    
    def resume(self):
        """Resume from pause or break."""
        if self.state == ExperimentState.PAUSED:
            self._log_marker(*self.lsl.send_marker(MarkerCode.RESUME))
            self._pause_event.clear()
            self.state = ExperimentState.RUNNING
            self._emit_state_change()
        elif self.state == ExperimentState.BREAK:
            self._log_marker(*self.lsl.send_marker(MarkerCode.BREAK_END))
            self.trials_since_break = 0
            self.state = ExperimentState.RUNNING
            self._emit_state_change()
    
    def stop(self):
        """Stop the experiment."""
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused
        
        if self._trial_thread and self._trial_thread.is_alive():
            self._trial_thread.join(timeout=2.0)
        
        self._log_marker(*self.lsl.send_marker(MarkerCode.EXP_END))
        
        if self.session_log:
            self.session_log.end_time = datetime.now().isoformat()
            # Only save if logging is enabled
            if self.config and self.config.enable_logging:
                self.session_log.save()
        
        self.state = ExperimentState.IDLE
        self._emit_state_change()
    
    def submit_likert(self, rating: int):
        """Submit a Likert scale response."""
        if self.state == ExperimentState.LIKERT:
            timestamp, code, marker = self.lsl.send_likert_response(rating)
            
            self.session_log.likert_responses.append({
                "timestamp": timestamp,
                "rating": rating,
                "after_trial": self.current_trial_index
            })
            
            # Move to break state (waiting for spacebar to continue)
            self.state = ExperimentState.BREAK
            self._emit_state_change()
    
    def _run_trial_loop(self):
        """Main trial loop running in background thread."""
        exp_info = EXPERIMENT_TYPES[self.config.experiment_type]
        audio_folder = os.path.join(AUDIO_DIR, exp_info["audio_folder"])
        marker_base = exp_info["marker_base"]
        
        while self.current_trial_index < len(self.trial_queue):
            # Check for stop
            if self._stop_event.is_set():
                break
            
            # Check for pause
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.05)
            
            if self._stop_event.is_set():
                break
            
            # Check for break
            if (self.trials_since_break >= self.config.trials_until_break and 
                self.current_trial_index < len(self.trial_queue)):
                self._start_break()
                
                # Wait for resume
                while self.state in (ExperimentState.BREAK, ExperimentState.LIKERT):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.05)
                
                if self._stop_event.is_set():
                    break
            
            # Run trial
            category = self.trial_queue[self.current_trial_index]
            self._run_single_trial(category, audio_folder, marker_base)
            
            self.current_trial_index += 1
            self.trials_since_break += 1
            
            # Inter-trial gap
            if self.current_trial_index < len(self.trial_queue):
                self._precise_sleep(self.config.inter_trial_gap_ms / 1000.0)
        
        # Experiment complete
        if not self._stop_event.is_set():
            self._log_marker(*self.lsl.send_marker(MarkerCode.EXP_END))
            self.session_log.end_time = datetime.now().isoformat()
            # Only save if logging is enabled
            if self.config.enable_logging:
                self.session_log.save()
            self.state = ExperimentState.COMPLETED
            self._emit_state_change()
            
            if self.on_experiment_complete:
                self.on_experiment_complete(self.session_log)
    
    def _run_single_trial(self, category: str, audio_folder: str, marker_base: int):
        """Execute a single trial."""
        trial = TrialData(
            trial_number=self.current_trial_index + 1,
            category=category,
            category_index=self.category_to_index[category],
            experiment_type=self.config.experiment_type
        )
        self.current_trial = trial
        
        if self.on_trial_start:
            self.on_trial_start(trial)
        
        # === CUE PHASE ===
        if self.on_phase_change:
            self.on_phase_change("cue", category)
        
        # Send cue marker and play audio
        timestamp, code, marker = self.lsl.send_cue_marker(
            category, marker_base, trial.category_index
        )
        trial.cue_onset = timestamp
        trial.markers.append({"time": timestamp, "code": code, "marker": marker})
        
        # Play category audio
        self.audio.play_by_path(audio_folder, category, blocking=False)
        
        # Wait for audio to finish (approximate - could be made more precise)
        audio_key = os.path.join(audio_folder, category)
        audio_duration = self.audio.get_duration(audio_key)
        self._precise_sleep(audio_duration / 1000.0)
        
        # === BUFFER PHASE ===
        if self.on_phase_change:
            self.on_phase_change("buffer", category)
        
        timestamp, code, marker = self.lsl.send_marker(MarkerCode.BUFFER_START)
        trial.buffer_start = timestamp
        trial.markers.append({"time": timestamp, "code": code, "marker": marker})
        
        self._precise_sleep(self.config.pre_recording_buffer_ms / 1000.0)
        
        # === RECORDING PHASE ===
        if self.on_phase_change:
            self.on_phase_change("recording", category)
        
        timestamp, code, marker = self.lsl.send_marker(MarkerCode.REC_START)
        trial.recording_start = timestamp
        trial.markers.append({"time": timestamp, "code": code, "marker": marker})
        
        self._precise_sleep(self.config.visualization_duration_ms / 1000.0)
        
        timestamp, code, marker = self.lsl.send_marker(MarkerCode.REC_END)
        trial.recording_end = timestamp
        trial.markers.append({"time": timestamp, "code": code, "marker": marker})
        
        # === END BEEP (if enabled) ===
        if self.config.enable_end_beep:
            if self.on_phase_change:
                self.on_phase_change("end_beep", category)
            
            timestamp, code, marker = self.lsl.send_marker(MarkerCode.END_BEEP)
            trial.end_beep = timestamp
            trial.markers.append({"time": timestamp, "code": code, "marker": marker})
            
            self.audio.play_beep()
        
        # Log trial
        self.session_log.trials.append(trial)
        
        if self.on_trial_complete:
            self.on_trial_complete(trial)
    
    def _start_break(self):
        """Start a break period."""
        self._log_marker(*self.lsl.send_marker(MarkerCode.BREAK_START))
        
        # Play press_to_continue audio if available
        press_continue_path = get_administrative_audio_path("press_to_continue")
        if os.path.exists(press_continue_path + ".mp3") or os.path.exists(press_continue_path + ".wav"):
            # Try to load and play it
            for ext in [".mp3", ".wav"]:
                full_path = press_continue_path + ext
                if os.path.exists(full_path):
                    self.audio.preload_file("_press_continue", full_path)
                    self.audio.play("_press_continue", blocking=False)
                    break
        
        if self.config.enable_likert:
            self.state = ExperimentState.LIKERT
        else:
            self.state = ExperimentState.BREAK
        
        self._emit_state_change()
        
        if self.on_break_start:
            self.on_break_start(self.current_trial_index, len(self.trial_queue))
    
    def _precise_sleep(self, duration_seconds: float):
        """
        High-precision sleep using busy-wait for final milliseconds.
        """
        if duration_seconds <= 0:
            return
            
        # Sleep for most of the duration (less precise but CPU-friendly)
        if duration_seconds > 0.002:
            time.sleep(duration_seconds - 0.002)
        
        # Busy-wait for final ~2ms (more precise)
        target = time.perf_counter() + 0.002 if duration_seconds > 0.002 else time.perf_counter() + duration_seconds
        while time.perf_counter() < target:
            pass
    
    def _log_marker(self, timestamp: float, code: int, marker: str):
        """Log a marker to the session log."""
        if self.session_log:
            self.session_log.events.append({
                "timestamp": timestamp,
                "code": code,
                "marker": marker
            })
    
    def _emit_state_change(self):
        """Emit state change callback."""
        if self.on_state_change:
            self.on_state_change(self.state)
    
    def _emit_error(self, message: str):
        """Emit error callback."""
        print(f"ERROR: {message}")
        if self.on_error:
            self.on_error(message)
    
    def get_progress(self) -> Dict:
        """Get current experiment progress."""
        total = len(self.trial_queue) if self.trial_queue else 0
        return {
            "current_trial": self.current_trial_index + 1,
            "total_trials": total,
            "trials_since_break": self.trials_since_break,
            "trials_until_break": self.config.trials_until_break if self.config else 0,
            "state": self.state.name,
            "current_category": self.current_trial.category if self.current_trial else None
        }


# Singleton instance
_engine_instance: Optional[ExperimentEngine] = None

def get_experiment_engine() -> ExperimentEngine:
    """Get or create the singleton experiment engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ExperimentEngine()
    return _engine_instance

def reset_experiment_engine():
    """Reset the singleton instance."""
    global _engine_instance
    if _engine_instance:
        _engine_instance.stop()
    _engine_instance = None