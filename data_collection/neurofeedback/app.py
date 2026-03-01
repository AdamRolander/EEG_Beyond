"""
Neurofeedback app - skeleton.
UI follows Imagery aesthetic; no features yet.
"""

import os
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

from xdf_parser import parse_xdf

app = Flask(__name__)
app.config['SECRET_KEY'] = 'neurofeedback-skeleton'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'xdf'}

os.makedirs(UPLOAD_DIR, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


@app.route('/api/upload_xdf', methods=['POST'])
def upload_xdf():
    """Accept XDF file upload and save to uploads/."""
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No file'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'ok': False, 'error': 'No file selected'}), 400
    if not allowed_file(f.filename):
        return jsonify({'ok': False, 'error': 'Only .xdf files allowed'}), 400
    filename = secure_filename(f.filename)
    path = os.path.join(UPLOAD_DIR, filename)
    f.save(path)
    parsed = parse_xdf(path)
    if not parsed.get('ok'):
        return jsonify({
            'ok': True,
            'filename': filename,
            'parse_error': parsed.get('error', 'Unknown error')
        })
    return jsonify({
        'ok': True,
        'filename': filename,
        'streams': parsed.get('streams', []),
        'channels': parsed.get('channels', []),
        'markers': parsed.get('markers', []),
        'notes': parsed.get('notes', [])
    })


if __name__ == '__main__':
    print("Neurofeedback app at http://localhost:8090")
    app.run(host='0.0.0.0', port=8090, debug=False)
