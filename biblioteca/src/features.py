"""Feature extraction: Riemannian covariance + Recurrence Quantification Analysis.

Two independent feature systems, intentionally complementary:

- **Riemannian covariance** captures spatial-spectral structure (which channels
  co-vary at which frequencies). It's the workhorse of motor-imagery BCI and
  is robust to amplitude scaling.

- **RQA** captures non-linear dynamic structure (does the trajectory through
  state space repeat itself? how regularly?). Computed on PC1 of the cleaned
  epoch — captures the dominant time-domain mode.

Both are fast: covariance is O(n_ch² × T), RQA on a 4-second epoch with
T~1000 takes <50 ms. Real-time-safe.
"""
from __future__ import annotations

from typing import Optional, List, Tuple

import numpy as np
from scipy.spatial.distance import pdist, squareform

try:
    from pyriemann.utils.distance import distance_riemann
    from pyriemann.utils.mean import mean_riemann
    PYRIEMANN_AVAILABLE = True
except ImportError:
    PYRIEMANN_AVAILABLE = False
    distance_riemann = None  # type: ignore
    mean_riemann = None  # type: ignore


# ═════════════════════════════════════════════════════════════════════════
# Riemannian covariance
# ═════════════════════════════════════════════════════════════════════════

def compute_covariance(epoch: np.ndarray, regularization: float = 1e-6) -> np.ndarray:
    """Sample covariance with Tikhonov regularization (Ledoit-Wolf-style shrinkage
    using a scaled identity).

    Parameters
    ----------
    epoch : (n_channels, n_samples)
    regularization : added scaled identity strength

    Returns
    -------
    cov : (n_channels, n_channels), guaranteed SPD
    """
    cov = np.cov(epoch)
    n_ch = cov.shape[0]
    trace_scale = np.trace(cov) / n_ch
    cov = cov + regularization * trace_scale * np.eye(n_ch)
    return cov


def riemannian_distance(spd_a: np.ndarray, spd_b: np.ndarray) -> float:
    """Affine-invariant Riemannian (AIRM) distance between two SPD matrices."""
    if not PYRIEMANN_AVAILABLE:
        raise ImportError("pyriemann not installed. Run: pip install pyriemann")
    return float(distance_riemann(spd_a, spd_b))


