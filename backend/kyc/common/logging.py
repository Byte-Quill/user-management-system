"""Stdlib JSON log formatter — replaces python-json-logger."""

import json
import logging


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        return json.dumps(log_entry, default=str)
