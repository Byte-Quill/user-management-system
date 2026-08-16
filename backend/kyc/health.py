"""Liveness and readiness probes for orchestrators (Render, K8s, etc.)."""
import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

logger = logging.getLogger("kyc.health")


def healthz(request):
    """Liveness: the process is up and can serve requests."""
    return JsonResponse({"status": "ok"})


@csrf_exempt
def readyz(request):
    """Readiness: the process can serve traffic (database reachable)."""
    checks = {"database": False}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except Exception as exc:  # noqa: BLE001 - health check must never crash
        logger.error("Readiness DB check failed: %s", exc)

    ok = all(checks.values())
    return JsonResponse(
        {"status": "ok" if ok else "unavailable", "checks": checks},
        status=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
