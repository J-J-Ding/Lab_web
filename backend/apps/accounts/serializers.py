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
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'role', 'is_active', 'is_superuser', 'date_joined')
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
    role = serializers.ChoiceField(choices=UserRole.choices, default=UserRole.CUSTOMER)
    is_active = StrictBoolean(default=True)


class AdminUpdateSerializer(ProfileSerializer):
    role = serializers.ChoiceField(choices=UserRole.choices, required=False)
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
