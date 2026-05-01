"""Per-class neural card.

Lifecycle:
    card = NeuralCard("cat", n_channels=16)
    card.update(cov_trial1, rqa_trial1, weight=1.0, metadata={...})
    card.update(cov_trial2, rqa_trial2, weight=2.0, metadata={...})  # flagged-best
    ...
    summary = card.freeze()    # after >= MIN_TRIALS_FOR_FREEZE eligible trials
    scores  = card.score(cov_new, rqa_new)
    card.save("data/.../card_cat.npz")
    same    = NeuralCard.load("data/.../card_cat.npz")

A frozen card is immutable. Calling `update()` after freeze raises CardError.
A non-frozen card cannot be scored against. `tightness_recent()` is a
real-time monitoring metric for the operator.

Fields stored in the .npz:
    - class_name, n_channels, n_trials, weights {riem, rqa, emb}
    - frozen flag + frozen_at timestamp
    - riemannian_centroid (n_ch, n_ch), riemannian_sigma (scalar)
    - rqa_centroid (5,), rqa_cov (5, 5), rqa_scale (scalar)
    - embedding_centroid (None for V1; placeholder for V2)
    - train_distances_riem, train_distances_rqa2 (per-trial diagnostics)
    - trial_covs (n_trials, n_ch, n_ch), trial_rqas (n_trials, 5),
      trial_weights (n_trials,), trial_metadata_json (string)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np

from .features import (
    riemannian_distance,
    riemannian_mean,
    mahalanobis_squared,
)


class CardError(Exception):
    """Raised when a card is used incorrectly (e.g. score before freeze)."""


@dataclass
class TrialContribution:
    """A single trial's contribution to a card."""
    trial_id: int
    cov: np.ndarray
    rqa: np.ndarray
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class NeuralCard:
    """Per-class signature: Riemannian + RQA components."""

    MIN_TRIALS_FOR_FREEZE = 5

    def __init__(
        self,
        class_name: str,
        n_channels: int,
        weight_riem: float = 0.7,
        weight_rqa: float = 0.3,
        weight_emb: float = 0.0,
    ):
        self.class_name = class_name
        self.n_channels = n_channels
        self.weight_riem = weight_riem
        self.weight_rqa = weight_rqa
        self.weight_emb = weight_emb

        # Pre-freeze state
        self._trials: List[TrialContribution] = []
        self._centroid_cache: Optional[np.ndarray] = None
        self._cache_dirty: bool = True

        # Post-freeze state
        self.frozen: bool = False
        self.frozen_at: Optional[float] = None
        self.riemannian_centroid: Optional[np.ndarray] = None
        self.riemannian_sigma: Optional[float] = None
        self.rqa_centroid: Optional[np.ndarray] = None
        self.rqa_cov: Optional[np.ndarray] = None
        self.rqa_scale: Optional[float] = None
        self.embedding_centroid: Optional[np.ndarray] = None  # V2 reserved

        # Diagnostics populated at freeze
        self.train_distances_riem: List[float] = []
        self.train_distances_rqa2: List[float] = []

    # ─── pre-freeze ────────────────────────────────────────────────────

    @property
    def n_trials(self) -> int:
        return len(self._trials)

    def update(
        self,
        cov: np.ndarray,
        rqa: np.ndarray,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.frozen:
            raise CardError(f"Card '{self.class_name}' is frozen.")
        if cov.shape != (self.n_channels, self.n_channels):
            raise ValueError(f"cov shape {cov.shape}, expected {(self.n_channels, self.n_channels)}")
        if rqa.shape != (5,):
            raise ValueError(f"rqa shape {rqa.shape}, expected (5,)")
        if weight <= 0:
            raise ValueError(f"weight must be positive, got {weight}")

        self._trials.append(TrialContribution(
            trial_id=len(self._trials),
            cov=np.asarray(cov, dtype=np.float64).copy(),
            rqa=np.asarray(rqa, dtype=np.float64).copy(),
            weight=float(weight),
            metadata=dict(metadata or {}),
        ))
        self._cache_dirty = True

    def current_centroid(self) -> Optional[np.ndarray]:
        """Recompute (or return cached) Riemannian centroid based on current trials."""
        if not self._trials:
            return None
        if self._cache_dirty:
            covs = [t.cov for t in self._trials]
            weights = np.array([t.weight for t in self._trials], dtype=np.float64)
            self._centroid_cache = riemannian_mean(covs, weights=weights)
            self._cache_dirty = False
        return self._centroid_cache

    def tightness_recent(self, n: int = 10) -> Optional[float]:
        """Mean Riemannian distance of the last n trials to the centroid built
        from earlier trials. Lower = subject converging on a stable signature.
        Returns None if fewer than (n + MIN_TRIALS_FOR_FREEZE) trials accumulated.
        """
        if len(self._trials) < n + self.MIN_TRIALS_FOR_FREEZE:
            return None
        early = [t.cov for t in self._trials[:-n]]
        early_w = np.array([t.weight for t in self._trials[:-n]], dtype=np.float64)
        early_centroid = riemannian_mean(early, weights=early_w)
        recent_d = [riemannian_distance(t.cov, early_centroid) for t in self._trials[-n:]]
        return float(np.mean(recent_d))

    # ─── freeze ────────────────────────────────────────────────────────

    def freeze(self, sigma_method: str = "median") -> Dict[str, Any]:
        if self.frozen:
            return self.summary()
        if len(self._trials) < self.MIN_TRIALS_FOR_FREEZE:
            raise CardError(
                f"Card '{self.class_name}' has only {len(self._trials)} trials; "
                f"need ≥ {self.MIN_TRIALS_FOR_FREEZE}."
            )

        covs = [t.cov for t in self._trials]
        rqas = np.stack([t.rqa for t in self._trials])
        weights = np.array([t.weight for t in self._trials], dtype=np.float64)
        weights_norm = weights / weights.sum()

        # ── Riemannian centroid + σ ─────────────────────────────────
        self.riemannian_centroid = riemannian_mean(covs, weights=weights)
        self.train_distances_riem = [
            float(riemannian_distance(c, self.riemannian_centroid)) for c in covs
        ]
        if sigma_method == "median":
            sigma = float(np.median(self.train_distances_riem))
        elif sigma_method == "mean":
            sigma = float(np.mean(self.train_distances_riem))
        else:
            raise ValueError(f"Unknown sigma_method: {sigma_method}")
        # σ guards: never zero (would make exp(-d/σ) blow up)
        self.riemannian_sigma = max(sigma, 1e-12)

        # ── RQA mean + covariance + k ───────────────────────────────
        self.rqa_centroid = (rqas * weights_norm[:, None]).sum(axis=0)
        diffs = rqas - self.rqa_centroid
        self.rqa_cov = (diffs.T * weights_norm) @ diffs
        # Tikhonov-regularize
        self.rqa_cov = self.rqa_cov + 1e-6 * (np.trace(self.rqa_cov) / 5.0) * np.eye(5)

        cov_inv = np.linalg.pinv(self.rqa_cov)
        self.train_distances_rqa2 = [
            float((r - self.rqa_centroid) @ cov_inv @ (r - self.rqa_centroid)) for r in rqas
        ]
        # k chosen so median trial maps to similarity 0.5 under exp(-d² / k)
        median_d2 = float(np.median(self.train_distances_rqa2))
        self.rqa_scale = max(median_d2 / np.log(2.0), 1e-12)

        self.frozen = True
        self.frozen_at = time.time()
        return self.summary()

    # ─── score ─────────────────────────────────────────────────────────

    def score(self, cov: np.ndarray, rqa: np.ndarray) -> Dict[str, float]:
        if not self.frozen:
            raise CardError(f"Card '{self.class_name}' must be frozen before scoring.")
        d_riem = float(riemannian_distance(cov, self.riemannian_centroid))
        s_riem = float(np.exp(-d_riem / self.riemannian_sigma))
        d_rqa2 = float(mahalanobis_squared(rqa, self.rqa_centroid, self.rqa_cov))
        s_rqa = float(np.exp(-d_rqa2 / self.rqa_scale))
        s_emb = 0.0  # V2: when embedding is added, compute (cos(emb_trial, emb_centroid) + 1) / 2

        s_combined = (
            self.weight_riem * s_riem
            + self.weight_rqa * s_rqa
            + self.weight_emb * s_emb
        )
        return {
            "riemannian": s_riem,
            "rqa": s_rqa,
            "embedding": s_emb,
            "combined": float(s_combined),
            "d_riem": d_riem,
            "d_rqa2": d_rqa2,
        }

    # ─── summary ───────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        d = {
            "class_name": self.class_name,
            "n_trials": self.n_trials,
            "frozen": self.frozen,
            "frozen_at": self.frozen_at,
            "n_channels": self.n_channels,
            "weights": {
                "riemannian": self.weight_riem,
                "rqa": self.weight_rqa,
                "embedding": self.weight_emb,
            },
            "riemannian_sigma": self.riemannian_sigma,
            "rqa_scale": self.rqa_scale,
        }
        if self.train_distances_riem:
            d["train_distance_riem"] = {
                "min": float(np.min(self.train_distances_riem)),
                "median": float(np.median(self.train_distances_riem)),
                "max": float(np.max(self.train_distances_riem)),
                "std": float(np.std(self.train_distances_riem)),
            }
        return d

    # ─── I/O ───────────────────────────────────────────────────────────

    def save(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not self._trials:
            raise CardError(f"Cannot save empty card '{self.class_name}'.")

        trial_covs = np.stack([t.cov for t in self._trials])
        trial_rqas = np.stack([t.rqa for t in self._trials])
        trial_weights = np.array([t.weight for t in self._trials], dtype=np.float64)
        trial_metadata_json = json.dumps([t.metadata for t in self._trials])

        np.savez_compressed(
            path,
            class_name=self.class_name,
            n_channels=self.n_channels,
            n_trials=self.n_trials,
            weight_riem=self.weight_riem,
            weight_rqa=self.weight_rqa,
            weight_emb=self.weight_emb,
            frozen=self.frozen,
            frozen_at=self.frozen_at if self.frozen_at is not None else 0.0,
            riemannian_centroid=(
                self.riemannian_centroid if self.riemannian_centroid is not None
                else np.zeros((self.n_channels, self.n_channels))
            ),
            riemannian_sigma=self.riemannian_sigma if self.riemannian_sigma is not None else 0.0,
            rqa_centroid=(self.rqa_centroid if self.rqa_centroid is not None else np.zeros(5)),
            rqa_cov=(self.rqa_cov if self.rqa_cov is not None else np.zeros((5, 5))),
            rqa_scale=self.rqa_scale if self.rqa_scale is not None else 0.0,
            embedding_centroid=(
                self.embedding_centroid if self.embedding_centroid is not None
                else np.array([np.nan])
            ),
            train_distances_riem=np.array(self.train_distances_riem, dtype=np.float64),
            train_distances_rqa2=np.array(self.train_distances_rqa2, dtype=np.float64),
            trial_covs=trial_covs,
            trial_rqas=trial_rqas,
            trial_weights=trial_weights,
            trial_metadata_json=trial_metadata_json,
        )

    @classmethod
    def load(cls, path) -> "NeuralCard":
        path = Path(path)
        data = np.load(path, allow_pickle=False)
        card = cls(
            class_name=str(data["class_name"]),
            n_channels=int(data["n_channels"]),
            weight_riem=float(data["weight_riem"]),
            weight_rqa=float(data["weight_rqa"]),
            weight_emb=float(data["weight_emb"]),
        )

        # Restore trial contributions
        trial_covs = data["trial_covs"]
        trial_rqas = data["trial_rqas"]
        trial_weights = data["trial_weights"]
        trial_metadata = json.loads(str(data["trial_metadata_json"]))
        for i in range(len(trial_covs)):
            card._trials.append(TrialContribution(
                trial_id=i,
                cov=trial_covs[i],
                rqa=trial_rqas[i],
                weight=float(trial_weights[i]),
                metadata=trial_metadata[i] if i < len(trial_metadata) else {},
            ))

        # Restore frozen state
        card.frozen = bool(data["frozen"])
        if card.frozen:
            ts = float(data["frozen_at"])
            card.frozen_at = ts if ts > 0 else None
            card.riemannian_centroid = np.array(data["riemannian_centroid"])
            card.riemannian_sigma = float(data["riemannian_sigma"])
            card.rqa_centroid = np.array(data["rqa_centroid"])
            card.rqa_cov = np.array(data["rqa_cov"])
            card.rqa_scale = float(data["rqa_scale"])
            emb = np.array(data["embedding_centroid"])
            card.embedding_centroid = None if np.isnan(emb).any() else emb
            card.train_distances_riem = list(np.array(data["train_distances_riem"]))
            card.train_distances_rqa2 = list(np.array(data["train_distances_rqa2"]))
        return card