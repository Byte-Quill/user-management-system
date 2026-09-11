from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):
    """Back the users-list ``icontains`` name search with trigram indexes.

    0014 added GIN trigram indexes for email/username but skipped
    first_name/last_name, so name searches (the most natural query for the
    super-admin console) degraded to a sequential scan as the table grows.
    """

    dependencies = [
        ("kyc", "0014_user_and_auditlog_search_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="user",
            index=GinIndex(
                name="kyc_user_fname_trgm_idx",
                fields=["first_name"],
                opclasses=["gin_trgm_ops"],
            ),
        ),
        migrations.AddIndex(
            model_name="user",
            index=GinIndex(
                name="kyc_user_lname_trgm_idx",
                fields=["last_name"],
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
