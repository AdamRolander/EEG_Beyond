// Top-level UI wiring. Owns global state, registers WS handlers,
// and renders the operator panel based on the current phase.

import { CLASSES, BLOCKS } from './config.js';
import { WS } from './websocket.js';
import * as audio from './audio.js';
import * as render from './screen_renderer.js';
import * as feedback from './feedback.js';
import * as experiment from './experiment.js';

const state = {
  ws: null,
  phase: 'IDLE',
  cardProgress: { cat: 0, wrench: 0, house: 0 },
  cardFrozen: { cat: false, wrench: false, house: false },
  thresholdMet: false,
  sessionId: null,
  subjectId: null,
  paused: false,
  busy: false,         // true while a block is mid-run; disables operator buttons
  perceptionBlocksRun: 0,
};

// ─── DOM helpers ──────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

function setStatus(msg) { $('status-text').textContent = msg; }

function updatePhaseDisplay(phase) {
  $('phase-display').textContent = phase;
  state.phase = phase;
  renderOperatorPanel();
}

function updateCardProgress(progress, frozen) {
  if (progress) state.cardProgress = progress;
  if (frozen) state.cardFrozen = frozen;
  const text = CLASSES.map(c => {
    const lock = state.cardFrozen[c] ? '🔒' : '';
    return `${c}: ${state.cardProgress[c] || 0}${lock}`;
  }).join('   ');
  $('card-progress').textContent = text;
}

function makeBtn(label, onClick, opts = {}) {
  const b = document.createElement('button');
  b.textContent = label;
  b.className = 'op-button' + (opts.primary ? ' primary' : '') + (opts.danger ? ' danger' : '');
  b.disabled = state.busy && !opts.alwaysEnabled;
  b.onclick = async (e) => {
    if (b.disabled) return;
    try { await onClick(e); }
    catch (err) { console.error(err); setStatus(`ERROR: ${err.message}`); }
  };
  return b;
}

function addNote(parent, text) {
  const p = document.createElement('p');
  p.className = 'instruction';
  p.textContent = text;
  parent.appendChild(p);
}

// ─── Operator panel rendering — one branch per phase ──────────────

