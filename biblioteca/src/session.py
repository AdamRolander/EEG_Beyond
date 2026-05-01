"""Session manager: phase machine + WebSocket protocol.

Owns the EEG inlet, preprocessor, marker outlet, and per-class neural cards.
The browser drives trial timing (audio, image presentation, fixation periods);
this module receives notifications via the WebSocket and emits the corresponding
LSL markers using `pylsl.local_clock()` — the same clock that timestamps EEG
samples — so epoch extraction by marker timestamp is exact.

Phase machine:

    IDLE → ICA_CAL → IDLE → PERCEPTION → IDLE → ACQUISITION
                                                    ↓
                                            (threshold met)
                                                    ↓
                                            AWAITING_FREEZE
                                                    ↓
                                              freeze_cards
                                                    ↓
                                                  IDLE → FEEDBACK → IDLE → PROBE → COMPLETE

The operator triggers each transition explicitly via `start_phase` /
`end_phase`. Threshold-met fires a notification but does not auto-transition;
the operator may choose to keep collecting acquisition data past threshold.

WebSocket message shape (all JSON):
    Browser → Server:
        {type: "start_phase", phase: "ICA_CAL"}
        {type: "trial_start", phase: ..., block: ..., position: ..., class: ..., exemplar_idx: ...}
        {type: "fixation_onset"}
        {type: "audio_cue_onset", class: "cat"}
        {type: "trial_imagery_onset", class: "cat"}
        {type: "trial_imagery_offset"}
        {type: "rest_onset"}
        {type: "trial_complete"}
        {type: "trial_error", message: "..."}
        {type: "block_start", block: 0}
        {type: "block_complete", block: 0, likert: 4, flags_best: [1, 3], flags_bad: []}
        {type: "anchor_start", block: 0}
        {type: "anchor_image_onset", class: "cat", exemplar_idx: 0}
        {type: "anchor_end"}
        {type: "ica_substep_start", substep: "eyes_open"}
        {type: "ica_substep_end", substep: "eyes_open"}
        {type: "fit_ica"}
        {type: "freeze_cards"}
        {type: "end_phase"}
        {type: "end_session"}
        {type: "pause"} / {type: "resume"}
        {type: "get_status"}
    Server → Browser:
        {type: "session_ready", session_id, eeg, ...}
        {type: "phase_change", phase, card_progress}
        {type: "ica_progress", status}
        {type: "ica_complete", n_components, n_rejected, labels, confidences, bad_mask}
        {type: "trial_processed", trial_id, artifact, peak_to_peak_uv}
        {type: "trial_failed", reason}
        {type: "trial_score", scores: {cat: 0.7, wrench: 0.2, house: 0.1}, cued_class: "cat"}   # FEEDBACK only
        {type: "block_complete_ack", block, card_progress}
        {type: "card_progress", progress: {cat: 12, wrench: 11, house: 13}}
        {type: "acquisition_threshold_met", progress, threshold}
        {type: "card_frozen", summaries}
        {type: "session_complete", summary}
        {type: "status", ...}
        {type: "error", message}
"""
from __future__ import annotations

import asyncio
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Dict, Any, List, Optional, Set

import numpy as np

from .config_session import SessionConfig
from .eeg_ingest import make_eeg_inlet
from .preprocessing import RealtimePreprocessor, ICACalibrator
from .features import compute_covariance, rqa_features_from_epoch
from .neural_card import NeuralCard, CardError
from .marker_outlet import MarkerOutlet
from . import markers as M


SendFn = Callable[[Dict[str, Any]], Awaitable[None]]


