"""Domain-focused tests: seed."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()

class SeedDemoTests(TestCase):
    def test_refuses_without_debug_and_no_force_flag(self):
        from django.core.management import CommandError, call_command

        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command("seed_demo")
        self.assertFalse(User.objects.filter(email="admin@kyc.local").exists())



