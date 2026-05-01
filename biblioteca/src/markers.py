"""LSL marker code definitions.

Every value here gets mirrored in `frontend/config.js`. Do not duplicate
constants outside these two files. Any new event must be added to both.
"""

# ─── Session lifecycle ────────────────────────────────────────────
EXP_START               = 90
EXP_END                 = 91
CARD_FROZEN             = 92

# ─── Phase boundaries ─────────────────────────────────────────────
PHASE_ICA_CAL_START     = 80
PHASE_ICA_CAL_END       = 81
PHASE_PERCEPTION_START  = 82
PHASE_PERCEPTION_END    = 83
PHASE_ACQUISITION_START = 84
PHASE_ACQUISITION_END   = 85
PHASE_FEEDBACK_START    = 86
PHASE_FEEDBACK_END      = 87
PHASE_PROBE_START       = 88
PHASE_PROBE_END         = 89

# ─── ICA calibration substeps ─────────────────────────────────────
ICA_CAL_EYES_OPEN       = 75
ICA_CAL_EYES_CLOSED     = 76
ICA_CAL_BLINK           = 77
ICA_CAL_JAW             = 78

# ─── Block / anchor ───────────────────────────────────────────────
BLOCK_START             = 30
BLOCK_END               = 31
ANCHOR_START            = 32
ANCHOR_IMAGE_ONSET      = 33
ANCHOR_END              = 34

# ─── Trial events ─────────────────────────────────────────────────
TRIAL_START             = 1
TRIAL_END               = 2
FIXATION_ONSET          = 10
AUDIO_CUE_ONSET         = 11
PERCEPTION_ONSET        = 12
PERCEPTION_OFFSET       = 13
IMAGERY_ONSET           = 14
IMAGERY_OFFSET          = 15
REST_ONSET              = 16

# ─── Subject responses ────────────────────────────────────────────
LIKERT_BASE             = 50    # +1..+5 → 51..55
TRIAL_FLAG_BEST         = 70
TRIAL_FLAG_BAD          = 71

# ─── Class identity ───────────────────────────────────────────────
CLASS_CAT               = 100
CLASS_WRENCH            = 101
CLASS_HOUSE             = 102

# ─── Exemplar identity ────────────────────────────────────────────
# code = EXEMPLAR_BASE + (class_offset * 10) + exemplar_idx
# cat:    200..204
# wrench: 210..214
# house:  220..224
EXEMPLAR_BASE           = 200

# ─── Control ──────────────────────────────────────────────────────
PAUSE                   = 60
RESUME                  = 61


# ─── Helper functions ─────────────────────────────────────────────

def exemplar_code(class_offset: int, exemplar_idx: int) -> int:
    """Compute the marker code for a (class, exemplar) pair.

    `class_offset` is the index of the class in the configured class list
    (cat=0, wrench=1, house=2 for default config).
    """
    return EXEMPLAR_BASE + class_offset * 10 + int(exemplar_idx)


def likert_code(value: int) -> int:
    """Marker code for a likert rating value 1..5."""
    if not (1 <= value <= 5):
        raise ValueError(f"likert value must be 1..5, got {value}")
    return LIKERT_BASE + value