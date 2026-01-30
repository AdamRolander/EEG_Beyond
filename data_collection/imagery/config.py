"""
Configuration for EEG Imagery Experiments
Contains default parameters, marker codes, and experiment settings.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import IntEnum
import os

# =============================================================================
# LSL Marker Codes
# =============================================================================

class MarkerCode(IntEnum):
    """Numeric marker codes for LSL streaming."""
    # Experiment lifecycle
    EXP_START = 90
    EXP_END = 91
    
    # Trial structure
    TRIAL_START = 1
    BUFFER_START = 10
    REC_START = 20
    REC_END = 21
    END_BEEP = 30
    
    # Breaks and responses
    BREAK_START = 40
    BREAK_END = 41
    LIKERT_1 = 51
    LIKERT_2 = 52
    LIKERT_3 = 53
    LIKERT_4 = 54
    LIKERT_5 = 55
    
    # Pause/Resume
    PAUSE = 60
    RESUME = 61
    
    # Category bases (actual code = base + category_index)
    CUE_COLOR_BASE = 100
    CUE_PRIMITIVE_BASE = 200
    CUE_COMPLEX_BASE = 300


# String markers corresponding to numeric codes
MARKER_STRINGS = {
    MarkerCode.EXP_START: "EXP_START",
    MarkerCode.EXP_END: "EXP_END",
    MarkerCode.TRIAL_START: "TRIAL_START",
    MarkerCode.BUFFER_START: "BUFFER_START",
    MarkerCode.REC_START: "REC_START",
    MarkerCode.REC_END: "REC_END",
    MarkerCode.END_BEEP: "END_BEEP",
    MarkerCode.BREAK_START: "BREAK_START",
    MarkerCode.BREAK_END: "BREAK_END",
    MarkerCode.PAUSE: "PAUSE",
    MarkerCode.RESUME: "RESUME",
}

# =============================================================================
# Experiment Types
# =============================================================================

EXPERIMENT_TYPES = {
    "colors": {
        "display_name": "Color Visualization",
        "audio_folder": "colors",
        "marker_base": MarkerCode.CUE_COLOR_BASE,
    },
    "primitives": {
        "display_name": "Primitive Solids",
        "audio_folder": "primitives",
        "marker_base": MarkerCode.CUE_PRIMITIVE_BASE,
    },
    "complex": {
        "display_name": "Complex Objects",
        "audio_folder": "complex",
        "marker_base": MarkerCode.CUE_COMPLEX_BASE,
    },
}

# =============================================================================
# Default Parameters
# =============================================================================

@dataclass
class ExperimentConfig:
    """Configuration for a single experiment session."""
    
    # Experiment type
    experiment_type: str = "colors"
    
    # Timing (all in milliseconds)
    visualization_duration_ms: int = 3000
    pre_recording_buffer_ms: int = 500
    inter_trial_gap_ms: int = 1000
    
    # Trial structure
    trials_per_category: int = 10
    trials_until_break: int = 15
    
    # Categories (dynamically loaded, but can be filtered)
    enabled_categories: List[str] = field(default_factory=list)
    
    # Options
    randomize_order: bool = True
    enable_end_beep: bool = True
    enable_likert: bool = True
    likert_scale: int = 5  # 3 or 5
    enable_logging: bool = False  # Off by default
    
    # LSL
    lsl_stream_name: str = "ImageryMarkers"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "experiment_type": self.experiment_type,
            "visualization_duration_ms": self.visualization_duration_ms,
            "pre_recording_buffer_ms": self.pre_recording_buffer_ms,
            "inter_trial_gap_ms": self.inter_trial_gap_ms,
            "trials_per_category": self.trials_per_category,
            "trials_until_break": self.trials_until_break,
            "enabled_categories": self.enabled_categories,
            "randomize_order": self.randomize_order,
            "enable_end_beep": self.enable_end_beep,
            "enable_likert": self.enable_likert,
            "likert_scale": self.likert_scale,
            "enable_logging": self.enable_logging,
            "lsl_stream_name": self.lsl_stream_name,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExperimentConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# Paths
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

def get_audio_path(experiment_type: str, category: str) -> str:
    """Get the full path to an audio file for a category."""
    folder = EXPERIMENT_TYPES[experiment_type]["audio_folder"]
    return os.path.join(AUDIO_DIR, folder, f"{category}.mp3")

def get_administrative_audio_path(name: str) -> str:
    """Get path to administrative audio (beeps, etc.)."""
    return os.path.join(AUDIO_DIR, "administrative", f"{name}.mp3")