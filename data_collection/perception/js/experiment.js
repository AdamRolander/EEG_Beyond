// Experiment state machine and trial logic
class ExperimentController {
  constructor() {
    this.state = 'IDLE'; // IDLE, RUNNING, PAUSED, BREAK, COMPLETE
    this.config = null;
    this.trialQueue = [];
    this.currentTrialIndex = 0;
    this.trialsSinceBreak = 0;
    this.stimulusOnsetTime = null;
    this.timeoutHandle = null;
    this.sessionId = null;

    this.onStateChange = null;
    this.onTrialStart = null;
    this.onPhaseChange = null;
    this.onBreakStart = null;
    this.onComplete = null;
  }

  initialize(config) {
    this.config = config;
    this.sessionId = new Date().toISOString().replace(/[:.]/g, '-');
    this.buildTrialQueue();
    this.currentTrialIndex = 0;
    this.trialsSinceBreak = 0;
    this.state = 'IDLE';
    console.log(`[Experiment] Initialized: ${this.trialQueue.length} trials`);
  }

  buildTrialQueue() {
    this.trialQueue = [];

    this.config.enabledStimuli.forEach(stimKey => {
      for (let r = 0; r < this.config.repetitions; r++) {
        let stimulus;

        if (CONFIG.stimuli.colors[stimKey]) {
          stimulus = {
            type: 'color',
            key: stimKey,
            code: CONFIG.stimuli.colors[stimKey].code
          };
        } else if (CONFIG.stimuli.primitives[stimKey]) {
          stimulus = {
            type: 'shape',
            key: stimKey,
            code: CONFIG.stimuli.primitives[stimKey].code,
            rotationSpeed: this.config.rotationSpeed
          };
        } else if (CONFIG.stimuli.complex[stimKey]) {
          stimulus = {
            type: 'shape',
            key: stimKey,
            code: CONFIG.stimuli.complex[stimKey].code,
            rotationSpeed: this.config.rotationSpeed
          };
        }

        if (stimulus) this.trialQueue.push(stimulus);
      }
    });

    if (this.config.randomize) {
      this.shuffleArray(this.trialQueue);
    }
  }

  shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [array[i], array[j]] = [array[j], array[i]];
    }
  }

  async start() {
    if (this.state !== 'IDLE') return;
    this.state = 'RUNNING';
    this.emitStateChange();

    lslBridge.sendMarker(CONFIG.markerCodes.EXP_START, { sessionId: this.sessionId });

    vrRenderer.showISI();
    this.scheduleNextTrial();
    console.log('[Experiment] Started');
  }

  scheduleNextTrial() {
    this.timeoutHandle = setTimeout(() => {
      this.runTrial();
    }, this.config.isiDuration);
  }

  async runTrial() {
    if (this.state !== 'RUNNING') return;

    if (this.trialsSinceBreak >= this.config.trialsUntilBreak &&
        this.currentTrialIndex < this.trialQueue.length) {
      this.startBreak();
      return;
    }

    if (this.currentTrialIndex >= this.trialQueue.length) {
      this.complete();
      return;
    }

    const trial = this.trialQueue[this.currentTrialIndex];

    if (this.onTrialStart) {
      this.onTrialStart(this.currentTrialIndex + 1, this.trialQueue.length);
    }

    lslBridge.sendMarker(CONFIG.markerCodes.TRIAL_START, {
      trialNumber: this.currentTrialIndex + 1,
      stimulusCode: trial.code
    });

    vrRenderer.showStimulus(trial);
    this.stimulusOnsetTime = performance.now();

    const stimulusMarkerCode = CONFIG.markerCodes[trial.code] || 0;
    lslBridge.sendMarker(CONFIG.markerCodes.STIM_ONSET, {
      trialNumber: this.currentTrialIndex + 1,
      stimulusCode: trial.code,
      stimulusMarker: stimulusMarkerCode
    });

    if (this.onPhaseChange) {
      this.onPhaseChange('stimulus', trial.key);
    }

    this.timeoutHandle = setTimeout(() => {
      this.endTrial();
    }, this.config.stimulusDuration);
  }

  endTrial() {
    if (this.state !== 'RUNNING') return;

    const trial = this.trialQueue[this.currentTrialIndex];
    const duration = performance.now() - this.stimulusOnsetTime;

    lslBridge.sendMarker(CONFIG.markerCodes.STIM_OFFSET, {
      trialNumber: this.currentTrialIndex + 1,
      stimulusCode: trial.code,
      actualDuration: duration
    });

    vrRenderer.showISI();

    if (this.onPhaseChange) {
      this.onPhaseChange('isi', '');
    }

    this.currentTrialIndex++;
    this.trialsSinceBreak++;
    this.scheduleNextTrial();
  }

  startBreak() {
    this.state = 'BREAK';
    this.emitStateChange();
    lslBridge.sendMarker(CONFIG.markerCodes.BREAK_START, {
      trialsCompleted: this.currentTrialIndex
    });
    if (this.onBreakStart) {
      this.onBreakStart(this.currentTrialIndex, this.trialQueue.length);
    }
  }

  resumeFromBreak(likertRating = null) {
    if (likertRating !== null) {
      lslBridge.sendMarker(CONFIG.markerCodes.LIKERT_BASE + likertRating, { rating: likertRating });
    }
    lslBridge.sendMarker(CONFIG.markerCodes.BREAK_END);
    this.trialsSinceBreak = 0;
    this.state = 'RUNNING';
    this.emitStateChange();
    this.scheduleNextTrial();
  }

  pause() {
    if (this.state !== 'RUNNING') return;
    clearTimeout(this.timeoutHandle);
    this.state = 'PAUSED';
    this.emitStateChange();
    lslBridge.sendMarker(CONFIG.markerCodes.PAUSE);
  }

  resume() {
    if (this.state !== 'PAUSED') return;
    this.state = 'RUNNING';
    this.emitStateChange();
    lslBridge.sendMarker(CONFIG.markerCodes.RESUME);
    this.scheduleNextTrial();
  }

  stop() {
    clearTimeout(this.timeoutHandle);
    lslBridge.sendMarker(CONFIG.markerCodes.EXP_END, {
      trialsCompleted: this.currentTrialIndex,
      totalTrials: this.trialQueue.length
    });
    vrRenderer.showISI();
    vrRenderer.exitVR();
    this.state = 'IDLE';
    this.emitStateChange();
  }

  complete() {
    clearTimeout(this.timeoutHandle);
    lslBridge.sendMarker(CONFIG.markerCodes.EXP_END, {
      trialsCompleted: this.trialQueue.length,
      totalTrials: this.trialQueue.length,
      complete: true
    });
    vrRenderer.showISI();
    this.state = 'COMPLETE';
    this.emitStateChange();
    if (this.onComplete) {
      this.onComplete({
        sessionId: this.sessionId,
        totalTrials: this.trialQueue.length,
        markersSent: lslBridge.markerCount
      });
    }
  }

  emitStateChange() {
    if (this.onStateChange) this.onStateChange(this.state);
  }
}

// Global instance
const experiment = new ExperimentController();
