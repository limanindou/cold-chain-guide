"""Tiny structured JSON logger (zero dependencies, so `sam deploy` needs no build step).

Every line is one JSON object with service, level, message and any bound context such as
incidentId, which makes CloudWatch Logs Insights queries trivial:
    fields @timestamp, level, message | filter incidentId = "..."
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


class Logger:
    def __init__(self, service: str):
        self.service = service
        self._ctx: dict = {}

    def reset(self, **ctx) -> None:
        self._ctx = {k: v for k, v in ctx.items() if v is not None}

    def bind(self, **ctx) -> None:
        self._ctx.update({k: v for k, v in ctx.items() if v is not None})

    def _emit(self, level: str, message: str, /, **fields) -> None:
        record = {
            **self._ctx,
            **fields,
            # written last so caller fields can never overwrite them
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": level,
            "service": self.service,
            "message": message,
        }
        sys.stdout.write(json.dumps(record, default=str) + "\n")

    def info(self, message: str, /, **fields) -> None:
        self._emit("INFO", message, **fields)

    def warning(self, message: str, /, **fields) -> None:
        self._emit("WARNING", message, **fields)

    def error(self, message: str, /, **fields) -> None:
        self._emit("ERROR", message, **fields)

    def exception(self, message: str, exc: BaseException, /, **fields) -> None:
        self._emit("ERROR", message, error=type(exc).__name__, detail=str(exc), **fields)
