// ─── Configuration ───────────────────────────────────────────
// Stimuli are loaded from the assets/ folder as GLB files.
// Each entry maps a key to its display name, GLB filename, and marker code.
const CONFIG = {
  // Stimulus classes — edit this to change what's available
  stimuli: {
    BANANA:     { name: 'Banana',     file: 'banana.glb',     code: 100 },
    STRAWBERRY: { name: 'Strawberry', file: 'strawberry.glb', code: 101 },
    CUBE:       { name: 'Cube',       file: 'cube.glb',       code: 102 }
  },

  // LSL marker codes — be verbose, we can always trim in post-processing
  markers: {
    // Session
    EXP_START:          90,
    EXP_END:            91,

    // Trial structure
    TRIAL_START:         1,
    TRIAL_END:           2,

    // Phase onsets
    FIXATION_ONSET:     10,
    PERCEPTION_ONSET:   11,
    MASK_ONSET:         12,
    IMAGERY_CUE:        13,   // audio cue plays
    IMAGERY_ONSET:      14,   // actual imagery recording starts (after delay)
    IMAGERY_OFFSET:     15,
    REST_ONSET:         16,

    // Stimulus identity — sent alongside PERCEPTION_ONSET & IMAGERY_ONSET
    // (these come from stimuli[key].code above: 100, 101, 102)

    // Breaks & ratings
    BREAK_START:        40,
    BREAK_END:          41,
    LIKERT_BASE:        50,   // 50 + rating value

    // Control
    PAUSE:              60,
    RESUME:             61
  },

  // Rendering
  rendering: {
    neutralGray:      0x808080,
    maskColor:        null,   // null = generated noise texture
    imageryColor:     0x000000,
    shapeScale:       0.8,
    vrDistance:        4.0,
    ambientLight:     0.5,
    directionalLight: 0.7,
    cameraFOV:        50
  },

  // Default timing (ms) — matches the research protocol
  defaults: {
    fixationDuration:    3000,
    perceptionDuration:  4000,
    maskDuration:        2000,
    imageryDuration:     4000,
    restDuration:        4000,
    imageryCueDelay:      500,  // delay between audio cue and imagery "recording"
    repetitions:           40,
    trialsUntilBreak:      10
  }
};