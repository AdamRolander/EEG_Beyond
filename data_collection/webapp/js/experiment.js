// ─── Experiment State Machine ────────────────────────────────
// Implements the perception–imagery paradigm:
//   Fixation → Perception → Mask → [Audio Cue] → Imagery → Rest → Repeat
class ExperimentController {
  constructor() {
    this.state = 'IDLE'; // IDLE | RUNNING | PAUSED | BREAK | COMPLETE
    this.config = null;
    this.trialQueue = [];
    this.currentTrialIndex = 0;
    this.trialsSinceBreak = 0;
    this.currentPhase = '';
    this.phaseOnsetTime = null;
    this.timeoutHandle = null;
    this.sessionId = null;
    this.likertRecords = [];

    // Callbacks
    this.onStateChange = null;
    this.onTrialStart = null;
    this.onPhaseChange = null;
    this.onBreakStart = null;
    this.onComplete = null;
  }

  /**
   * Initialize experiment with config from UI.
   */
  initialize(config) {
    this.config = config;
    this.sessionId = new Date().toISOString().replace(/[:.]/g, '-');
    this.likertRecords = [];
    this.currentTrialIndex = 0;
    this.trialsSinceBreak = 0;
    this.state = 'IDLE';
    this._buildTrialQueue();
    console.log(`[Exp] Initialized: ${this.trialQueue.length} trials, session=${this.sessionId}`);
  }

  _buildTrialQueue() {
    this.trialQueue = [];

    const stimKeys = this.config.enabledStimuli.filter(k => CONFIG.stimuli[k]);

    if (this.config.randomize) {
      // Build all trials then shuffle
      stimKeys.forEach(stimKey => {
        const stimCfg = CONFIG.stimuli[stimKey];
        for (let r = 0; r < this.config.repetitions; r++) {
          this.trialQueue.push({
            key: stimKey, name: stimCfg.name,
            code: stimCfg.code, file: stimCfg.file
          });
        }
      });
      // Fisher-Yates shuffle
      for (let i = this.trialQueue.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [this.trialQueue[i], this.trialQueue[j]] = [this.trialQueue[j], this.trialQueue[i]];
      }
    } else {
      // Interleave: cycle through classes each repetition
      // banana, strawberry, cube, banana, strawberry, cube, ...
      for (let r = 0; r < this.config.repetitions; r++) {
        stimKeys.forEach(stimKey => {
          const stimCfg = CONFIG.stimuli[stimKey];
          this.trialQueue.push({
            key: stimKey, name: stimCfg.name,
            code: stimCfg.code, file: stimCfg.file
          });
        });
      }
    }
  }

  // ── Control ────────────────────────────────────────────────

  start() {
    if (this.state !== 'IDLE') return;
    this.state = 'RUNNING';
    this._emit('state');

    lslBridge.sendMarker(CONFIG.markers.EXP_START, { sessionId: this.sessionId });
    vrRenderer.showNeutral();

    // Brief delay then first trial
    this.timeoutHandle = setTimeout(() => this._runTrial(), 1000);
    console.log('[Exp] Started');
  }

  pause() {
    if (this.state !== 'RUNNING') return;
    clearTimeout(this.timeoutHandle);
    this.state = 'PAUSED';
    this._emit('state');
    lslBridge.sendMarker(CONFIG.markers.PAUSE, { trialNumber: this.currentTrialIndex + 1 });
  }

  resume() {
    if (this.state !== 'PAUSED') return;
    this.state = 'RUNNING';
    this._emit('state');
    lslBridge.sendMarker(CONFIG.markers.RESUME, { trialNumber: this.currentTrialIndex + 1 });
    // Resume from next trial
    this.timeoutHandle = setTimeout(() => this._runTrial(), 500);
  }

  stop() {
    clearTimeout(this.timeoutHandle);
    lslBridge.sendMarker(CONFIG.markers.EXP_END, {
      trialsCompleted: this.currentTrialIndex,
      totalTrials: this.trialQueue.length
    });
    vrRenderer.showNeutral();
    vrRenderer.exitVR();
    this.state = 'IDLE';
    this._emit('state');
  }

