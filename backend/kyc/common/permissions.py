"""DRF role/ownership permissions for the KYC API."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

class IsReviewer(BasePermission):
    """Allow access only to reviewers (admins/super admins)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_reviewer)


class IsSuperAdmin(BasePermission):
    """Allow access only to super admins (user management)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_super_admin)


class IsCEO(BasePermission):
    """Allow access only to the CEO role (company analytics)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_ceo)


class IsOwnerOrReviewer(BasePermission):
    """Applicants access their own applications; reviewers read all."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_reviewer and request.method not in SAFE_METHODS:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_reviewer:
            return request.method in SAFE_METHODS
        return obj.applicant_id == request.user.id
