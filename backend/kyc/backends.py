"""Custom authentication backends.

The login form sends a single identifier in the ``email`` field. The default
``ModelBackend`` only matches ``USERNAME_FIELD`` (email), so phone-only
accounts (``email IS NULL``) could never sign in. ``EmailOrPhoneBackend``
resolves the identifier against both the unique email and phone columns.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrPhoneBackend(ModelBackend):
    """Authenticate with email OR phone + password.

    Mirrors the identifier handling the SPA uses: an identifier containing
    ``@`` is treated as an email, anything else as a phone number that is
    normalized to the canonical stored form before lookup.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        # Lazy import: serializers imports models at module load, so importing
        # it here (at call time) avoids a circular import at startup.
        from .serializers import legacy_phone_key, normalize_phone

        identifier = username.strip()
        if "@" in identifier:
            user = UserModel.objects.filter(email__iexact=identifier).first()
        else:
            # Treat as a phone number. Resolve against both the canonical E164
            # form and the legacy digits-only form so accounts created before
            # the libphonenumber switch can still sign in.
            candidates = {legacy_phone_key(identifier)}
            try:
                candidates.add(normalize_phone(identifier))
            except ValueError:
                pass
            user = UserModel.objects.filter(phone__in=candidates).first()

        if user is None:
            # Run the password hasher anyway to keep response timing similar
            # for unknown and known identifiers.
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
