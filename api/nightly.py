"""Vercel cron-triggered nightly pipeline."""
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cron_secret = os.environ.get("CRON_SECRET")
        if cron_secret:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {cron_secret}":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"unauthorized")
                return

        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from pipeline import run_nightly

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
