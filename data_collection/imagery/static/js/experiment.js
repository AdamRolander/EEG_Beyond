/**
 * EEG Imagery Experiment - Frontend Controller
 * Simplified version with reliable state management
 */

// State
let socket = null;
let experimentState = 'IDLE';
let experimentType = 'colors';
let selectedLikert = null;
let neurofeedbackPhase = 1;  // 1 = collect ratings, 2 = real-time feedback
let trialRatingKeyHandler = null;  // one-shot handler for 1-5 keys

// Connect when page loads
document.addEventListener('DOMContentLoaded', function() {
    connectSocket();
    setupUI();
    loadCategories('colors');
});

// =============================================================================
// Socket Connection
// =============================================================================

function connectSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected');
        document.getElementById('connection-status').textContent = 'Online';
        document.getElementById('connection-status').className = 'status connected';
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected');
        document.getElementById('connection-status').textContent = 'Offline';
        document.getElementById('connection-status').className = 'status disconnected';
    });
    
    // State events
    socket.on('state_change', function(data) {
        console.log('State:', data.state);
        experimentState = data.state;
        updateUI();
    });
    
    socket.on('initialized', function(data) {
        console.log('Initialized:', data);
        if (data.success) {
            if (data.neurofeedback_phase !== undefined) neurofeedbackPhase = data.neurofeedback_phase;
            socket.emit('start');
        } else {
            alert('Init failed: ' + data.error);
            resetToConfig();
        }
    });
    
    socket.on('started', function(data) {
        console.log('Started:', data);
        if (!data.success) {
            alert('Start failed: ' + data.error);
            resetToConfig();
        }
    });
    
    socket.on('stopped', function(data) {
        console.log('Stopped');
        resetToConfig();
    });
    
    socket.on('trial_complete', function(data) {
        console.log('Trial complete:', data);
        if (neurofeedbackPhase === 1) {
            showTrialRatingPrompt(data.trial_number);
        }
    });
    
    socket.on('trial_start', function(data) {
        console.log('Trial:', data);
        hideTrialRatingPrompt();
        document.getElementById('progress-text').textContent = data.trial_number + ' / ' + data.total_trials;
        var pct = (data.trial_number / data.total_trials) * 100;
        document.getElementById('progress-bar').style.setProperty('--progress', pct + '%');
    });
    
    socket.on('phase_change', function(data) {
        console.log('Phase:', data.phase, data.category);
        
        // Update display
        var display = document.getElementById('experiment-display');
        display.className = 'experiment-display ' + data.phase;
        
        document.getElementById('category-display').textContent = data.category;
        
        var phaseEl = document.getElementById('phase-indicator');
        phaseEl.className = 'phase-indicator ' + data.phase;
        
        var msgEl = document.getElementById('state-message');
        
        if (data.phase === 'cue') {
            phaseEl.textContent = 'CUE';
            msgEl.textContent = 'Listen...';
        } else if (data.phase === 'buffer') {
            phaseEl.textContent = 'PREPARE';
            msgEl.textContent = 'Get ready to visualize';
        } else if (data.phase === 'recording') {
            phaseEl.textContent = '● REC';
            msgEl.textContent = 'Visualize now';
        } else if (data.phase === 'end_beep') {
            phaseEl.textContent = 'DONE';
            msgEl.textContent = '';
        }
    });
    
    socket.on('break_start', function(data) {
        console.log('Break:', data);
        experimentState = data.enable_likert ? 'LIKERT' : 'BREAK';
        
        // Show break panel
        showPanel('break');
        
        // Update text
        document.getElementById('break-progress').innerHTML = 
            'Completed: <span>' + data.completed + '</span> / <span>' + data.total + '</span> trials';
        
        // Handle likert
        var likertContainer = document.getElementById('likert-container');
        var continueBtn = document.getElementById('continue-btn');
        
        if (data.enable_likert) {
            likertContainer.style.display = 'block';
            buildLikertScale(data.likert_scale);
            continueBtn.disabled = true;
            continueBtn.textContent = 'Select rating first';
        } else {
            likertContainer.style.display = 'none';
            continueBtn.disabled = false;
            continueBtn.textContent = 'Continue (Space)';
        }
        
        selectedLikert = null;
    });
    
    socket.on('experiment_complete', function(data) {
        console.log('Complete:', data);
        experimentState = 'COMPLETED';
        hideTrialRatingPrompt();
        showPanel('complete');
        document.getElementById('session-id').textContent = data.session_id;
        document.getElementById('completed-trials').textContent = data.total_trials;
    });
    
    socket.on('progress', function(data) {
        console.log('Progress:', data);
        experimentState = data.state;
        updateUI();
    });
    
    socket.on('error', function(data) {
        console.error('Error:', data.message);
        alert('Error: ' + data.message);
    });
}

// =============================================================================
// UI Updates
// =============================================================================

function showPanel(name) {
    document.getElementById('config-panel').classList.add('hidden');
    document.getElementById('experiment-panel').classList.add('hidden');
    document.getElementById('break-panel').classList.add('hidden');
    document.getElementById('complete-panel').classList.add('hidden');
    
    document.getElementById(name + '-panel').classList.remove('hidden');
}

