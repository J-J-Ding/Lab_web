import re
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User, UserRole


class StrictString(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class StrictBoolean(serializers.BooleanField):
    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail('invalid', input=data)
        return data


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({'detail': 'Unknown or read-only fields are not accepted.'})
        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    identity = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    def get_identity(self, user):
        return 'Root' if user.is_superuser else {'ADMIN':'Teacher','TEACHER':'Teacher','STUDENT':'Student','CUSTOMER':'Customer'}[user.role]

    def get_display_name(self, user):
        profile = getattr(user, 'member_profile', None)
        revision = (profile.published_revision or profile.draft_revision) if profile else None
        return revision.display_name if revision else ' '.join(filter(None, (user.first_name, user.last_name)))

    def get_capabilities(self, user):
        team = user.is_active and (user.is_superuser or user.role in ('ADMIN','TEACHER','STUDENT'))
        return {'can_edit_content':team,'can_manage_team':team and (user.is_superuser or user.role in ('ADMIN','TEACHER')), 'can_manage_accounts':user.is_active and user.is_superuser}

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'role', 'is_active', 'is_superuser', 'date_joined', 'identity', 'display_name', 'capabilities')
        read_only_fields = fields


def check_password(password, user):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({'password': exc.messages}) from None


class ProfileSerializer(StrictSerializer):
    first_name = StrictString(max_length=150, required=False, allow_blank=True)
    last_name = StrictString(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)


class RegisterSerializer(ProfileSerializer):
    username = StrictString(max_length=150, validators=[UnicodeUsernameValidator()])
    password = StrictString(max_length=128, trim_whitespace=False, write_only=True)

    def validate_username(self, value):
        value = User.normalize_username(value)
        if not re.fullmatch(r'[A-Za-z0-9._@+\-]+', value):
            raise serializers.ValidationError('Use letters, digits and . _ @ + - for the login name; enter your name in your profile.')
        UnicodeUsernameValidator()(value)
        if len(value) > 150:
            raise serializers.ValidationError('Username too long.')
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate(self, attrs):
        candidate = User(**{k: v for k, v in attrs.items() if k not in ('password',)})
        check_password(attrs['password'], candidate)
        return attrs


class AdminCreateSerializer(RegisterSerializer):
    role = serializers.ChoiceField(choices=[(r,r) for r in ('CUSTOMER','STUDENT','TEACHER')], default=UserRole.CUSTOMER)
    is_active = StrictBoolean(default=True)


class AdminUpdateSerializer(ProfileSerializer):
    role = serializers.ChoiceField(choices=[(r,r) for r in ('CUSTOMER','STUDENT','TEACHER')], required=False)
    is_active = StrictBoolean(required=False)


class LoginSerializer(StrictSerializer):
    username = StrictString(max_length=150)
    password = StrictString(max_length=128, trim_whitespace=False, write_only=True)

    def validate_username(self, value):
        return User.normalize_username(value)


class PasswordSerializer(StrictSerializer):
    new_password = StrictString(max_length=128, trim_whitespace=False, write_only=True)


class ChangePasswordSerializer(PasswordSerializer):
    old_password = StrictString(max_length=128, trim_whitespace=False, write_only=True)
