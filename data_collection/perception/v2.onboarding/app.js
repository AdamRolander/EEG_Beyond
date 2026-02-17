(function () {
  'use strict';

  var STIMULI = {
    colors: ['Red', 'Green', 'Blue', 'Yellow'],
    primitives: ['Sphere', 'Cube', 'Cylinder'],
    complex: ['Torus', 'Pyramid', 'Octahedron']
  };

  var state = {
    connected: false,
    activeTab: 'colors',
    enableLikert: true,
    likertScale: 5,
    selectedStimuli: new Set(),
    totalTrials: 0,
    estimatedMinutes: 0,
    currentTrial: 0,
    completedBeforeBreak: 0
  };

  var panels = {
    config: document.getElementById('config-panel'),
    onboarding: document.getElementById('onboarding-panel'),
    vr: document.getElementById('vr-panel'),
    running: document.getElementById('running-panel'),
    break: document.getElementById('break-panel'),
    complete: document.getElementById('complete-panel')
  };

  var onboardingPage1 = document.getElementById('onboarding-page-1');
  var onboardingPage2 = document.getElementById('onboarding-page-2');
  var onboardingPage3 = document.getElementById('onboarding-page-3');
  var onboardingVisual1 = document.getElementById('onboarding-visual-1');
  var onboardingVisual3 = document.getElementById('onboarding-visual-3');
  var onboardingInstruction1 = document.getElementById('onboarding-instruction-1');
  var onboardingNext1 = document.getElementById('onboarding-next-1');
  var onboardingNext2 = document.getElementById('onboarding-next-2');
  var onboardingContinue = document.getElementById('onboarding-continue');

  var statusPill = document.getElementById('status-pill');
  var bridgeUrl = document.getElementById('bridge-url');
  var connectBtn = document.getElementById('connect-btn');
  var startBtn = document.getElementById('start-btn');
  var stimulusDuration = document.getElementById('stimulus-duration');
  var isiDuration = document.getElementById('isi-duration');
  var repetitions = document.getElementById('repetitions');
  var trialsUntilBreak = document.getElementById('trials-until-break');
  var stimuliContainer = document.getElementById('stimuli-container');
  var selectAllBtn = document.getElementById('select-all-btn');
  var deselectAllBtn = document.getElementById('deselect-all-btn');
  var shapeOptions = document.getElementById('shape-options');
  var randomizeOrder = document.getElementById('randomize-order');
  var enableLikert = document.getElementById('enable-likert');
  var likertScaleSelect = document.getElementById('likert-scale');
  var likertScaleRow = document.getElementById('likert-scale-row');
  var totalTrialsEl = document.getElementById('total-trials');
  var estimatedDurationEl = document.getElementById('estimated-duration');

  var enterVrBtn = document.getElementById('enter-vr-btn');
  var cancelVrBtn = document.getElementById('cancel-vr-btn');
  var progressFill = document.getElementById('progress-fill');
  var progressText = document.getElementById('progress-text');
  var phaseIndicator = document.getElementById('phase-indicator');
  var currentStimulus = document.getElementById('current-stimulus');
  var stateMessage = document.getElementById('state-message');
  var pauseBtn = document.getElementById('pause-btn');
  var stopBtn = document.getElementById('stop-btn');

  var breakProgress = document.getElementById('break-progress');
  var likertContainer = document.getElementById('likert-container');
  var likertOptions = document.getElementById('likert-options');
  var likertMax = document.getElementById('likert-max');
  var continueBtn = document.getElementById('continue-btn');

  var sessionId = document.getElementById('session-id');
  var completedTrialsEl = document.getElementById('completed-trials');
  var markersSent = document.getElementById('markers-sent');
  var restartBtn = document.getElementById('restart-btn');

  function showOnly(panel) {
    Object.keys(panels).forEach(function (key) {
      panels[key].classList.add('hidden');
    });
    panel.classList.remove('hidden');
  }

  var onboardingDrag = { active: false, startX: 0, startY: 0, rotX: 0, rotY: 0 };
  var onboardingAnimId = null;

  var ONBOARDING_INSTRUCTIONS = {
    colors: 'You will see a visual stimulus on the screen.',
    primitives: 'You will see a three-dimensional object.',
    complex: 'You will see a three-dimensional visual stimulus.'
  };

  function showOnboardingPage(num) {
    onboardingPage1.classList.toggle('hidden', num !== 1);
    onboardingPage2.classList.toggle('hidden', num !== 2);
    onboardingPage3.classList.toggle('hidden', num !== 3);
  }

  function buildOnboardingVisual(container, mode) {
    container.innerHTML = '';
    if (mode === 'colors') {
      var circle = document.createElement('div');
      circle.className = 'onboarding-color-circle';
      container.appendChild(circle);
      return;
    }
    if (mode === 'primitives') {
      var scene = document.createElement('div');
      scene.className = 'onboarding-3d-scene';
      var obj = document.createElement('div');
      obj.className = 'onboarding-3d-object onboarding-3d-sphere';
      scene.appendChild(obj);
      container.appendChild(scene);
      setupOnboarding3DDrag(scene, obj);
      return;
    }
    if (mode === 'complex') {
      var sceneCube = document.createElement('div');
      sceneCube.className = 'onboarding-3d-scene';
      var cube = document.createElement('div');
      cube.className = 'onboarding-3d-object onboarding-3d-cube';
      var faces = ['front', 'back', 'right', 'left', 'top', 'bottom'];
      faces.forEach(function (face) {
        var faceEl = document.createElement('div');
        faceEl.className = 'onboarding-3d-cube-face face-' + face;
        cube.appendChild(faceEl);
      });
      sceneCube.appendChild(cube);
      container.appendChild(sceneCube);
      setupOnboarding3DDrag(sceneCube, cube);
      return;
    }
  }

  function setupOnboarding3DDrag(scene, obj) {
    var rotX = 8;
    var rotY = 0;
    var floatPhase = 0;
    var lastTime = null;
    function animate(time) {
      if (lastTime === null) lastTime = time;
      var dt = (time - lastTime) / 1000;
      lastTime = time;
      if (!scene._dragActive) {
        rotY += 15 * dt;
        if (rotY >= 360) rotY -= 360;
        if (rotY < 0) rotY += 360;
      }
      floatPhase += dt * 0.8;
      var y = 3 * Math.sin(floatPhase);
      obj.style.transform = 'translateY(' + y + 'px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg)';
      scene._animId = requestAnimationFrame(animate);
    }
    scene._animId = requestAnimationFrame(animate);
    scene._dragActive = false;
    scene._rotX = rotX;
    scene._rotY = rotY;
    scene._startRotX = 0;
    scene._startRotY = 0;
    scene.addEventListener('mousedown', function (e) {
      e.preventDefault();
      scene._dragActive = true;
      scene._startX = e.clientX;
      scene._startY = e.clientY;
      scene._startRotX = scene._rotX;
      scene._startRotY = scene._rotY;
    });
    document.addEventListener('mousemove', function onMove(e) {
      if (!scene._dragActive) return;
      scene._rotX = scene._startRotX + (e.clientY - scene._startY) * 0.4;
      scene._rotY = scene._startRotY + (e.clientX - scene._startX) * 0.4;
    });
    document.addEventListener('mouseup', function onUp() {
      if (scene._dragActive) scene._dragActive = false;
    });
  }

  function startOnboarding() {
    showOnly(panels.onboarding);
    showOnboardingPage(1);
    onboardingInstruction1.textContent = ONBOARDING_INSTRUCTIONS[state.activeTab] || ONBOARDING_INSTRUCTIONS.colors;
    buildOnboardingVisual(onboardingVisual1, state.activeTab);
  }

  function getStimuliForTab() {
    return STIMULI[state.activeTab] || [];
  }

  function renderStimuli() {
    var list = getStimuliForTab();
    stimuliContainer.innerHTML = '';
    list.forEach(function (name) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'stimulus-chip' + (state.selectedStimuli.has(name) ? ' selected' : '');
      chip.textContent = name;
      chip.dataset.stimulus = name;
      chip.addEventListener('click', function () {
        if (state.selectedStimuli.has(name)) {
          state.selectedStimuli.delete(name);
        } else {
          state.selectedStimuli.add(name);
        }
        chip.classList.toggle('selected', state.selectedStimuli.has(name));
        updateSummary();
      });
      stimuliContainer.appendChild(chip);
    });
  }

  function updateShapeOptionsVisibility() {
    if (state.activeTab === 'primitives' || state.activeTab === 'complex') {
      shapeOptions.classList.remove('hidden');
    } else {
      shapeOptions.classList.add('hidden');
    }
  }

  function updateLikertScaleRow() {
    likertScaleRow.classList.toggle('hidden', !enableLikert.checked);
  }

  function computeTotalTrials() {
    var n = state.selectedStimuli.size * (parseInt(repetitions.value, 10) || 0);
    state.totalTrials = n;
    return n;
  }

  function computeEstimatedMinutes() {
    var stim = parseInt(stimulusDuration.value, 10) || 0;
    var isi = parseInt(isiDuration.value, 10) || 0;
    var total = state.totalTrials * (stim + isi) / 1000 / 60;
    state.estimatedMinutes = total;
    return total;
  }

  function updateSummary() {
    computeTotalTrials();
    computeEstimatedMinutes();
    totalTrialsEl.textContent = state.totalTrials;
    estimatedDurationEl.textContent = state.estimatedMinutes.toFixed(1);
  }

  function renderBreakLikert() {
    var scale = parseInt(likertScaleSelect.value, 10) || 5;
    state.likertScale = scale;
    likertMax.textContent = scale;
    likertOptions.innerHTML = '';
    for (var i = 1; i <= scale; i++) {
      var label = document.createElement('label');
      var radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'break-likert';
      radio.value = String(i);
      radio.addEventListener('change', function () {
        continueBtn.disabled = false;
        continueBtn.textContent = 'CONTINUE';
      });
      label.appendChild(radio);
      label.appendChild(document.createTextNode(' ' + i));
      likertOptions.appendChild(label);
    }
  }

  function setConnection(connected) {
    state.connected = connected;
    if (connected) {
      statusPill.textContent = 'ONLINE';
      statusPill.classList.remove('offline');
      statusPill.classList.add('online');
      startBtn.disabled = false;
      startBtn.textContent = 'START EXPERIMENT';
    } else {
      statusPill.textContent = 'OFFLINE';
      statusPill.classList.remove('online');
      statusPill.classList.add('offline');
      startBtn.disabled = true;
      startBtn.textContent = 'CONNECT TO LSL BRIDGE FIRST';
    }
  }

  function resetToConfig() {
    state.connected = false;
    state.activeTab = 'colors';
    state.selectedStimuli.clear();
    state.currentTrial = 0;
    state.completedBeforeBreak = 0;
    setConnection(false);
    document.querySelectorAll('.tab-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.tab === 'colors');
    });
    state.activeTab = 'colors';
    renderStimuli();
    updateShapeOptionsVisibility();
    updateSummary();
    continueBtn.disabled = true;
    continueBtn.textContent = 'SELECT RATING TO CONTINUE';
    showOnly(panels.config);
  }

  // Tabs
  document.querySelectorAll('.tab-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var tab = btn.dataset.tab;
      if (!tab) return;
      state.activeTab = tab;
      document.querySelectorAll('.tab-btn').forEach(function (b) {
        b.classList.toggle('active', b.dataset.tab === tab);
      });
      renderStimuli();
      updateShapeOptionsVisibility();
      updateSummary();
    });
  });

  selectAllBtn.addEventListener('click', function () {
    getStimuliForTab().forEach(function (name) {
      state.selectedStimuli.add(name);
    });
    renderStimuli();
    updateSummary();
  });

  deselectAllBtn.addEventListener('click', function () {
    getStimuliForTab().forEach(function (name) {
      state.selectedStimuli.delete(name);
    });
    renderStimuli();
    updateSummary();
  });

  enableLikert.addEventListener('change', function () {
    state.enableLikert = enableLikert.checked;
    updateLikertScaleRow();
  });

  likertScaleSelect.addEventListener('change', function () {
    state.likertScale = parseInt(likertScaleSelect.value, 10) || 5;
  });

  [stimulusDuration, isiDuration, repetitions].forEach(function (el) {
    el.addEventListener('input', updateSummary);
  });

  panels.config.addEventListener('click', function (e) {
    var wrap = e.target.closest('.config-number-wrap');
    if (!wrap) return;
    var input = wrap.querySelector('input[type="number"]');
    if (!input) return;
    if (e.target.classList.contains('config-number-arrow-up')) {
      input.stepUp();
      updateSummary();
    } else if (e.target.classList.contains('config-number-arrow-down')) {
      input.stepDown();
      updateSummary();
    }
  });

  connectBtn.addEventListener('click', function () {
    setConnection(true);
  });

  startBtn.addEventListener('click', function () {
    if (!state.connected) return;
    startOnboarding();
  });

  onboardingNext1.addEventListener('click', function () {
    var scene1 = onboardingVisual1.querySelector('.onboarding-3d-scene');
    if (scene1 && scene1._animId != null) cancelAnimationFrame(scene1._animId);
    showOnboardingPage(2);
  });

  onboardingNext2.addEventListener('click', function () {
    showOnboardingPage(3);
    buildOnboardingVisual(onboardingVisual3, state.activeTab);
  });

  onboardingContinue.addEventListener('click', function () {
    var scene = onboardingVisual3.querySelector('.onboarding-3d-scene');
    if (scene && scene._animId != null) {
      cancelAnimationFrame(scene._animId);
    }
    showOnly(panels.vr);
  });

  cancelVrBtn.addEventListener('click', function () {
    showOnly(panels.config);
  });

  enterVrBtn.addEventListener('click', function () {
    state.currentTrial = 0;
    state.totalTrials = computeTotalTrials();
    progressText.textContent = '0 / ' + state.totalTrials;
    progressFill.style.width = '0%';
    phaseIndicator.textContent = 'VR ACTIVE';
    currentStimulus.textContent = '—';
    stateMessage.textContent = '—';
    showOnly(panels.running);
  });

  pauseBtn.addEventListener('click', function () {
    state.completedBeforeBreak = state.currentTrial;
    breakProgress.textContent = 'COMPLETED: ' + state.currentTrial + ' / ' + state.totalTrials + ' TRIALS';
    state.enableLikert = enableLikert.checked;
    if (state.enableLikert) {
      likertContainer.classList.remove('hidden');
      renderBreakLikert();
      continueBtn.disabled = true;
      continueBtn.textContent = 'SELECT RATING TO CONTINUE';
    } else {
      likertContainer.classList.add('hidden');
      continueBtn.disabled = false;
      continueBtn.textContent = 'CONTINUE';
    }
    showOnly(panels.break);
  });

  continueBtn.addEventListener('click', function () {
    showOnly(panels.running);
  });

  stopBtn.addEventListener('click', function () {
    var id = 'session-' + Date.now();
    sessionId.textContent = id;
    completedTrialsEl.textContent = state.totalTrials;
    markersSent.textContent = String(state.totalTrials + 10);
    showOnly(panels.complete);
  });

  restartBtn.addEventListener('click', function () {
    resetToConfig();
  });

  document.addEventListener('keydown', function (e) {
    if (e.code === 'Space') {
      if (!panels.running.classList.contains('hidden')) {
        e.preventDefault();
        pauseBtn.click();
      }
    }
    if (e.code === 'Escape') {
      if (!panels.running.classList.contains('hidden') || !panels.break.classList.contains('hidden')) {
        e.preventDefault();
        stopBtn.click();
      }
    }
  });

  // Init
  updateLikertScaleRow();
  renderStimuli();
  updateShapeOptionsVisibility();
  updateSummary();
})();
