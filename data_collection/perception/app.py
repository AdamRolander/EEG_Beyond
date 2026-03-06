#!/usr/bin/env python3
"""Simple local development server for the perception app."""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
print("Serving at http://localhost:3000")
HTTPServer(('0.0.0.0', 3000), SimpleHTTPRequestHandler).serve_forever()
