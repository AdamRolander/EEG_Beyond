/**
 * EEG Imagery Experiment - Frontend Controller
 * Handles UI state, WebSocket communication, and keyboard controls
 */

// =============================================================================
// State Management
// =============================================================================

const state = {
    socket: null,
    connected: false,
    experimentType: 'colors',
    experimentState: 'IDLE',
    categories: {},
    selectedLikert: null,
    initialized: false
};

// =============================================================================
// DOM Elements
// =============================================================================

const elements = {
    // Connection
    connectionStatus: document.getElementById('connection-status'),
    
    // Tabs
    tabButtons: document.querySelectorAll('.tab-btn'),
    
    // Config
    configPanel: document.getElementById('config-panel'),
    visualizationDuration: document.getElementById('visualization-duration'),
    preBuffer: document.getElementById('pre-buffer'),
    interTrialGap: document.getElementById('inter-trial-gap'),
    trialsPerCategory: document.getElementById('trials-per-category'),
    trialsUntilBreak: document.getElementById('trials-until-break'),
    categoriesContainer: document.getElementById('categories-container'),
    selectAllBtn: document.getElementById('select-all-btn'),
    deselectAllBtn: document.getElementById('deselect-all-btn'),
    randomizeOrder: document.getElementById('randomize-order'),
    enableEndBeep: document.getElementById('enable-end-beep'),
    enableLikert: document.getElementById('enable-likert'),
    likertScale: document.getElementById('likert-scale'),
    likertScaleRow: document.getElementById('likert-scale-row'),
    enableLogging: document.getElementById('enable-logging'),
    totalTrials: document.getElementById('total-trials'),
    estimatedDuration: document.getElementById('estimated-duration'),
    startBtn: document.getElementById('start-btn'),
    
    // Experiment
    experimentPanel: document.getElementById('experiment-panel'),
    experimentDisplay: document.getElementById('experiment-display'),
    progressBar: document.getElementById('progress-bar'),
    progressText: document.getElementById('progress-text'),
    phaseIndicator: document.getElementById('phase-indicator'),
    categoryDisplay: document.getElementById('category-display'),
    stateMessage: document.getElementById('state-message'),
    pauseBtn: document.getElementById('pause-btn'),
    stopBtn: document.getElementById('stop-btn'),
    
    // Break
    breakPanel: document.getElementById('break-panel'),
    breakProgress: document.getElementById('break-progress'),
    likertContainer: document.getElementById('likert-container'),
    likertOptions: document.getElementById('likert-options'),
    continueBtn: document.getElementById('continue-btn'),
    
    // Complete
    completePanel: document.getElementById('complete-panel'),
    sessionId: document.getElementById('session-id'),
    completedTrials: document.getElementById('completed-trials'),
    restartBtn: document.getElementById('restart-btn')
};

// =============================================================================
// WebSocket Connection
// =============================================================================

function connectSocket() {
    state.socket = io({
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000,
        timeout: 5000
    });
    
    state.socket.on('connect', () => {
        console.log('Connected to server');
        state.connected = true;
        updateConnectionStatus(true);
        
        // Request current state on reconnect
        state.socket.emit('get_progress');
    });
    
    state.socket.on('disconnect', () => {
        console.log('Disconnected from server');
        state.connected = false;
        updateConnectionStatus(false);
    });
    
    state.socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        state.connected = false;
        updateConnectionStatus(false);
    });
    
    // Experiment events
    state.socket.on('state_change', handleStateChange);
    state.socket.on('initialized', handleInitialized);
    state.socket.on('started', handleStarted);
    state.socket.on('trial_start', handleTrialStart);
    state.socket.on('phase_change', handlePhaseChange);
    state.socket.on('trial_complete', handleTrialComplete);
    state.socket.on('break_start', handleBreakStart);
    state.socket.on('experiment_complete', handleExperimentComplete);
    state.socket.on('progress', handleProgress);
    state.socket.on('error', handleError);
    state.socket.on('stopped', handleStopped);
}

function updateConnectionStatus(connected) {
    elements.connectionStatus.textContent = connected ? 'Online' : 'Offline';
    elements.connectionStatus.className = `status ${connected ? 'connected' : 'disconnected'}`;
}

// =============================================================================
// Event Handlers - WebSocket
// =============================================================================

function handleStateChange(data) {
    console.log('State change:', data.state);
    state.experimentState = data.state;
    updateUIForState(data.state);
}

function handleInitialized(data) {
    if (data.success) {
        console.log('Experiment initialized:', data);
        state.initialized = true;
        elements.startBtn.textContent = 'Start Experiment';
        // Auto-start after initialization
        state.socket.emit('start');
    } else {
        alert('Initialization failed: ' + data.error);
        elements.startBtn.disabled = false;
        elements.startBtn.textContent = 'Initialize & Start';
    }
}