function updateUI() {
    if (experimentState === 'IDLE') {
        showPanel('config');
        document.getElementById('start-btn').disabled = false;
        document.getElementById('start-btn').textContent = 'Initialize & Start';
    } else if (experimentState === 'RUNNING') {
        showPanel('experiment');
        document.getElementById('pause-btn').textContent = 'Pause (Space)';
    } else if (experimentState === 'PAUSED') {
        showPanel('experiment');
        document.getElementById('pause-btn').textContent = 'Resume (Space)';
        document.getElementById('phase-indicator').textContent = 'PAUSED';
        document.getElementById('state-message').textContent = 'Press Space to resume';
    } else if (experimentState === 'BREAK' || experimentState === 'LIKERT') {
        showPanel('break');
    } else if (experimentState === 'COMPLETED') {
        showPanel('complete');
    }
}

function resetToConfig() {
    experimentState = 'IDLE';
    hideTrialRatingPrompt();
    showPanel('config');
    document.getElementById('start-btn').disabled = false;
    document.getElementById('start-btn').textContent = 'Initialize & Start';
}

// =============================================================================
// Likert Scale
// =============================================================================

function buildLikertScale(points) {
    var container = document.getElementById('likert-options');
    var labels = points === 3 ? ['Low', 'Med', 'High'] : ['1', '2', '3', '4', '5'];
    
    var html = '';
    for (var i = 0; i < labels.length; i++) {
        html += '<div class="likert-option" data-value="' + (i + 1) + '">' + labels[i] + '</div>';
    }
    container.innerHTML = html;
    
    // Add click handlers
    var options = container.querySelectorAll('.likert-option');
    for (var j = 0; j < options.length; j++) {
        options[j].addEventListener('click', function() {
            // Clear all
            var all = container.querySelectorAll('.likert-option');
            for (var k = 0; k < all.length; k++) {
                all[k].classList.remove('selected');
            }
            // Select this one
            this.classList.add('selected');
            selectedLikert = parseInt(this.getAttribute('data-value'));
            
            // Enable continue
            document.getElementById('continue-btn').disabled = false;
            document.getElementById('continue-btn').textContent = 'Continue (Space)';
        });
    }
}

// =============================================================================
// Categories
// =============================================================================

async function loadCategories(type) {
    experimentType = type;
    
    // Update tabs
    var tabs = document.querySelectorAll('.tab-btn');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].classList.toggle('active', tabs[i].getAttribute('data-tab') === type);
    }
    
    var container = document.getElementById('categories-container');
    container.innerHTML = '<p class="loading">Loading...</p>';
    
    try {
        var response = await fetch('/api/categories/' + type);
        var data = await response.json();
        
        if (data.categories && data.categories.length > 0) {
            var html = '';
            for (var j = 0; j < data.categories.length; j++) {
                var cat = data.categories[j];
                html += '<label class="category-checkbox">';
                html += '<input type="checkbox" value="' + cat + '" checked>';
                html += '<span>' + cat + '</span>';
                html += '</label>';
            }
            container.innerHTML = html;
            
            // Add change handlers for summary
            var checkboxes = container.querySelectorAll('input');
            for (var k = 0; k < checkboxes.length; k++) {
                checkboxes[k].addEventListener('change', updateSummary);
            }
        } else {
            container.innerHTML = '<p class="loading">No audio files found</p>';
        }
    } catch (e) {
        container.innerHTML = '<p class="loading">Failed to load</p>';
    }
    
    var nfGroup = document.getElementById('neurofeedback-group');
    if (nfGroup) nfGroup.style.display = (type === 'fruits') ? 'block' : 'none';
    updateSummary();
}

function getSelectedCategories() {
    var checkboxes = document.getElementById('categories-container').querySelectorAll('input:checked');
    var cats = [];
    for (var i = 0; i < checkboxes.length; i++) {
        cats.push(checkboxes[i].value);
    }
    return cats;
}

function showTrialRatingPrompt(trialNumber) {
    var el = document.getElementById('trial-rating-prompt');
    if (!el) return;
    el.classList.remove('hidden');
    function onKey(e) {
        var key = e.key;
        if (key >= '1' && key <= '5') {
            var rating = parseInt(key, 10);
            socket.emit('trial_rating', { trial_number: trialNumber, rating: rating });
            document.removeEventListener('keydown', onKey);
            trialRatingKeyHandler = null;
            el.classList.add('hidden');
        }
    }
    if (trialRatingKeyHandler) document.removeEventListener('keydown', trialRatingKeyHandler);
    trialRatingKeyHandler = onKey;
    document.addEventListener('keydown', onKey);
}

function hideTrialRatingPrompt() {
    var el = document.getElementById('trial-rating-prompt');
    if (el) el.classList.add('hidden');
    if (trialRatingKeyHandler) {
        document.removeEventListener('keydown', trialRatingKeyHandler);
        trialRatingKeyHandler = null;
    }
}

