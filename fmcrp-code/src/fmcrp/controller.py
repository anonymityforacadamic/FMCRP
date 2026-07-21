from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import DEFAULT_FIWI_THRESHOLD, DEFAULT_MATCHING_WINDOW_SIZE
from .models import FunctionSpec, Replica
from .scheduler import FMCRPScheduler


def build_scheduler(path: Path) -> FMCRPScheduler:
    payload = json.loads(path.read_text(encoding="utf-8"))
    parameters = payload.get("parameters", {})
    functions = [FunctionSpec(item["name"], item["base"], item["runtime"], frozenset(item["dependencies"]), item["load_costs"], item.get("base_cost", 1.0), item.get("runtime_cost", 1.0)) for item in payload["functions"]]
    replicas = [Replica(item["name"], item["base"], item["runtime"], set(item["dependencies"]), item.get("memory_mb", 128)) for item in payload.get("replicas", [])]
    return FMCRPScheduler(
        functions,
        replicas,
        parameters.get("fiwi_threshold", payload.get("theta", DEFAULT_FIWI_THRESHOLD)),
        parameters.get("matching_window_size", DEFAULT_MATCHING_WINDOW_SIZE),
    )


class Handler(BaseHTTPRequestHandler):
    scheduler: FMCRPScheduler

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, default=lambda value: value.__dict__).encode()
        self.send_response(status); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz": self._json(200, {"status": "ok", "replicas": len(self.scheduler.replicas)})
        else: self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("content-length", "0"))))
            if self.path == "/schedule":
                result = self.scheduler.schedule(payload["function"], payload.get("rates", {}), payload.get("predicted_counts"), payload.get("window_limit"))
            elif self.path == "/control":
                demand = {(item["base"], item["runtime"], frozenset(item["dependencies"])): item["count"] for item in payload["demand"]}
                result = self.scheduler.retention_actions(demand, payload.get("requested_last_period", {}), payload.get("hits_last_period", {}), payload.get("previous_accuracy", 0.0))
            else: raise ValueError("use /schedule or /control")
            self._json(200, result)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})

    def log_message(self, *_: object) -> None: pass


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=8080); parser.add_argument("--metadata", default="examples/metadata.json")
    args = parser.parse_args(); Handler.scheduler = build_scheduler(Path(args.metadata)); ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__": main()
