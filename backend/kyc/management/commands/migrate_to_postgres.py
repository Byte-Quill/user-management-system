"""Migrate data from the local SQLite database to PostgreSQL.

Usage:
    # 1. Make sure DATABASE_URL points at your PostgreSQL instance.
    # 2. Run migrations against Postgres first:
    #        python manage.py migrate
    # 3. Then run this command with the SQLite file as the source:
    #        python manage.py migrate_to_postgres --sqlite db.sqlite3

It dumps every model from the SQLite database and loads it into the configured
(default) database, preserving primary keys so relations stay intact.

WARNING: this is a one-shot migration tool. It is NOT idempotent: running it
twice against a non-empty target database will create duplicate rows.
"""
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Copy all data from a SQLite file into the configured (Postgres) database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite",
            default="db.sqlite3",
            help="Path to the source SQLite database file (default: db.sqlite3)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be migrated without writing anything.",
        )

    def handle(self, *args, **options):
        sqlite_path = Path(options["sqlite"])
        if not sqlite_path.exists():
            raise CommandError(f"SQLite file not found: {sqlite_path}")

        from django.conf import settings
        from django.db import connections

        settings.DATABASES["sqlite_source"] = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(sqlite_path),
        }
        connections.databases["sqlite_source"] = settings.DATABASES["sqlite_source"]

        from django.apps import apps

        total = 0
        plans = []
        for model in apps.get_models():
            objects = list(model.objects.using("sqlite_source").all())
            if not objects:
                continue
            data = serializers.serialize("json", objects)
            plans.append((model, objects, data))
            total += len(objects)
            self.stdout.write(f"  {model._meta.label}: {len(objects)} rows")

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"Dry run: {total} rows would be migrated (nothing written).")
            )
            return

        if total == 0:
            self.stdout.write("Nothing to migrate.")
            return

        try:
            with transaction.atomic():
                for model, objects, data in plans:
                    for obj in serializers.deserialize("json", data):
                        obj.save(using="default")
                    self.stdout.write(f"  wrote {model._meta.label}: {len(objects)} rows")
        except Exception as exc:  # noqa: BLE001 - roll back and report
            raise CommandError(
                f"Migration failed and was rolled back (no partial writes): {exc}"
            ) from exc

        self.stdout.write(self.style.SUCCESS(f"Migrated {total} rows to Postgres."))