  resumeFromBreak(likertRating = null) {
    if (likertRating !== null) {
      lslBridge.sendMarker(CONFIG.markers.LIKERT_BASE + likertRating, {
        rating: likertRating,
        trialNumber: this.currentTrialIndex
      });
    }
    // Record
    this.likertRecords.push({
      sessionId: this.sessionId,
      trialIndex: this.currentTrialIndex,
      timestamp: new Date().toISOString(),
      rating: likertRating
    });

    lslBridge.sendMarker(CONFIG.markers.BREAK_END, { trialNumber: this.currentTrialIndex });
    this.trialsSinceBreak = 0;
    this.state = 'RUNNING';
    this._emit('state');

    // Show neutral screen during the transition delay
    vrRenderer.showNeutral();
    const delay = CONFIG.defaults.breakResumeDelay || 2000;
    this.timeoutHandle = setTimeout(() => this._runTrial(), delay);
  }

  // ── Trial Execution ────────────────────────────────────────

  _runTrial() {
    if (this.state !== 'RUNNING') return;

    // Check for break
    if (this.trialsSinceBreak >= this.config.trialsUntilBreak &&
        this.currentTrialIndex < this.trialQueue.length) {
      this._startBreak();
      return;
    }

    // Check for completion
    if (this.currentTrialIndex >= this.trialQueue.length) {
      this._complete();
      return;
    }

    const trial = this.trialQueue[this.currentTrialIndex];
    const trialNum = this.currentTrialIndex + 1;
    const totalTrials = this.trialQueue.length;

    if (this.onTrialStart) this.onTrialStart(trialNum, totalTrials);

    lslBridge.sendMarker(CONFIG.markers.TRIAL_START, {
      trialNumber: trialNum,
      stimulusKey: trial.key,
      stimulusCode: trial.code
    });

    // Phase chain: fixation → perception → mask → cue → imagery → rest → next
    this._phaseFixation(trial, trialNum);
  }

  _phaseFixation(trial, trialNum) {
    if (this.state !== 'RUNNING') return;
    this.currentPhase = 'fixation';
    this._emitPhase('FIXATION', '＋');

    vrRenderer.showFixation();
    lslBridge.sendMarker(CONFIG.markers.FIXATION_ONSET, {
      trialNumber: trialNum, stimulusCode: trial.code
    });

    this.timeoutHandle = setTimeout(
      () => this._phasePerception(trial, trialNum),
      this.config.fixationDuration
    );
  }

  _phasePerception(trial, trialNum) {
    if (this.state !== 'RUNNING') return;
    this.currentPhase = 'perception';
    this._emitPhase('PERCEPTION', trial.name);
    this.phaseOnsetTime = performance.now();

    vrRenderer.showStimulus(trial.key);
    lslBridge.sendMarker(CONFIG.markers.PERCEPTION_ONSET, {
      trialNumber: trialNum, stimulusCode: trial.code
    });
    // Also send the stimulus identity marker
    lslBridge.sendMarker(trial.code, {
      trialNumber: trialNum, phase: 'perception'
    });

    this.timeoutHandle = setTimeout(
      () => this._phaseMask(trial, trialNum),
      this.config.perceptionDuration
    );
  }

  _phaseMask(trial, trialNum) {
    if (this.state !== 'RUNNING') return;
    this.currentPhase = 'mask';
    this._emitPhase('MASK', '');

    vrRenderer.showMask();
    lslBridge.sendMarker(CONFIG.markers.MASK_ONSET, {
      trialNumber: trialNum, stimulusCode: trial.code,
      perceptionDuration: performance.now() - this.phaseOnsetTime
    });

    this.timeoutHandle = setTimeout(
      () => this._phaseImageryCue(trial, trialNum),
      this.config.maskDuration
    );
  }

