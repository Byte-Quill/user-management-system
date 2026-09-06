"""Assert the SPA validation contract still reflects the backend rules."""
import json
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase


class ValidationContractTests(SimpleTestCase):
    def load_contract(self) -> dict:
        out = StringIO()
        call_command("validation_contract", stdout=out)
        return json.loads(out.getvalue())

    def test_emits_expected_rule_values(self):
        contract = self.load_contract()
        self.assertEqual(contract["otp_length"], 6)
        self.assertEqual(contract["password_min_length"], 8)
        self.assertEqual(contract["dob_min"], "1900-01-01")
        self.assertEqual(contract["max_upload_mb"], 5)
        self.assertEqual(contract["email_max_length"], 254)
        self.assertEqual(contract["name_max_length"], 150)
        self.assertEqual(contract["phone_max_length"], 30)
        self.assertEqual(contract["application_max_lengths"]["full_name"], 255)
        self.assertEqual(
            contract["allowed_upload_extensions"],
            [".jpg", ".jpeg", ".png", ".pdf"],
        )

    def test_emits_a_stable_shape(self):
        contract = self.load_contract()
        expected_keys = {
            "_comment",
            "dob_min",
            "max_upload_mb",
            "allowed_upload_extensions",
            "max_documents_per_application",
            "phone_default_region",
            "phone_max_length",
            "password_min_length",
            "otp_length",
            "name_max_length",
            "email_max_length",
            "page_size",
            "application_max_lengths",
            "gender_values",
            "application_id_types",
            "document_doc_types",
            "application_statuses",
        }
        self.assertEqual(set(contract.keys()), expected_keys)
        self.assertEqual(
            set(contract["application_max_lengths"]),
            {
                "full_name",
                "nationality",
                "phone",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "postal_code",
                "country",
                "id_number",
            },
        )
