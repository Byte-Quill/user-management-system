"""Custom authentication backends."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrPhoneBackend(ModelBackend):
    """Authenticate with email OR phone + password."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        from kyc.serializers import legacy_phone_key, normalize_phone

        identifier = username.strip()
        if "@" in identifier:
            user = UserModel.objects.filter(email__iexact=identifier).first()
        else:
            candidates = {legacy_phone_key(identifier)}
            try:
                candidates.add(normalize_phone(identifier))
            except ValueError:
                pass
            user = UserModel.objects.filter(phone__in=candidates).first()

        if user is None:
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
