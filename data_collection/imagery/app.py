"""
Flask Application for EEG Imagery Experiments
Web-based GUI for experiment configuration and control.
"""

import os
import json
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from config import ExperimentConfig, EXPERIMENT_TYPES, AUDIO_DIR
from experiment_engine import (
    ExperimentEngine, 
    ExperimentState,
    get_experiment_engine,
    reset_experiment_engine
)
from audio_manager import get_audio_manager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'imagery-experiment-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global engine reference
engine: ExperimentEngine = None


def setup_engine_callbacks():
    """Set up callbacks from engine to WebSocket."""
    global engine
    
    def on_state_change(state: ExperimentState):
        socketio.emit('state_change', {'state': state.name})
    
    def on_trial_start(trial):
        socketio.emit('trial_start', {
            'trial_number': trial.trial_number,
            'category': trial.category,
            'total_trials': len(engine.trial_queue)
        })
    
    def on_phase_change(phase: str, category: str):
        socketio.emit('phase_change', {
            'phase': phase,
            'category': category
        })
    
    def on_trial_complete(trial):
        socketio.emit('trial_complete', {
            'trial_number': trial.trial_number,
            'category': trial.category
        })
    
    def on_break_start(completed: int, total: int):
        socketio.emit('break_start', {
            'completed': completed,
            'total': total,
            'enable_likert': engine.config.enable_likert,
            'likert_scale': engine.config.likert_scale
        })
    
    def on_experiment_complete(session_log):
        socketio.emit('experiment_complete', {
            'session_id': session_log.session_id,
            'total_trials': len(session_log.trials)
        })
    
    def on_error(message: str):
        socketio.emit('error', {'message': message})
    
    engine.on_state_change = on_state_change
    engine.on_trial_start = on_trial_start
    engine.on_phase_change = on_phase_change
    engine.on_trial_complete = on_trial_complete
    engine.on_break_start = on_break_start
    engine.on_experiment_complete = on_experiment_complete
    engine.on_error = on_error


# =============================================================================
# Routes
# =============================================================================

@app.route('/')
def index():
    """Main page."""
    return render_template('index.html', experiment_types=EXPERIMENT_TYPES)


@app.route('/api/categories/<experiment_type>')
def get_categories(experiment_type):
    """Get available categories for an experiment type by scanning audio folder."""
    if experiment_type not in EXPERIMENT_TYPES:
        return jsonify({'error': 'Unknown experiment type'}), 400
    
    audio_folder = os.path.join(AUDIO_DIR, EXPERIMENT_TYPES[experiment_type]["audio_folder"])
    audio_manager = get_audio_manager()
    categories = audio_manager.scan_audio_folder(audio_folder)
    
    return jsonify({
        'experiment_type': experiment_type,
        'categories': categories,
        'display_name': EXPERIMENT_TYPES[experiment_type]['display_name']
    })


@app.route('/api/experiment_types')
def get_experiment_types():
    """Get all experiment types."""
    types = []
    for key, info in EXPERIMENT_TYPES.items():
        audio_folder = os.path.join(AUDIO_DIR, info["audio_folder"])
        audio_manager = get_audio_manager()
        categories = audio_manager.scan_audio_folder(audio_folder)
        types.append({
            'id': key,
            'display_name': info['display_name'],
            'categories': categories
        })
    return jsonify(types)


# =============================================================================
# WebSocket Events
# =============================================================================

@socketio.on('connect')
def on_connect():
    """Handle client connection."""
    print("Client connected")
    global engine
    if engine:
        emit('state_change', {'state': engine.state.name})
        if engine.state != ExperimentState.IDLE:
            emit('progress', engine.get_progress())


@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection."""
    print("Client disconnected")


@socketio.on('initialize')
def on_initialize(data):
    """Initialize experiment with configuration."""
    global engine
    
    try:
        config = ExperimentConfig(
            experiment_type=data.get('experiment_type', 'colors'),
            visualization_duration_ms=int(data.get('visualization_duration_ms', 3000)),
            pre_recording_buffer_ms=int(data.get('pre_recording_buffer_ms', 500)),
            inter_trial_gap_ms=int(data.get('inter_trial_gap_ms', 1000)),
            trials_per_category=int(data.get('trials_per_category', 10)),
            trials_until_break=int(data.get('trials_until_break', 15)),
            enabled_categories=data.get('enabled_categories', []),
            randomize_order=data.get('randomize_order', True),
            enable_end_beep=data.get('enable_end_beep', True),
            enable_likert=data.get('enable_likert', True),
            likert_scale=int(data.get('likert_scale', 5)),
            enable_logging=data.get('enable_logging', False)
        )
        
        # Reset and create new engine
        reset_experiment_engine()
        engine = get_experiment_engine()
        setup_engine_callbacks()
        
        if engine.initialize(config):
            emit('initialized', {
                'success': True,
                'total_trials': len(engine.trial_queue),
                'categories': engine.categories
            })
        else:
            emit('initialized', {'success': False, 'error': 'Initialization failed'})
            
    except Exception as e:
        emit('initialized', {'success': False, 'error': str(e)})


@socketio.on('start')
def on_start():
    """Start the experiment."""
    global engine
    if engine and engine.state == ExperimentState.IDLE:
        engine.start()
        emit('started', {'success': True})
    else:
        emit('started', {'success': False, 'error': 'Engine not ready or not in IDLE state'})


@socketio.on('pause')
def on_pause():
    """Pause the experiment."""
    global engine
    if engine:
        engine.pause()


@socketio.on('resume')
def on_resume():
    """Resume from pause or break."""
    global engine
    if engine:
        engine.resume()


@socketio.on('stop')
def on_stop():
    """Stop the experiment."""
    global engine
    if engine:
        engine.stop()
    emit('stopped', {'success': True})


@socketio.on('submit_likert')
def on_submit_likert(data):
    """Submit Likert scale response."""
    global engine
    if engine and engine.state == ExperimentState.LIKERT:
        rating = int(data.get('rating', 3))
        engine.submit_likert(rating)
        emit('likert_submitted', {'rating': rating})


@socketio.on('get_progress')
def on_get_progress():
    """Get current experiment progress."""
    global engine
    if engine:
        emit('progress', engine.get_progress())


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("EEG Imagery Experiment Platform")
    print("="*60)
    print(f"Audio directory: {AUDIO_DIR}")
    print("\nAvailable experiment types:")
    for key, info in EXPERIMENT_TYPES.items():
        audio_folder = os.path.join(AUDIO_DIR, info["audio_folder"])
        categories = get_audio_manager().scan_audio_folder(audio_folder)
        print(f"  - {info['display_name']}: {len(categories)} categories")
    print("\nStarting server at http://localhost:8080")
    print("="*60 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)