function handleStarted(data) {
    if (!data.success) {
        alert('Failed to start: ' + data.error);
    }
}

function handleStopped(data) {
    console.log('Experiment stopped');
    state.experimentState = 'IDLE';
    state.initialized = false;
    showPanel('config');
    elements.startBtn.disabled = false;
    elements.startBtn.textContent = 'Initialize & Start';
}

function handleTrialStart(data) {
    console.log('Trial start:', data);
    elements.progressText.textContent = `${data.trial_number} / ${data.total_trials}`;
    const progress = (data.trial_number / data.total_trials) * 100;
    elements.progressBar.style.setProperty('--progress', `${progress}%`);
}

function handlePhaseChange(data) {
    console.log('Phase change:', data);
    
    // Make sure we're showing the experiment panel during phases
    if (state.experimentState === 'RUNNING') {
        showPanel('experiment');
    }
    
    const display = elements.experimentDisplay;
    display.className = 'experiment-display ' + data.phase;
    
    elements.phaseIndicator.className = `phase-indicator ${data.phase}`;
    elements.categoryDisplay.textContent = data.category;
    
    switch (data.phase) {
        case 'cue':
            elements.phaseIndicator.textContent = 'CUE';
            elements.stateMessage.textContent = 'Listen...';
            break;
        case 'buffer':
            elements.phaseIndicator.textContent = 'PREPARE';
            elements.stateMessage.textContent = 'Get ready to visualize';
            break;
        case 'recording':
            elements.phaseIndicator.textContent = '● REC';
            elements.stateMessage.textContent = 'Visualize now';
            break;
        case 'end_beep':
            elements.phaseIndicator.textContent = 'DONE';
            elements.stateMessage.textContent = '';
            break;
    }
}

function handleTrialComplete(data) {
    console.log('Trial complete:', data);
}

function handleBreakStart(data) {
    console.log('Break start:', data);
    
    // Force show break panel
    showPanel('break');
    
    // Update progress text
    const breakProgressEl = document.getElementById('break-progress');
    if (breakProgressEl) {
        breakProgressEl.innerHTML = `Completed: <span>${data.completed}</span> / <span>${data.total}</span> trials`;
    }
    
    // Handle Likert scale
    const likertContainer = document.getElementById('likert-container');
    const continueBtn = document.getElementById('continue-btn');
    
    if (data.enable_likert) {
        if (likertContainer) {
            likertContainer.classList.remove('hidden');
            likertContainer.style.display = 'block';
        }
        buildLikertScale(data.likert_scale);
        if (continueBtn) {
            continueBtn.disabled = true;
            continueBtn.textContent = 'Select rating to continue';
        }
    } else {
        if (likertContainer) {
            likertContainer.classList.add('hidden');
            likertContainer.style.display = 'none';
        }
        if (continueBtn) {
            continueBtn.disabled = false;
            continueBtn.textContent = 'Continue (Space)';
        }
    }
    
    state.selectedLikert = null;
    state.experimentState = data.enable_likert ? 'LIKERT' : 'BREAK';
}

function handleExperimentComplete(data) {
    console.log('Experiment complete:', data);
    showPanel('complete');
    elements.sessionId.textContent = data.session_id;
    elements.completedTrials.textContent = data.total_trials;
    state.experimentState = 'COMPLETED';
}

function handleProgress(data) {
    console.log('Progress:', data);
    state.experimentState = data.state;
    
    if (data.total_trials > 0) {
        elements.progressText.textContent = `${data.current_trial} / ${data.total_trials}`;
        const progress = (data.current_trial / data.total_trials) * 100;
        elements.progressBar.style.setProperty('--progress', `${progress}%`);
    }
    
    // Update UI based on current state
    updateUIForState(data.state);
}

function handleError(data) {
    console.error('Error:', data.message);
    alert('Error: ' + data.message);
}

// =============================================================================
// UI State Management
// =============================================================================

function updateUIForState(experimentState) {
    console.log('Updating UI for state:', experimentState);
    
    switch (experimentState) {
        case 'IDLE':
            showPanel('config');
            elements.startBtn.disabled = false;
            elements.startBtn.textContent = 'Initialize & Start';
            state.initialized = false;
            break;
            
        case 'RUNNING':
            showPanel('experiment');
            elements.pauseBtn.textContent = 'Pause (Space)';
            elements.stateMessage.textContent = '';
            break;
            
        case 'PAUSED':
            showPanel('experiment');
            elements.pauseBtn.textContent = 'Resume (Space)';
            elements.phaseIndicator.textContent = 'PAUSED';
            elements.phaseIndicator.className = 'phase-indicator';
            elements.stateMessage.textContent = 'Press Space to resume';
            break;
            
        case 'BREAK':
            showPanel('break');
            const continueBtn = document.getElementById('continue-btn');
            if (continueBtn && !document.getElementById('enable-likert')?.checked) {
                continueBtn.disabled = false;
                continueBtn.textContent = 'Continue (Space)';
            }
            break;
            
        case 'LIKERT':
            showPanel('break');
            break;
            
        case 'COMPLETED':
            showPanel('complete');
            break;
    }
}

