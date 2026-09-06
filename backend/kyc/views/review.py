"""Reviewer queue endpoint."""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from kyc.common.permissions import IsReviewer
from kyc.models import KYCApplication
from kyc.serializers import KYCApplicationSerializer

class ReviewQueueView(generics.ListAPIView):
    """Reviewer-facing queue of applications awaiting a decision."""

    serializer_class = KYCApplicationSerializer
    permission_classes = (IsAuthenticated, IsReviewer)

    def get_serializer_context(self):

        context = super().get_serializer_context()
        context["include_document_url"] = False
        return context

    def get_queryset(self):
        return (
            KYCApplication.objects.filter(status=KYCApplication.Status.SUBMITTED)
            .select_related("applicant")
            .prefetch_related("documents")
        )
