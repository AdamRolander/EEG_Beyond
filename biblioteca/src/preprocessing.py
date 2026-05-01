"""Real-time-safe preprocessing.

Two parts:
1. `RealtimePreprocessor`: per-epoch pipeline (bandpass + notch + CAR + saved-ICA
   forward application + artifact check). Causal filters only — no `filtfilt`.
2. `ICACalibrator`: offline-fit ICA on the calibration phase, label components
   with `mne-icalabel`, save unmixing matrix + bad-component mask.

The pipeline trades the small numerical noise of edge transients in causal
filters for strict real-time safety. If you need filtfilt-style precision for
post-hoc analysis, re-run preprocessing on the saved raw EEG offline.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi, iirnotch

try:
    import mne
    MNE_AVAILABLE = True
except ImportError:
    MNE_AVAILABLE = False
    mne = None  # type: ignore

try:
    from mne_icalabel import label_components  # noqa: F401
    ICALABEL_AVAILABLE = True
except ImportError:
    ICALABEL_AVAILABLE = False


# ═════════════════════════════════════════════════════════════════════════
# Causal IIR filter
# ═════════════════════════════════════════════════════════════════════════

class CausalFilter:
    """Single-pass IIR with `lfilter_zi` initialization per epoch.

    The filter is reset for each epoch (state is not carried between epochs).
    This is appropriate for trial-locked epochs that are temporally separated;
    it introduces a brief edge transient at the start of each epoch (~50 ms
    for a 4th-order Butterworth at 1 Hz cutoff). The imagery window starts
    after the audio cue, so this transient falls in the cue period, not the
    imagery period — safe by design.
    """

    def __init__(self, b: np.ndarray, a: np.ndarray):
        self.b = np.asarray(b, dtype=np.float64)
        self.a = np.asarray(a, dtype=np.float64)

    def apply(self, data: np.ndarray) -> np.ndarray:
        """data: (n_channels, n_samples). Returns filtered data, same shape."""
        out = np.empty_like(data, dtype=np.float64)
        zi_template = lfilter_zi(self.b, self.a)
        for ch in range(data.shape[0]):
            zi = zi_template * data[ch, 0]
            y, _ = lfilter(self.b, self.a, data[ch], zi=zi)
            out[ch] = y
        return out


def design_bandpass(low_hz: float, high_hz: float, sample_rate: float, order: int = 4) -> CausalFilter:
    nyq = sample_rate / 2.0
    low = max(0.001, low_hz / nyq)
    high = min(0.999, high_hz / nyq)
    b, a = butter(order, [low, high], btype="band")
    return CausalFilter(b, a)


def design_notch(freq_hz: float, sample_rate: float, q: float = 30.0) -> CausalFilter:
    b, a = iirnotch(freq_hz / (sample_rate / 2.0), q)
    return CausalFilter(b, a)


def common_average_reference(data: np.ndarray) -> np.ndarray:
    """Subtract the per-sample mean across channels."""
    return data - data.mean(axis=0, keepdims=True)


# ═════════════════════════════════════════════════════════════════════════
# Real-time pipeline
# ═════════════════════════════════════════════════════════════════════════

class RealtimePreprocessor:
    """Per-epoch pipeline: bandpass → notch → CAR → (optional) ICA → artifact check."""

    def __init__(
        self,
        sample_rate: float,
        n_channels: int,
        bandpass: Tuple[float, float] = (1.0, 40.0),
        notch_freqs: Tuple[float, ...] = (60.0,),
        use_car: bool = True,
        artifact_pp_threshold_uv: float = 150.0,
    ):
        self.sample_rate = sample_rate
        self.n_channels = n_channels
        self.bandpass_filter = design_bandpass(bandpass[0], bandpass[1], sample_rate)
        self.notch_filters = [design_notch(f, sample_rate) for f in notch_freqs]
        self.use_car = use_car
        self.artifact_pp_threshold_v = artifact_pp_threshold_uv * 1e-6

        # ICA — populated by load_ica()
        self.ica_unmixing: Optional[np.ndarray] = None
        self.ica_mixing: Optional[np.ndarray] = None
        self.bad_components: Optional[np.ndarray] = None

    # ─── ICA wiring ────────────────────────────────────────────────────

    def load_ica(self, ica_dir: Path):
        ica_dir = Path(ica_dir)
        unmixing = np.load(ica_dir / "ica_unmixing.npy")
        bad_mask = np.load(ica_dir / "ica_bad_components.npy")
        self.ica_unmixing = unmixing
        self.ica_mixing = np.linalg.pinv(unmixing)
        self.bad_components = bad_mask.astype(bool)

    def has_ica(self) -> bool:
        return self.ica_unmixing is not None

    # ─── apply ─────────────────────────────────────────────────────────

    def apply(
        self,
        epoch: np.ndarray,
        apply_ica: bool = True,
    ) -> Tuple[np.ndarray, Dict]:
        """Apply full pipeline.

        Returns
        -------
        cleaned : (n_ch, n_samples)
        info    : {peak_to_peak_uv: float, artifact: bool}
        """
        out = self.bandpass_filter.apply(epoch)
        for nf in self.notch_filters:
            out = nf.apply(out)
        if self.use_car:
            out = common_average_reference(out)
        if apply_ica and self.ica_unmixing is not None:
            sources = self.ica_unmixing @ out                       # (n_components, T)
            sources[self.bad_components] = 0
            out = self.ica_mixing @ sources                          # back to channel space

        peak_to_peak = float((out.max(axis=1) - out.min(axis=1)).max())
        info = {
            "peak_to_peak_uv": peak_to_peak * 1e6,
            "artifact": peak_to_peak > self.artifact_pp_threshold_v,
        }
        return out, info


# ═════════════════════════════════════════════════════════════════════════
# ICA calibration (offline, run once at session start)
# ═════════════════════════════════════════════════════════════════════════

class ICACalibrator:
    """Fit Picard ICA on the calibration phase EEG and auto-label components."""

    def __init__(
        self,
        sample_rate: float,
        channel_labels: List[str],
        method: str = "picard",
        n_components: Optional[int] = None,
        reject_categories: Optional[List[str]] = None,
        confidence_threshold: float = 0.7,
    ):
        if not MNE_AVAILABLE:
            raise ImportError("mne not installed. Run: pip install mne")
        self.sample_rate = sample_rate
        self.channel_labels = channel_labels
        self.method = method
        self.n_components = n_components or len(channel_labels)
        self.reject_categories = reject_categories or [
            "muscle artifact", "eye blink", "heart beat", "line noise", "channel noise",
        ]
        self.confidence_threshold = confidence_threshold

        self.ica = None
        self.bad_components_mask: Optional[np.ndarray] = None
        self.component_labels: Optional[List[str]] = None
        self.component_confidences: Optional[List[float]] = None

    def fit(self, calibration_data: np.ndarray, montage: str = "standard_1020") -> Dict:
        """Fit ICA on (n_channels, n_samples). Data should already be bandpassed."""
        info = mne.create_info(
            ch_names=self.channel_labels,
            sfreq=self.sample_rate,
            ch_types="eeg",
        )
        try:
            info.set_montage(montage, on_missing="ignore")
        except Exception:
            pass
        raw = mne.io.RawArray(calibration_data.astype(np.float64), info, verbose="ERROR")
        raw.set_eeg_reference("average", projection=False, verbose="ERROR")

        self.ica = mne.preprocessing.ICA(
            n_components=self.n_components,
            method=self.method,
            random_state=42,
            max_iter="auto",
            verbose="ERROR",
        )
        self.ica.fit(raw, verbose="ERROR")

        # Auto-label
        if ICALABEL_AVAILABLE:
            from mne_icalabel import label_components as _label
            try:
                result = _label(raw, self.ica, method="iclabel")
                self.component_labels = list(result["labels"])
                self.component_confidences = [float(c) for c in result["y_pred_proba"]]
                self.bad_components_mask = np.array([
                    (lbl in self.reject_categories) and (conf >= self.confidence_threshold)
                    for lbl, conf in zip(self.component_labels, self.component_confidences)
                ])
            except Exception as e:
                print(f"[ICA] icalabel failed ({e}); no components auto-rejected.")
                self.component_labels = ["unknown"] * self.n_components
                self.component_confidences = [0.0] * self.n_components
                self.bad_components_mask = np.zeros(self.n_components, dtype=bool)
        else:
            print("[ICA] mne-icalabel not installed; no auto-labeling. "
                  "All components retained — mark manually if needed.")
            self.component_labels = ["unlabeled"] * self.n_components
            self.component_confidences = [0.0] * self.n_components
            self.bad_components_mask = np.zeros(self.n_components, dtype=bool)

        return {
            "n_components": self.n_components,
            "labels": self.component_labels,
            "confidences": self.component_confidences,
            "bad_mask": self.bad_components_mask.tolist(),
            "n_rejected": int(self.bad_components_mask.sum()),
        }

    def manually_set_bad(self, indices: List[int]):
        """Operator override: explicitly set which components to reject."""
        if self.bad_components_mask is None:
            raise RuntimeError("Call fit() before manually_set_bad().")
        mask = np.zeros(self.n_components, dtype=bool)
        for i in indices:
            if 0 <= i < self.n_components:
                mask[i] = True
        self.bad_components_mask = mask

    def save(self, ica_dir: Path):
        ica_dir = Path(ica_dir)
        ica_dir.mkdir(parents=True, exist_ok=True)
        if self.ica is None:
            raise RuntimeError("Call fit() before save().")

        # Compose unmixing matrix (n_components, n_channels) for forward application
        unmixing = self.ica.unmixing_matrix_ @ self.ica.pca_components_
        np.save(ica_dir / "ica_unmixing.npy", unmixing)
        np.save(ica_dir / "ica_bad_components.npy", self.bad_components_mask)

        # Full MNE solution for traceability / re-analysis
        self.ica.save(ica_dir / "ica-ica.fif", overwrite=True)

        with open(ica_dir / "ica_components.json", "w") as f:
            json.dump({
                "n_components": int(self.n_components),
                "labels": list(self.component_labels) if self.component_labels else [],
                "confidences": list(self.component_confidences) if self.component_confidences else [],
                "bad_mask": [bool(b) for b in self.bad_components_mask.tolist()],
                "n_rejected": int(self.bad_components_mask.sum()),
                "method": self.method,
                "confidence_threshold": float(self.confidence_threshold),
            }, f, indent=2)
        print(f"[ICA] Saved to {ica_dir} ({self.bad_components_mask.sum()}/{self.n_components} components rejected)")