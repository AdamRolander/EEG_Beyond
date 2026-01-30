"""
Audio Manager for EEG Imagery Experiments
Handles audio playback with precise timing using pygame mixer.
"""

import os
import time
from typing import Dict, Optional, List
from dataclasses import dataclass

# Try pygame first (better timing), fall back to alternatives
AUDIO_BACKEND = None
pygame = None

try:
    import pygame as pg
    pygame = pg
    # Initialize pygame fully for better audio support
    pygame.init()
    try:
        # Use larger buffer for mp3 compatibility
        pygame.mixer.quit()  # Reset if already initialized
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        AUDIO_BACKEND = "pygame"
        print(f"Audio backend: pygame (mixer initialized)")
    except pygame.error as e:
        print(f"WARNING: pygame mixer init failed ({e}). Trying alternative settings...")
        try:
            pygame.mixer.init()  # Try default settings
            AUDIO_BACKEND = "pygame"
            print(f"Audio backend: pygame (default settings)")
        except pygame.error as e2:
            print(f"WARNING: pygame mixer failed completely ({e2})")
            AUDIO_BACKEND = "pygame_no_audio"
except ImportError:
    print("pygame not installed, trying sounddevice...")
    try:
        import sounddevice as sd
        import soundfile as sf
        AUDIO_BACKEND = "sounddevice"
        print(f"Audio backend: sounddevice")
    except ImportError:
        AUDIO_BACKEND = None
        print("WARNING: No audio backend available. Install pygame or sounddevice.")


@dataclass
class AudioFile:
    """Represents a loaded audio file."""
    name: str
    path: str
    sound: Optional[object] = None  # pygame.mixer.Sound or numpy array
    duration_ms: float = 0


