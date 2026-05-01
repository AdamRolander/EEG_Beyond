"""Smoke test: NeuralCard lifecycle.

Builds two cards (cat / wrench) from synthetic trials with class-specific
spatial patterns, freezes them, scores new trials, verifies classification
accuracy is well above chance, and tests the save/load round trip.

No EEG hardware needed. Run:
    python scripts/test_card_lifecycle.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Allow `python scripts/test_card_lifecycle.py` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.neural_card import NeuralCard, CardError
from src.features import compute_covariance, rqa_features_from_epoch


def make_synthetic_epoch(n_ch=16, n_samples=1000, fs=250, class_offset=0.0, seed=None):
    """A (n_ch, n_samples) epoch with class-specific spatial pattern.

    Each class is identified by a different spatial weighting of a shared 10 Hz
    alpha signal. This gives different covariance structures per class (the
    pattern shifts which channels are most active) and is enough for the card's
    Riemannian metric to discriminate.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples) / fs
    alpha = np.sin(2 * np.pi * 10 * t)
    # Class-specific spatial pattern across channels
    pattern = np.linspace(0, 1, n_ch) + class_offset
    epoch = pattern[:, None] * alpha[None, :] * 10e-6
    # Add 1/f-ish noise
    epoch += rng.normal(0, 5e-6, size=(n_ch, n_samples))
    # Per-channel small DC offsets (centered out by CAR in real pipeline)
    epoch += rng.normal(0, 1e-6, size=(n_ch, 1))
    return epoch


def main() -> int:
    n_ch = 16
    print("=" * 60)
    print("Card lifecycle smoke test")
    print("=" * 60)

    cat = NeuralCard("cat", n_ch)
    wrench = NeuralCard("wrench", n_ch)

    print("\n[1/5] Building cards from 30 synthetic trials each ...")
    for i in range(30):
        cat_epoch = make_synthetic_epoch(class_offset=0.0, seed=i)
        wrench_epoch = make_synthetic_epoch(class_offset=1.5, seed=100 + i)
        cat.update(
            compute_covariance(cat_epoch),
            rqa_features_from_epoch(cat_epoch),
            metadata={"trial": i, "class": "cat"},
        )
        wrench.update(
            compute_covariance(wrench_epoch),
            rqa_features_from_epoch(wrench_epoch),
            metadata={"trial": i, "class": "wrench"},
        )
    print(f"      cat.n_trials = {cat.n_trials}, wrench.n_trials = {wrench.n_trials}")

    # Pre-freeze score should fail
    print("\n[2/5] Verifying pre-freeze score raises CardError ...")
    raised = False
    try:
        cat.score(np.eye(n_ch), np.zeros(5))
    except CardError:
        raised = True
    if not raised:
        print("  ✗ pre-freeze score did NOT raise")
        return 1
    print("      ✓ CardError raised")

    # Freeze
    print("\n[3/5] Freezing cards ...")
    cat.freeze()
    wrench.freeze()
    print(f"      cat:    σ={cat.riemannian_sigma:.4e}, k={cat.rqa_scale:.4e}")
    print(f"      wrench: σ={wrench.riemannian_sigma:.4e}, k={wrench.rqa_scale:.4e}")

    # Classification check
    print("\n[4/5] Classifying 10 new cat-like + 10 wrench-like trials ...")
    cat_correct = 0
    for i in range(10):
        e = make_synthetic_epoch(class_offset=0.0, seed=1000 + i)
        cov, rqa = compute_covariance(e), rqa_features_from_epoch(e)
        s_cat = cat.score(cov, rqa)["combined"]
        s_wrench = wrench.score(cov, rqa)["combined"]
        if s_cat > s_wrench:
            cat_correct += 1
    wrench_correct = 0
    for i in range(10):
        e = make_synthetic_epoch(class_offset=1.5, seed=2000 + i)
        cov, rqa = compute_covariance(e), rqa_features_from_epoch(e)
        s_cat = cat.score(cov, rqa)["combined"]
        s_wrench = wrench.score(cov, rqa)["combined"]
        if s_wrench > s_cat:
            wrench_correct += 1
    print(f"      cat-like → cat:    {cat_correct}/10")
    print(f"      wrench-like → wrench: {wrench_correct}/10")
    if cat_correct < 8 or wrench_correct < 8:
        print(f"  ✗ classification weak (need ≥ 8/10 each)")
        return 1
    print("      ✓ classification ≥ 80% on synthetic data")

    # Save / load round trip
    print("\n[5/5] Save → load → re-score ...")
    with tempfile.TemporaryDirectory() as td:
        cat_path = Path(td) / "card_cat.npz"
        cat.save(cat_path)
        cat2 = NeuralCard.load(cat_path)

        e = make_synthetic_epoch(class_offset=0.0, seed=9999)
        cov, rqa = compute_covariance(e), rqa_features_from_epoch(e)
        s_orig = cat.score(cov, rqa)
        s_loaded = cat2.score(cov, rqa)

        diffs = {k: abs(s_orig[k] - s_loaded[k]) for k in s_orig}
        max_diff = max(diffs.values())
        print(f"      max component diff: {max_diff:.2e}")
        if max_diff > 1e-10:
            print("  ✗ save/load does not preserve scoring")
            for k, v in diffs.items():
                print(f"        {k}: {v:.2e}")
            return 1
        # Sanity: loaded card has same internal stats
        assert cat2.frozen
        assert cat2.n_trials == cat.n_trials
        assert np.allclose(cat2.riemannian_centroid, cat.riemannian_centroid)
        assert abs(cat2.riemannian_sigma - cat.riemannian_sigma) < 1e-12
        print("      ✓ save/load preserves scoring + internals exactly")

    print("\n" + "=" * 60)
    print("Card lifecycle smoke test PASSED.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())