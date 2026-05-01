#!/usr/bin/env python3
"""Smoke test: ingest → preprocessing → features.

Spins up the simulated EEG inlet, waits for the buffer to fill, pulls a 4-second
epoch, runs it through the realtime preprocessor, computes Riemannian covariance
+ RQA, and prints summary stats. Validates the full V1 feature extraction path
without requiring hardware or LSL.

Run from repo root:
    python scripts/test_simulated_ingest.py
"""
import sys
import time
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.config_session import SessionConfig
from src.eeg_ingest import make_eeg_inlet
from src.preprocessing import RealtimePreprocessor
from src.features import (
    compute_covariance,
    riemannian_distance,
    rqa_features_from_epoch,
)


def main():
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
    cfg = SessionConfig.from_yaml(cfg_path)
    print(f"Loaded config: {cfg.subject.id}, classes={cfg.class_names}")

    # 1. Spin up simulated inlet
    inlet = make_eeg_inlet(
        stream_name_hint=cfg.eeg.stream_name_hint,
        buffer_seconds=cfg.eeg.buffer_seconds,
        expected_n_channels=cfg.eeg.expected_n_channels,
        expected_sample_rate=cfg.eeg.expected_sample_rate or 250,
        simulate=True,  # force simulation
    )
    inlet.discover_and_connect()
    inlet.start()
    print(f"Inlet status: {inlet.status()}")

    # 2. Wait for buffer to fill
    print("Waiting for buffer to fill (5 s) ...")
    time.sleep(5)
    print(f"  buffer samples: {inlet.status()['buffer_samples']}")

    # 3. Build preprocessor
    pp = RealtimePreprocessor(
        sample_rate=inlet.sample_rate,
        n_channels=inlet.n_channels,
        bandpass=(cfg.preprocessing.bandpass_low_hz, cfg.preprocessing.bandpass_high_hz),
        notch_freqs=tuple(cfg.preprocessing.notch_freqs_hz),
        use_car=cfg.preprocessing.car,
        artifact_pp_threshold_uv=cfg.preprocessing.artifact_pp_threshold_uv,
    )
    print("Preprocessor built.")

    # 4. Pull a 4 s epoch (latest available)
    res = inlet.get_latest(4.0)
    if res is None:
        print("FAIL: could not get epoch from buffer")
        inlet.stop()
        sys.exit(1)
    timestamps, epoch = res
    print(f"Epoch: {epoch.shape} (n_ch, n_samples), span = {timestamps[-1] - timestamps[0]:.3f} s")

    # 5. Apply pipeline (no ICA loaded in this smoke test)
    cleaned, info = pp.apply(epoch, apply_ica=False)
    print(f"Cleaned epoch: {cleaned.shape}, p2p = {info['peak_to_peak_uv']:.1f} µV, "
          f"artifact = {info['artifact']}")

    # 6. Riemannian covariance
    cov = compute_covariance(cleaned)
    print(f"Covariance: {cov.shape}, trace = {np.trace(cov):.3e}, "
          f"min eigval = {np.linalg.eigvalsh(cov).min():.3e}")

    # 7. Distance to itself should be ~0; distance to a different epoch should be >0
    d_self = riemannian_distance(cov, cov)
    res2 = inlet.get_latest(2.0)
    if res2 is not None:
        _, epoch2 = res2
        cleaned2, _ = pp.apply(epoch2, apply_ica=False)
        cov2 = compute_covariance(cleaned2)
        d_other = riemannian_distance(cov, cov2)
        print(f"Riemannian d(cov, cov)         = {d_self:.4e}")
        print(f"Riemannian d(cov, cov_other)   = {d_other:.4e}")
        if d_self < 1e-6 and d_other > d_self:
            print("  ✓ self-distance ≈ 0 and cross-distance > 0")
        else:
            print("  ✗ unexpected distance behavior")

    # 8. RQA features
    rqa = rqa_features_from_epoch(
        cleaned,
        dim=cfg.card.rqa_phase_space_dim,
        tau=cfg.card.rqa_tau,
        threshold_pct=cfg.card.rqa_recurrence_threshold_pct,
    )
    print(f"RQA features: {rqa}")
    print(f"  RR={rqa[0]:.3f}, DET={rqa[1]:.3f}, "
          f"avg_diag={rqa[2]:.2f}, ENTR={rqa[3]:.3f}, LAM={rqa[4]:.3f}")

    # 9. Cleanup
    inlet.stop()
    print("\nSmoke test PASSED.")


if __name__ == "__main__":
    main()