class AudioManager:
    """
    Manages audio playback for experiment cues and beeps.
    Preloads audio files for minimal latency during playback.
    """
    
    def __init__(self):
        self.loaded_sounds: Dict[str, AudioFile] = {}
        self.backend = AUDIO_BACKEND
        self._beep_sound: Optional[AudioFile] = None
        print(f"AudioManager initialized with backend: {self.backend}")
        
    def scan_audio_folder(self, folder_path: str) -> List[str]:
        """
        Scan a folder for audio files and return category names.
        
        Args:
            folder_path: Path to folder containing .mp3/.wav files
            
        Returns:
            List of category names (filenames without extension)
        """
        categories = []
        if not os.path.exists(folder_path):
            print(f"Audio folder not found: {folder_path}")
            return categories
            
        for filename in sorted(os.listdir(folder_path)):
            if filename.lower().endswith(('.mp3', '.wav', '.ogg')):
                name = os.path.splitext(filename)[0]
                categories.append(name)
                
        return categories
    
    def preload_folder(self, folder_path: str) -> Dict[str, AudioFile]:
        """
        Preload all audio files from a folder.
        
        Args:
            folder_path: Path to folder containing audio files
            
        Returns:
            Dictionary mapping category names to AudioFile objects
        """
        loaded = {}
        
        if not os.path.exists(folder_path):
            print(f"Audio folder not found: {folder_path}")
            return loaded
        
        print(f"Preloading audio from: {folder_path}")
            
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.mp3', '.wav', '.ogg')):
                name = os.path.splitext(filename)[0]
                path = os.path.join(folder_path, filename)
                audio = self._load_audio_file(name, path)
                if audio:
                    loaded[name] = audio
                    # Store with full path as key for reliable lookup
                    key = os.path.join(folder_path, name)
                    self.loaded_sounds[key] = audio
                    print(f"    Registered with key: {key}")
        
        print(f"Loaded {len(loaded)} audio files from {folder_path}")
        return loaded
    
    def preload_file(self, name: str, path: str) -> Optional[AudioFile]:
        """Preload a single audio file."""
        audio = self._load_audio_file(name, path)
        if audio:
            self.loaded_sounds[name] = audio
        return audio
    
    def _load_audio_file(self, name: str, path: str) -> Optional[AudioFile]:
        """Load an audio file using the available backend."""
        if not os.path.exists(path):
            print(f"Audio file not found: {path}")
            return None
            
        audio = AudioFile(name=name, path=path)
        
        if self.backend == "pygame" and pygame:
            try:
                # For mp3 files, pygame.mixer.Sound might not work well
                # Try loading as Sound first
                sound = pygame.mixer.Sound(path)
                audio.sound = sound
                audio.duration_ms = sound.get_length() * 1000
                print(f"  Loaded: {name} ({audio.duration_ms:.0f}ms) from {os.path.basename(path)}")
            except Exception as e:
                print(f"  Failed to load {path}: {e}")
                return None
                
        elif self.backend == "sounddevice":
            try:
                import soundfile as sf
                data, samplerate = sf.read(path)
                audio.sound = (data, samplerate)
                audio.duration_ms = (len(data) / samplerate) * 1000
                print(f"  Loaded: {name} ({audio.duration_ms:.0f}ms)")
            except Exception as e:
                print(f"  Failed to load {path}: {e}")
                return None
        else:
            print(f"  No audio backend available to load {name}")
            return None
            
        return audio
    
    def play(self, name: str, blocking: bool = False) -> float:
        """
        Play a preloaded audio file.
        
        Args:
            name: Name of the preloaded audio
            blocking: If True, wait for audio to finish
            
        Returns:
            Timestamp when playback started (time.perf_counter)
        """
        if name not in self.loaded_sounds:
            print(f"Audio not loaded: {name}")
            print(f"  Available sounds: {list(self.loaded_sounds.keys())}")
            return time.perf_counter()
            
        audio = self.loaded_sounds[name]
        start_time = time.perf_counter()
        
        if self.backend == "pygame" and pygame and audio.sound:
            try:
                audio.sound.play()
                if blocking:
                    pygame.time.wait(int(audio.duration_ms))
            except Exception as e:
                print(f"Error playing {name}: {e}")
                
        elif self.backend == "sounddevice" and audio.sound:
            try:
                import sounddevice as sd
                data, samplerate = audio.sound
                sd.play(data, samplerate)
                if blocking:
                    sd.wait()
            except Exception as e:
                print(f"Error playing {name}: {e}")
        
        return start_time
    
    def play_by_path(self, folder_path: str, name: str, blocking: bool = False) -> float:
        """Play audio by folder path and name (for preloaded folder audio)."""
        key = os.path.join(folder_path, name)
        return self.play(key, blocking)
    
    def load_beep(self, beep_path: str) -> bool:
        """Load the end-of-trial beep sound."""
        print(f"Loading beep from: {beep_path}")
        self._beep_sound = self._load_audio_file("beep", beep_path)
        if self._beep_sound:
            self.loaded_sounds["_beep"] = self._beep_sound
            return True
        return False
    
    def play_beep(self) -> float:
        """Play the end-of-trial beep."""
        if "_beep" in self.loaded_sounds:
            return self.play("_beep", blocking=False)
        print("Beep sound not loaded")
        return time.perf_counter()
    
    def stop_all(self):
        """Stop all currently playing audio."""
        if self.backend == "pygame" and pygame:
            pygame.mixer.stop()
        elif self.backend == "sounddevice":
            import sounddevice as sd
            sd.stop()
    
    def get_duration(self, name: str) -> float:
        """Get duration of a loaded audio file in milliseconds."""
        if name in self.loaded_sounds:
            return self.loaded_sounds[name].duration_ms
        return 0
    
    def cleanup(self):
        """Clean up audio resources."""
        self.stop_all()
        self.loaded_sounds.clear()
        if self.backend == "pygame" and pygame:
            pygame.mixer.quit()


# Singleton instance
_audio_manager: Optional[AudioManager] = None

def get_audio_manager() -> AudioManager:
    """Get or create the singleton audio manager instance."""
    global _audio_manager
    if _audio_manager is None:
        _audio_manager = AudioManager()
    return _audio_manager

def reset_audio_manager():
    """Reset the singleton instance."""
    global _audio_manager
    if _audio_manager:
        _audio_manager.cleanup()
    _audio_manager = None