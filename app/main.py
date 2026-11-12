"""
Small health/readiness helper used by local diagnostics.
The actual OpenAI-compatible inference API is served by `vllm serve`.
vLLM request-body logging is disabled with --disable-log-requests.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import time

from app.logging_config import configure_logging

configure_logging()
log = logging.getLogger("inference.health")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        started = time.monotonic()
        if self.path not in ("/health", "/ready"):
            self.send_error(404)
            return
        payload = {"status": "ok"}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        log.info("health_check path=%s status=200 duration_ms=%.2f",
                 self.path, (time.monotonic() - started) * 1000)

    def log_message(self, fmt, *args):
        # Default BaseHTTPRequestHandler logs paths only; keep a controlled format.
        log.info("http_access client=%s message=%s", self.client_address[0], fmt % args)

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.getenv("HEALTH_PORT", "8081"))), Handler).serve_forever()