  _phaseImageryCue(trial, trialNum) {
    if (this.state !== 'RUNNING') return;

    // Show black screen for imagery
    vrRenderer.showImagery();

    // Play audio cue
    if (this.config.enableAudioCue) {
      lslBridge.sendMarker(CONFIG.markers.IMAGERY_CUE, {
        trialNumber: trialNum, stimulusCode: trial.code
      });

      if (this.config.audioCueType === 'name') {
        AudioCues.playCue(trial.key);
      } else {
        AudioCues.playBeep();
      }
    }

    // Delay before "recording" imagery starts
    this.timeoutHandle = setTimeout(
      () => this._phaseImagery(trial, trialNum),
      this.config.imageryCueDelay
    );
  }

  _phaseImagery(trial, trialNum) {
    if (this.state !== 'RUNNING') return;
    this.currentPhase = 'imagery';
    this._emitPhase('IMAGERY', trial.name);
    this.phaseOnsetTime = performance.now();

    lslBridge.sendMarker(CONFIG.markers.IMAGERY_ONSET, {
      trialNumber: trialNum, stimulusCode: trial.code
    });
    // Stimulus identity marker for imagery phase
    lslBridge.sendMarker(trial.code, {
      trialNumber: trialNum, phase: 'imagery'
    });

    this.timeoutHandle = setTimeout(
      () => this._phaseImageryEnd(trial, trialNum),
      this.config.imageryDuration
    );
  }

  _phaseImageryEnd(trial, trialNum) {
    if (this.state !== 'RUNNING') return;

    lslBridge.sendMarker(CONFIG.markers.IMAGERY_OFFSET, {
      trialNumber: trialNum, stimulusCode: trial.code,
      imageryDuration: performance.now() - this.phaseOnsetTime
    });

    this._phaseRest(trial, trialNum);
  }

  _phaseRest(trial, trialNum) {
    if (this.state !== 'RUNNING') return;
    this.currentPhase = 'rest';
    this._emitPhase('REST', '');

    vrRenderer.showRest();
    AudioCues.playBeepRest();
    lslBridge.sendMarker(CONFIG.markers.REST_ONSET, {
      trialNumber: trialNum, stimulusCode: trial.code
    });

    this.timeoutHandle = setTimeout(() => {
      if (this.state !== 'RUNNING') return;

      lslBridge.sendMarker(CONFIG.markers.TRIAL_END, {
        trialNumber: trialNum, stimulusCode: trial.code
      });

      this.currentTrialIndex++;
      this.trialsSinceBreak++;
      this._runTrial();
    }, this.config.restDuration);
  }

  // ── Break / Complete ───────────────────────────────────────

  _startBreak() {
    this.state = 'BREAK';
    this._emit('state');
    lslBridge.sendMarker(CONFIG.markers.BREAK_START, {
      trialsCompleted: this.currentTrialIndex
    });
    if (this.onBreakStart) {
      this.onBreakStart(this.currentTrialIndex, this.trialQueue.length);
    }
  }

  _complete() {
    clearTimeout(this.timeoutHandle);
    lslBridge.sendMarker(CONFIG.markers.EXP_END, {
      trialsCompleted: this.trialQueue.length,
      totalTrials: this.trialQueue.length,
      complete: true
    });
    vrRenderer.showNeutral();
    this.state = 'COMPLETE';
    this._emit('state');
    if (this.onComplete) {
      this.onComplete({
        sessionId: this.sessionId,
        totalTrials: this.trialQueue.length,
        markersSent: lslBridge.markerCount,
        likertRecords: this.likertRecords
      });
    }
  }

  // ── Helpers ────────────────────────────────────────────────

  _emit(type) {
    if (type === 'state' && this.onStateChange) this.onStateChange(this.state);
  }

  _emitPhase(phaseName, stimulusLabel) {
    if (this.onPhaseChange) this.onPhaseChange(phaseName, stimulusLabel);
  }
}

// Global instance
const experiment = new ExperimentController();