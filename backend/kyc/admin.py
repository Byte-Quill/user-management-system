from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditLog, Document, KYCApplication, User, log_action


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # The stock add form only asks for username + password, but this model
    # authenticates by email (USERNAME_FIELD = "email", unique). Without an
    # email field on the add form, admin-created users could never log in and
    # a second one would violate the unique constraint on the empty email.
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {"classes": ("wide",), "fields": ("email", "phone", "gender")}),
    )
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Profile",
            {
                "fields": (
                    "middle_name",
                    "phone",
                    "gender",
                    "date_of_birth",
                    "nationality",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                )
            },
        ),
        ("Role", {"fields": ("role",)}),
        # Staff can verify manually when a user cannot complete the OTP flow
        # (e.g. lost inbox access).
        ("Email verification", {"fields": ("email_verified",)}),
    )
    list_display = ("email", "username", "phone", "role", "email_verified", "is_staff")
    list_filter = BaseUserAdmin.list_filter + ("role",)


class DocumentInline(admin.TabularInline):
    """Read-only view of an application's documents.

    Uploads and removals must go through the API so that content validation,
    file cleanup, and the audit trail are applied consistently.
    """

    model = Document
    extra = 0
    fields = ("doc_type", "original_filename", "uploaded_at")
    readonly_fields = ("doc_type", "original_filename", "uploaded_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(KYCApplication)
class KYCApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "applicant", "status", "created_at")
    list_filter = ("status", "id_type")
    search_fields = ("full_name", "id_number", "applicant__email")
    list_select_related = ("applicant", "reviewer")
    readonly_fields = ("created_at", "updated_at", "submitted_at", "reviewed_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    inlines = [DocumentInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Only reviewer/admin users may be assigned as the reviewer.
        if db_field.name == "reviewer":
            kwargs["queryset"] = User.objects.filter(
                role__in=(User.Role.REVIEWER, User.Role.ADMIN)
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            old_status = (
                KYCApplication.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        if not change:
            # Keep the audit trail complete for admin-created applications.
            log_action(
                obj,
                request.user,
                AuditLog.Action.CREATED,
                detail="Created via Django admin",
            )
        elif old_status is not None and old_status != obj.status:
            # Keep the audit trail in sync when staff change state outside the API.
            log_action(
                obj,
                request.user,
                AuditLog.Action.UPDATED,
                detail=f"Admin status change: {old_status} -> {obj.status}",
            )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "application", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("application__full_name", "actor__email", "detail")
    readonly_fields = ("application", "actor", "action", "detail", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # The audit trail is append-only and written by the application logic.
        return False

    def has_change_permission(self, request, obj=None):
        # View-only: renders the detail page without Save buttons.
        return False

    def has_delete_permission(self, request, obj=None):
        # Audit records are immutable.
        return False
