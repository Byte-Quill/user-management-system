"""Seed demo users and a sample application for local development."""
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from kyc.models import AuditLog, KYCApplication

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo users (super admin/admin/ceo/applicant) and a sample application."

    def handle(self, *args, **options):
        # No override: these are well-known credentials, so the command
        # must never run against a production database.
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo creates weak, well-known credentials (Admin@123 etc.) "
                "and is meant for local development only. Refusing to run with "
                "DJANGO_DEBUG=false."
            )
        super_admin, created = User.objects.get_or_create(
            email="superadmin@kyc.local",
            defaults={
                "username": "superadmin",
                "role": User.Role.SUPER_ADMIN,
                "is_staff": True,
                "is_superuser": True,
                # Trusted local-dev fixtures: skip the email-OTP gate.
                "email_verified": True,
            },
        )
        if created:
            super_admin.set_password("Super@123")
            super_admin.save()

        admin, created = User.objects.get_or_create(
            email="admin@kyc.local",
            defaults={
                "username": "admin",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "email_verified": True,
            },
        )
        if created:
            admin.set_password("Admin@123")
            admin.save()

        ceo, created = User.objects.get_or_create(
            email="ceo@kyc.local",
            defaults={
                "username": "ceo",
                "role": User.Role.CEO,
                "email_verified": True,
            },
        )
        if created:
            ceo.set_password("Ceo@12345")
            ceo.save()

        applicant, created = User.objects.get_or_create(
            email="user@kyc.local",
            defaults={
                "username": "applicant",
                "role": User.Role.APPLICANT,
                "first_name": "Demo",
                "last_name": "Applicant",
                "phone": "+919876543210",
                "gender": User.Gender.PREFER_NOT_TO_SAY,
                "email_verified": True,
            },
        )
        if created:
            applicant.set_password("User@123")
            applicant.save()

        if not applicant.applications.exists():
            app = KYCApplication.objects.create(
                applicant=applicant,
                full_name="Demo Applicant",
                date_of_birth=date(1990, 1, 15),
                nationality="Indian",
                phone="+91-9876543210",
                address_line1="221B Baker Street",
                city="Mumbai",
                state="Maharashtra",
                postal_code="400001",
                country="India",
                id_type=KYCApplication.IDType.PASSPORT,
                id_number="A1234567",
                id_expiry=date(2030, 12, 31),
            )
            AuditLog.objects.create(
                application=app, actor=applicant, action=AuditLog.Action.CREATED
            )
            self.stdout.write(self.style.SUCCESS("Created sample draft application."))

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("  superadmin@kyc.local / Super@123")
        self.stdout.write("  admin@kyc.local / Admin@123")
        self.stdout.write("  ceo@kyc.local / Ceo@12345")
        self.stdout.write("  user@kyc.local / User@123")
