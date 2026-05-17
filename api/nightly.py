"""Vercel cron-triggered nightly pipeline."""
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import run_nightly


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            run_nightly()
            status = 200
            body = b"nightly run complete"
        except Exception as e:
            status = 500
            body = f"nightly failed: {e}".encode()
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)