def riemannian_mean(
    spd_list: List[np.ndarray],
    weights: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Weighted geodesic mean of SPD matrices on the AIRM manifold.

    `weights` must be non-negative; will be normalized to sum to 1.
    """
    if not PYRIEMANN_AVAILABLE:
        raise ImportError("pyriemann not installed.")
    if not spd_list:
        raise ValueError("Empty spd_list")
    arr = np.stack(spd_list, axis=0)
    if weights is not None:
        w = np.asarray(weights, dtype=np.float64)
        if w.shape[0] != arr.shape[0]:
            raise ValueError("weights length must match spd_list length")
        if (w < 0).any():
            raise ValueError("weights must be non-negative")
        w = w / w.sum()
        return mean_riemann(arr, sample_weight=w)
    return mean_riemann(arr)


# ═════════════════════════════════════════════════════════════════════════
# RQA features
# ═════════════════════════════════════════════════════════════════════════

def estimate_tau(signal: np.ndarray, max_lag: int = 50) -> int:
    """Choose embedding delay τ as the first zero crossing of autocorrelation.

    If autocorrelation never reaches zero within `max_lag`, returns the lag
    where it first dips below 1/e (a fallback used in nonlinear dynamics).
    """
    s = signal - signal.mean()
    n = len(s)
    if n < 2:
        return 1
    full = np.correlate(s, s, mode="full")
    autocorr = full[n - 1: n - 1 + max_lag]
    if autocorr[0] == 0:
        return 1
    autocorr = autocorr / autocorr[0]
    zero = np.where(autocorr <= 0)[0]
    if len(zero) > 0:
        return max(1, int(zero[0]))
    one_over_e = np.where(autocorr <= 1.0 / np.e)[0]
    if len(one_over_e) > 0:
        return max(1, int(one_over_e[0]))
    return 1


def takens_embed(signal: np.ndarray, dim: int = 3, tau: int = 1) -> np.ndarray:
    """Takens delay embedding. Returns (N, dim) where N = len(signal) - (dim-1)*tau."""
    n = len(signal) - (dim - 1) * tau
    if n <= 0:
        raise ValueError(f"Signal of length {len(signal)} too short for dim={dim}, tau={tau}")
    out = np.empty((n, dim), dtype=np.float64)
    for d in range(dim):
        out[:, d] = signal[d * tau: d * tau + n]
    return out


def recurrence_matrix(embedded: np.ndarray, threshold_pct: float = 0.1) -> np.ndarray:
    """Binary recurrence matrix using a percentile threshold on pairwise distances.

    Parameters
    ----------
    embedded : (N, dim)
    threshold_pct : threshold on distances, as a fraction (e.g., 0.1 = 10th percentile
        of off-diagonal pairwise distances). Lower = sparser recurrence.

    Returns
    -------
    R : (N, N) uint8 binary matrix
    """
    distances = squareform(pdist(embedded))
    off_diag = distances[~np.eye(distances.shape[0], dtype=bool)]
    if off_diag.size == 0:
        return np.eye(distances.shape[0], dtype=np.uint8)
    threshold = np.percentile(off_diag, threshold_pct * 100)
    return (distances <= threshold).astype(np.uint8)


def _diagonal_runs(R: np.ndarray, min_len: int = 2) -> List[int]:
    """Lengths of runs of consecutive 1s along off-main diagonals (k != 0)."""
    runs: List[int] = []
    n = R.shape[0]
    for k in range(-(n - 1), n):
        if k == 0:
            continue
        diag = np.diag(R, k=k)
        run_len = 0
        for v in diag:
            if v == 1:
                run_len += 1
            else:
                if run_len >= min_len:
                    runs.append(run_len)
                run_len = 0
        if run_len >= min_len:
            runs.append(run_len)
    return runs


def _vertical_runs(R: np.ndarray, min_len: int = 2) -> List[int]:
    """Lengths of runs of consecutive 1s along columns (vertical lines)."""
    runs: List[int] = []
    for col in range(R.shape[1]):
        column = R[:, col]
        run_len = 0
        for v in column:
            if v == 1:
                run_len += 1
            else:
                if run_len >= min_len:
                    runs.append(run_len)
                run_len = 0
        if run_len >= min_len:
            runs.append(run_len)
    return runs


def rqa_features(
    signal_1d: np.ndarray,
    dim: int = 3,
    tau: Optional[int] = None,
    threshold_pct: float = 0.1,
    min_diag: int = 2,
) -> np.ndarray:
    """Compute the 5-feature RQA vector.

    Parameters
    ----------
    signal_1d : 1D signal (e.g., a single channel or PC1 across channels)
    dim : embedding dimension (default 3)
    tau : embedding delay; if None, estimated from autocorrelation
    threshold_pct : recurrence threshold (fraction of pairwise-distance distribution)
    min_diag : minimum line length to count toward DET / LAM

    Returns
    -------
    features : (5,) np.ndarray of
        [recurrence_rate, determinism, avg_diag_length, entropy_diag, laminarity]
    """
    if tau is None:
        tau = estimate_tau(signal_1d)
    embedded = takens_embed(signal_1d, dim=dim, tau=tau)
    R = recurrence_matrix(embedded, threshold_pct=threshold_pct)
    n = R.shape[0]

    # 1. Recurrence rate
    rr = float(R.sum() / (n * n))

    # 2-4. Diagonal-line statistics
    diag_lengths = _diagonal_runs(R, min_len=min_diag)
    n_recurrent_off_main = int(R.sum() - n)
    if diag_lengths and n_recurrent_off_main > 0:
        det = float(sum(diag_lengths) / n_recurrent_off_main)
        avg_diag = float(np.mean(diag_lengths))
        unique, counts = np.unique(diag_lengths, return_counts=True)
        probs = counts / counts.sum()
        entropy = float(-np.sum(probs * np.log(probs + 1e-12)))
    else:
        det = avg_diag = entropy = 0.0

    # 5. Laminarity (vertical-line ratio)
    vert_lengths = _vertical_runs(R, min_len=min_diag)
    if R.sum() > 0 and vert_lengths:
        lam = float(sum(vert_lengths) / R.sum())
    else:
        lam = 0.0

    return np.array([rr, det, avg_diag, entropy, lam], dtype=np.float64)


def channel_pc1(epoch: np.ndarray) -> np.ndarray:
    """First principal component across channels — used as the 1D signal for RQA.

    epoch: (n_channels, n_samples) → returns (n_samples,).
    """
    centered = epoch - epoch.mean(axis=1, keepdims=True)
    cov = centered @ centered.T / (epoch.shape[1] - 1)
    eigvals, eigvecs = np.linalg.eigh(cov)
    pc1_dir = eigvecs[:, -1]   # eigvector with largest eigenvalue
    return pc1_dir @ epoch


def rqa_features_from_epoch(
    epoch: np.ndarray,
    dim: int = 3,
    tau: Optional[int] = None,
    threshold_pct: float = 0.1,
) -> np.ndarray:
    """Convenience: extract RQA on the PC1 of an epoch."""
    signal = channel_pc1(epoch)
    return rqa_features(signal, dim=dim, tau=tau, threshold_pct=threshold_pct)


# ═════════════════════════════════════════════════════════════════════════
# Mahalanobis with regularized covariance (used in card scoring)
# ═════════════════════════════════════════════════════════════════════════

def mahalanobis_squared(
    x: np.ndarray,
    mean: np.ndarray,
    cov: np.ndarray,
    regularization: float = 1e-6,
) -> float:
    """Squared Mahalanobis distance with Tikhonov regularization.

    The card stores `rqa_cov` for this scoring; `regularization` guards against
    near-singular covariance when n_trials is small.
    """
    diff = x - mean
    cov_reg = cov + regularization * np.trace(cov) / cov.shape[0] * np.eye(cov.shape[0])
    inv = np.linalg.pinv(cov_reg)
    return float(diff @ inv @ diff)