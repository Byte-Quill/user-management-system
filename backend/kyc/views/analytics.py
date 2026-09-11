"""CEO analytics: KPIs, approval rate, pipeline breakdown, email activity."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from kyc.common.permissions import IsCEO
from kyc.models import EmailLog, KYCApplication
from kyc.serializers import EmailLogSerializer

User = get_user_model()


class AnalyticsView(APIView):
    """CEO analytics: KPIs, approval rate, pipeline breakdown, email activity."""

    permission_classes = (IsAuthenticated, IsCEO)

    def get(self, request):
        now = timezone.now()
        last_30 = now - timedelta(days=30)

        total = KYCApplication.objects.count()
        by_status = dict(KYCApplication.objects.values_list("status").annotate(count=Count("id")))
        approved = by_status.get(KYCApplication.Status.APPROVED, 0)
        rejected = by_status.get(KYCApplication.Status.REJECTED, 0)
        decided = approved + rejected
        approval_rate = round(approved / decided * 100, 1) if decided else None

        recent = KYCApplication.objects.filter(submitted_at__gte=last_30).count()

        emails = EmailLog.objects.filter(created_at__gte=last_30)
        email_counts = dict(emails.values_list("status").annotate(count=Count("id")))
        recent_emails = EmailLog.objects.select_related("user").order_by("-created_at")[:20]

        return Response(
            {
                "kpis": {
                    "total_applications": total,
                    "submitted_last_30_days": recent,
                    "users": User.objects.count(),
                    "pending_review": by_status.get(KYCApplication.Status.SUBMITTED, 0),
                },
                "approval_rate": approval_rate,
                "pipeline": {s: by_status.get(s, 0) for s in KYCApplication.Status.values},
                "email_activity": {
                    "sent_last_30_days": email_counts.get(EmailLog.Status.SENT, 0),
                    "failed_last_30_days": email_counts.get(EmailLog.Status.FAILED, 0),
                    "recent": EmailLogSerializer(recent_emails, many=True).data,
                },
            }
        )