function renderOperatorPanel() {
  const panel = $('operator-panel');
  panel.innerHTML = '';

  // ── Active-block controls ──
  // While a block is running, every other operator button is disabled.
  // Surface pause/resume + abort here so the operator always has them.
  if (state.busy) {
    const wrap = document.createElement('div');
    wrap.className = 'active-block';
    addNote(wrap, state.paused
      ? '⏸ Block paused (between trials). Resume or abort.'
      : 'Block in progress. Spacebar pauses between trials.');

    const pauseBtn = makeBtn(state.paused ? '▶ Resume' : '⏸ Pause', () => {
      state.paused = !state.paused;
      experiment.setPaused(state.paused);
      state.ws.send(state.paused ? 'pause' : 'resume');
      setStatus(state.paused ? '⏸ PAUSED' : 'Resumed.');
      renderOperatorPanel();
    }, { alwaysEnabled: true });
    wrap.appendChild(pauseBtn);

    const abortBtn = makeBtn('✗ Abort current block', () => {
      if (!confirm(
        'Abort the current block? The block will be marked low-quality '
        + '(no eligible trials commit to cards).'
      )) return;
      experiment.setAborted(true);
      state.paused = false;
      experiment.setPaused(false);
      setStatus('Aborting block...');
    }, { alwaysEnabled: true, danger: true });
    wrap.appendChild(abortBtn);

    panel.appendChild(wrap);

    const sep = document.createElement('hr');
    sep.className = 'panel-sep';
    panel.appendChild(sep);
  }

  const f = state.cardFrozen;
  const allFrozen = f.cat && f.wrench && f.house;

  switch (state.phase) {
    case 'IDLE': {
      addNote(panel,
        allFrozen
          ? 'Cards frozen. Run feedback then probe.'
          : 'Run ICA calibration → perception → acquisition → freeze cards.');
      panel.appendChild(makeBtn('1. Start ICA Calibration', () => sendStart('ICA_CAL')));
      panel.appendChild(makeBtn('2. Start Perception', () => sendStart('PERCEPTION')));
      panel.appendChild(makeBtn('3. Start Acquisition', () => sendStart('ACQUISITION')));
      if (allFrozen) {
        panel.appendChild(makeBtn('4. Start Feedback', () => sendStart('FEEDBACK'), { primary: true }));
        panel.appendChild(makeBtn('5. Start Probe', () => sendStart('PROBE'), { primary: true }));
      }
      break;
    }
    case 'ICA_CAL': {
      addNote(panel,
        'Run each substep (~45s while subject performs the action), then Fit ICA, then End Phase.');
      const substeps = [
        ['eyes_open', 'Eyes open, relax'],
        ['eyes_closed', 'Eyes closed, relax'],
        ['blink', 'Blink every 2 seconds'],
        ['jaw', 'Clench jaw 5×'],
      ];
      for (const [id, label] of substeps) {
        const row = document.createElement('div');
        row.className = 'btn-row';
        const startBtn = makeBtn(`Start: ${label}`, () => {
          state.ws.send('ica_substep_start', { substep: id });
          render.showInstruction(label);
        });
        const endBtn = makeBtn(`End`, () => {
          state.ws.send('ica_substep_end', { substep: id });
          render.showInstruction('Rest...');
        });
        row.appendChild(startBtn); row.appendChild(endBtn);
        panel.appendChild(row);
      }
      panel.appendChild(makeBtn('Fit ICA (run on calibration window)', () => {
        render.clearScreen();
        state.ws.send('fit_ica');
      }, { primary: true }));
      panel.appendChild(makeBtn('End ICA Phase →', () => {
        render.clearScreen();
        state.ws.send('end_phase');
      }));
      break;
    }
    case 'PERCEPTION': {
      addNote(panel, `Block ${state.perceptionBlocksRun + 1} of ~${BLOCKS.perception_blocks}.`);
      panel.appendChild(makeBtn('▶ Run Perception Block (9 trials)', async () => {
        await withBusy(async () => {
          await experiment.runPerceptionBlock();
          state.perceptionBlocksRun++;
        });
      }, { primary: true }));
      panel.appendChild(makeBtn('End Perception Phase →', () => state.ws.send('end_phase')));
      break;
    }
    case 'ACQUISITION': {
      const minProg = Math.min(...CLASSES.map(c => state.cardProgress[c] || 0));
      addNote(panel, state.thresholdMet
        ? `✓ Threshold met (min ${minProg}/class). Run more to strengthen, or End → Freeze.`
        : `Min progress: ${minProg}/${BLOCKS.acquisition_threshold_per_class} per class.`);
      panel.appendChild(makeBtn('▶ Run Acquisition Block (anchor + 9 trials)', async () => {
        await withBusy(() => experiment.runImageryBlock('ACQUISITION'));
      }, { primary: true }));
      panel.appendChild(makeBtn('End Acquisition → AWAITING_FREEZE', () => state.ws.send('end_phase')));
      break;
    }
    case 'AWAITING_FREEZE': {
      addNote(panel, 'Cards are about to be frozen. This is irreversible for the session.');
      panel.appendChild(makeBtn('🔒 Freeze Cards', () => state.ws.send('freeze_cards'), { primary: true }));
      panel.appendChild(makeBtn('Back to Acquisition', () => sendStart('ACQUISITION')));
      break;
    }
    case 'FEEDBACK': {
      addNote(panel, 'Subject sees per-class similarity bars during rest. Watch for ceiling effects.');
      panel.appendChild(makeBtn('▶ Run Feedback Block', async () => {
        await withBusy(() => experiment.runImageryBlock('FEEDBACK'));
      }, { primary: true }));
      panel.appendChild(makeBtn('End Feedback Phase →', () => state.ws.send('end_phase')));
      break;
    }
    case 'PROBE': {
      addNote(panel, 'No bars shown — this is the headline H1 measurement.');
      panel.appendChild(makeBtn('▶ Run Probe Block', async () => {
        await withBusy(() => experiment.runImageryBlock('PROBE'));
      }, { primary: true }));
      panel.appendChild(makeBtn('End Probe Phase →', () => state.ws.send('end_phase')));
      break;
    }
    case 'COMPLETE': {
      addNote(panel, 'Session complete. Reload the page to start a new session.');
      break;
    }
    default:
      addNote(panel, `Unknown phase: ${state.phase}`);
  }
}

