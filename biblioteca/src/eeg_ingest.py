"""LSL EEG ingest with thread-safe ring buffer and LSL-time epoch extraction.

Headset-agnostic: subscribes to any LSL stream of type='EEG'. Channel labels,
sample rate, and channel count are read from the stream's XML metadata.

Two inlets are provided:
- LSLEEGInlet: real LSL subscription via pylsl.
- SimulatedEEGInlet: synthetic 1/f-ish EEG with alpha rhythm and occasional
  blink artifacts; for development without hardware.

Both expose the same interface:
    inlet.discover_and_connect() -> bool
    inlet.start() / inlet.stop()
    inlet.get_epoch_by_lsl_time(t_start, duration) -> (timestamps, samples) or None
    inlet.get_latest(duration) -> (timestamps, samples) or None
    inlet.status() -> dict

Epochs are returned as (n_channels, n_samples) — channel-first, the convention
used by MNE and by the rest of this codebase.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional, Tuple, List, Union

import numpy as np

try:
    import pylsl
    PYLSL_AVAILABLE = True
except ImportError:
    PYLSL_AVAILABLE = False
    pylsl = None  # type: ignore


# ═════════════════════════════════════════════════════════════════════════
# Ring buffer
# ═════════════════════════════════════════════════════════════════════════

class RingBuffer:
    """Thread-safe ring buffer of (LSL timestamp, sample-vector) pairs.

    Internally stores deques of fixed maxlen. `append_chunk` is O(n_samples).
    `get_epoch_by_lsl_time` is O(buffer_length) — fine for ≤30 s @ 1 kHz.
    """

    def __init__(self, max_seconds: float, sample_rate: float, n_channels: int):
        self.max_samples = max(1, int(max_seconds * sample_rate))
        self.n_channels = n_channels
        self._timestamps: deque = deque(maxlen=self.max_samples)
        self._samples: deque = deque(maxlen=self.max_samples)
        self._lock = threading.Lock()

    def append_chunk(self, timestamps: np.ndarray, samples: np.ndarray):
        """timestamps: (n,), samples: (n, n_ch)."""
        with self._lock:
            for t, s in zip(timestamps, samples):
                self._timestamps.append(float(t))
                self._samples.append(np.asarray(s, dtype=np.float64))

    def latest_timestamp(self) -> Optional[float]:
        with self._lock:
            return self._timestamps[-1] if self._timestamps else None

    def earliest_timestamp(self) -> Optional[float]:
        with self._lock:
            return self._timestamps[0] if self._timestamps else None

    def diagnose_epoch_extraction(
        self, t_start: float, duration: float
    ) -> str:
        """Human-readable diagnostic of why an extraction would fail right now."""
        with self._lock:
            n = len(self._timestamps)
            if n == 0:
                return "buffer is empty (inlet not delivering samples)"
            earliest = self._timestamps[0]
            latest = self._timestamps[-1]
        t_end = t_start + duration
        if t_end > latest:
            return (
                f"requested window ends at t={t_end:.3f} but latest sample is "
                f"at t={latest:.3f} (gap = {t_end - latest:.3f}s; "
                f"buffer has {n} samples spanning {latest - earliest:.2f}s)"
            )
        if t_start < earliest:
            return (
                f"requested window starts at t={t_start:.3f} but earliest sample "
                f"is at t={earliest:.3f} (window is older than the buffer)"
            )
        return (
            f"window in range [{earliest:.3f}, {latest:.3f}] but no samples "
            f"matched the mask (this should not happen)"
        )

    def get_epoch_by_lsl_time(
        self, t_start: float, duration: float, wait_max_s: float = 0.0
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Extract samples falling in [t_start, t_start + duration].

        If `wait_max_s > 0`, waits up to that long for the buffer to fill past
        `t_start + duration`. Useful when a marker arrives very close to "now"
        and the EEG has not yet been pulled.

        Returns (timestamps, samples) where samples is (n_ch, n_samples), or
        None if not enough data is available.
        """
        t_end = t_start + duration
        deadline = time.monotonic() + wait_max_s
        while True:
            with self._lock:
                if self._timestamps and self._timestamps[-1] >= t_end:
                    ts_arr = np.fromiter(self._timestamps, dtype=np.float64, count=len(self._timestamps))
                    samples_arr = np.stack(list(self._samples), axis=0)  # (N, n_ch)
                    mask = (ts_arr >= t_start) & (ts_arr <= t_end)
                    if not mask.any():
                        return None
                    return ts_arr[mask], samples_arr[mask].T  # → (n_ch, n_samples)
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)

    def get_latest(
        self, duration: float
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Return the most recent `duration` seconds, or None if not enough data."""
        with self._lock:
            if not self._timestamps:
                return None
            t_end = self._timestamps[-1]
            t_start = t_end - duration
            ts_arr = np.fromiter(self._timestamps, dtype=np.float64, count=len(self._timestamps))
            samples_arr = np.stack(list(self._samples), axis=0)
            mask = ts_arr >= t_start
            if not mask.any():
                return None
            return ts_arr[mask], samples_arr[mask].T

    def __len__(self):
        with self._lock:
            return len(self._timestamps)


# ═════════════════════════════════════════════════════════════════════════
# Real LSL inlet
# ═════════════════════════════════════════════════════════════════════════

class LSLEEGInlet:
    """Subscribe to an LSL EEG outlet and ingest samples into a ring buffer."""

    def __init__(
        self,
        stream_name_hint: str = "",
        buffer_seconds: float = 30,
        expected_n_channels: Optional[int] = None,
        expected_sample_rate: Optional[float] = None,
    ):
        if not PYLSL_AVAILABLE:
            raise ImportError("pylsl not installed. Run: pip install pylsl")
        self.stream_name_hint = stream_name_hint
        self.buffer_seconds = buffer_seconds
        self.expected_n_channels = expected_n_channels
        self.expected_sample_rate = expected_sample_rate

        self.inlet: Optional["pylsl.StreamInlet"] = None
        self.sample_rate: Optional[float] = None
        self.n_channels: Optional[int] = None
        self.channel_labels: List[str] = []
        self.stream_name: Optional[str] = None
        self.buffer: Optional[RingBuffer] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ─── connection ────────────────────────────────────────────────────

    def discover_and_connect(self, timeout_sec: float = 5.0) -> bool:
        streams = pylsl.resolve_byprop("type", "EEG", timeout=timeout_sec)
        if not streams:
            print("[EEG] No EEG-type LSL streams found.")
            return False
        if self.stream_name_hint:
            filtered = [s for s in streams if self.stream_name_hint.lower() in s.name().lower()]
            if not filtered:
                print(f"[EEG] No streams matched hint '{self.stream_name_hint}'. "
                      f"Available: {[s.name() for s in streams]}")
                return False
            streams = filtered

        info = streams[0]
        self.inlet = pylsl.StreamInlet(info, max_buflen=int(self.buffer_seconds))
        full_info = self.inlet.info()
        self.sample_rate = full_info.nominal_srate()
        self.n_channels = full_info.channel_count()
        self.stream_name = full_info.name()
        self.channel_labels = self._extract_channel_labels(full_info)

        if self.expected_n_channels and self.n_channels != self.expected_n_channels:
            print(f"[EEG] WARNING: stream has {self.n_channels} channels, "
                  f"expected {self.expected_n_channels}.")
        if self.expected_sample_rate and abs(self.sample_rate - self.expected_sample_rate) > 1.0:
            print(f"[EEG] WARNING: stream rate {self.sample_rate} Hz, "
                  f"expected {self.expected_sample_rate} Hz.")

        self.buffer = RingBuffer(self.buffer_seconds, self.sample_rate, self.n_channels)
        print(f"[EEG] Connected to '{self.stream_name}' "
              f"({self.n_channels} ch @ {self.sample_rate} Hz)")
        return True

    @staticmethod
    def _extract_channel_labels(info) -> List[str]:
        labels: List[str] = []
        try:
            ch = info.desc().child("channels").child("channel")
            while not ch.empty():
                lbl = ch.child_value("label")
                if lbl:
                    labels.append(lbl)
                ch = ch.next_sibling()
        except Exception:
            pass
        if not labels:
            labels = [f"Ch{i + 1}" for i in range(info.channel_count())]
        return labels

    # ─── streaming ─────────────────────────────────────────────────────

    def start(self):
        if self.inlet is None:
            raise RuntimeError("Call discover_and_connect() before start().")
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._pull_loop, daemon=True, name="LSLEEGInlet")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    def _pull_loop(self):
        while self._running:
            try:
                samples, timestamps = self.inlet.pull_chunk(timeout=0.1, max_samples=512)
                if samples and len(samples) > 0:
                    self.buffer.append_chunk(np.asarray(timestamps), np.asarray(samples))
            except Exception as e:
                print(f"[EEG] pull error: {e}")
                time.sleep(0.05)

    # ─── access ────────────────────────────────────────────────────────

    def get_epoch_by_lsl_time(self, t_start: float, duration: float, wait_max_s: float = 0.5):
        if self.buffer is None:
            return None
        return self.buffer.get_epoch_by_lsl_time(t_start, duration, wait_max_s=wait_max_s)

    def get_latest(self, duration: float):
        if self.buffer is None:
            return None
        return self.buffer.get_latest(duration)

    def status(self) -> dict:
        return {
            "connected": self.inlet is not None,
            "stream_name": self.stream_name,
            "sample_rate": self.sample_rate,
            "n_channels": self.n_channels,
            "channel_labels": self.channel_labels,
            "buffer_samples": len(self.buffer) if self.buffer else 0,
            "simulated": False,
        }


# ═════════════════════════════════════════════════════════════════════════
# Simulated inlet (development without hardware)
# ═════════════════════════════════════════════════════════════════════════

class SimulatedEEGInlet:
    """Synthesised 16-channel EEG: alpha + 1/f-ish noise + occasional blinks.

    Timestamps follow `pylsl.local_clock()` if available, else `time.time()`,
    so feature/marker alignment with real LSL marker streams works correctly.
    """

    def __init__(
        self,
        sample_rate: float = 250,
        n_channels: int = 16,
        buffer_seconds: float = 30,
        channel_labels: Optional[List[str]] = None,
        chunk_duration_s: float = 0.05,
    ):
        self.sample_rate = sample_rate
        self.n_channels = n_channels
        self.buffer_seconds = buffer_seconds
        self.stream_name = "SimulatedEEG"
        self.channel_labels = channel_labels or [f"Sim{i + 1}" for i in range(n_channels)]
        self.buffer = RingBuffer(buffer_seconds, sample_rate, n_channels)
        self.inlet = self  # so .inlet is non-None for parity with LSLEEGInlet
        self.chunk_duration_s = chunk_duration_s

        self._running = False
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def _now() -> float:
        return pylsl.local_clock() if PYLSL_AVAILABLE else time.time()

    def discover_and_connect(self, timeout_sec: float = 5.0) -> bool:
        return True

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sim_loop, daemon=True, name="SimulatedEEGInlet")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    def _sim_loop(self):
        """Generate synthetic EEG samples in real time.

        Tracks the LSL timestamp of the last emitted sample. Each iteration,
        emits however many samples are needed to bring the buffer up to "now"
        — so a 200ms sleep overshoot produces a 200ms catch-up chunk on the
        next iteration, instead of leaving the buffer permanently behind.
        This matters on macOS where `time.sleep` granularity is coarse.
        """
        dt = 1.0 / self.sample_rate
        # Start "the previous sample" one period in the past so the first
        # iteration emits a normal-sized chunk rather than a dt-sized blip.
        last_emitted = self._now() - self.chunk_duration_s
        target_chunk_size = max(1, int(self.sample_rate * self.chunk_duration_s))

        while self._running:
            now_lsl = self._now()
            # How many samples do we owe to reach now_lsl?
            n_to_emit = int((now_lsl - last_emitted) / dt)
            if n_to_emit < 1:
                # We're ahead of schedule; sleep a fraction of dt and recheck.
                time.sleep(dt * 0.5)
                continue
            # Cap chunk size so a long stall doesn't produce one giant chunk
            # (which would briefly hold the buffer lock for a long time).
            n_to_emit = min(n_to_emit, target_chunk_size * 4)

            t_arr = last_emitted + dt * (1 + np.arange(n_to_emit))
            samples = np.zeros((n_to_emit, self.n_channels))
            t_local = t_arr % 100.0  # phase reference; bounded for sin precision
            for ch in range(self.n_channels):
                alpha_amp = 10e-6 * (0.5 + 0.5 * np.sin(ch * 0.4))
                samples[:, ch] = alpha_amp * np.sin(2 * np.pi * 10 * t_local + ch * 0.3)
                samples[:, ch] += np.random.randn(n_to_emit) * 5e-6
            if np.random.rand() < 0.01:  # ~once per second of sim
                start = np.random.randint(0, n_to_emit)
                end = min(start + 5, n_to_emit)
                samples[start:end, :2] += 100e-6
            self.buffer.append_chunk(t_arr, samples)
            last_emitted = float(t_arr[-1])

            # Sleep until the next chunk *should* be ready.
            time.sleep(self.chunk_duration_s)

    def get_epoch_by_lsl_time(self, t_start: float, duration: float, wait_max_s: float = 0.5):
        return self.buffer.get_epoch_by_lsl_time(t_start, duration, wait_max_s=wait_max_s)

    def get_latest(self, duration: float):
        return self.buffer.get_latest(duration)

    def status(self) -> dict:
        return {
            "connected": True,
            "stream_name": self.stream_name,
            "sample_rate": self.sample_rate,
            "n_channels": self.n_channels,
            "channel_labels": self.channel_labels,
            "buffer_samples": len(self.buffer),
            "simulated": True,
        }


# ═════════════════════════════════════════════════════════════════════════
# Factory
# ═════════════════════════════════════════════════════════════════════════

InletType = Union[LSLEEGInlet, SimulatedEEGInlet]


def make_eeg_inlet(
    stream_name_hint: str = "",
    buffer_seconds: float = 30,
    expected_n_channels: Optional[int] = None,
    expected_sample_rate: Optional[float] = None,
    simulate: bool = False,
) -> InletType:
    """Return a real LSL inlet, or a simulated inlet if `simulate=True`
    or pylsl is unavailable.
    """
    if simulate or not PYLSL_AVAILABLE:
        if not simulate:
            print("[EEG] pylsl not installed — falling back to SimulatedEEGInlet.")
        return SimulatedEEGInlet(
            sample_rate=expected_sample_rate or 250,
            n_channels=expected_n_channels or 16,
            buffer_seconds=buffer_seconds,
        )
    return LSLEEGInlet(
        stream_name_hint=stream_name_hint,
        buffer_seconds=buffer_seconds,
        expected_n_channels=expected_n_channels,
        expected_sample_rate=expected_sample_rate,
    )