/**
 * EEG Stimulus Platform - Experiment Controller Module
 * 
 * Main state machine and timing control for experiments.
 * Handles trial sequencing, WebXR, and user input.
 */

import * as THREE from 'three';
import { Config } from './config.js';
import { EventLogger } from './event-logger.js';
import { StimulusFactory } from './stimuli/stimulus-factory.js';

export class ExperimentController {
    constructor() {
        // Experiment state
        this.isRunning = false;
        this.isPaused = false;
        this.currentTrialIndex = 0;
        this.trialQueue = [];
        
        // Three.js objects
        this.renderer = null;
        this.scene = null;
        this.camera = null;
        this.currentStimulus = null;
        
        // Timing
        this.stimulusOnsetTime = null;
        this.lastFrameTime = null;
        this.scheduledTimeout = null;
        
        // VR
        this.vrEnabled = false;
        this.vrButton = null;
        
        // Configuration
        this.config = { ...Config.defaults };
        
        // Callbacks
        this.onTrialStart = null;
        this.onTrialEnd = null;
        this.onExperimentEnd = null;
    }
    
    // ============================================================
    // INITIALIZATION
    // ============================================================
    
    /**
     * Initialize Three.js scene
     * 
     * @param {HTMLElement} container - DOM element for canvas
     */
    initScene(container) {
        // Create renderer
        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            powerPreference: 'high-performance'
        });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.outputEncoding = THREE.LinearEncoding;
        
        container.appendChild(this.renderer.domElement);
        
        // Create scene
        this.scene = new THREE.Scene();
        this.scene.background = StimulusFactory.createNeutralBackground();
        
        // Create camera
        this.camera = new THREE.PerspectiveCamera(
            Config.scene.cameraFOV,
            window.innerWidth / window.innerHeight,
            Config.scene.cameraNear,
            Config.scene.cameraFar
        );
        this.camera.position.z = Config.scene.cameraZ;
        
        // Add lighting
        const lights = StimulusFactory.createLighting();
        lights.forEach(light => this.scene.add(light));
        
        // Event listeners
        window.addEventListener('resize', () => this.onWindowResize());
        
        console.log('[ExperimentController] Scene initialized');
    }
    
    /**
     * Initialize WebXR VR support
     */
    async initWebXR() {
        if (!navigator.xr) {
            console.warn('[WebXR] Not supported');
            return false;
        }
        
        const isSupported = await navigator.xr.isSessionSupported('immersive-vr');
        if (!isSupported) {
            console.warn('[WebXR] Immersive VR not supported');
            return false;
        }
        
        this.renderer.xr.enabled = true;
        this.vrEnabled = true;
        
        console.log('[WebXR] VR enabled');
        return true;
    }
    
    /**
     * Create VR button
     */
    createVRButton() {
        const button = document.createElement('button');
        button.id = 'vr-button';
        button.textContent = 'ENTER VR';
        button.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 15px 30px;
            background: #2a2a5a;
            border: 1px solid #4a4a8a;
            color: #e0e0e0;
            font-family: monospace;
            cursor: pointer;
            z-index: 1000;
        `;
        
        button.onclick = async () => {
            try {
                const session = await navigator.xr.requestSession('immersive-vr', {
                    optionalFeatures: ['local-floor', 'bounded-floor']
                });
                
                this.renderer.xr.setSession(session);
                button.textContent = 'VR ACTIVE';
                button.disabled = true;
                
                session.addEventListener('end', () => {
                    button.textContent = 'ENTER VR';
                    button.disabled = false;
                });
            } catch (e) {
                console.error('[WebXR] Failed to start session:', e);
            }
        };
        
        document.body.appendChild(button);
        this.vrButton = button;
    }
    
    // ============================================================
    // EXPERIMENT CONTROL
    // ============================================================
    
    /**
     * Configure experiment parameters
     */
    configure(options) {
        this.config = { ...this.config, ...options };
    }
    
    /**
     * Build trial queue from configuration
     */
    buildTrialQueue(stimulusType = 'combined') {
        this.trialQueue = [];
        
        // Color trials
        if (stimulusType === 'color' || stimulusType === 'combined') {
            const colors = Object.values(Config.colors);
            for (let rep = 0; rep < this.config.repetitions; rep++) {
                colors.forEach(color => {
                    this.trialQueue.push({
                        type: 'color',
                        config: color
                    });
                });
            }
        }
        
        // Shape trials
        if (stimulusType === 'shape' || stimulusType === 'combined') {
            const shapes = Object.keys(Config.shapes);
            for (let rep = 0; rep < this.config.repetitions; rep++) {
                shapes.forEach(shape => {
                    this.trialQueue.push({
                        type: 'shape',
                        config: Config.shapes[shape],
                        shapeName: shape
                    });
                });
            }
        }
        
        console.log(`[ExperimentController] Built ${this.trialQueue.length} trials`);
        return this.trialQueue;
    }
    
    /**
     * Randomize trial order
     */
    randomizeTrials(seed = null) {
        // Fisher-Yates shuffle with optional seeded RNG
        const random = seed !== null 
            ? this.seededRandom(seed) 
            : Math.random;
        
        for (let i = this.trialQueue.length - 1; i > 0; i--) {
            const j = Math.floor(random() * (i + 1));
            [this.trialQueue[i], this.trialQueue[j]] = 
                [this.trialQueue[j], this.trialQueue[i]];
        }
        
        console.log('[ExperimentController] Trials randomized');
    }
    
    /**
     * Seeded random number generator
     */
    seededRandom(seed) {
        let s = seed;
        return function() {
            s = Math.sin(s) * 10000;
            return s - Math.floor(s);
        };
    }
    
    /**
     * Start experiment
     */
    start() {
        EventLogger.init();
        
        this.isRunning = true;
        this.isPaused = false;
        this.currentTrialIndex = 0;
        
        // Initial ISI
        this.showISI();
        this.scheduledTimeout = setTimeout(
            () => this.startNextTrial(),
            this.config.isiDuration
        );
        
        // Start render loop
        this.lastFrameTime = performance.now();
        this.renderer.setAnimationLoop((time) => this.animate(time));
        
        console.log('[ExperimentController] Experiment started');
    }
    
    /**
     * Pause experiment
     */
    pause() {
        if (!this.isRunning) return;
        
        this.isPaused = true;
        EventLogger.log('PAUSE');
        
        // Clear pending timeout
        if (this.scheduledTimeout) {
            clearTimeout(this.scheduledTimeout);
        }
        
        console.log('[ExperimentController] Paused');
    }
    
    /**
     * Resume experiment
     */
    resume() {
        if (!this.isRunning || !this.isPaused) return;
        
        this.isPaused = false;
        EventLogger.log('RESUME');
        
        // Resume with remaining time (simplified: restart current state)
        this.startNextTrial();
        
        console.log('[ExperimentController] Resumed');
    }
    
    /**
     * Toggle pause state
     */
    togglePause() {
        if (this.isPaused) {
            this.resume();
        } else {
            this.pause();
        }
    }
    
    /**
     * Abort experiment
     */
    abort() {
        if (!this.isRunning) return;
        
        EventLogger.log('ABORT', {
            reason: 'user_abort',
            trialIndex: this.currentTrialIndex
        });
        
        this.end();
    }
    
    /**
     * Skip to next trial
     */
    skipTrial() {
        if (!this.isRunning || this.isPaused) return;
        
        EventLogger.log('SKIP', {
            trialIndex: this.currentTrialIndex
        });
        
        if (this.scheduledTimeout) {
            clearTimeout(this.scheduledTimeout);
        }
        
        this.endCurrentTrial();
    }
    
    /**
     * End experiment
     */
    end() {
        this.isRunning = false;
        
        if (this.scheduledTimeout) {
            clearTimeout(this.scheduledTimeout);
        }
        
        this.renderer.setAnimationLoop(null);
        
        EventLogger.log('EXPERIMENT_END', {
            totalTrials: this.trialQueue.length,
            completedTrials: this.currentTrialIndex
        });
        
        // Callback
        if (this.onExperimentEnd) {
            this.onExperimentEnd(EventLogger.getSummary());
        }
        
        console.log('[ExperimentController] Experiment ended');
    }
    
    // ============================================================
    // TRIAL CONTROL
    // ============================================================
    
    /**
     * Show inter-stimulus interval
     */
    showISI() {
        // Remove current stimulus
        if (this.currentStimulus) {
            if (this.currentStimulus.isMesh) {
                this.scene.remove(this.currentStimulus);
                this.camera.remove(this.currentStimulus);
            }
            this.currentStimulus = null;
        }
        
        // Reset background to neutral gray
        this.scene.background = StimulusFactory.createNeutralBackground();
    }
    
    /**
     * Start next trial
     */
    startNextTrial() {
        if (!this.isRunning || this.isPaused) return;
        
        if (this.currentTrialIndex >= this.trialQueue.length) {
            this.end();
            return;
        }
        
        const trial = this.trialQueue[this.currentTrialIndex];
        
        // Create and show stimulus
        if (trial.type === 'color') {
            this.showColorStimulus(trial.config);
        } else if (trial.type === 'shape') {
            this.showShapeStimulus(trial.shapeName);
        }
        
        // Log onset
        this.stimulusOnsetTime = performance.now();
        EventLogger.logOnset(
            trial.type,
            trial.config.code,
            this.currentTrialIndex + 1
        );
        
        // Callback
        if (this.onTrialStart) {
            this.onTrialStart(this.currentTrialIndex, trial);
        }
        
        // Schedule offset
        this.scheduledTimeout = setTimeout(
            () => this.endCurrentTrial(),
            this.config.stimulusDuration
        );
    }
    
    /**
     * Show color stimulus
     */
    showColorStimulus(colorConfig) {
        StimulusFactory.applyColorToScene(this.scene, colorConfig);
        
        // Store reference for tracking
        this.currentStimulus = {
            type: 'color',
            config: colorConfig
        };
    }
    
    /**
     * Show shape stimulus
     */
    showShapeStimulus(shapeName) {
        // Reset background for shape viewing
        this.scene.background = StimulusFactory.createNeutralBackground();
        
        // Create shape
        const shape = StimulusFactory.createShapeStimulus(shapeName, {
            rotationSpeed: this.config.rotationSpeed
        });
        
        // Position for VR (head-locked) or desktop (scene-centered)
        if (this.vrEnabled && this.renderer.xr.isPresenting) {
            shape.position.set(0, 0, -3);
            this.camera.add(shape);
            if (!this.scene.children.includes(this.camera)) {
                this.scene.add(this.camera);
            }
        } else {
            shape.position.set(0, 0, 0);
            this.scene.add(shape);
        }
        
        this.currentStimulus = shape;
    }
    
    /**
     * End current trial
     */
    endCurrentTrial() {
        if (!this.isRunning || !this.currentStimulus) return;
        
        const trial = this.trialQueue[this.currentTrialIndex];
        const duration = performance.now() - this.stimulusOnsetTime;
        
        // Log offset
        EventLogger.logOffset(
            trial.type,
            trial.config.code,
            this.currentTrialIndex + 1,
            duration
        );
        
        // Callback
        if (this.onTrialEnd) {
            this.onTrialEnd(this.currentTrialIndex, trial, duration);
        }
        
        // Show ISI
        this.showISI();
        
        // Advance
        this.currentTrialIndex++;
        
        // Schedule next trial
        this.scheduledTimeout = setTimeout(
            () => this.startNextTrial(),
            this.config.isiDuration
        );
    }
    
    // ============================================================
    // ANIMATION LOOP
    // ============================================================
    
    /**
     * Main animation loop
     */
    animate(time) {
        if (!this.isRunning) return;
        
        // Calculate delta time
        const deltaTime = (time - this.lastFrameTime) / 1000;
        this.lastFrameTime = time;
        
        // Update shape rotation if active
        if (this.currentStimulus && this.currentStimulus.isMesh) {
            StimulusFactory.updateRotation(this.currentStimulus, deltaTime);
        }
        
        // Render
        this.renderer.render(this.scene, this.camera);
    }
    
    // ============================================================
    // EVENT HANDLERS
    // ============================================================
    
    /**
     * Handle window resize
     */
    onWindowResize() {
        if (!this.camera || !this.renderer) return;
        
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }
    
    // ============================================================
    // GETTERS
    // ============================================================
    
    get progress() {
        return {
            current: this.currentTrialIndex,
            total: this.trialQueue.length,
            percent: this.trialQueue.length > 0 
                ? (this.currentTrialIndex / this.trialQueue.length) * 100 
                : 0
        };
    }
    
    get elapsedTime() {
        return EventLogger.experimentStartTime 
            ? (performance.now() - EventLogger.experimentStartTime) / 1000 
            : 0;
    }
}

export default ExperimentController;