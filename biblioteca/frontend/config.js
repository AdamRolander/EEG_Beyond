// Frontend constants. Mirrors src/markers.py and config/default.yaml.
// IMPORTANT: when src/markers.py changes, update MARKERS below to match.

export const MARKERS = {
  EXP_START: 90, EXP_END: 91, CARD_FROZEN: 92,
  PHASE_ICA_CAL_START: 80, PHASE_ICA_CAL_END: 81,
  PHASE_PERCEPTION_START: 82, PHASE_PERCEPTION_END: 83,
  PHASE_ACQUISITION_START: 84, PHASE_ACQUISITION_END: 85,
  PHASE_FEEDBACK_START: 86, PHASE_FEEDBACK_END: 87,
  PHASE_PROBE_START: 88, PHASE_PROBE_END: 89,
  ICA_CAL_EYES_OPEN: 75, ICA_CAL_EYES_CLOSED: 76,
  ICA_CAL_BLINK: 77, ICA_CAL_JAW: 78,
  BLOCK_START: 30, BLOCK_END: 31,
  ANCHOR_START: 32, ANCHOR_IMAGE_ONSET: 33, ANCHOR_END: 34,
  TRIAL_START: 1, TRIAL_END: 2,
  FIXATION_ONSET: 10, AUDIO_CUE_ONSET: 11,
  PERCEPTION_ONSET: 12, PERCEPTION_OFFSET: 13,
  IMAGERY_ONSET: 14, IMAGERY_OFFSET: 15, REST_ONSET: 16,
  LIKERT_BASE: 50, TRIAL_FLAG_BEST: 70, TRIAL_FLAG_BAD: 71,
  CLASS_CAT: 100, CLASS_WRENCH: 101, CLASS_HOUSE: 102,
  EXEMPLAR_BASE: 200,
  PAUSE: 60, RESUME: 61,
};

// Class definitions — must match config/default.yaml subject.classes
export const CLASSES = ['cat', 'wrench', 'house'];

export const CLASS_CODES = {
  cat: 100,
  wrench: 101,
  house: 102,
};

export const N_EXEMPLARS_PER_CLASS = 5;

// Asset paths — referenced by /assets static mount in server.py
export const ASSETS = {
  imagePath: (cls, idx) => `/assets/images/${cls}/${idx + 1}.png`,
  audioPath: (cls) => `/assets/audio/${cls}.mp3`,
};

// Trial timing in milliseconds. Mirror values in config/default.yaml.
// IMPORTANT: `perception` here MUST match phases.perception_block.perception_duration_ms
// in the YAML config — the server extracts that many seconds of EEG starting at
// perception_onset, so a shorter image presentation yields a "epoch extraction failed"
// error when trial_complete arrives before the buffer has caught up.
export const TIMING = {
  fixation: 500,            // pre-cue fixation -- og 1000
  audio_cue: 800,            // upper-bound; we wait for actual `ended` event
  imagery: 3000,             // imagery window length -- og 4000
  rest: 2000,                // inter-trial rest
  perception: 600,          // duration of image presentation in PERCEPTION phase -- og 4000
  anchor_per_item_ms: 600,   // duration of each rotating exemplar in anchor
  anchor_passes: 4,          // number of full cat→wrench→house cycles in an anchor
};

// Block / phase parameters. Mirror config/default.yaml phases.* sections.
export const BLOCKS = {
  trials_per_block: 9,                // 3 per class
  trials_per_class_per_block: 3,
  perception_blocks: 10,              // 30 trials/class total over 10 blocks
  acquisition_threshold_per_class: 30, // operator can run more if desired
};

// WebSocket URL. Connects to the FastAPI /ws endpoint.
export const WS_URL = `ws://${location.host}/ws`;