function showPanel(panelName) {
    console.log('Showing panel:', panelName);
    
    // Hide all panels
    elements.configPanel.classList.add('hidden');
    elements.experimentPanel.classList.add('hidden');
    elements.breakPanel.classList.add('hidden');
    elements.completePanel.classList.add('hidden');
    
    // Show requested panel
    switch (panelName) {
        case 'config':
            elements.configPanel.classList.remove('hidden');
            break;
        case 'experiment':
            elements.experimentPanel.classList.remove('hidden');
            break;
        case 'break':
            elements.breakPanel.classList.remove('hidden');
            break;
        case 'complete':
            elements.completePanel.classList.remove('hidden');
            break;
    }
}

// =============================================================================
// Tab Management
// =============================================================================

function switchTab(experimentType) {
    state.experimentType = experimentType;
    
    // Update tab buttons
    elements.tabButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === experimentType);
    });
    
    // Load categories for this experiment type
    loadCategories(experimentType);
}

async function loadCategories(experimentType) {
    elements.categoriesContainer.innerHTML = '<p class="loading">Loading categories...</p>';
    
    try {
        const response = await fetch(`/api/categories/${experimentType}`);
        const data = await response.json();
        
        if (data.categories && data.categories.length > 0) {
            state.categories[experimentType] = data.categories;
            renderCategories(data.categories);
        } else {
            elements.categoriesContainer.innerHTML = 
                '<p class="loading">No audio files found. Add .mp3 files to the audio folder.</p>';
        }
    } catch (error) {
        console.error('Failed to load categories:', error);
        elements.categoriesContainer.innerHTML = 
            '<p class="loading">Failed to load categories</p>';
    }
    
    updateSummary();
}

function renderCategories(categories) {
    elements.categoriesContainer.innerHTML = categories.map(cat => `
        <label class="category-checkbox">
            <input type="checkbox" value="${cat}" checked>
            <span>${cat}</span>
        </label>
    `).join('');
    
    // Add change listeners
    elements.categoriesContainer.querySelectorAll('input').forEach(input => {
        input.addEventListener('change', updateSummary);
    });
}

