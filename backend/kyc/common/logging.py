"""Stdlib JSON log formatter — replaces python-json-logger.

A single dependency-free formatter that emits one JSON object per line with
the fields the operators query on: timestamp, logger name, level, request ID,
and message. Uses the stdlib ``json`` module — no third-party package needed.
"""

import json
import logging


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON.

    Compatible with the ``format``-string field names used by
    ``python-json-logger`` (``%(asctime)s``, ``%(name)s``, etc.) so the
    logging config needs no other changes beyond swapping the formatter class.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        return json.dumps(log_entry, default=str)
