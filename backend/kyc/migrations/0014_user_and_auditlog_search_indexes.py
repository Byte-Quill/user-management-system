from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    """Search/pagination indexes.

    - pg_trgm + GIN trigram indexes back the users-list ``icontains`` search
      (email, username) so it stops scanning the table as it grows.
    - Composite (application, -created_at) index backs the paginated
      per-application audit history.
    """

    dependencies = [
        ("kyc", "0013_roles_and_emaillog"),
    ]

    operations = [
        # Requires the pg_trgm contrib module (shipped in the postgres image).
        TrigramExtension(),
        migrations.AddIndex(
            model_name="user",
            index=GinIndex(
                name="kyc_user_email_trgm_idx",
                fields=["email"],
                opclasses=["gin_trgm_ops"],
            ),
        ),
        migrations.AddIndex(
            model_name="user",
            index=GinIndex(
                name="kyc_user_uname_trgm_idx",
                fields=["username"],
                opclasses=["gin_trgm_ops"],
            ),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["application", "-created_at"],
                name="kyc_audit_app_created_idx",
            ),
        ),
    ]
