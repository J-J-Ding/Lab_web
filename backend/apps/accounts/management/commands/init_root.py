import getpass
import warnings

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.accounts.services import audit


class Command(BaseCommand):
    help = 'Create a ROOT account using a secure interactive password prompt; never promotes an existing account.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)

    def handle(self, *args, **options):
        username = User.normalize_username(options['username'])
        if User.objects.filter(username=username).exists():
            raise CommandError('Account already exists; no changes made.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                password = getpass.getpass('ROOT password: ')
                confirmation = getpass.getpass('Confirm password: ')
        except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
            raise CommandError('Secure interactive password input is required.') from None
        if not password or password != confirmation:
            raise CommandError('Passwords must be nonempty and match.')
        user = User(username=username, is_superuser=True, is_staff=True, is_active=True)
        try:
            if len(password) > 128:
                raise ValidationError('Password exceeds maximum length.')
            validate_password(password, user=user)
            user.set_password(password)
            user.full_clean()
            with transaction.atomic():
                user.save()
                audit('root.initialized', target=user)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from None
        except IntegrityError:
            raise CommandError('Account creation failed; no account was changed.') from None
        self.stdout.write(self.style.SUCCESS('ROOT account created.'))
