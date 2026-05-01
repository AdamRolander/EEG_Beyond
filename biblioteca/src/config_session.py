"""Session configuration schema.

Loads `config/default.yaml` (or an override file) into a typed, validated
Pydantic v2 model. All other modules accept a `SessionConfig` instance and
read parameters from it — never re-read YAML directly elsewhere.
"""
from pathlib import Path
from typing import Optional, List, Dict, Literal
import yaml
from pydantic import BaseModel, Field, ConfigDict


# ─────────────────────────── Subject ─────────────────────────────────────

class SubjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = "S001"
    notes: str = ""


# ─────────────────────────── EEG ingest ──────────────────────────────────

class EEGConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stream_name_hint: str = ""
    expected_n_channels: int = 16
    expected_sample_rate: Optional[float] = None
    buffer_seconds: int = 30
    simulate: bool = False
    # If set, overrides whatever channel labels the LSL stream reports.
    # Required for ICLabel auto-rejection to work, since the CNN needs
    # 10-20 names (e.g. "O1", "Oz", "Pz") to compute scalp topographies.
    # Length must equal expected_n_channels. Set to null to use stream metadata.
    channel_labels: Optional[List[str]] = None


# ─────────────────────────── Preprocessing ───────────────────────────────

class ICAConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enable: bool = True
    method: str = "picard"
    n_components: Optional[int] = None
    # When False, ICA still runs and is saved, but no auto-rejection is
    # attempted (ICLabel is skipped). Useful for custom montages where
    # standard 10-20 channel positions aren't available — ICLabel was
    # trained on standard positions and can't classify custom layouts.
    auto_label: bool = True
    auto_label_threshold: float = 0.7
    reject_categories: List[str] = Field(default_factory=lambda: [
        "muscle artifact", "eye blink", "heart beat", "line noise", "channel noise",
    ])


class PreprocessingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bandpass_low_hz: float = 1.0
    bandpass_high_hz: float = 40.0
    notch_freqs_hz: List[float] = Field(default_factory=lambda: [60.0])
    car: bool = True
    ica: ICAConfig = Field(default_factory=ICAConfig)
    artifact_pp_threshold_uv: float = 150.0


# ─────────────────────────── Stimuli ─────────────────────────────────────

class ClassConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: int
    audio_file: str
    exemplars: List[str]


# ─────────────────────────── Phases ──────────────────────────────────────

class ICACalibrationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eyes_open_seconds: int = 60
    eyes_closed_seconds: int = 60
    blink_seconds: int = 30
    jaw_clench_seconds: int = 30


class PerceptionBlockConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trials_per_class: int = 30
    trials_per_block: int = 9
    perception_duration_ms: int = 4000
    fixation_duration_ms: int = 1000
    rest_duration_ms: int = 2000


class AcquisitionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trials_per_block: int = 9
    threshold_high_quality_per_class: int = 30
    block_likert_min: int = 4
    exclude_flagged_bad: bool = True
    upweight_flagged_best: float = 2.0
    max_blocks: int = 25


class FeedbackPhaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_blocks: int = 6
    n_trials_per_block: int = 9


class ProbePhaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_blocks: int = 6
    n_trials_per_block: int = 9


class PhasesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ica_calibration: ICACalibrationConfig = Field(default_factory=ICACalibrationConfig)
    perception_block: PerceptionBlockConfig = Field(default_factory=PerceptionBlockConfig)
    acquisition: AcquisitionConfig = Field(default_factory=AcquisitionConfig)
    feedback: FeedbackPhaseConfig = Field(default_factory=FeedbackPhaseConfig)
    probe: ProbePhaseConfig = Field(default_factory=ProbePhaseConfig)


# ─────────────────────────── Trial timing ────────────────────────────────

class TrialTimingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixation_duration_ms: int = 1000
    audio_cue_duration_ms: int = 700
    imagery_duration_ms: int = 4000
    rest_duration_ms: int = 2000


class AnchorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enable: bool = True
    image_duration_ms: int = 2000
    blank_between_ms: int = 500
    rotate_exemplar_index: bool = True


# ─────────────────────────── Card ────────────────────────────────────────

class CardWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    riemannian: float = 0.7
    rqa: float = 0.3
    embedding: float = 0.0


class CardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feature_weights: CardWeights = Field(default_factory=CardWeights)
    riemannian_sigma_method: Literal["median", "mean"] = "median"
    rqa_phase_space_dim: int = 3
    rqa_tau: Optional[int] = None
    rqa_recurrence_threshold_pct: float = 0.1
    imagery_epoch_start_s: float = 0.0
    imagery_epoch_end_s: float = 4.0


# ─────────────────────────── Output ──────────────────────────────────────

class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_root: str = "data"


# ─────────────────────────── Top-level ───────────────────────────────────

class SessionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: SubjectConfig = Field(default_factory=SubjectConfig)
    eeg: EEGConfig = Field(default_factory=EEGConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    classes: Dict[str, ClassConfig]
    phases: PhasesConfig = Field(default_factory=PhasesConfig)
    trial: TrialTimingConfig = Field(default_factory=TrialTimingConfig)
    anchor: AnchorConfig = Field(default_factory=AnchorConfig)
    card: CardConfig = Field(default_factory=CardConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    # ─── Convenience accessors ──────────────────────────────────────────

    @property
    def class_names(self) -> List[str]:
        return list(self.classes.keys())

    @property
    def class_codes(self) -> Dict[str, int]:
        return {name: cfg.code for name, cfg in self.classes.items()}

    def class_by_code(self, code: int) -> Optional[str]:
        for name, cfg in self.classes.items():
            if cfg.code == code:
                return name
        return None

    # ─── I/O ────────────────────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: Path) -> "SessionConfig":
        path = Path(path)
        with path.open() as f:
            raw = yaml.safe_load(f)
        return cls(**raw)

    def to_yaml(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            yaml.safe_dump(self.model_dump(), f, sort_keys=False, default_flow_style=False)


# ─────────────────────────── Smoke test ──────────────────────────────────

if __name__ == "__main__":
    import sys
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "config" / "default.yaml"
    cfg = SessionConfig.from_yaml(cfg_path)
    print(f"Loaded config from {cfg_path}")
    print(f"  Subject: {cfg.subject.id}")
    print(f"  Classes: {cfg.class_names}")
    print(f"  Class codes: {cfg.class_codes}")
    print(f"  Acquisition threshold: {cfg.phases.acquisition.threshold_high_quality_per_class}/class")
    print(f"  Card weights: r={cfg.card.feature_weights.riemannian} "
          f"rqa={cfg.card.feature_weights.rqa} "
          f"emb={cfg.card.feature_weights.embedding}")
    print("OK.")