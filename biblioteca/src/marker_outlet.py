"""LSL marker outlet + in-memory log.

The session manager pushes integer marker codes through a single LSL
StreamOutlet; pylsl timestamps each marker with `local_clock()` at emission,
which is the same clock the EEG inlet uses for its sample timestamps.
Aligning epochs to markers is therefore exact.

A parallel in-memory log captures every emitted marker with its timestamp
and arbitrary JSON payload, then is dumped to `markers.csv` at session end.
"""
from __future__ import annotations

import csv
import json
import threading
import time
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

try:
    import pylsl
    PYLSL_AVAILABLE = True
except ImportError:
    PYLSL_AVAILABLE = False
    pylsl = None  # type: ignore


MarkerLogEntry = Tuple[float, int, Dict[str, Any]]


class MarkerOutlet:
    def __init__(self, name: str = "VisualImageryMarkers", source_id: str = "vim_markers"):
        self.name = name
        self.source_id = source_id
        self.outlet: Optional["pylsl.StreamOutlet"] = None
        self._log: List[MarkerLogEntry] = []
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return self.outlet is not None

    def open(self) -> bool:
        """Create the LSL outlet. Returns False (gracefully) if pylsl unavailable."""
        if not PYLSL_AVAILABLE:
            print("[MarkerOutlet] pylsl not available — markers logged in-memory only.")
            return False
        info = pylsl.StreamInfo(
            name=self.name,
            type="Markers",
            channel_count=1,
            nominal_srate=pylsl.IRREGULAR_RATE,
            channel_format=pylsl.cf_int32,
            source_id=self.source_id,
        )
        self.outlet = pylsl.StreamOutlet(info)
        print(f"[MarkerOutlet] Opened LSL outlet '{self.name}'.")
        return True

    def emit(self, code: int, payload: Optional[Dict[str, Any]] = None) -> float:
        """Push a marker. Returns the LSL timestamp at which it was pushed."""
        ts = pylsl.local_clock() if PYLSL_AVAILABLE else time.time()
        if self.outlet is not None:
            try:
                self.outlet.push_sample([int(code)], timestamp=ts)
            except Exception as e:
                print(f"[MarkerOutlet] push failed for code {code}: {e}")
        with self._lock:
            self._log.append((ts, int(code), dict(payload or {})))
        return ts

    def get_log(self) -> List[MarkerLogEntry]:
        with self._lock:
            return list(self._log)

    def find_latest(self, code: int) -> Optional[Tuple[float, Dict[str, Any]]]:
        """Most recent (timestamp, payload) for `code`, or None."""
        with self._lock:
            for ts, c, p in reversed(self._log):
                if c == code:
                    return (ts, p)
        return None

    def save_csv(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            log = list(self._log)
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["lsl_timestamp", "code", "payload_json"])
            for ts, code, payload in log:
                w.writerow([f"{ts:.6f}", code, json.dumps(payload)])
        print(f"[MarkerOutlet] Saved {len(log)} markers to {path}")