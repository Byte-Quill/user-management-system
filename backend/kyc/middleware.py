"""Request ID middleware for correlation logging."""
import logging
import threading
import uuid

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("kyc.request")

# Thread-local storage: with threaded gunicorn workers the logger object is
# shared across threads, so a bare attribute set would race.
_local = threading.local()


def get_request_id() -> str:
    """Return the current thread's request ID (or '-' outside a request)."""
    return getattr(_local, "request_id", "-")


class RequestIDMiddleware(MiddlewareMixin):
    """Attach a request ID to each request and response for tracing."""

    def process_request(self, request):
        # Prefer an incoming header (e.g. from a load balancer).
        request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        request.request_id = request_id
        _local.request_id = request_id
        return None

    def process_response(self, request, response):
        if hasattr(request, "request_id"):
            response["X-Request-ID"] = request.request_id
        _local.request_id = None
        return response


class RequestIDFilter(logging.Filter):
    """Inject request_id into log records."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True