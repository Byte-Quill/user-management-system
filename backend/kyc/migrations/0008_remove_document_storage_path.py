# Removes the Supabase Storage mirror path. Documents are stored locally in
# MEDIA_ROOT and served through the authenticated download view, so the
# storage_path column is no longer needed.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kyc', '0007_remove_under_review_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='document',
            name='storage_path',
        ),
    ]
