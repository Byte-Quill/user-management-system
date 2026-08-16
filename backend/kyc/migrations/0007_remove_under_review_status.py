# Removes the unused "under_review" status choice. No code path ever set this
# state, so no data migration is required.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kyc', '0006_alter_auditlog_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kycapplication',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('resubmission_requested', 'Resubmission Requested')], db_index=True, default='draft', max_length=30),
        ),
    ]
