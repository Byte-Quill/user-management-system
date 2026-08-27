# Role model change: the separate "reviewer" role is folded into "admin",
# and "super_admin" / "ceo" roles are added. Existing reviewer rows are
# migrated to admin (data migration below). Also adds the EmailLog model
# for CEO email-activity analytics.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def reviewer_to_admin(apps, schema_editor):
    User = apps.get_model("kyc", "User")
    User.objects.filter(role="reviewer").update(role="admin")


def admin_to_reviewer(apps, schema_editor):
    # Best-effort reverse: there is no way to know which admins were
    # originally reviewers, so this is a no-op (the role no longer exists).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kyc', '0012_alter_user_managers_alter_user_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('applicant', 'Applicant'), ('admin', 'Admin'), ('super_admin', 'Super Admin'), ('ceo', 'CEO')], default='applicant', max_length=20),
        ),
        migrations.RunPython(reviewer_to_admin, admin_to_reviewer),
        migrations.CreateModel(
            name='EmailLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('purpose', models.CharField(choices=[('verify_email', 'Verify Email'), ('reset_password', 'Reset Password')], max_length=20)),
                ('recipient', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('sent', 'Sent'), ('failed', 'Failed')], max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(fields=['-created_at'], name='kyc_emaillo_created_idx'),
        ),
    ]