async function withBusy(fn) {
  state.busy = true;
  renderOperatorPanel();
  try { await fn(); }
  finally {
    state.busy = false;
    renderOperatorPanel();
  }
}

function sendStart(phase) { state.ws.send('start_phase', { phase }); }

// ─── Bootstrap ────────────────────────────────────────────────────

async function init() {
  setStatus('Loading audio...');
  await audio.preloadAudio();

  setStatus('Connecting...');
  state.ws = new WS();
  experiment.setWS(state.ws);

  // ── server → client handlers ──
  state.ws.on('session_ready', (m) => {
    state.sessionId = m.session_id;
    state.subjectId = m.subject_id;
    setStatus(`Connected · subject ${m.subject_id} · session ${m.session_id}`);
    $('eeg-status').textContent =
      `EEG: ${m.eeg.n_channels}ch @ ${m.eeg.sample_rate}Hz${m.eeg.simulated ? ' (sim)' : ''}`;
    updatePhaseDisplay(m.phase);
  });

  state.ws.on('phase_change', (m) => {
    updatePhaseDisplay(m.phase);
    updateCardProgress(m.card_progress, m.card_frozen);
  });

  state.ws.on('ica_progress', (m) => setStatus(`ICA: ${m.status} (${m.duration_s?.toFixed(1) || '?'}s)`));

  state.ws.on('ica_complete', (m) => {
    if (m.skipped) { setStatus('ICA skipped (disabled in config)'); return; }
    setStatus(`ICA done — rejected ${m.n_rejected} / ${m.n_components} components`);
    console.log('[ICA] labels:', m.labels);
    console.log('[ICA] confidences:', m.confidences);
  });

  state.ws.on('trial_processed', (m) => {
    if (m.artifact) {
      console.warn(`[trial ${m.trial_id}] artifact, p2p ${m.peak_to_peak_uv?.toFixed(1)} µV`);
    }
  });

  state.ws.on('trial_failed', (m) => {
    console.error('[trial failed]', m.reason);
    setStatus(`Trial failed: ${m.reason}`);
  });

  state.ws.on('trial_score', (m) => {
    feedback.updateBars(m.scores);
  });

  state.ws.on('block_complete_ack', (m) => {
    updateCardProgress(m.card_progress, null);
  });

  state.ws.on('card_progress', (m) => {
    updateCardProgress(m.progress, null);
  });

  state.ws.on('acquisition_threshold_met', (m) => {
    state.thresholdMet = true;
    setStatus(`✓ Acquisition threshold met (≥${m.threshold}/class).`);
    renderOperatorPanel();
  });

  state.ws.on('card_frozen', (m) => {
    setStatus('Cards frozen. Ready for Feedback.');
    state.cardFrozen = { cat: true, wrench: true, house: true };
    updateCardProgress(state.cardProgress, state.cardFrozen);
    console.log('[cards frozen] summaries:', m.summaries);
  });

  state.ws.on('session_complete', (m) => {
    const acc = m.summary.probe_accuracy;
    setStatus(`Session complete · probe acc = ${acc !== null ? acc.toFixed(3) : 'N/A'} (n=${m.summary.n_probe_trials})`);
    console.log('[session summary]', m.summary);
  });

  state.ws.on('status', (m) => console.log('[status]', m));
  state.ws.on('error', (m) => {
    console.error('[server error]', m.message);
    setStatus(`ERROR: ${m.message}`);
  });

  state.ws.onClose(() => {
    setStatus('Disconnected.');
  });

  await state.ws.connect();

  // End session
  $('btn-end-session').onclick = () => {
    if (confirm('End the session? This will save all artifacts and freeze the experiment.')) {
      state.ws.send('end_session');
    }
  };

  // Spacebar = pause/resume during a block
  document.addEventListener('keydown', (e) => {
    if (e.code !== 'Space') return;
    if (document.activeElement && ['INPUT', 'BUTTON', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
    e.preventDefault();
    if (!state.busy) return;  // pause is meaningless outside an active block
    state.paused = !state.paused;
    experiment.setPaused(state.paused);
    state.ws.send(state.paused ? 'pause' : 'resume');
    setStatus(state.paused ? '⏸ PAUSED (spacebar to resume)' : 'Resumed.');
    renderOperatorPanel();
  });
}

init().catch(e => {
  console.error('Init failed:', e);
  setStatus(`Init failed: ${e.message}`);
});