"""
Neurofeedback app - skeleton.
UI follows Imagery aesthetic; no features yet.
"""

import os
from flask import Flask, render_template

app = Flask(__name__)
app.config['SECRET_KEY'] = 'neurofeedback-skeleton'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


if __name__ == '__main__':
    print("Neurofeedback app at http://localhost:8090")
    app.run(host='0.0.0.0', port=8090, debug=False)
