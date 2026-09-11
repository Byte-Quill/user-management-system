from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditLog, Document, EmailLog, KYCApplication, User, log_action


@admin.register(User)
class UserAdmin(BaseUserAdmin):
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
        ("Email verification", {"fields": ("email_verified",)}),
    )
    list_display = ("email", "username", "phone", "role", "email_verified", "is_staff")
    list_filter = BaseUserAdmin.list_filter + ("role",)


class DocumentInline(admin.TabularInline):
    """Read-only view of an application's documents."""

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

        if db_field.name == "reviewer":
            kwargs["queryset"] = User.objects.filter(
                role__in=(User.Role.ADMIN, User.Role.SUPER_ADMIN)
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            old_status = (
                KYCApplication.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
            )
        super().save_model(request, obj, form, change)
        if not change:
            log_action(
                obj,
                request.user,
                AuditLog.Action.CREATED,
                detail="Created via Django admin",
            )
        elif old_status is not None and old_status != obj.status:
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

        return False

    def has_change_permission(self, request, obj=None):

        return False

    def has_delete_permission(self, request, obj=None):

        return False


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("purpose", "recipient", "status", "created_at")
    list_filter = ("purpose", "status")
    search_fields = ("recipient", "subject", "user__email")
    readonly_fields = ("user", "purpose", "recipient", "subject", "status", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request):

        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