class SessionManager:
    PHASES = (
        "IDLE", "ICA_CAL", "PERCEPTION",
        "ACQUISITION", "AWAITING_FREEZE",
        "FEEDBACK", "PROBE", "COMPLETE",
    )

    def __init__(self, config: SessionConfig, send: SendFn):
        self.config = config
        self.send = send
        self.session_id = datetime.now().strftime("%Y%m%dT%H%M%S")
        self.session_dir = Path(config.output.data_root) / config.subject.id / self.session_id

        # Components — created on connect()
        self.inlet = None
        self.preprocessor: Optional[RealtimePreprocessor] = None
        self.markers = MarkerOutlet()
        self.ica_calibrator: Optional[ICACalibrator] = None

        # Cards (instantiated empty in connect(); populated during ACQUISITION)
        self.cards: Dict[str, NeuralCard] = {}

        # State
        self.phase: str = "IDLE"
        self.current_trial: Optional[Dict[str, Any]] = None
        self.pending_block_trials: List[Dict[str, Any]] = []
        self.session_started_at: Optional[float] = None

        # Logs
        self.trial_log: List[Dict[str, Any]] = []
        self.block_likerts: List[Dict[str, Any]] = []

        # Handler dispatch table
        self._handlers: Dict[str, Callable] = {
            "get_status": self.on_get_status,
            "start_phase": self.on_start_phase,
            "end_phase": self.on_end_phase,
            "ica_substep_start": self.on_ica_substep_start,
            "ica_substep_end": self.on_ica_substep_end,
            "fit_ica": self.on_fit_ica,
            "trial_start": self.on_trial_start,
            "trial_imagery_onset": self.on_trial_imagery_onset,
            "trial_imagery_offset": self.on_trial_imagery_offset,
            "trial_complete": self.on_trial_complete,
            "trial_error": self.on_trial_error,
            "block_start": self.on_block_start,
            "block_complete": self.on_block_complete,
            "anchor_start": self.on_anchor_start,
            "anchor_image_onset": self.on_anchor_image_onset,
            "anchor_end": self.on_anchor_end,
            "fixation_onset": self.on_fixation_onset,
            "audio_cue_onset": self.on_audio_cue_onset,
            "perception_onset": self.on_perception_onset,
            "perception_offset": self.on_perception_offset,
            "rest_onset": self.on_rest_onset,
            "freeze_cards": self.on_freeze_cards,
            "end_session": self.on_end_session,
            "pause": self.on_pause,
            "resume": self.on_resume,
        }

    # ─── lifecycle ────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Create session dir, open marker outlet, connect EEG, build preprocessor + cards."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        # Snapshot config for reproducibility
        try:
            with (self.session_dir / "config.json").open("w") as f:
                json.dump(self.config.model_dump(), f, indent=2, default=str)
        except Exception as e:
            print(f"[Session] config snapshot failed: {e}")

        # Marker outlet
        self.markers.open()

        # EEG inlet
        self.inlet = make_eeg_inlet(
            stream_name_hint=self.config.eeg.stream_name_hint,
            buffer_seconds=self.config.eeg.buffer_seconds,
            expected_n_channels=self.config.eeg.expected_n_channels,
            expected_sample_rate=self.config.eeg.expected_sample_rate or 250,
            simulate=self.config.eeg.simulate,
        )
        connected = self.inlet.discover_and_connect(timeout_sec=5.0)
        if not connected:
            await self.send({
                "type": "error",
                "message": (
                    "Could not connect to an EEG stream. Verify the LSL outlet is running, "
                    "or set eeg.simulate=true (or env EEG_SIMULATE=1) for development."
                ),
            })
            return
        self.inlet.start()

        # Apply config override of channel labels (e.g. for OpenBCI GUI which
        # streams generic "Channel_1" names — ICLabel can't classify those).
        cfg_labels = self.config.eeg.channel_labels
        if cfg_labels is not None:
            if len(cfg_labels) != self.inlet.n_channels:
                await self.send({
                    "type": "error",
                    "message": (
                        f"config.eeg.channel_labels has {len(cfg_labels)} entries "
                        f"but inlet reports {self.inlet.n_channels} channels."
                    ),
                })
                return
            print(f"[Session] Overriding inlet labels {self.inlet.channel_labels[:4]}... "
                  f"with config labels {cfg_labels[:4]}...")
            self.inlet.channel_labels = list(cfg_labels)

        # Preprocessor (built using actual inlet metadata, not just config)
        self.preprocessor = RealtimePreprocessor(
            sample_rate=self.inlet.sample_rate,
            n_channels=self.inlet.n_channels,
            bandpass=(
                self.config.preprocessing.bandpass_low_hz,
                self.config.preprocessing.bandpass_high_hz,
            ),
            notch_freqs=tuple(self.config.preprocessing.notch_freqs_hz),
            use_car=self.config.preprocessing.car,
            artifact_pp_threshold_uv=self.config.preprocessing.artifact_pp_threshold_uv,
        )

        # Cards (one per class, empty at session start)
        for cls_name in self.config.class_names:
            self.cards[cls_name] = NeuralCard(
                class_name=cls_name,
                n_channels=self.inlet.n_channels,
                weight_riem=self.config.card.feature_weights.riemannian,
                weight_rqa=self.config.card.feature_weights.rqa,
                weight_emb=self.config.card.feature_weights.embedding,
            )

        self.session_started_at = self.markers.emit(
            M.EXP_START, {"subject": self.config.subject.id, "session_id": self.session_id},
        )

        await self.send({
            "type": "session_ready",
            "session_id": self.session_id,
            "subject_id": self.config.subject.id,
            "session_dir": str(self.session_dir),
            "eeg": self.inlet.status(),
            "phase": self.phase,
            "classes": self.config.class_names,
            "class_codes": self.config.class_codes,
        })

    async def cleanup(self) -> None:
        """Save what's preservable, stop EEG. Safe to call multiple times."""
        try:
            await self._save_session_artifacts()
        except Exception as e:
            print(f"[Session] cleanup save error: {e}")
        if self.inlet is not None:
            try:
                self.inlet.stop()
            except Exception as e:
                print(f"[Session] inlet stop error: {e}")

    # ─── dispatch ─────────────────────────────────────────────────────

    async def handle(self, msg: Dict[str, Any]) -> None:
        msg_type = msg.get("type")
        if not msg_type:
            await self.send({"type": "error", "message": "missing 'type' field"})
            return
        handler = self._handlers.get(msg_type)
        if handler is None:
            await self.send({"type": "error", "message": f"unknown message type: '{msg_type}'"})
            return
        try:
            await handler(msg)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.send({"type": "error", "message": f"{type(e).__name__}: {e}"})

    # ─── status / phase ───────────────────────────────────────────────

    async def on_get_status(self, msg: Dict[str, Any]) -> None:
        await self.send({
            "type": "status",
            "phase": self.phase,
            "session_id": self.session_id,
            "subject_id": self.config.subject.id,
            "eeg": self.inlet.status() if self.inlet else None,
            "card_progress": self._card_progress(),
            "card_frozen": {cls: card.frozen for cls, card in self.cards.items()},
            "markers_emitted": len(self.markers.get_log()),
        })

    async def on_start_phase(self, msg: Dict[str, Any]) -> None:
        target = msg["phase"].upper()
        if target not in self.PHASES:
            await self.send({"type": "error", "message": f"unknown phase: {target}"})
            return
        legal = self._allowed_transitions(self.phase)
        if target not in legal:
            await self.send({
                "type": "error",
                "message": f"invalid transition {self.phase} → {target}; allowed: {legal}",
            })
            return
        # Emit phase-start marker
        marker_for_start = {
            "ICA_CAL": M.PHASE_ICA_CAL_START,
            "PERCEPTION": M.PHASE_PERCEPTION_START,
            "ACQUISITION": M.PHASE_ACQUISITION_START,
            "FEEDBACK": M.PHASE_FEEDBACK_START,
            "PROBE": M.PHASE_PROBE_START,
        }.get(target)
        if marker_for_start is not None:
            self.markers.emit(marker_for_start, {})
        self.phase = target
        await self._broadcast_phase_change(target)

    async def on_end_phase(self, msg: Dict[str, Any]) -> None:
        """Operator-driven phase end."""
        end_marker = {
            "ICA_CAL": M.PHASE_ICA_CAL_END,
            "PERCEPTION": M.PHASE_PERCEPTION_END,
            "ACQUISITION": M.PHASE_ACQUISITION_END,
            "FEEDBACK": M.PHASE_FEEDBACK_END,
            "PROBE": M.PHASE_PROBE_END,
        }.get(self.phase)
        if end_marker is None:
            await self.send({"type": "error", "message": f"cannot end phase from {self.phase}"})
            return
        self.markers.emit(end_marker, {})

        # Transition rules
        if self.phase == "ACQUISITION":
            self.phase = "AWAITING_FREEZE"
        elif self.phase == "PROBE":
            self.phase = "COMPLETE"
        else:
            self.phase = "IDLE"
        await self._broadcast_phase_change(self.phase)

    def _allowed_transitions(self, current: str) -> List[str]:
        if current == "IDLE":
            return ["ICA_CAL", "PERCEPTION", "ACQUISITION", "FEEDBACK", "PROBE", "COMPLETE"]
        if current == "AWAITING_FREEZE":
            # Freeze first, or go back to acquisition for more data
            return ["ACQUISITION"]
        return ["IDLE"]

    async def _broadcast_phase_change(self, phase: str) -> None:
        await self.send({
            "type": "phase_change",
            "phase": phase,
            "card_progress": self._card_progress(),
            "card_frozen": {cls: card.frozen for cls, card in self.cards.items()},
        })

    # ─── ICA calibration ──────────────────────────────────────────────

    async def on_ica_substep_start(self, msg: Dict[str, Any]) -> None:
        substep = msg["substep"]
        code = self._ica_substep_code(substep)
        if code is not None:
            self.markers.emit(code, {"substep": substep, "stage": "start"})

    async def on_ica_substep_end(self, msg: Dict[str, Any]) -> None:
        substep = msg["substep"]
        code = self._ica_substep_code(substep)
        if code is not None:
            self.markers.emit(code, {"substep": substep, "stage": "end"})

    def _ica_substep_code(self, substep: str) -> Optional[int]:
        return {
            "eyes_open": M.ICA_CAL_EYES_OPEN,
            "eyes_closed": M.ICA_CAL_EYES_CLOSED,
            "blink": M.ICA_CAL_BLINK,
            "jaw": M.ICA_CAL_JAW,
        }.get(substep)

    async def on_fit_ica(self, msg: Dict[str, Any]) -> None:
        """Fit ICA on the calibration window and load the unmixing matrix into the preprocessor."""
        if not self.config.preprocessing.ica.enable:
            await self.send({"type": "ica_complete", "skipped": True})
            return

        start_marker = self.markers.find_latest(M.PHASE_ICA_CAL_START)
        if start_marker is None:
            await self.send({"type": "error", "message": "no PHASE_ICA_CAL_START marker found"})
            return
        t_start = start_marker[0]

        # Latest sample timestamp from the inlet's ring buffer
        latest_ts = None
        if self.inlet is not None and self.inlet.buffer is not None:
            latest_ts = self.inlet.buffer.latest_timestamp()
        if latest_ts is None:
            await self.send({"type": "error", "message": "no EEG data in buffer for ICA fit"})
            return
        duration = latest_ts - t_start - 1.0  # 1 s tail margin
        if duration < 60:
            await self.send({
                "type": "error",
                "message": f"only {duration:.1f}s of calibration data available; need ≥ 60s",
            })
            return

        epoch_data = self.inlet.get_epoch_by_lsl_time(t_start, duration, wait_max_s=1.0)
        if epoch_data is None:
            await self.send({"type": "error", "message": "could not extract calibration window from buffer"})
            return
        _, calibration = epoch_data

        await self.send({"type": "ica_progress", "status": "fitting", "duration_s": float(duration)})

        def _do_ica():
            # Bandpass + notch first; ICA is fit on filtered data
            filtered = self.preprocessor.bandpass_filter.apply(calibration)
            for nf in self.preprocessor.notch_filters:
                filtered = nf.apply(filtered)
            calib = ICACalibrator(
                sample_rate=self.inlet.sample_rate,
                channel_labels=self.inlet.channel_labels,
                method=self.config.preprocessing.ica.method,
                n_components=self.config.preprocessing.ica.n_components,
                reject_categories=self.config.preprocessing.ica.reject_categories,
                confidence_threshold=self.config.preprocessing.ica.auto_label_threshold,
                auto_label=self.config.preprocessing.ica.auto_label,
            )
            result = calib.fit(filtered)
            ica_dir = self.session_dir / "ica"
            calib.save(ica_dir)
            return calib, result, ica_dir

        try:
            calib, result, ica_dir = await asyncio.to_thread(_do_ica)
            self.ica_calibrator = calib
            self.preprocessor.load_ica(ica_dir)
            await self.send({
                "type": "ica_complete",
                "n_components": result["n_components"],
                "n_rejected": result["n_rejected"],
                "labels": result["labels"],
                "confidences": result["confidences"],
                "bad_mask": result["bad_mask"],
                "saved_to": str(ica_dir),
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.send({"type": "error", "message": f"ICA fit failed: {e}"})

    # ─── trial flow ───────────────────────────────────────────────────

    async def on_trial_start(self, msg: Dict[str, Any]) -> None:
        self.current_trial = {
            "phase": self.phase,
            "block": msg.get("block"),
            "position": msg.get("position"),
            "class": msg.get("class"),
            "exemplar_idx": msg.get("exemplar_idx"),
            "trial_id": len(self.trial_log) + len(self.pending_block_trials),
            "fixation_onset_lsl": None,
            "audio_cue_onset_lsl": None,
            "perception_onset_lsl": None,
            "perception_offset_lsl": None,
            "imagery_onset_lsl": None,
            "imagery_offset_lsl": None,
            "rest_onset_lsl": None,
        }
        ts = self.markers.emit(M.TRIAL_START, {
            "phase": self.phase,
            "block": msg.get("block"),
            "position": msg.get("position"),
            "class": msg.get("class"),
            "exemplar_idx": msg.get("exemplar_idx"),
        })
        self.current_trial["trial_start_lsl"] = ts

    async def on_fixation_onset(self, msg: Dict[str, Any]) -> None:
        ts = self.markers.emit(M.FIXATION_ONSET, {})
        if self.current_trial is not None:
            self.current_trial["fixation_onset_lsl"] = ts

    async def on_audio_cue_onset(self, msg: Dict[str, Any]) -> None:
        cls = msg.get("class") or (self.current_trial["class"] if self.current_trial else None)
        ts = self.markers.emit(M.AUDIO_CUE_ONSET, {"class": cls})
        if self.current_trial is not None:
            self.current_trial["audio_cue_onset_lsl"] = ts

    async def on_perception_onset(self, msg: Dict[str, Any]) -> None:
        cls = msg.get("class") or (self.current_trial["class"] if self.current_trial else None)
        exemplar_idx = msg.get("exemplar_idx")
        ts = self.markers.emit(M.PERCEPTION_ONSET, {"class": cls, "exemplar_idx": exemplar_idx})
        # Class identity marker
        cls_code = self.config.class_codes.get(cls) if cls else None
        if cls_code is not None:
            self.markers.emit(cls_code, {"context": "perception"})
        # Exemplar identity marker
        if exemplar_idx is not None and cls in self.config.class_names:
            offset = self.config.class_names.index(cls)
            self.markers.emit(M.exemplar_code(offset, int(exemplar_idx)), {})
        if self.current_trial is not None:
            self.current_trial["perception_onset_lsl"] = ts

    async def on_perception_offset(self, msg: Dict[str, Any]) -> None:
        ts = self.markers.emit(M.PERCEPTION_OFFSET, {})
        if self.current_trial is not None:
            self.current_trial["perception_offset_lsl"] = ts

    async def on_trial_imagery_onset(self, msg: Dict[str, Any]) -> None:
        cls = msg.get("class") or (self.current_trial["class"] if self.current_trial else None)
        ts = self.markers.emit(M.IMAGERY_ONSET, {"class": cls})
        cls_code = self.config.class_codes.get(cls) if cls else None
        if cls_code is not None:
            self.markers.emit(cls_code, {"context": "imagery"})
        if self.current_trial is not None:
            self.current_trial["imagery_onset_lsl"] = ts

    async def on_trial_imagery_offset(self, msg: Dict[str, Any]) -> None:
        ts = self.markers.emit(M.IMAGERY_OFFSET, {})
        if self.current_trial is not None:
            self.current_trial["imagery_offset_lsl"] = ts

    async def on_rest_onset(self, msg: Dict[str, Any]) -> None:
        ts = self.markers.emit(M.REST_ONSET, {})
        if self.current_trial is not None:
            self.current_trial["rest_onset_lsl"] = ts

    async def on_trial_complete(self, msg: Dict[str, Any]) -> None:
        if self.current_trial is None:
            await self.send({"type": "error", "message": "trial_complete with no active trial"})
            return

        # Pick the right onset and duration depending on phase
        if self.phase == "PERCEPTION":
            t_onset = self.current_trial.get("perception_onset_lsl")
            duration = self.config.phases.perception_block.perception_duration_ms / 1000.0
            window_offset = 0.0
        else:
            t_onset = self.current_trial.get("imagery_onset_lsl")
            duration = (
                self.config.card.imagery_epoch_end_s
                - self.config.card.imagery_epoch_start_s
            )
            window_offset = self.config.card.imagery_epoch_start_s

        if t_onset is None:
            await self._fail_trial("no onset marker recorded")
            return

        t_start = t_onset + window_offset
        # Pull epoch from buffer (allow up to 2s for the buffer to catch up).
        # The previous default of 1s was too tight when chunks land every ~50ms
        # and trial_complete arrives close to the chunk boundary.
        epoch_data = await asyncio.to_thread(
            self.inlet.get_epoch_by_lsl_time, t_start, duration, 2.0,
        )
        if epoch_data is None:
            # Surface a real reason instead of "epoch not in buffer"
            diag = "buffer not accessible"
            if self.inlet is not None and self.inlet.buffer is not None:
                diag = self.inlet.buffer.diagnose_epoch_extraction(t_start, duration)
            await self._fail_trial(
                f"epoch extraction failed: {diag} "
                f"(t_start={t_start:.3f}, duration={duration:.3f}, phase={self.phase})"
            )
            return
        timestamps, epoch = epoch_data

        # Preprocess + features in a thread (CPU-bound, ~50ms)
        def _process():
            cleaned, info = self.preprocessor.apply(
                epoch, apply_ica=self.preprocessor.has_ica()
            )
            cov = compute_covariance(cleaned)
            rqa = rqa_features_from_epoch(
                cleaned,
                dim=self.config.card.rqa_phase_space_dim,
                tau=self.config.card.rqa_tau,
                threshold_pct=self.config.card.rqa_recurrence_threshold_pct,
            )
            return cleaned, info, cov, rqa

        try:
            cleaned, info, cov, rqa = await asyncio.to_thread(_process)
        except Exception as e:
            await self._fail_trial(f"preprocessing/features failed: {e}")
            return

        self.markers.emit(M.TRIAL_END, {})

        record = dict(self.current_trial)
        record.update({
            "n_samples_in_epoch": int(epoch.shape[1]),
            "peak_to_peak_uv": info["peak_to_peak_uv"],
            "artifact": bool(info["artifact"]),
        })

        # Phase-specific handling
        if self.phase in ("FEEDBACK", "PROBE"):
            # All cards must be frozen
            unfrozen = [c for c, card in self.cards.items() if not card.frozen]
            if unfrozen:
                await self._fail_trial(f"cards not frozen: {unfrozen}")
                return
            scores = {cls: self.cards[cls].score(cov, rqa) for cls in self.cards}
            argmax = max(scores, key=lambda c: scores[c]["combined"])
            record["scores"] = scores
            record["argmax_class"] = argmax
            record["argmax_correct"] = (argmax == self.current_trial["class"])
            self.trial_log.append(record)
            if self.phase == "FEEDBACK":
                bars = {cls: round(s["combined"], 3) for cls, s in scores.items()}
                await self.send({
                    "type": "trial_score",
                    "scores": bars,
                    "cued_class": self.current_trial["class"],
                })
            # PROBE: silent — no UI feedback
        elif self.phase == "ACQUISITION":
            # Buffer until block end (eligibility decided then via likert + flags)
            record["_cov"] = cov
            record["_rqa"] = rqa
            self.pending_block_trials.append(record)
        else:
            # PERCEPTION, ICA_CAL, etc. — log but no card update
            self.trial_log.append(record)

        await self.send({
            "type": "trial_processed",
            "trial_id": record.get("trial_id"),
            "phase": self.phase,
            "artifact": record["artifact"],
            "peak_to_peak_uv": record["peak_to_peak_uv"],
        })
        self.current_trial = None

    async def on_trial_error(self, msg: Dict[str, Any]) -> None:
        await self._fail_trial(msg.get("message", "browser-reported error"))

    async def _fail_trial(self, reason: str) -> None:
        if self.current_trial is not None:
            failed = dict(self.current_trial)
            failed["error"] = reason
            self.trial_log.append(failed)
        await self.send({"type": "trial_failed", "reason": reason})
        self.current_trial = None

    # ─── blocks / anchors ─────────────────────────────────────────────

    async def on_block_start(self, msg: Dict[str, Any]) -> None:
        self.markers.emit(M.BLOCK_START, {"block": msg.get("block"), "phase": self.phase})

    async def on_block_complete(self, msg: Dict[str, Any]) -> None:
        likert = int(msg.get("likert", 0))
        flags_best: Set[int] = set(msg.get("flags_best", []))
        flags_bad: Set[int] = set(msg.get("flags_bad", []))
        block_idx = msg.get("block")

        # Markers for the block end
        if 1 <= likert <= 5:
            self.markers.emit(M.likert_code(likert), {"block": block_idx})
        for pos in flags_best:
            self.markers.emit(M.TRIAL_FLAG_BEST, {"block": block_idx, "position": pos})
        for pos in flags_bad:
            self.markers.emit(M.TRIAL_FLAG_BAD, {"block": block_idx, "position": pos})
        self.markers.emit(M.BLOCK_END, {"block": block_idx})

        self.block_likerts.append({
            "phase": self.phase,
            "block": block_idx,
            "likert": likert,
            "flags_best": sorted(flags_best),
            "flags_bad": sorted(flags_bad),
        })

        if self.phase == "ACQUISITION":
            await self._commit_acquisition_block(likert, flags_best, flags_bad, block_idx)
        else:
            # FEEDBACK / PROBE / PERCEPTION: flush pending trials to log without card update
            for t in self.pending_block_trials:
                t.pop("_cov", None)
                t.pop("_rqa", None)
                self.trial_log.append(t)
            self.pending_block_trials.clear()

        await self.send({
            "type": "block_complete_ack",
            "block": block_idx,
            "card_progress": self._card_progress(),
        })

    async def _commit_acquisition_block(
        self,
        likert: int,
        flags_best: Set[int],
        flags_bad: Set[int],
        block_idx: Any,
    ) -> None:
        cfg = self.config.phases.acquisition
        for t in self.pending_block_trials:
            pos = t.get("position")
            cls = t.get("class")
            eligible = (
                likert >= cfg.block_likert_min
                and pos not in flags_bad
                and not t.get("artifact", False)
            )
            weight = cfg.upweight_flagged_best if pos in flags_best else 1.0

            persistent = dict(t)
            cov = persistent.pop("_cov", None)
            rqa = persistent.pop("_rqa", None)
            persistent["eligible_for_card"] = bool(eligible)
            persistent["card_weight"] = float(weight) if eligible else 0.0
            persistent["block_likert"] = likert
            persistent["flag_best"] = pos in flags_best
            persistent["flag_bad"] = pos in flags_bad
            self.trial_log.append(persistent)

            if eligible and cov is not None and rqa is not None and cls in self.cards:
                self.cards[cls].update(cov, rqa, weight, metadata={
                    "block": block_idx,
                    "position": pos,
                    "likert": likert,
                    "flag_best": pos in flags_best,
                })

        self.pending_block_trials.clear()

        progress = self._card_progress()
        await self.send({"type": "card_progress", "progress": progress})

        threshold = cfg.threshold_high_quality_per_class
        if all(progress[c] >= threshold for c in progress):
            await self.send({
                "type": "acquisition_threshold_met",
                "progress": progress,
                "threshold": threshold,
            })

    async def on_anchor_start(self, msg: Dict[str, Any]) -> None:
        self.markers.emit(M.ANCHOR_START, {"block": msg.get("block")})

    async def on_anchor_image_onset(self, msg: Dict[str, Any]) -> None:
        cls = msg.get("class")
        exemplar_idx = msg.get("exemplar_idx")
        self.markers.emit(M.ANCHOR_IMAGE_ONSET, {"class": cls, "exemplar_idx": exemplar_idx})
        if cls and exemplar_idx is not None and cls in self.config.class_names:
            offset = self.config.class_names.index(cls)
            self.markers.emit(M.exemplar_code(offset, int(exemplar_idx)), {"context": "anchor"})

    async def on_anchor_end(self, msg: Dict[str, Any]) -> None:
        self.markers.emit(M.ANCHOR_END, {})

    # ─── freeze / pause / resume / end ───────────────────────────────

    async def on_freeze_cards(self, msg: Dict[str, Any]) -> None:
        if self.phase != "AWAITING_FREEZE":
            await self.send({
                "type": "error",
                "message": f"can only freeze in AWAITING_FREEZE; current = {self.phase}",
            })
            return

        def _do_freeze():
            summaries: Dict[str, Any] = {}
            errors: Dict[str, str] = {}
            for cls, card in self.cards.items():
                try:
                    summaries[cls] = card.freeze(
                        sigma_method=self.config.card.riemannian_sigma_method,
                    )
                    card.save(self.session_dir / f"card_{cls}.npz")
                except Exception as e:
                    errors[cls] = f"{type(e).__name__}: {e}"
            return summaries, errors

        summaries, errors = await asyncio.to_thread(_do_freeze)
        if errors:
            await self.send({"type": "error", "message": f"card freeze errors: {errors}"})
            return
        self.markers.emit(M.CARD_FROZEN, {"summaries": {k: v.get("n_trials") for k, v in summaries.items()}})
        self.phase = "IDLE"
        await self.send({
            "type": "card_frozen",
            "summaries": summaries,
            "next_phase_suggestion": "FEEDBACK",
        })
        await self._broadcast_phase_change(self.phase)

    async def on_pause(self, msg: Dict[str, Any]) -> None:
        self.markers.emit(M.PAUSE, {})

    async def on_resume(self, msg: Dict[str, Any]) -> None:
        self.markers.emit(M.RESUME, {})

    async def on_end_session(self, msg: Dict[str, Any]) -> None:
        self.markers.emit(M.EXP_END, {})
        await self._save_session_artifacts()
        self.phase = "COMPLETE"
        await self.send({"type": "session_complete", "summary": self._session_summary()})

    # ─── reporting / I/O helpers ──────────────────────────────────────

    def _card_progress(self) -> Dict[str, int]:
        return {cls: card.n_trials for cls, card in self.cards.items()}

    def _session_summary(self) -> Dict[str, Any]:
        probe_trials = [
            t for t in self.trial_log
            if t.get("phase") == "PROBE" and "argmax_class" in t
        ]
        n_probe = len(probe_trials)
        probe_acc = (
            sum(1 for t in probe_trials if t.get("argmax_correct")) / n_probe
            if n_probe else None
        )
        return {
            "session_id": self.session_id,
            "subject_id": self.config.subject.id,
            "phase_at_summary": self.phase,
            "n_trials_logged": len(self.trial_log),
            "n_blocks_logged": len(self.block_likerts),
            "card_progress": self._card_progress(),
            "card_frozen": {cls: card.frozen for cls, card in self.cards.items()},
            "probe_accuracy": probe_acc,
            "n_probe_trials": n_probe,
            "session_started_at_lsl": self.session_started_at,
        }

    async def _save_session_artifacts(self) -> None:
        if self.session_dir is None:
            return
        # trial_log.json
        try:
            with (self.session_dir / "trial_log.json").open("w") as f:
                json.dump(self.trial_log, f, indent=2, default=str)
        except Exception as e:
            print(f"[Session] trial_log save failed: {e}")
        # likerts.csv
        try:
            with (self.session_dir / "likerts.csv").open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["phase", "block", "likert", "flags_best", "flags_bad"])
                for r in self.block_likerts:
                    w.writerow([
                        r["phase"], r["block"], r["likert"],
                        ";".join(map(str, r["flags_best"])),
                        ";".join(map(str, r["flags_bad"])),
                    ])
        except Exception as e:
            print(f"[Session] likerts save failed: {e}")
        # markers.csv
        try:
            self.markers.save_csv(self.session_dir / "markers.csv")
        except Exception as e:
            print(f"[Session] markers save failed: {e}")
        # session_summary.json
        try:
            with (self.session_dir / "session_summary.json").open("w") as f:
                json.dump(self._session_summary(), f, indent=2, default=str)
        except Exception as e:
            print(f"[Session] summary save failed: {e}")