// ─── Main UI Controller ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  let selectedLikert = null;

  // ── DOM refs ───────────────────────────────────────────────
  const connectBtn    = document.getElementById('connect-btn');
  const startBtn      = document.getElementById('start-btn');
  const enterVrBtn    = document.getElementById('enter-vr-btn');
  const cancelVrBtn   = document.getElementById('cancel-vr-btn');
  const pauseBtn      = document.getElementById('pause-btn');
  const stopBtn       = document.getElementById('stop-btn');
  const continueBtn   = document.getElementById('continue-btn');
  const restartBtn    = document.getElementById('restart-btn');
  const downloadBtn   = document.getElementById('download-csv-btn');

  const configPanel     = document.getElementById('config-panel');
  const vrPanel         = document.getElementById('vr-panel');
  const experimentPanel = document.getElementById('experiment-panel');
  const breakPanel      = document.getElementById('break-panel');
  const completePanel   = document.getElementById('complete-panel');

  const stimDisplay     = document.getElementById('stimulus-display');

  // 2D overlay elements (created dynamically for browser mode)
  let overlay2D = null;

  // ── Panel management ───────────────────────────────────────
  function showPanel(id) {
    [configPanel, vrPanel, experimentPanel, breakPanel, completePanel].forEach(p =>
      p.classList.add('hidden')
    );
    document.getElementById(id + '-panel').classList.remove('hidden');
  }

  // ── Populate stimulus checkboxes from CONFIG ───────────────
  function populateStimuli() {
    const container = document.getElementById('stimuli-container');
    container.innerHTML = Object.entries(CONFIG.stimuli).map(([key, cfg]) => `
      <label class="stimulus-chip selected">
        <input type="checkbox" value="${key}" checked style="display:none;">
        <span>${cfg.name}</span>
      </label>
    `).join('');

    container.querySelectorAll('.stimulus-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const cb = chip.querySelector('input');
        cb.checked = !cb.checked;
        chip.classList.toggle('selected', cb.checked);
        updateSummary();
      });
    });
  }

  function getSelectedStimuli() {
    const cbs = document.querySelectorAll('#stimuli-container input:checked');
    return Array.from(cbs).map(cb => cb.value);
  }

  // ── Summary ────────────────────────────────────────────────
  function updateSummary() {
    const selected = getSelectedStimuli();
    const reps = parseInt(document.getElementById('repetitions').value) || 0;
    const total = selected.length * reps;
    document.getElementById('total-trials').textContent = total;

    // Total time per trial
    const fix  = parseInt(document.getElementById('fixation-duration').value) || 0;
    const perc = parseInt(document.getElementById('perception-duration').value) || 0;
    const mask = parseInt(document.getElementById('mask-duration').value) || 0;
    const img  = parseInt(document.getElementById('imagery-duration').value) || 0;
    const rest = parseInt(document.getElementById('rest-duration').value) || 0;
    const delay = parseInt(document.getElementById('imagery-cue-delay').value) || 0;

    const trialMs = fix + perc + mask + delay + img + rest;
    const totalMin = Math.ceil((total * trialMs) / 60000);
    document.getElementById('estimated-duration').textContent = totalMin;
  }

  // ── Option toggles ────────────────────────────────────────
  document.getElementById('enable-likert').addEventListener('change', function () {
    document.getElementById('likert-scale-row').style.display = this.checked ? 'flex' : 'none';
  });

  document.getElementById('enable-audio-cue').addEventListener('change', function () {
    document.getElementById('audio-cue-type-row').style.display = this.checked ? 'flex' : 'none';
  });

  // Update summary when any timing input changes
  ['fixation-duration', 'perception-duration', 'mask-duration',
   'imagery-duration', 'rest-duration', 'imagery-cue-delay', 'repetitions'].forEach(id => {
    document.getElementById(id).addEventListener('change', updateSummary);
  });

  // ── LSL Connection ────────────────────────────────────────
  connectBtn.addEventListener('click', async function () {
    const url = document.getElementById('bridge-url').value;
    connectBtn.disabled = true;
    connectBtn.textContent = 'CONNECTING...';

    try {
      await lslBridge.connect(url);
      startBtn.disabled = false;
      startBtn.textContent = 'START EXPERIMENT';
      connectBtn.textContent = 'CONNECTED ✓';
    } catch (e) {
      alert('Failed to connect: ' + e.message);
      connectBtn.disabled = false;
      connectBtn.textContent = 'CONNECT TO LSL BRIDGE';
    }
  });

  lslBridge.onStatusChange = (connected) => {
    const pill = document.getElementById('connection-status');
    pill.textContent = connected ? 'ONLINE' : 'OFFLINE';
    pill.className = 'status-pill ' + (connected ? 'online' : 'offline');
    if (!connected) {
      startBtn.disabled = true;
      startBtn.textContent = 'CONNECT TO LSL BRIDGE FIRST';
    }
  };

  // ── Start Experiment ──────────────────────────────────────
  startBtn.addEventListener('click', async function () {
    const selected = getSelectedStimuli();
    if (selected.length === 0) {
      alert('Select at least one stimulus');
      return;
    }

    const config = {
      fixationDuration:   parseInt(document.getElementById('fixation-duration').value),
      perceptionDuration: parseInt(document.getElementById('perception-duration').value),
      maskDuration:       parseInt(document.getElementById('mask-duration').value),
      imageryDuration:    parseInt(document.getElementById('imagery-duration').value),
      restDuration:       parseInt(document.getElementById('rest-duration').value),
      imageryCueDelay:    parseInt(document.getElementById('imagery-cue-delay').value),
      repetitions:        parseInt(document.getElementById('repetitions').value),
      trialsUntilBreak:   parseInt(document.getElementById('trials-until-break').value),
      enabledStimuli:     selected,
      randomize:          document.getElementById('randomize-order').checked,
      enableLikert:       document.getElementById('enable-likert').checked,
      likertScale:        parseInt(document.getElementById('likert-scale').value),
      enableAudioCue:     document.getElementById('enable-audio-cue').checked,
      audioCueType:       document.getElementById('audio-cue-type').value
    };

    const mode = document.querySelector('input[name="display-mode"]:checked').value;

    experiment.initialize(config);

    // Preload audio cues
    if (config.enableAudioCue && config.audioCueType === 'name') {
      await AudioCues.preloadAll();
    }

    // Preload 3D models
    await StimulusFactory.preloadModels();

    if (mode === 'vr') {
      // Show VR ready panel
      initRenderer('vr');
      showPanel('vr');
    } else {
      // Browser mode — go straight to experiment
      initRenderer('browser');
      showPanel('experiment');
      startExperiment();
    }
  });

  function initRenderer(mode) {
    // Remove old container if any
    document.getElementById('vr-container')?.remove();

    const container = document.createElement('div');
    container.id = 'vr-container';
    container.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;';
    document.body.appendChild(container);

    vrRenderer.init(container, mode);

    // Create 2D overlay for browser mode (phase text on screen)
    if (mode === 'browser') {
      create2DOverlay(container);
    }
  }

  function create2DOverlay(container) {
    overlay2D = document.createElement('div');
    overlay2D.id = 'overlay-2d';
    overlay2D.style.cssText = `
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      z-index: 1; display: flex; align-items: center; justify-content: center;
      pointer-events: none; font-family: 'Space Mono', monospace;
      color: white; font-size: 3rem; text-align: center;
    `;
    container.appendChild(overlay2D);
  }

  function update2DOverlay(text, color) {
    if (overlay2D) {
      overlay2D.textContent = text || '';
      if (color) overlay2D.style.color = color;
    }
  }

  function startExperiment() {
    wireExperimentCallbacks();
    vrRenderer.startRenderLoop();
    experiment.start();
  }

  // ── VR Panel ──────────────────────────────────────────────
  enterVrBtn.addEventListener('click', async function () {
    try {
      await vrRenderer.enterVR();
      showPanel('experiment');
      startExperiment();
    } catch (e) {
      alert('Failed to enter VR: ' + e.message);
    }
  });

  cancelVrBtn.addEventListener('click', function () {
    vrRenderer.dispose();
    document.getElementById('vr-container')?.remove();
    showPanel('config');
  });

  // ── Experiment callbacks ──────────────────────────────────
  function wireExperimentCallbacks() {
    experiment.onStateChange = (state) => {
      if (state === 'BREAK') showPanel('break');
      else if (state === 'COMPLETE') {
        // Exit fullscreen in browser mode
        if (document.fullscreenElement) document.exitFullscreen();
        showPanel('complete');
      }
    };

    experiment.onTrialStart = (current, total) => {
      document.getElementById('progress-text').textContent = `${current} / ${total}`;
      const pct = (current / total) * 100;
      document.getElementById('progress-fill').style.width = pct + '%';
    };

    experiment.onPhaseChange = (phase, stimulus) => {
      document.getElementById('phase-indicator').textContent = phase;
      document.getElementById('current-stimulus').textContent = stimulus || '—';

      // Update 2D overlay for browser mode
      switch (phase) {
        case 'FIXATION':
          update2DOverlay('＋', '#ffffff');
          break;
        case 'PERCEPTION':
          update2DOverlay('', ''); // 3D object visible
          break;
        case 'MASK':
          update2DOverlay('', '');
          break;
        case 'IMAGERY':
          update2DOverlay('', '');
          break;
        case 'REST':
          update2DOverlay('Rest', '#999999');
          break;
        default:
          update2DOverlay('', '');
      }
    };

    experiment.onBreakStart = (completed, total) => {
      document.getElementById('break-progress').innerHTML =
        `COMPLETED: <span>${completed}</span> / <span>${total}</span> TRIALS`;
      buildLikertScale();
      showPanel('break');

      // Also update 2D overlay
      update2DOverlay('BREAK', '#D5A84C');
    };

    experiment.onComplete = (data) => {
      document.getElementById('session-id').textContent = data.sessionId;
      document.getElementById('completed-trials').textContent = data.totalTrials;
      document.getElementById('markers-sent').textContent = data.markersSent;
      showPanel('complete');

      // Auto-download CSV if there are ratings
      if (data.likertRecords?.length > 0) {
        exportLikertCSV(data.sessionId, data.likertRecords);
      }
    };
  }

  // ── Pause / Stop ──────────────────────────────────────────
  pauseBtn.addEventListener('click', function () {
    if (experiment.state === 'PAUSED') {
      experiment.resume();
      pauseBtn.textContent = 'PAUSE (SPACE)';
    } else {
      experiment.pause();
      pauseBtn.textContent = 'RESUME (SPACE)';
    }
  });

  stopBtn.addEventListener('click', function () {
    experiment.stop();
    cleanupDisplay();
    showPanel('config');
  });

  // ── Break / Likert ────────────────────────────────────────
  function buildLikertScale() {
    const scale = parseInt(document.getElementById('likert-scale').value);
    const enableLikert = document.getElementById('enable-likert').checked;
    const container = document.getElementById('likert-options');
    document.getElementById('likert-max').textContent = scale;

    if (!enableLikert) {
      document.getElementById('likert-container').classList.add('hidden');
      continueBtn.disabled = false;
      continueBtn.textContent = 'CONTINUE';
      selectedLikert = null;
      return;
    }

    document.getElementById('likert-container').classList.remove('hidden');
    container.innerHTML = '';

    for (let i = 1; i <= scale; i++) {
      const opt = document.createElement('div');
      opt.className = 'likert-option';
      opt.dataset.value = i;
      opt.textContent = i;
      opt.addEventListener('click', function () {
        container.querySelectorAll('.likert-option').forEach(o => o.classList.remove('selected'));
        this.classList.add('selected');
        selectedLikert = parseInt(this.dataset.value);
        continueBtn.disabled = false;
        continueBtn.textContent = 'CONTINUE';
      });
      container.appendChild(opt);
    }

    selectedLikert = null;
    continueBtn.disabled = true;
    continueBtn.textContent = 'SELECT RATING TO CONTINUE';
  }

  continueBtn.addEventListener('click', function () {
    experiment.resumeFromBreak(selectedLikert);
    showPanel('experiment');
    update2DOverlay('', '');
  });

  // ── Complete / Restart ────────────────────────────────────
  restartBtn.addEventListener('click', function () {
    cleanupDisplay();
    showPanel('config');
  });

  downloadBtn.addEventListener('click', function () {
    if (experiment.likertRecords?.length > 0) {
      exportLikertCSV(experiment.sessionId, experiment.likertRecords);
    }
  });

  function cleanupDisplay() {
    vrRenderer.dispose();
    document.getElementById('vr-container')?.remove();
    overlay2D = null;
    if (document.fullscreenElement) document.exitFullscreen();
  }

  // ── CSV Export ─────────────────────────────────────────────
  function escapeCSV(val) {
    const s = String(val == null ? '' : val);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function exportLikertCSV(sessionId, records) {
    const headers = ['Session ID', 'Trial Index', 'Timestamp', 'Rating'];
    const rows = records.map(r => [
      escapeCSV(r.sessionId),
      escapeCSV(r.trialIndex),
      escapeCSV(r.timestamp),
      escapeCSV(r.rating)
    ].join(','));
    const csv = '\uFEFF' + [headers.join(','), ...rows].join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `likert_${sessionId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Keyboard Controls ─────────────────────────────────────
  document.addEventListener('keydown', function (e) {
    if (e.code === 'Escape') {
      e.preventDefault();
      if (experiment.state === 'RUNNING' || experiment.state === 'PAUSED') {
        experiment.stop();
        cleanupDisplay();
        showPanel('config');
      }
    }

    if (e.code === 'Space') {
      e.preventDefault();
      if (experiment.state === 'RUNNING') {
        experiment.pause();
        pauseBtn.textContent = 'RESUME (SPACE)';
      } else if (experiment.state === 'PAUSED') {
        experiment.resume();
        pauseBtn.textContent = 'PAUSE (SPACE)';
      } else if (experiment.state === 'BREAK') {
        const enableLikert = document.getElementById('enable-likert').checked;
        if (selectedLikert !== null || !enableLikert) {
          experiment.resumeFromBreak(selectedLikert);
          showPanel('experiment');
          update2DOverlay('', '');
        }
      }
    }

    // Fullscreen toggle with F key (browser mode)
    if (e.code === 'KeyF' && experiment.state === 'RUNNING') {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen?.();
      } else {
        document.exitFullscreen?.();
      }
    }
  });

  // ── Initialize ─────────────────────────────────────────────
  populateStimuli();
  updateSummary();
  console.log('[Main] Perception–Imagery platform initialized');
});