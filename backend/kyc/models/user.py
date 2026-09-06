"""User accounts: custom user model with KYC roles and public IDs."""
import secrets

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils.translation import gettext_lazy as _


USER_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
USER_ID_PREFIX = "PHIN-"
USER_ID_RANDOM_LENGTH = 8


def generate_user_id() -> str:
    """Return a unique, auto-generated public User ID (e.g. PHIN-A7K2M9X4)."""
    for _ in range(10):
        candidate = USER_ID_PREFIX + "".join(
            secrets.choice(USER_ID_ALPHABET) for _ in range(USER_ID_RANDOM_LENGTH)
        )
        if not User.objects.filter(username=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate a unique user ID after 10 attempts")


class UserManager(DjangoUserManager):
    """User manager that treats email as optional."""

    @classmethod
    def normalize_email(cls, email):
        if not email:
            return None
        return super().normalize_email(email)


class User(AbstractUser):
    """Custom user with a role for the KYC workflow."""

    class Role(models.TextChoices):
        APPLICANT = "applicant", "Applicant"
        ADMIN = "admin", "Admin"
        SUPER_ADMIN = "super_admin", "Super Admin"
        CEO = "ceo", "CEO"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"

    objects = UserManager()

    email = models.EmailField(null=True, blank=True, unique=True)
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.APPLICANT
    )
    middle_name = models.CharField(max_length=150, blank=True, default="")
    gender = models.CharField(
        max_length=20, choices=Gender.choices, blank=True, default=""
    )

    phone = models.CharField(max_length=30, null=True, blank=True, unique=True)

    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True, default="")
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")

    email_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:

        verbose_name = _("user")
        verbose_name_plural = _("users")
        indexes = [
            GinIndex(
                name="kyc_user_email_trgm_idx",
                fields=["email"],
                opclasses=["gin_trgm_ops"],
            ),
            GinIndex(
                name="kyc_user_uname_trgm_idx",
                fields=["username"],
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __str__(self):
        identifier = self.email or self.phone or self.username
        return f"{identifier} ({self.role})"

    @property
    def is_reviewer(self):

        return self.role in (self.Role.ADMIN, self.Role.SUPER_ADMIN)

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_ceo(self):
        return self.role == self.Role.CEO