function updateSummary() {
    var cats = getSelectedCategories();
    var perCat = parseInt(document.getElementById('trials-per-category').value) || 0;
    var total = cats.length * perCat;
    
    document.getElementById('total-trials').textContent = total;
    
    var vizMs = parseInt(document.getElementById('visualization-duration').value) || 0;
    var bufferMs = parseInt(document.getElementById('pre-buffer').value) || 0;
    var gapMs = parseInt(document.getElementById('inter-trial-gap').value) || 0;
    var trialMs = vizMs + bufferMs + gapMs + 1000;
    var totalMin = Math.ceil((total * trialMs) / 60000);
    
    document.getElementById('estimated-duration').textContent = totalMin;
}

// =============================================================================
// UI Setup
// =============================================================================

function setupUI() {
    // Tabs
    var tabs = document.querySelectorAll('.tab-btn');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].addEventListener('click', function() {
            loadCategories(this.getAttribute('data-tab'));
        });
    }
    
    // Select all/none
    document.getElementById('select-all-btn').addEventListener('click', function() {
        var cbs = document.getElementById('categories-container').querySelectorAll('input');
        for (var j = 0; j < cbs.length; j++) cbs[j].checked = true;
        updateSummary();
    });
    
    document.getElementById('deselect-all-btn').addEventListener('click', function() {
        var cbs = document.getElementById('categories-container').querySelectorAll('input');
        for (var j = 0; j < cbs.length; j++) cbs[j].checked = false;
        updateSummary();
    });
    
    // Likert toggle
    document.getElementById('enable-likert').addEventListener('change', function() {
        document.getElementById('likert-scale-row').style.display = this.checked ? 'flex' : 'none';
    });
    
    // Config changes
    document.getElementById('visualization-duration').addEventListener('change', updateSummary);
    document.getElementById('pre-buffer').addEventListener('change', updateSummary);
    document.getElementById('inter-trial-gap').addEventListener('change', updateSummary);
    document.getElementById('trials-per-category').addEventListener('change', updateSummary);
    
    // Start button
    document.getElementById('start-btn').addEventListener('click', function() {
        var cats = getSelectedCategories();
        if (cats.length === 0) {
            alert('Select at least one category');
            return;
        }
        
        this.disabled = true;
        this.textContent = 'Initializing...';
        
        var config = {
            experiment_type: experimentType,
            visualization_duration_ms: parseInt(document.getElementById('visualization-duration').value),
            pre_recording_buffer_ms: parseInt(document.getElementById('pre-buffer').value),
            inter_trial_gap_ms: parseInt(document.getElementById('inter-trial-gap').value),
            trials_per_category: parseInt(document.getElementById('trials-per-category').value),
            trials_until_break: parseInt(document.getElementById('trials-until-break').value),
            enabled_categories: cats,
            randomize_order: document.getElementById('randomize-order').checked,
            enable_end_beep: document.getElementById('enable-end-beep').checked,
            enable_likert: document.getElementById('enable-likert').checked,
            likert_scale: parseInt(document.getElementById('likert-scale').value),
            enable_logging: document.getElementById('enable-logging') ? document.getElementById('enable-logging').checked : false,
            enable_neurofeedback: (experimentType === 'fruits' && document.getElementById('enable-neurofeedback')) ? document.getElementById('enable-neurofeedback').checked : false,
            neurofeedback_phase: (experimentType === 'fruits' && document.querySelector('input[name="neurofeedback-phase"]:checked')) ? parseInt(document.querySelector('input[name="neurofeedback-phase"]:checked').value, 10) : 1
        };
        
        socket.emit('initialize', config);
    });
    
    // Pause button
    document.getElementById('pause-btn').addEventListener('click', function() {
        if (experimentState === 'PAUSED') {
            socket.emit('resume');
        } else {
            socket.emit('pause');
        }
    });
    
    // Stop button
    document.getElementById('stop-btn').addEventListener('click', function() {
        socket.emit('stop');
    });
    
    // Continue button
    document.getElementById('continue-btn').addEventListener('click', function() {
        if (experimentState === 'LIKERT' && selectedLikert) {
            socket.emit('submit_likert', { rating: selectedLikert });
        }
        socket.emit('resume');
    });
    
    // Restart button
    document.getElementById('restart-btn').addEventListener('click', function() {
        resetToConfig();
    });
    
    // Keyboard
    document.addEventListener('keydown', function(e) {
        if (e.code === 'Escape') {
            e.preventDefault();
            socket.emit('stop');
            setTimeout(resetToConfig, 300);
        }
        
        if (e.code === 'Space') {
            e.preventDefault();
            
            if (experimentState === 'RUNNING') {
                socket.emit('pause');
            } else if (experimentState === 'PAUSED') {
                socket.emit('resume');
            } else if (experimentState === 'BREAK') {
                socket.emit('resume');
            } else if (experimentState === 'LIKERT' && selectedLikert) {
                socket.emit('submit_likert', { rating: selectedLikert });
                socket.emit('resume');
            }
        }
    });
}