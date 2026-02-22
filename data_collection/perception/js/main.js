// Main application initialization and UI control
document.addEventListener('DOMContentLoaded', function () {
  let currentTab = 'colors';
  let selectedLikert = null;

  // DOM Elements
  const connectBtn      = document.getElementById('connect-btn');
  const startBtn        = document.getElementById('start-btn');
  const enterVrBtn      = document.getElementById('enter-vr-btn');
  const cancelVrBtn     = document.getElementById('cancel-vr-btn');
  const pauseBtn        = document.getElementById('pause-btn');
  const stopBtn         = document.getElementById('stop-btn');
  const continueBtn     = document.getElementById('continue-btn');
  const restartBtn      = document.getElementById('restart-btn');

  // Panels
  const configPanel     = document.getElementById('config-panel');
  const vrPanel         = document.getElementById('vr-panel');
  const experimentPanel = document.getElementById('experiment-panel');
  const breakPanel      = document.getElementById('break-panel');
  const completePanel   = document.getElementById('complete-panel');

  // =================================================================
  // Panel Management
  // =================================================================
  function showPanel(panelId) {
    [configPanel, vrPanel, experimentPanel, breakPanel, completePanel].forEach(p => {
      p.classList.add('hidden');
    });
    document.getElementById(panelId + '-panel').classList.remove('hidden');
  }

  // =================================================================
  // Tab Management
  // =================================================================
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      currentTab = this.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      this.classList.add('active');

      const shapeOptions = document.getElementById('shape-options');
      shapeOptions.style.display = (currentTab !== 'colors') ? 'block' : 'none';

      populateStimuli();
    });
  });

  function populateStimuli() {
    const container = document.getElementById('stimuli-container');
    container.style.display = '';  // remove inline style
    container.classList.remove('hidden');
    const stimuli = CONFIG.stimuli[currentTab];
    container.innerHTML = Object.entries(stimuli).map(([key, config]) => `
      <label class="stimulus-chip selected">
        <input type="checkbox" value="${key}" checked style="display:none;">
        <span>${config.name}</span>
      </label>
    `).join('');

    container.querySelectorAll('input').forEach(input => {
      const chip = input.parentElement;
      chip.addEventListener('click', function() {
        const checkbox = this.querySelector('input');
        checkbox.checked = !checkbox.checked;
        this.classList.toggle('selected', checkbox.checked);
        updateSummary();
      });
    });

    updateSummary();
  }

  function getSelectedStimuli() {
    const checkboxes = document.getElementById('stimuli-container').querySelectorAll('input:checked');
    return Array.from(checkboxes).map(cb => cb.value);
  }

  function updateSummary() {
    const selected = getSelectedStimuli();
    const reps = parseInt(document.getElementById('repetitions').value) || 0;
    const total = selected.length * reps;
    document.getElementById('total-trials').textContent = total;

    const stimDur = parseInt(document.getElementById('stimulus-duration').value) || 0;
    const isi     = parseInt(document.getElementById('isi-duration').value) || 0;
    const totalMin = Math.ceil((total * (stimDur + isi)) / 60000);
    document.getElementById('estimated-duration').textContent = totalMin;
  }

  document.getElementById('select-all-btn').addEventListener('click', () => {
    document.querySelectorAll('#stimuli-container input').forEach(cb => cb.checked = true);
    updateSummary();
  });

  document.getElementById('deselect-all-btn').addEventListener('click', () => {
    document.querySelectorAll('#stimuli-container input').forEach(cb => cb.checked = false);
    updateSummary();
  });

  ['stimulus-duration', 'isi-duration', 'repetitions'].forEach(id => {
    document.getElementById(id).addEventListener('change', updateSummary);
  });

  document.getElementById('enable-likert').addEventListener('change', function () {
    document.getElementById('likert-scale-row').style.display = this.checked ? 'flex' : 'none';
  });

  // =================================================================
  // LSL Connection
  // =================================================================
  connectBtn.addEventListener('click', async function () {
    const url = document.getElementById('bridge-url').value;
    connectBtn.disabled = true;
    connectBtn.textContent = 'Connecting...';

    try {
      await lslBridge.connect(url);
      startBtn.disabled = false;
      startBtn.textContent = 'Start Experiment';
      connectBtn.textContent = 'Connected ✓';
    } catch (e) {
      alert('Failed to connect: ' + e.message);
      connectBtn.disabled = false;
      connectBtn.textContent = 'Connect to LSL Bridge';
    }
  });

  lslBridge.onStatusChange = (connected) => {
    const status = document.getElementById('connection-status');
    status.textContent = connected ? 'Online' : 'Offline';
    status.className = 'status ' + (connected ? 'connected' : 'disconnected');
    if (!connected) {
      startBtn.disabled = true;
      startBtn.textContent = 'Connect to LSL Bridge First';
    }
  };

  // =================================================================
  // Experiment Control
  // =================================================================
  startBtn.addEventListener('click', function () {
    const selected = getSelectedStimuli();
    if (selected.length === 0) {
      alert('Please select at least one stimulus');
      return;
    }

    const config = {
      stimulusDuration:  parseInt(document.getElementById('stimulus-duration').value),
      isiDuration:       parseInt(document.getElementById('isi-duration').value),
      repetitions:       parseInt(document.getElementById('repetitions').value),
      trialsUntilBreak:  parseInt(document.getElementById('trials-until-break').value),
      rotationSpeed:     parseFloat(document.getElementById('rotation-speed').value),
      enabledStimuli:    selected,
      randomize:         document.getElementById('randomize-order').checked,
      enableLikert:      document.getElementById('enable-likert').checked,
      likertScale:       parseInt(document.getElementById('likert-scale').value)
    };

    experiment.initialize(config);

    const container = document.createElement('div');
    container.id = 'vr-container';
    container.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;';
    document.body.appendChild(container);
    vrRenderer.init(container);

    showPanel('vr');
  });

  enterVrBtn.addEventListener('click', async function () {
    try {
      await vrRenderer.enterVR();
      showPanel('experiment');

      experiment.onStateChange = (state) => {
        if (state === 'BREAK') showPanel('break');
        else if (state === 'COMPLETE') showPanel('complete');
      };

      experiment.onTrialStart = (current, total) => {
        document.getElementById('progress-text').textContent = `${current} / ${total}`;
        const pct = (current / total) * 100;
        document.getElementById('progress-bar').style.setProperty('--progress', pct + '%');
      };

      experiment.onPhaseChange = (phase, stimulus) => {
        document.getElementById('current-stimulus').textContent = stimulus;
        document.getElementById('phase-indicator').textContent =
          phase === 'stimulus' ? '● PRESENTING' : 'ISI';
      };

      experiment.onBreakStart = (completed, total) => {
        document.getElementById('break-progress').innerHTML =
          `Completed: <span>${completed}</span> / <span>${total}</span> trials`;
        buildLikertScale();
        showPanel('break');
      };

      experiment.onComplete = (data) => {
        document.getElementById('session-id').textContent = data.sessionId;
        document.getElementById('completed-trials').textContent = data.totalTrials;
        document.getElementById('markers-sent').textContent = data.markersSent;
        showPanel('complete');
      };

      vrRenderer.startRenderLoop();
      experiment.start();
    } catch (e) {
      alert('Failed to enter VR: ' + e.message);
    }
  });

  cancelVrBtn.addEventListener('click', function () {
    vrRenderer.dispose();
    document.getElementById('vr-container')?.remove();
    showPanel('config');
  });

  pauseBtn.addEventListener('click', function () {
    if (experiment.state === 'PAUSED') {
      experiment.resume();
      pauseBtn.textContent = 'Pause (Space)';
    } else {
      experiment.pause();
      pauseBtn.textContent = 'Resume (Space)';
    }
  });

  stopBtn.addEventListener('click', function () {
    experiment.stop();
    vrRenderer.dispose();
    document.getElementById('vr-container')?.remove();
    showPanel('config');
  });

  // =================================================================
  // Likert Scale
  // =================================================================
  function buildLikertScale() {
    const points  = parseInt(document.getElementById('likert-scale').value);
    const labels  = points === 3 ? ['Low', 'Med', 'High'] : ['1', '2', '3', '4', '5'];
    const container = document.getElementById('likert-options');

    container.innerHTML = labels.map((label, i) =>
      `<div class="likert-option" data-value="${i + 1}">${label}</div>`
    ).join('');

    container.querySelectorAll('.likert-option').forEach(opt => {
      opt.addEventListener('click', function () {
        container.querySelectorAll('.likert-option').forEach(o => o.classList.remove('selected'));
        this.classList.add('selected');
        selectedLikert = parseInt(this.dataset.value);
        continueBtn.disabled = false;
        continueBtn.textContent = 'Continue (Space)';
      });
    });

    selectedLikert = null;
    continueBtn.disabled = !document.getElementById('enable-likert').checked;
  }

  continueBtn.addEventListener('click', function () {
    experiment.resumeFromBreak(selectedLikert);
    showPanel('experiment');
  });

  // =================================================================
  // Complete / Restart
  // =================================================================
  restartBtn.addEventListener('click', function () {
    vrRenderer.dispose();
    document.getElementById('vr-container')?.remove();
    showPanel('config');
  });

  // =================================================================
  // Keyboard Controls
  // =================================================================
  document.addEventListener('keydown', function (e) {
    if (e.code === 'Escape') {
      e.preventDefault();
      if (experiment.state === 'RUNNING' || experiment.state === 'PAUSED') {
        experiment.stop();
        vrRenderer.dispose();
        document.getElementById('vr-container')?.remove();
        showPanel('config');
      }
    }

    if (e.code === 'Space') {
      e.preventDefault();
      if (experiment.state === 'RUNNING') {
        experiment.pause();
        pauseBtn.textContent = 'Resume (Space)';
      } else if (experiment.state === 'PAUSED') {
        experiment.resume();
        pauseBtn.textContent = 'Pause (Space)';
      } else if (experiment.state === 'BREAK' &&
        (selectedLikert || !document.getElementById('enable-likert').checked)) {
        experiment.resumeFromBreak(selectedLikert);
        showPanel('experiment');
      }
    }
  });

  // =================================================================
  // Initialize
  // =================================================================
  populateStimuli(); 
  updateSummary();
  console.log('EEG Perception Platform initialized');
});
