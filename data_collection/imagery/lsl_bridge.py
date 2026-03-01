"""
LSL Bridge for EEG Imagery Experiments
Handles Lab Streaming Layer marker streaming with precise timing.
"""

import time
from typing import Optional, Tuple
from config import MarkerCode, MARKER_STRINGS

# Try to import pylsl, provide fallback for testing without LSL
try:
    from pylsl import StreamInfo, StreamOutlet, local_clock
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False
    print("WARNING: pylsl not installed. Running in simulation mode.")


class LSLBridge:
    """
    Manages LSL outlet for streaming experiment markers.
    Sends both numeric codes and string markers for redundancy.
    """
    
    def __init__(self, stream_name: str = "ImageryMarkers", source_id: str = "imagery_exp_001"):
        self.stream_name = stream_name
        self.source_id = source_id
        self.outlet: Optional[object] = None
        self.string_outlet: Optional[object] = None
        self.rating_outlet: Optional[object] = None  # Trial ratings (trial_number, rating 1-5)
        self._connected = False
        
    def connect(self) -> bool:
        """Initialize LSL outlets. Returns True if successful."""
        if not LSL_AVAILABLE:
            print("LSL not available - markers will be logged but not streamed")
            self._connected = False
            return False
            
        try:
            # Numeric marker stream
            info_numeric = StreamInfo(
                name=self.stream_name,
                type='Markers',
                channel_count=1,
                nominal_srate=0,  # Irregular sampling
                channel_format='int32',
                source_id=self.source_id
            )
            self.outlet = StreamOutlet(info_numeric)
            
            # String marker stream (for redundancy and readability)
            info_string = StreamInfo(
                name=f"{self.stream_name}_Strings",
                type='Markers',
                channel_count=1,
                nominal_srate=0,
                channel_format='string',
                source_id=f"{self.source_id}_str"
            )
            self.string_outlet = StreamOutlet(info_string)
            
            # Trial ratings stream (Phase 1 neurofeedback): [trial_number, rating 1-5]
            info_rating = StreamInfo(
                name="ImageryTrialRatings",
                type='Markers',
                channel_count=2,
                nominal_srate=0,
                channel_format='int32',
                source_id=f"{self.source_id}_ratings"
            )
            desc = info_rating.desc()
            channels = desc.append_child("channels")
            ch1 = channels.append_child("channel")
            ch1.append_child_value("label", "trial_number")
            ch2 = channels.append_child("channel")
            ch2.append_child_value("label", "rating")
            self.rating_outlet = StreamOutlet(info_rating)
            
            self._connected = True
            print(f"LSL outlets created: {self.stream_name}, ImageryTrialRatings")
            return True
            
        except Exception as e:
            print(f"Failed to create LSL outlets: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Clean up LSL outlets."""
        self.outlet = None
        self.string_outlet = None
        self.rating_outlet = None
        self._connected = False
        print("LSL outlets closed")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def get_timestamp(self) -> float:
        """Get current LSL timestamp for logging."""
        if LSL_AVAILABLE:
            return local_clock()
        return time.perf_counter()
    
    def send_marker(self, code: int, string_marker: Optional[str] = None) -> Tuple[float, int, str]:
        """
        Send a marker to LSL streams.
        
        Args:
            code: Numeric marker code
            string_marker: Optional string marker (auto-generated if not provided)
            
        Returns:
            Tuple of (timestamp, code, string_marker) for logging
        """
        timestamp = self.get_timestamp()
        
        # Auto-generate string marker if not provided
        if string_marker is None:
            string_marker = MARKER_STRINGS.get(code, f"MARKER_{code}")
        
        # Send to LSL if connected
        if self._connected and self.outlet:
            try:
                self.outlet.push_sample([code])
                if self.string_outlet:
                    self.string_outlet.push_sample([string_marker])
            except Exception as e:
                print(f"LSL send error: {e}")
        
        # Always log
        print(f"[{timestamp:.3f}] MARKER: {string_marker} ({code})")
        
        return timestamp, code, string_marker
    
    def send_cue_marker(self, category: str, marker_base: int, category_index: int) -> Tuple[float, int, str]:
        """
        Send a cue marker for a specific category.
        
        Args:
            category: Category name (e.g., "red", "sphere")
            marker_base: Base marker code for this experiment type
            category_index: Index of this category within its type
            
        Returns:
            Tuple of (timestamp, code, string_marker) for logging
        """
        code = marker_base + category_index
        string_marker = f"CUE_{category.upper()}"
        return self.send_marker(code, string_marker)
    
    def send_likert_response(self, rating: int) -> Tuple[float, int, str]:
        """Send a Likert scale response marker."""
        code = MarkerCode.LIKERT_1 + (rating - 1)
        string_marker = f"LIKERT_{rating}"
        return self.send_marker(code, string_marker)
    
    def send_trial_rating(self, trial_number: int, rating: int) -> Optional[float]:
        """
        Send per-trial rating (Phase 1 neurofeedback) to LSL.
        Stream: ImageryTrialRatings, 2 channels: trial_number, rating (1-5).
        Returns LSL timestamp or None if not connected.
        """
        if not self._connected or not self.rating_outlet:
            return None
        try:
            ts = self.get_timestamp()
            self.rating_outlet.push_sample([trial_number, rating])
            print(f"[{ts:.3f}] LSL TrialRating: trial={trial_number} rating={rating}")
            return ts
        except Exception as e:
            print(f"LSL trial rating send error: {e}")
            return None


# Singleton instance for easy access
_bridge_instance: Optional[LSLBridge] = None

def get_lsl_bridge(stream_name: str = "ImageryMarkers") -> LSLBridge:
    """Get or create the singleton LSL bridge instance."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = LSLBridge(stream_name)
    return _bridge_instance

def reset_lsl_bridge():
    """Reset the singleton instance (for testing or reconfiguration)."""
    global _bridge_instance
    if _bridge_instance:
        _bridge_instance.disconnect()
    _bridge_instance = None