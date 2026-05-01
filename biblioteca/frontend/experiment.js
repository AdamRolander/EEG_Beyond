// Experiment orchestration. Browser drives all trial timing; the server
// emits the corresponding LSL markers based on the WebSocket messages
// emitted here. Each trial-event WS message corresponds 1:1 to one LSL
// marker, timestamped via pylsl.local_clock() at the server.

import { CLASSES, TIMING, ASSETS, N_EXEMPLARS_PER_CLASS, BLOCKS } from './config.js';
import * as render from './screen_renderer.js';
import * as audio from './audio.js';
import * as feedback from './feedback.js';
import { showLikert } from './likert.js';

let ws = null;
let paused = false;
let aborted = false;
let blockCounter = 0;

export function setWS(w) { ws = w; }
export function setPaused(p) { paused = p; }
export function setAborted(v) { aborted = v; }
export function getBlockCounter() { return blockCounter; }
export function resetBlockCounter() { blockCounter = 0; }

export class AbortBlock extends Error {
  constructor() { super('block aborted'); this.name = 'AbortBlock'; }
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function pauseGate() {
  while (paused) {
    if (aborted) { aborted = false; paused = false; throw new AbortBlock(); }
    await sleep(100);
  }
  if (aborted) { aborted = false; throw new AbortBlock(); }
}

// One block of 9 trials (3 per class), shuffled.
function makeBlockTrials(perClass = BLOCKS.trials_per_class_per_block) {
  const trials = [];
  for (const cls of CLASSES) {
    for (let i = 0; i < perClass; i++) {
      trials.push({
        cls,
        exemplar_idx: Math.floor(Math.random() * N_EXEMPLARS_PER_CLASS),
      });
    }
  }
  // Fisher-Yates shuffle
  for (let i = trials.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [trials[i], trials[j]] = [trials[j], trials[i]];
  }
  return trials;
}

// ─── Anchor sequence ──────────────────────────────────────────────
// Rotates through cat/wrench/house exemplars with audio cues.
// Used at the start of acquisition / feedback / probe blocks to
// reground the subject in the three categories.

async function runAnchor(blockIdx) {
  ws.send('anchor_start', { block: blockIdx });

  for (let pass = 0; pass < TIMING.anchor_passes; pass++) {
    for (const cls of CLASSES) {
      await pauseGate();
      const exemplar_idx = Math.floor(Math.random() * N_EXEMPLARS_PER_CLASS);
      const src = ASSETS.imagePath(cls, exemplar_idx);
      await render.preloadImage(src);
      render.showImage(src);
      ws.send('anchor_image_onset', { class: cls, exemplar_idx });

      // Play audio cue while image is on; whichever is longer wins
      const audioP = audio.play(cls, TIMING.anchor_per_item_ms);
      const minVisibleP = sleep(TIMING.anchor_per_item_ms);
      await Promise.all([audioP, minVisibleP]);
    }
  }

  ws.send('anchor_end');
  render.showBlank();
  await sleep(500);
}

// ─── Single trials ────────────────────────────────────────────────

async function runImageryTrial(phase, blockIdx, position, trial) {
  await pauseGate();

  ws.send('trial_start', {
    phase, block: blockIdx, position,
    class: trial.cls,
    exemplar_idx: trial.exemplar_idx,
  });

  // 1) Fixation (pre-cue)
  render.showFixation();
  ws.send('fixation_onset');
  await sleep(TIMING.fixation);

  // 2) Audio cue (fixation stays on)
  ws.send('audio_cue_onset', { class: trial.cls });
  await audio.play(trial.cls, TIMING.audio_cue);

  // 3) Imagery — fixation cross still visible
  ws.send('trial_imagery_onset', { class: trial.cls });
  await sleep(TIMING.imagery);
  ws.send('trial_imagery_offset');

  // 4) Rest. In FEEDBACK: show bars during rest so subject sees the score.
  if (phase === 'FEEDBACK') {
    feedback.highlightCued(trial.cls);
    render.showFeedback();
  } else {
    render.showBlank();
  }
  ws.send('rest_onset');
  await sleep(TIMING.rest);

  ws.send('trial_complete');
}

async function runPerceptionTrial(blockIdx, position, trial) {
  await pauseGate();

  ws.send('trial_start', {
    phase: 'PERCEPTION',
    block: blockIdx, position,
    class: trial.cls,
    exemplar_idx: trial.exemplar_idx,
  });

  render.showFixation();
  ws.send('fixation_onset');
  await sleep(TIMING.fixation);

  // Image presentation IS the cue in perception trials (no audio)
  const src = ASSETS.imagePath(trial.cls, trial.exemplar_idx);
  await render.preloadImage(src);
  render.showImage(src);
  ws.send('perception_onset', { class: trial.cls, exemplar_idx: trial.exemplar_idx });
  await sleep(TIMING.perception);
  ws.send('perception_offset');

  render.showBlank();
  ws.send('rest_onset');
  await sleep(TIMING.rest);

  ws.send('trial_complete');
}

// ─── Blocks ───────────────────────────────────────────────────────

// Imagery block (acquisition / feedback / probe): anchor + 9 trials + likert
export async function runImageryBlock(phase) {
  const blockIdx = blockCounter++;
  ws.send('block_start', { block: blockIdx });

  let trials;
  try {
    await runAnchor(blockIdx);

    trials = makeBlockTrials();

    if (phase === 'FEEDBACK') feedback.resetBars();

    for (let i = 0; i < trials.length; i++) {
      await runImageryTrial(phase, blockIdx, i, trials[i]);
    }
  } catch (e) {
    if (e instanceof AbortBlock) {
      // Aborted mid-block: clean the screen, mark every position as bad
      // and submit likert=1 so no eligible trial reaches the cards.
      if (phase === 'FEEDBACK') feedback.clearHighlight();
      render.clearScreen();
      const allPositions = trials ? trials.map((_, i) => i) : [];
      ws.send('block_complete', {
        block: blockIdx, likert: 1,
        flags_best: [], flags_bad: allPositions,
      });
      return { blockIdx, aborted: true };
    }
    throw e;
  }

  if (phase === 'FEEDBACK') feedback.clearHighlight();
  render.clearScreen();

  // Likert + flags
  const result = await showLikert(blockIdx, trials);
  ws.send('block_complete', {
    block: blockIdx,
    likert: result.likert,
    flags_best: result.flagsBest,
    flags_bad: result.flagsBad,
  });

  return { blockIdx, ...result };
}

// Perception block: 9 trials, no anchor, no audio, no likert/flags
export async function runPerceptionBlock() {
  const blockIdx = blockCounter++;
  ws.send('block_start', { block: blockIdx });

  let trials;
  try {
    trials = makeBlockTrials();
    for (let i = 0; i < trials.length; i++) {
      await runPerceptionTrial(blockIdx, i, trials[i]);
    }
  } catch (e) {
    if (e instanceof AbortBlock) {
      render.clearScreen();
      ws.send('block_complete', {
        block: blockIdx, likert: 1, flags_best: [], flags_bad: [],
      });
      return { blockIdx, aborted: true };
    }
    throw e;
  }

  render.clearScreen();

  // V1: skip likert for perception. Send dummy block_complete with neutral
  // likert so the server's eligibility logic (which only fires in
  // ACQUISITION) has a complete record.
  ws.send('block_complete', {
    block: blockIdx,
    likert: 5,
    flags_best: [],
    flags_bad: [],
  });

  return { blockIdx };
}