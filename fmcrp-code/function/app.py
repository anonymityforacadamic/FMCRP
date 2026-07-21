import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = json.dumps({"function": "fmcrp-target", "status": "ok"}).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(payload))); self.end_headers(); self.wfile.write(payload)

    def log_message(self, *_): pass


ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()