function getSelectedCategories() {
    const checkboxes = elements.categoriesContainer.querySelectorAll('input:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

// =============================================================================
// Likert Scale
// =============================================================================

function buildLikertScale(points) {
    const likertOptions = document.getElementById('likert-options');
    if (!likertOptions) return;
    
    const labels = points === 3 
        ? ['Low', 'Med', 'High']
        : ['1', '2', '3', '4', '5'];
    
    likertOptions.innerHTML = labels.map((label, i) => `
        <div class="likert-option" data-value="${i + 1}">
            ${label}
        </div>
    `).join('');
    
    // Add click listeners
    likertOptions.querySelectorAll('.likert-option').forEach(option => {
        option.addEventListener('click', () => selectLikert(option));
    });
}

function selectLikert(option) {
    const likertOptions = document.getElementById('likert-options');
    if (!likertOptions) return;
    
    // Clear previous selection
    likertOptions.querySelectorAll('.likert-option').forEach(opt => {
        opt.classList.remove('selected');
    });
    
    // Select new option
    option.classList.add('selected');
    state.selectedLikert = parseInt(option.dataset.value);
    
    // Enable continue button
    const continueBtn = document.getElementById('continue-btn');
    if (continueBtn) {
        continueBtn.disabled = false;
        continueBtn.textContent = 'Continue (Space)';
    }
}

// =============================================================================
// Configuration
// =============================================================================

function updateSummary() {
    const categories = getSelectedCategories();
    const trialsPerCategory = parseInt(elements.trialsPerCategory.value) || 0;
    const totalTrials = categories.length * trialsPerCategory;
    
    const visualizationMs = parseInt(elements.visualizationDuration.value) || 0;
    const bufferMs = parseInt(elements.preBuffer.value) || 0;
    const gapMs = parseInt(elements.interTrialGap.value) || 0;
    const trialDuration = visualizationMs + bufferMs + gapMs + 1000; // +1s for audio
    
    const totalMs = totalTrials * trialDuration;
    const minutes = Math.ceil(totalMs / 60000);
    
    elements.totalTrials.textContent = totalTrials;
    elements.estimatedDuration.textContent = minutes;
}

function getConfig() {
    return {
        experiment_type: state.experimentType,
        visualization_duration_ms: parseInt(elements.visualizationDuration.value),
        pre_recording_buffer_ms: parseInt(elements.preBuffer.value),
        inter_trial_gap_ms: parseInt(elements.interTrialGap.value),
        trials_per_category: parseInt(elements.trialsPerCategory.value),
        trials_until_break: parseInt(elements.trialsUntilBreak.value),
        enabled_categories: getSelectedCategories(),
        randomize_order: elements.randomizeOrder.checked,
        enable_end_beep: elements.enableEndBeep.checked,
        enable_likert: elements.enableLikert.checked,
        likert_scale: parseInt(elements.likertScale.value),
        enable_logging: elements.enableLogging ? elements.enableLogging.checked : false
    };
}

// =============================================================================
// Event Listeners - UI
// =============================================================================

function setupEventListeners() {
    // Tab switching
    elements.tabButtons.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    
    // Category selection
    elements.selectAllBtn.addEventListener('click', () => {
        elements.categoriesContainer.querySelectorAll('input').forEach(cb => cb.checked = true);
        updateSummary();
    });
    
    elements.deselectAllBtn.addEventListener('click', () => {
        elements.categoriesContainer.querySelectorAll('input').forEach(cb => cb.checked = false);
        updateSummary();
    });
    
    // Likert toggle
    elements.enableLikert.addEventListener('change', () => {
        elements.likertScaleRow.style.display = elements.enableLikert.checked ? 'flex' : 'none';
    });
    
    // Config changes
    [elements.visualizationDuration, elements.preBuffer, elements.interTrialGap, 
     elements.trialsPerCategory].forEach(el => {
        el.addEventListener('change', updateSummary);
    });
    
    // Start button
    elements.startBtn.addEventListener('click', () => {
        const config = getConfig();
        
        if (config.enabled_categories.length === 0) {
            alert('Please select at least one category');
            return;
        }
        
        elements.startBtn.disabled = true;
        elements.startBtn.textContent = 'Initializing...';
        state.socket.emit('initialize', config);
    });
    
    // Pause button
    elements.pauseBtn.addEventListener('click', () => {
        if (state.experimentState === 'PAUSED') {
            state.socket.emit('resume');
        } else {
            state.socket.emit('pause');
        }
    });
    
    // Stop button
    elements.stopBtn.addEventListener('click', () => {
        stopExperiment();
    });
    
    // Continue button (break)
    elements.continueBtn.addEventListener('click', () => {
        handleContinue();
    });
    
    // Restart button
    elements.restartBtn.addEventListener('click', () => {
        state.initialized = false;
        state.experimentState = 'IDLE';
        showPanel('config');
    });
    
    // Keyboard controls
    document.addEventListener('keydown', (e) => {
        // ESC key - stop experiment from any state
        if (e.code === 'Escape') {
            e.preventDefault();
            stopExperiment();
            return;
        }
        
        // Space key - context-dependent
        if (e.code === 'Space') {
            e.preventDefault();
            handleSpacebar();
        }
    });
}

function stopExperiment() {
    console.log('Stopping experiment...');
    state.socket.emit('stop');
    
    // Force UI reset after short delay in case server doesn't respond
    setTimeout(() => {
        state.experimentState = 'IDLE';
        state.initialized = false;
        showPanel('config');
        elements.startBtn.disabled = false;
        elements.startBtn.textContent = 'Initialize & Start';
    }, 500);
}

function handleContinue() {
    console.log('Continue clicked, state:', state.experimentState, 'likert:', state.selectedLikert);
    
    if (state.experimentState === 'LIKERT' && state.selectedLikert) {
        state.socket.emit('submit_likert', { rating: state.selectedLikert });
    }
    state.socket.emit('resume');
}

function handleSpacebar() {
    console.log('Spacebar pressed, state:', state.experimentState);
    
    switch (state.experimentState) {
        case 'RUNNING':
            state.socket.emit('pause');
            break;
        case 'PAUSED':
            state.socket.emit('resume');
            break;
        case 'BREAK':
            state.socket.emit('resume');
            break;
        case 'LIKERT':
            if (state.selectedLikert) {
                state.socket.emit('submit_likert', { rating: state.selectedLikert });
                state.socket.emit('resume');
            }
            break;
    }
}

// =============================================================================
// Initialization
// =============================================================================

function init() {
    connectSocket();
    setupEventListeners();
    
    // Load initial categories
    loadCategories('colors');
    
    // Initial summary
    updateSummary();
    
    // Set initial visibility for likert scale row
    if (elements.likertScaleRow && elements.enableLikert) {
        elements.likertScaleRow.style.display = elements.enableLikert.checked ? 'flex' : 'none';
    }
    
    console.log('EEG Imagery Experiment UI initialized');
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);